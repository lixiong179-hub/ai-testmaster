"""MCP Server 端点 - 暴露工具列表与 SSE 流式调用入口。

路由（由 main.py 以 prefix=/api/v1 挂载）:
    - GET  /mcp/tools         返回 MCP 工具列表
    - POST /mcp/sse           SSE 流式调用工具，依次推送 start/progress/result 事件

权限:
    - GET /mcp/tools: 仅需登录
    - POST /mcp/sse:  查询类工具仅需登录；写类工具（generate_test_case）需 mcp:write 权限
"""
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.v1.endpoints.auth_deps import get_current_user
from app.core.exception import create_response
from app.core.permissions import MCP_SCOPE_WRITE, PermissionCode
from app.db.database import async_get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.agent.mcp_server import get_mcp_server

router = APIRouter(prefix="/mcp", tags=["mcp-server"])

# 写类工具集合：除登录外额外要求 mcp:write 权限码
_WRITE_TOOL_NAMES = {"generate_test_case"}


class MCPCallRequest(BaseModel):
    """MCP 工具调用请求体。"""

    tool_name: str = Field(..., description="MCP 工具名称")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="工具入参 JSON"
    )


def _sse(event: str, payload: Dict[str, Any]) -> Dict[str, str]:
    """构造 SSE 事件 dict，data 字段 JSON 序列化为字符串。"""
    return {
        "event": event,
        "data": json.dumps(payload, ensure_ascii=False, default=str),
    }


def _has_permission_code(user: User, code: str) -> bool:
    """基于预加载的 roles 关系检查用户是否持有指定权限码。

    get_current_user 已 selectinload(User.roles)，此处直接遍历角色 permissions
    JSON 列表，避免在 async 上下文额外发起同步 DB 查询。超级管理员自动放行。
    """
    if getattr(user, "is_superuser", False):
        return True
    for role in getattr(user, "roles", []) or []:
        if role.permissions and code in role.permissions:
            return True
    return False


@router.get(
    "/tools",
    response_model=ApiResponse[List[Dict[str, Any]]],
    summary="获取 MCP 工具列表",
)
async def list_mcp_tools(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """返回当前 MCPServer 注册的所有工具元信息。

    仅校验登录态，不要求 mcp:read scope（与任务规格一致）。
    """
    _ = current_user  # 登录态校验通过即可
    tools = get_mcp_server().list_tools()
    return create_response(data=tools, msg="获取成功")


@router.post(
    "/sse",
    summary="SSE 流式调用 MCP 工具",
    description=f"查询类工具仅需登录；写类工具需 `{MCP_SCOPE_WRITE}` 权限。"
                "依次推送 start / progress / result 事件，错误时推送 error 事件。",
)
async def call_mcp_tool_sse(
    request: MCPCallRequest,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
) -> EventSourceResponse:
    """SSE 流式调用 MCP 工具。

    事件序列：
        1. event: start   data: {"tool_name": "..."}
        2. event: progress data: {"message": "执行中..."}
        3. event: result  data: {工具返回结果}
        错误时：event: error data: {"error": "..."}

    权限：写类工具（generate_test_case）在开启 SSE 流之前校验 mcp:write
    权限码，缺失时直接返回 403，避免流式响应已开始后无法改写状态码。
    """
    server = get_mcp_server()
    tool = server.get_tool(request.tool_name)
    if tool is None:
        async def _not_found():
            yield _sse("error", {"error": f"工具不存在: {request.tool_name}"})

        return EventSourceResponse(_not_found())

    if request.tool_name in _WRITE_TOOL_NAMES and not _has_permission_code(
        current_user, PermissionCode.MCP_WRITE,
    ):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"缺少权限: {PermissionCode.MCP_WRITE}",
        )

    async def _event_stream():
        yield _sse("start", {"tool_name": request.tool_name})
        yield _sse("progress", {"message": "执行中..."})
        try:
            result = await server.call_tool(
                request.tool_name, request.arguments, db, current_user,
            )
            # 持久化 handler 内的写操作（如 AgentSession / TestTask），
            # 失败仅记录日志，不影响已生成的结果回传客户端
            try:
                await db.commit()
            except Exception as e:
                logger.warning(f"MCP SSE commit 失败: {e}")
            yield _sse("result", result)
        except Exception as e:
            logger.exception(f"MCP SSE 调用失败: {e}")
            yield _sse("error", {"error": str(e)})

    return EventSourceResponse(_event_stream())


__all__ = ["router"]
