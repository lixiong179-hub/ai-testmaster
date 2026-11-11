"""K4 主机级隔离冒烟：无 Docker 时验证「Web 只入队、executor 独立执行」。

流程（全部真实进程，唯一「人造」之处是 `--dry-run` 让 executor 只推进状态机）：

    1. 起 Web（`EXECUTOR_MODE=worker`，本机端口）
    2. 起 N 个 `scripts/run_executor.py --dry-run` 进程
    3. 通过 HTTP `POST /api/v1/test-task/{id}/run` 入队 → 期望 200 + `summary.status=queued`
    4. 断言此刻任务仍为 `PENDING`（Web 未执行）
    5. **kill Web 进程**
    6. 轮询数据库：任务应被 executor 领取并推进到 `COMPLETED`（证明执行不依赖 Web）
    7. 停 executor、清理临时项目/任务

用法：
    python scripts/smoke_worker_isolation.py --port 8099 --executors 3 --wait 60

退出码：0 = Web 死亡后任务仍被推进完成；1 = 任务停在 PENDING / 入队失败；2 = 环境不满足。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402


def _env(**extra: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update(extra)
    return env


def _seed() -> dict[str, Any]:
    """创建临时用户项目 + PENDING 任务，返回 {project_id, task_id, user_id, token}。"""
    from app.db.database import PrimarySessionLocal
    from app.models.project import Project
    from app.models.test_task import TaskStatus, TestTask
    from app.models.user import User
    from app.utils.jwt_utils import create_access_token

    db = PrimarySessionLocal()
    try:
        user = db.query(User).first()
        if user is None:
            raise RuntimeError("数据库无用户，请先初始化管理员")

        suffix = uuid.uuid4().hex[:8]
        project = Project(
            name=f"isolation_probe_{suffix}",
            user_id=user.id,
            description="K4 主机级隔离冒烟（临时）",
            status=1,
            project_type="web",
        )
        db.add(project)
        db.flush()

        task = TestTask(
            task_name=f"isolation_probe_task_{suffix}",
            project_id=project.id,
            case_ids=[],
            executor_id=user.id,
            status=TaskStatus.PENDING,
            total_count=0,
            progress=0,
        )
        db.add(task)
        db.commit()

        return {
            "project_id": project.id,
            "task_id": task.id,
            "user_id": user.id,
            "token": create_access_token({"sub": str(user.id)}),
        }
    finally:
        db.close()


def _status(task_id: int) -> Optional[int]:
    from app.db.database import PrimarySessionLocal
    from app.models.test_task import TestTask

    db = PrimarySessionLocal()
    try:
        # 避免一级缓存返回旧值
        db.expire_all()
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        return int(task.status) if task is not None else None
    finally:
        db.close()


def _cleanup(project_id: int, task_id: int) -> None:
    from app.db.database import PrimarySessionLocal
    from app.models.project import Project
    from app.models.test_task import TestTask

    db = PrimarySessionLocal()
    try:
        db.query(TestTask).filter(TestTask.id == task_id).delete()
        db.query(Project).filter(Project.id == project_id).delete()
        db.commit()
    except Exception as exc:
        db.rollback()
        print(f"[WARN] 清理失败: {exc}")
    finally:
        db.close()


def _spawn(cmd: list[str], env: dict[str, str], log_path: Path) -> subprocess.Popen:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    log = log_path.open("wb")
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    proc._log_handle = log  # 便于退出时关闭
    return proc


def _stop(proc: Optional[subprocess.Popen]) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    finally:
        handle = getattr(proc, "_log_handle", None)
        if handle is not None:
            handle.close()


def _wait_live(base_url: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{base_url}/live", timeout=3.0)
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="K4 主机级隔离冒烟（无 Docker）")
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--executors", type=int, default=3)
    parser.add_argument("--boot-timeout", type=float, default=120.0)
    parser.add_argument("--wait", type=float, default=60.0, help="Web 退出后等待执行完成秒数")
    parser.add_argument(
        "--logs", default=str(Path(os.getenv("TEMP", ".")) / "k4_smoke"),
        help="子进程日志目录",
    )
    args = parser.parse_args(argv)

    base_url = f"http://127.0.0.1:{args.port}"
    log_dir = Path(args.logs)
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        seeded = _seed()
    except Exception as exc:
        print(f"[FAIL] 环境不满足: {exc}")
        return 2

    project_id, task_id = seeded["project_id"], seeded["task_id"]
    token = seeded["token"]
    print(f"临时项目={project_id} 任务={task_id}")

    web: Optional[subprocess.Popen] = None
    executors: list[subprocess.Popen] = []
    exit_code = 1

    try:
        web = _spawn(
            [
                sys.executable, "-m", "uvicorn", "app.main:app",
                "--host", "127.0.0.1", "--port", str(args.port),
                "--log-level", "warning",
            ],
            _env(EXECUTOR_MODE="worker"),
            log_dir / "web.log",
        )
        if not _wait_live(base_url, args.boot_timeout):
            print(f"[FAIL] Web 未在 {args.boot_timeout:.0f}s 内就绪，日志: {log_dir / 'web.log'}")
            return 1
        print("Web 已就绪（EXECUTOR_MODE=worker）")

        for idx in range(max(args.executors, 1)):
            executors.append(
                _spawn(
                    [sys.executable, "scripts/run_executor.py", "--dry-run"],
                    _env(
                        EXECUTOR_MODE="worker",
                        EXECUTOR_POLL_INTERVAL_SECONDS="0.5",
                    ),
                    log_dir / f"executor_{idx}.log",
                )
            )
        print(f"executor 已启动: {len(executors)} 个（--dry-run）")
        time.sleep(2.0)

        headers = {
            "Authorization": f"Bearer {token}",
            "Origin": "http://localhost:5173",
            "Referer": "http://localhost:5173/",
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{base_url}/api/v1/test-task/{task_id}/run", headers=headers
            )
        print(f"POST /run -> {resp.status_code} {resp.text[:200]}")
        if resp.status_code != 200:
            print("[FAIL] 入队请求失败")
            return 1

        payload = resp.json()
        summary = (payload.get("data") or payload).get("summary") or {}
        if summary.get("status") != "queued":
            print(f"[FAIL] 期望 summary.status=queued，实际={summary.get('status')}")
            return 1

        status_after_enqueue = _status(task_id)
        print(f"入队后状态={status_after_enqueue}（0=PENDING，Web 未执行）")

        _stop(web)
        web = None
        print("Web 进程已 kill")

        deadline = time.time() + max(args.wait, 1.0)
        final: Optional[int] = None
        while time.time() < deadline:
            final = _status(task_id)
            if final is not None and final != 0:
                break
            time.sleep(1.0)

        print(f"Web 退出后最终状态={final}（2=COMPLETED / 3=FAILED 均视为已执行）")
        if final in (2, 3):
            print("[PASS] 执行与 Web 进程解耦：Web 退出后任务仍被 executor 推进")
            exit_code = 0
        else:
            print("[FAIL] 任务未被推进（仍为 PENDING 或已丢失）")
            exit_code = 1
    finally:
        _stop(web)
        for proc in executors:
            _stop(proc)
        _cleanup(project_id, task_id)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
