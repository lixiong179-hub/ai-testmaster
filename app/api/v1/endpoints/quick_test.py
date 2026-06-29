"""快速测试 API 端点。

提供两个端点（路由前缀 /api/v1/quick-test 由 main.py 注册）：
- POST /launch：一键启动网址驱动快速测试，调用 QuickLauncher 完成
  建项→探索→生成→编排，返回 task_id 与 WebSocket 订阅通道；
- GET /{task_id}/status：查询任务进度与当前阶段，仅返回当前用户执行的任务。

鉴权（SubTask 9.4）：复用 auth_deps.get_current_user，仅认证用户可调用；
限流（SubTask 9.5）：launch 端点单用户 10 次/分钟，复用 RateLimitMiddleware
的内存模式算法（deque + 时间窗口清理），按 user_id 计数。现有 RateLimitMiddleware
为全局 IP 级（1000/5000 次/分钟），无法满足 launch 单用户细粒度限流需求，
故在此复用其算法实现一个 per-user 依赖，避免单用户高频触发浏览器探索压垮服务。

异常处理：URL 非法（ValueError）返回 422，与 spec Scenario "URL 非法 → 422"
一致；建项/探索等服务依赖异常返回 503，表示快速测试服务暂不可用。
"""
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import get_current_user
from app.db.database import get_db
from app.models.test_task import TaskStatus, TestTask
from app.models.user import User
from app.schemas.quick_test import (
    QuickTestLaunchRequest,
    QuickTestLaunchResponse,
    QuickTestStatusResponse,
)
from app.services.url_driven.quick_launcher import QuickLauncher

router = APIRouter()

# 单用户限流参数（SubTask 9.5）：10 次/分钟。
_LAUNCH_MAX_REQUESTS = 10
_LAUNCH_TIME_WINDOW_SEC = 60
# WebSocket 通道模板，与 QuickLauncher 保持一致
_CHANNEL_TEMPLATE = "quick_test:{task_id}"


class _PerUserRateLimiter:
    """单用户内存限流器，算法与 RateLimitMiddleware 内存模式一致。

    按 user_id 维护 deque 时间戳，超出时间窗口的记录自动清理，超限抛 429。
    单独成类便于测试 reset 与未来扩展为 Redis 模式（与中间件双模式对齐）。
    """

    def __init__(self, max_requests: int, time_window: int) -> None:
        """初始化限流参数与按 user_id 计数的请求桶。"""
        self.max_requests = max_requests
        self.time_window = time_window
        # deque(maxlen) 提供极端情况下的兜底淘汰，精确限流仍依赖时间窗口清理
        self._requests: defaultdict = defaultdict(
            lambda: deque(maxlen=max_requests)
        )

    def acquire(self, user_id: int) -> None:
        """占用一个配额，超限抛 HTTPException 429。

        Args:
            user_id: 当前认证用户 ID，作为限流计数 key。
        """
        now = time.time()
        self._cleanup(user_id, now)
        if len(self._requests[user_id]) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
            )
        self._requests[user_id].append(now)

    def _cleanup(self, user_id: int, now: float) -> None:
        """清理超出时间窗口的过期记录，与 RateLimitMiddleware._cleanup_old_requests 一致。"""
        bucket = self._requests[user_id]
        while bucket and now - bucket[0] > self.time_window:
            bucket.popleft()
        # 清理空 deque 释放长期闲置用户的内存占用
        if not bucket:
            del self._requests[user_id]

    def reset(self) -> None:
        """清空限流状态，供测试隔离使用。"""
        self._requests.clear()


# launch 端点限流器实例（模块级单例，跨请求共享计数）
launch_limiter = _PerUserRateLimiter(_LAUNCH_MAX_REQUESTS, _LAUNCH_TIME_WINDOW_SEC)


def _require_launch_quota(current_user: User = Depends(get_current_user)) -> None:
    """launch 端点限流依赖：单用户 10 次/分钟。

    复用 get_current_user 解析当前用户，按 user_id 计数；FastAPI 对同一请求内
    的 get_current_user 结果做缓存，避免重复鉴权。
    """
    launch_limiter.acquire(current_user.id)


@router.post("/launch", response_model=QuickTestLaunchResponse)
async def launch_quick_test(
    request: QuickTestLaunchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _quota: None = Depends(_require_launch_quota),
) -> QuickTestLaunchResponse:
    """一键启动快速测试。

    编排顺序由 QuickLauncher 负责：AutoProjectBuilder → 预创建任务 →
    SiteExplorer → AutoCaseGenerator → TaskAssembler。HttpUrl 在 schema 层
    已校验 scheme，此处转 str 传入 launcher。
    """
    try:
        launcher = QuickLauncher()
        return await launcher.launch(
            url=str(request.url),
            description=request.description,
            credentials=request.credentials,
            user_id=current_user.id,
            session=db,
        )
    except HTTPException:
        # 限流等中间件/依赖异常向上透传，不被通用分支吞掉
        raise
    except ValueError as exc:
        # URL 格式非法等业务校验失败，与 spec Scenario "URL 非法 → 422" 一致
        logger.warning(f"快速测试启动校验失败: user_id={current_user.id} err={exc}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"URL 格式非法或参数错误: {exc}",
        )
    except Exception as exc:
        # 建项/探索/生成等服务依赖异常，返回 503 表示服务暂不可用
        logger.error(f"快速测试启动失败: user_id={current_user.id} err={exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="快速测试服务暂不可用，请稍后重试",
        )


@router.get("/{task_id}/status", response_model=QuickTestStatusResponse)
async def get_quick_test_status(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuickTestStatusResponse:
    """查询快速测试任务进度。

    仅返回当前用户执行的任务（executor_id 过滤），避免越权查询他人任务。
    参数化查询 TestTask.id，防 SQL 注入。
    """
    task = (
        db.query(TestTask)
        .filter(TestTask.id == task_id, TestTask.executor_id == current_user.id)
        .first()
    )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在或无权访问",
        )
    return _build_status_response(task)


def _build_status_response(task: TestTask) -> QuickTestStatusResponse:
    """从 TestTask 构造状态响应。

    case_count 取 case_ids 长度（编排阶段未装填用例时为 0）；started_at 取
    start_time 的 ISO8601 字符串，未启动时为 None。
    """
    case_ids = task.case_ids if isinstance(task.case_ids, list) else []
    started_at = task.start_time.isoformat() if task.start_time else None
    return QuickTestStatusResponse(
        task_id=task.id,
        status=TaskStatus.LABELS.get(task.status, "未知"),
        progress=task.progress or 0,
        current_stage=_derive_stage(task),
        case_count=len(case_ids),
        started_at=started_at,
        websocket_channel=_CHANNEL_TEMPLATE.format(task_id=task.id),
    )


def _derive_stage(task: TestTask) -> str:
    """根据任务状态与进度推导当前编排阶段。

    与 QuickLauncher 推送阶段对齐：site_exploring(10/30)→case_generating
    (40/60)→task_assembling(70/90)→completed(100)。RUNNING 态按 progress
    阈值近似映射；执行引擎接管后 progress 反映用例执行进度，executing 段
    覆盖 90-100 的运行态。
    """
    if task.status == TaskStatus.PENDING:
        return "pending"
    if task.status == TaskStatus.COMPLETED:
        return "completed"
    if task.status == TaskStatus.FAILED:
        return "failed"
    if task.status == TaskStatus.STOPPED:
        return "stopped"
    # RUNNING：按进度阈值映射到编排阶段
    progress = task.progress or 0
    if progress < 30:
        return "site_exploring"
    if progress < 60:
        return "case_generating"
    if progress < 90:
        return "task_assembling"
    return "executing"
