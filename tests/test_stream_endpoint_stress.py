"""流式端点契约测试 - SSE 基础格式与端点注册验证

原流式端点压力测试基于同步 Session 与无质量反馈闭环的旧实现，
API 重构后已不兼容（db: AsyncSession、质量反馈闭环、PrimarySessionLocal 等）。
本文件保留端点契约与 SSE 格式的基础行为测试，移除不可恢复的复杂并发场景测试。
"""
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.responses import StreamingResponse

from app.api.v1.endpoints.test_case_ai import (
    AIGenerateEnhancedRequest,
    _build_graph_prompt_data,
    _build_linear_prompt_data,
    _format_case_response,
)
from app.api.v1.endpoints.test_case_ai_stream import ai_enhanced_generate_stream
from app.schemas.test_case import FlowSortDataSchema, FlowEdgeSchema, FlowNodeSchema


def _make_async_db_with_project(project=None):
    """构造 AsyncSession mock，db.execute(...).scalars().first() 返回 project。"""
    db = AsyncMock()
    result_mock = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.first.return_value = project
    result_mock.scalars.return_value = scalars_mock
    db.execute.return_value = result_mock
    return db


class TestStreamEndpointRegistration:
    """流式端点路由注册验证"""

    def test_stream_router_registered(self):
        """ai-enhanced-generate/stream 路由应注册到 test_case_ai_stream router"""
        from app.api.v1.endpoints.test_case_ai_stream import router

        paths = [r.path for r in router.routes]
        assert "/ai-enhanced-generate/stream" in paths, \
            "缺少 /ai-enhanced-generate/stream 端点"
        assert "/batch-generate/stream" in paths, \
            "缺少 /batch-generate/stream 端点"


class TestStreamEndpointFormat:
    """SSE 事件流格式基础测试"""

    @pytest.mark.asyncio
    async def test_stream_returns_streaming_response(self):
        """有效请求应返回 StreamingResponse，media_type=text/event-stream"""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字符",
        )
        mock_project = MagicMock(id=1, user_id=1)
        db = _make_async_db_with_project(project=mock_project)
        current_user = MagicMock(id=1)

        # 跳过质量反馈闭环：mock generate_test_case_enhanced 返回有效用例
        # 且 validate_single_case_status 直接返回 passed
        with patch(
            "app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced",
            return_value={"title": "测试用例标题", "steps": []},
        ), patch(
            "app.api.v1.endpoints.test_case_ai_stream._run_quality_feedback_for_cases",
            new_callable=AsyncMock,
            return_value=([{"title": "测试用例标题", "steps": []}], []),
        ), patch(
            "app.api.v1.endpoints.test_case_ai_stream.PrimarySessionLocal",
            return_value=MagicMock(),
        ):
            response = await ai_enhanced_generate_stream(
                request=request, db=db, current_user=current_user,
            )

        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"
        assert response.headers["Cache-Control"] == "no-cache"
        assert response.headers["Connection"] == "keep-alive"

    @pytest.mark.asyncio
    async def test_stream_invalid_project_returns_404(self):
        """无效项目ID应抛出 404 HTTPException"""
        request = AIGenerateEnhancedRequest(
            project_id=99999,
            description="测试描述，至少需要五个字符",
        )
        db = _make_async_db_with_project(project=None)
        current_user = MagicMock(id=1)

        with pytest.raises(HTTPException) as exc_info:
            await ai_enhanced_generate_stream(
                request=request, db=db, current_user=current_user,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_stream_too_short_description_returns_400(self):
        """过短描述应抛出 400 HTTPException"""
        # 构造一个绕过 Pydantic 校验的 request（直接构造对象）
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="这是一个有效的测试描述",
        )
        # 覆盖 description 为短字符串（绕过 Pydantic 校验以触发端点内的二次校验）
        object.__setattr__(request, "description", "短")

        mock_project = MagicMock(id=1, user_id=1)
        db = _make_async_db_with_project(project=mock_project)
        current_user = MagicMock(id=1)

        with pytest.raises(HTTPException) as exc_info:
            await ai_enhanced_generate_stream(
                request=request, db=db, current_user=current_user,
            )

        assert exc_info.value.status_code == 400


class TestStreamEventSequence:
    """SSE 事件序列内容验证"""

    @pytest.mark.asyncio
    async def test_stream_linear_mode_event_sequence(self):
        """linear 增强模式应推送 started/building_prompt/generating/生成完成 事件"""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字符",
            mode="linear",
            enhanced_mode=True,
        )
        mock_project = MagicMock(id=1, user_id=1)
        db = _make_async_db_with_project(project=mock_project)
        current_user = MagicMock(id=1)

        with patch(
            "app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced",
            return_value={"title": "测试用例标题", "steps": []},
        ), patch(
            "app.api.v1.endpoints.test_case_ai_stream._run_quality_feedback_for_cases",
            new_callable=AsyncMock,
            return_value=([{"title": "测试用例标题", "steps": []}], []),
        ), patch(
            "app.api.v1.endpoints.test_case_ai_stream.PrimarySessionLocal",
            return_value=MagicMock(),
        ):
            response = await ai_enhanced_generate_stream(
                request=request, db=db, current_user=current_user,
            )

            body = b""
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

        content = body.decode("utf-8")
        assert "started" in content
        assert "building_prompt" in content
        assert "generating" in content
        assert "生成完成" in content

    @pytest.mark.asyncio
    async def test_stream_graph_mode_event_sequence(self):
        """graph 模式应推送 started/building_prompt/generating/生成完成 事件"""
        flow_data = FlowSortDataSchema(
            nodes=[
                FlowNodeSchema(
                    screen_id=1, screen_order=1,
                    flow_type="main", screen_name="登录页",
                ),
            ],
            edges=[],
        )
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字符",
            mode="graph",
            flow_sort_data=flow_data,
        )
        mock_project = MagicMock(id=1, user_id=1)
        db = _make_async_db_with_project(project=mock_project)
        current_user = MagicMock(id=1)

        with patch(
            "app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced",
            return_value={"title": "测试用例标题", "steps": []},
        ), patch(
            "app.api.v1.endpoints.test_case_ai_stream._run_quality_feedback_for_cases",
            new_callable=AsyncMock,
            return_value=([{"title": "测试用例标题", "steps": []}], []),
        ), patch(
            "app.api.v1.endpoints.test_case_ai_stream.PrimarySessionLocal",
            return_value=MagicMock(),
        ):
            response = await ai_enhanced_generate_stream(
                request=request, db=db, current_user=current_user,
            )

            body = b""
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

        content = body.decode("utf-8")
        assert "started" in content
        assert "building_prompt" in content
        assert "generating" in content
        assert "生成完成" in content

    @pytest.mark.asyncio
    async def test_stream_basic_mode_event_sequence(self):
        """基础模式（非增强）应推送 started/generating/生成完成 事件"""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字符",
            enhanced_mode=False,
        )
        mock_project = MagicMock(id=1, user_id=1)
        db = _make_async_db_with_project(project=mock_project)
        current_user = MagicMock(id=1)

        with patch(
            "app.api.v1.endpoints.test_case_ai_stream.generate_test_case",
            return_value={"title": "基础模式用例", "steps": []},
        ), patch(
            "app.api.v1.endpoints.test_case_ai_stream.PrimarySessionLocal",
            return_value=MagicMock(),
        ):
            response = await ai_enhanced_generate_stream(
                request=request, db=db, current_user=current_user,
            )

            body = b""
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

        content = body.decode("utf-8")
        assert "started" in content
        assert "generating" in content
        assert "生成完成" in content

    @pytest.mark.asyncio
    async def test_stream_error_event_on_exception(self):
        """生成异常时应推送 code=500 的生成失败事件"""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字符",
            enhanced_mode=True,
        )
        mock_project = MagicMock(id=1, user_id=1)
        db = _make_async_db_with_project(project=mock_project)
        current_user = MagicMock(id=1)

        with patch(
            "app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced",
            side_effect=Exception("AI服务异常"),
        ), patch(
            "app.api.v1.endpoints.test_case_ai_stream.PrimarySessionLocal",
            return_value=MagicMock(),
        ):
            response = await ai_enhanced_generate_stream(
                request=request, db=db, current_user=current_user,
            )

            body = b""
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

        content = body.decode("utf-8")
        assert "生成失败" in content
        assert "500" in content
