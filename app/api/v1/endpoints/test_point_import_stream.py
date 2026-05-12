"""XMind AI增强导入SSE流式端点。

通过Server-Sent Events推送AI解析实时进度，提升用户体验。
事件类型:
    - progress: 进度事件，包含 completed_batches/total_batches/completed_paths/total_paths
    - result: 最终结果事件，包含完整导入/预览数据
    - error: 错误事件，包含错误信息
"""
import asyncio
import json
import os
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_point_mutate import check_project_permission
from app.services.xmind_parser import XmindParser, XmindParseError
from app.services.xmind_ai_parser import XmindAIParser
from app.services.xmind_import_service import (
    validate_file,
    save_upload_file,
    handle_ai_enhanced_import,
)
from app.core.config import settings
from app.utils.ai_client_core import (
    AIAuthenticationError,
    AIPermissionError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)
from loguru import logger

router = APIRouter()


def _sse_event(event: str, data: dict) -> str:
    """格式化SSE事件。

    注意：SSE协议中data字段不能包含裸换行，
    需确保JSON序列化结果为单行。
    """
    json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return f"event: {event}\ndata: {json_str}\n\n"


async def _run_ai_parse_with_progress(
    paths: list,
    preview: bool,
    project_id: int,
    current_username: str,
) -> AsyncGenerator[str, None]:
    """在后台线程运行AI解析，通过SSE推送进度。"""
    total_paths = len(paths)
    progress_state = {"completed_batches": 0, "total_batches": 0}

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def progress_callback(completed_batches: int, total_batches: int,
                          completed_paths: int, total_paths_count: int):
        """线程安全的进度回调，将进度事件放入异步队列。"""
        progress_state["completed_batches"] = completed_batches
        progress_state["total_batches"] = total_batches
        try:
            loop.call_soon_threadsafe(
                queue.put_nowait,
                _sse_event("progress", {
                    "completed_batches": completed_batches,
                    "total_batches": total_batches,
                    "completed_paths": completed_paths,
                    "total_paths": total_paths_count,
                    "percentage": round(completed_batches / total_batches * 100) if total_batches > 0 else 0,
                }),
            )
        except RuntimeError:
            # 事件循环已关闭时忽略（如客户端断开连接）
            pass

    # 发送初始进度
    yield _sse_event("progress", {
        "completed_batches": 0,
        "total_batches": 0,
        "completed_paths": 0,
        "total_paths": total_paths,
        "percentage": 0,
        "status": "starting",
    })

    # 在线程池中运行AI解析（不捕获异常，让task.result()自然抛出）
    def _sync_parse():
        ai_parser = XmindAIParser()
        return ai_parser.parse_paths(paths, progress_callback=progress_callback)

    task = loop.run_in_executor(None, _sync_parse)

    # 同时从队列中读取进度事件
    while not task.done():
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.5)
            yield event
        except asyncio.TimeoutError:
            continue

    # 读取队列中剩余的进度事件
    while not queue.empty():
        try:
            event = queue.get_nowait()
            yield event
        except asyncio.QueueEmpty:
            break

    # 获取AI解析结果
    try:
        ai_cases = task.result()
    except AITimeoutError:
        yield _sse_event("error", {"detail": "AI增强解析超时，请稍后重试或关闭AI增强模式", "error_type": "timeout"})
        return
    except AIAuthenticationError:
        yield _sse_event("error", {"detail": "AI服务认证失败，请联系管理员", "error_type": "auth"})
        return
    except AIRateLimitError:
        yield _sse_event("error", {"detail": "AI服务请求过于频繁，请稍后重试", "error_type": "rate_limit"})
        return
    except AIPermissionError:
        yield _sse_event("error", {"detail": "AI服务权限不足，请联系管理员", "error_type": "permission"})
        return
    except AIServiceError as exc:
        yield _sse_event("error", {"detail": f"AI增强解析失败：{exc.message}", "error_type": "ai_service"})
        return
    except Exception as exc:
        logger.exception(f"AI增强解析未知错误: {exc}")
        yield _sse_event("error", {"detail": "AI增强解析发生未知错误，请稍后重试", "error_type": "unknown"})
        return

    if not ai_cases:
        yield _sse_event("error", {"detail": "AI增强解析返回空结果，请检查文件内容", "error_type": "empty_result"})
        return

    # 发送完成进度
    yield _sse_event("progress", {
        "completed_batches": progress_state.get("total_batches", 0),
        "total_batches": progress_state.get("total_batches", 0),
        "completed_paths": len(ai_cases),
        "total_paths": total_paths,
        "percentage": 100,
        "status": "completed",
    })

    # 写入数据库并返回结果
    # 注意：SSE场景下请求级别的db会话在StreamingResponse返回后已关闭，
    # 需在此处独立创建会话，生命周期由本函数管理
    try:
        from app.db.database import PrimarySessionLocal
        db = PrimarySessionLocal()
        try:
            result = handle_ai_enhanced_import(
                db=db,
                project_id=project_id,
                current_username=current_username,
                ai_cases=ai_cases,
                preview=preview,
                ai_timeout=False,
                total_paths=total_paths,
            )
            # 将result转为可序列化dict
            result_dict = _serialize_result(result)
            yield _sse_event("result", result_dict)
        finally:
            db.close()
    except Exception as exc:
        logger.exception(f"AI增强导入数据库写入失败: {exc}")
        yield _sse_event("error", {"detail": f"导入失败：{str(exc)}", "error_type": "db_error"})


def _serialize_result(result) -> dict:
    """将Pydantic响应模型转为可序列化dict。"""
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()
    if isinstance(result, dict):
        return result
    return {"raw": str(result)}


@router.post("/import-xmind-stream")
async def import_xmind_stream(
    file: UploadFile = File(..., description="XMind 文件"),
    project_id: int = Form(..., description="项目ID"),
    preview: bool = Form(False, description="是否预览模式"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """XMind AI增强导入SSE流式端点。

    返回Server-Sent Events流，实时推送AI解析进度和最终结果。
    仅支持AI增强模式（自动启用）。
    """
    check_project_permission(db, project_id, current_user.id)
    validate_file(file)

    logger.info(f"XMind SSE导入请求: project_id={project_id}, preview={preview}")

    tmp_path = await save_upload_file(file)
    try:
        parser = XmindParser()
        all_paths = parser.extract_paths(tmp_path)
        if not all_paths:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            async def _error_gen():
                yield _sse_event("error", {"detail": "XMind文件未提取到有效路径", "error_type": "parse_error"})
            return StreamingResponse(_error_gen(), media_type="text/event-stream")

        total_paths = len(all_paths)
        if preview:
            sample_size = settings.XMIND_AI_PREVIEW_SAMPLE
            paths = all_paths[:sample_size]
            logger.info(f"AI SSE预览采样: {len(paths)}/{total_paths} 条路径")
        else:
            paths = all_paths

        async def event_generator():
            try:
                async for event in _run_ai_parse_with_progress(
                    paths=paths,
                    preview=preview,
                    project_id=project_id,
                    current_username=current_user.username,
                ):
                    yield event
            finally:
                # 清理临时文件
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except XmindParseError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        async def _error_gen():
            yield _sse_event("error", {"detail": "XMind解析失败", "error_type": "parse_error"})
        return StreamingResponse(_error_gen(), media_type="text/event-stream")
