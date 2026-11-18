"""K4 举证脚本：多进程并发领取同一任务，验证「恰好一个副本执行」。

对应风险 R-05（多副本重复领取）。本机无 Docker 时，用**真实多进程 + 独立
数据库连接**复现 `--scale executor=3` 的竞争条件，比单元测试的顺序断言更强：

    python scripts/verify_executor_claim.py --workers 3

输出 `winner / claimed=False` 表格；退出码：
    0  恰好 1 个进程领取成功（互斥成立）
    1  0 个或多个进程领取成功（互斥被破坏）
    2  环境不满足（无数据库连接 / 无可用用户）

说明：脚本只创建 1 条 `PENDING` 任务（`case_ids=[]`，不触发浏览器执行），
结束后删除临时项目与任务，不污染业务数据。
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _claim(task_id: int, start_at: float) -> tuple[int, Optional[int]]:
    """子进程：等到统一开跑时刻后尝试领取（返回 (pid, 领取到的 task_id)）。"""
    from app.db.database import PrimarySessionLocal
    from app.services.execution_dispatcher import ExecutionDispatcher

    delay = start_at - time.time()
    if delay > 0:
        time.sleep(delay)

    db = PrimarySessionLocal()
    try:
        claimed = ExecutionDispatcher(db).claim_next(task_id=task_id)
        return mp.current_process().pid or 0, claimed
    finally:
        db.close()


def _seed() -> tuple[int, int]:
    """创建临时项目 + PENDING 任务，返回 (project_id, task_id)。"""
    from app.db.database import PrimarySessionLocal
    from app.models.project import Project
    from app.models.test_task import TaskStatus, TestTask
    from app.models.user import User

    db = PrimarySessionLocal()
    try:
        user = db.query(User).first()
        if user is None:
            raise RuntimeError("数据库中无可用用户，请先初始化（ADMIN_INITIAL_PASSWORD）")

        suffix = uuid.uuid4().hex[:8]
        project = Project(
            name=f"claim_probe_{suffix}",
            user_id=user.id,
            description="K4 并发领取举证（临时）",
            status=1,
            project_type="web",
        )
        db.add(project)
        db.flush()

        task = TestTask(
            task_name=f"claim_probe_task_{suffix}",
            project_id=project.id,
            case_ids=[],
            executor_id=user.id,
            status=TaskStatus.PENDING,
            total_count=0,
            progress=0,
        )
        db.add(task)
        db.commit()
        return project.id, task.id
    finally:
        db.close()


def _cleanup(project_id: int, task_id: int) -> None:
    """删除临时任务与项目（尽力而为）。"""
    from app.db.database import PrimarySessionLocal
    from app.models.project import Project
    from app.models.test_task import TestTask

    db = PrimarySessionLocal()
    try:
        db.query(TestTask).filter(TestTask.id == task_id).delete()
        db.query(Project).filter(Project.id == project_id).delete()
        db.commit()
    except Exception as exc:  # 清理失败不影响举证结论
        db.rollback()
        print(f"[WARN] 清理临时数据失败: {exc}")
    finally:
        db.close()


def _status(task_id: int) -> Optional[int]:
    from app.db.database import PrimarySessionLocal
    from app.models.test_task import TestTask

    db = PrimarySessionLocal()
    try:
        task = db.query(TestTask).filter(TestTask.id == task_id).first()
        return int(task.status) if task is not None else None
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="K4 多进程并发领取举证")
    parser.add_argument("--workers", type=int, default=3, help="并发副本数（默认 3）")
    parser.add_argument("--start-delay", type=float, default=1.5, help="统一开跑前的等待秒数")
    args = parser.parse_args(argv)

    try:
        project_id, task_id = _seed()
    except Exception as exc:
        print(f"[FAIL] 环境不满足: {exc}")
        return 2

    print(f"临时任务已创建: task_id={task_id} project_id={project_id}")
    start_at = time.time() + max(args.start_delay, 0.2)

    try:
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=max(args.workers, 1)) as pool:
            results = pool.starmap(_claim, [(task_id, start_at)] * args.workers)
    finally:
        final_status = _status(task_id)

    winners = [row for row in results if row[1] is not None]
    try:
        print("\n| 进程 PID | 是否领取 | 领取任务 |")
        print("| --- | --- | --- |")
        for pid, claimed in results:
            print(f"| {pid} | {'YES' if claimed else '-'} | {claimed or '-'} |")
        print(f"\nwinner={len(winners)} workers={args.workers} final_status={final_status}")
    finally:
        # 无论打印是否成功（如 Windows GBK 控制台编码异常）都要清理临时数据
        _cleanup(project_id, task_id)

    if len(winners) == 1:
        print("[PASS] 互斥成立：恰好 1 个副本领取成功（其余返回 0 行）")
        return 0
    print(f"[FAIL] 互斥被破坏：{len(winners)} 个副本同时领取成功")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
