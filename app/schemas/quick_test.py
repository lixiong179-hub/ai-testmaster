"""网址驱动快速测试 - 请求/响应 Schema。

定义快速测试端点的数据契约：
- QuickTestLaunchRequest：用户提交的网址 + 可选描述/凭据；
- QuickTestLaunchResponse：编排完成后的 task_id 与 WebSocket 订阅通道；
- QuickTestStatusResponse：任务进度查询响应，含当前阶段与用例计数。

字段约束遵循 spec 的"快速测试 API 端点" Requirement：
- url 必填且为合法 HttpUrl，杜绝 file/ftp/javascript 等非 http scheme；
- description 可选，用于聚焦测试范围（透传给 AutoCaseGenerator 的 Prompt）；
- credentials 可选，仅含 username/password，供 SiteExplorer 自动登录；
- websocket_channel 形如 `quick_test:{task_id}`，与 push_service 通道命名一致；
- started_at 为 ISO8601 字符串，任务未启动时为 None。
"""
from typing import Dict, Optional

from pydantic import BaseModel, Field, HttpUrl


class QuickTestLaunchRequest(BaseModel):
    """快速测试启动请求。

    业务用途：用户在前端输入网址（可选描述/凭据）后提交，触发一键编排。
    验证规则：url 必填且为合法 HttpUrl；description/credentials 可选。
    对应 API：POST /api/v1/quick-test/launch
    """

    url: HttpUrl = Field(..., description="被测站点网址，必须为 http/https")
    description: Optional[str] = Field(
        None, description="自然语言描述，聚焦测试范围，如'重点测登录和搜索功能'"
    )
    credentials: Optional[Dict[str, str]] = Field(
        None, description="登录凭据 {username, password}，仅登录页场景使用"
    )


class QuickTestLaunchResponse(BaseModel):
    """快速测试启动响应。

    业务用途：编排完成（建项→探索→生成→任务装配）后返回，前端据此订阅
    WebSocket 通道并查询任务进度。
    对应 API：POST /api/v1/quick-test/launch 的成功响应
    """

    task_id: int = Field(..., description="已创建的测试任务 ID")
    project_id: int = Field(..., description="自动创建的项目 ID")
    estimated_duration_sec: int = Field(
        ..., description="预估执行时长（秒），按用例数 * 30 估算"
    )
    websocket_channel: str = Field(
        ..., description="WebSocket 订阅通道，形如 quick_test:{task_id}"
    )


class QuickTestStatusResponse(BaseModel):
    """快速测试任务状态查询响应。

    业务用途：前端轮询或断线重连后拉取当前进度，配合 WebSocket 推送补齐
    历史阶段。status 为中文标签（与 TaskStatus.LABELS 一致），current_stage
    为编排阶段标识（与 QuickLauncher 推送阶段对齐），便于前端定位进度条位置。
    对应 API：GET /api/v1/quick-test/{task_id}/status
    """

    task_id: int = Field(..., description="测试任务 ID")
    status: str = Field(..., description="任务状态中文标签：等待执行/执行中/执行完成/执行失败/已停止")
    progress: int = Field(..., ge=0, le=100, description="执行进度百分比 0-100")
    current_stage: str = Field(
        ..., description="当前编排阶段：pending/site_exploring/case_generating/"
        "task_assembling/executing/completed/failed/stopped"
    )
    case_count: int = Field(..., ge=0, description="任务关联用例数")
    started_at: Optional[str] = Field(
        None, description="任务开始执行时间 ISO8601，未启动时为 None"
    )
    websocket_channel: str = Field(
        ..., description="WebSocket 订阅通道，形如 quick_test:{task_id}"
    )
