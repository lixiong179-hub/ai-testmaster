"""
流式端点压力测试 - SSE高并发稳定性验�?

覆盖范围:
- SSE事件流格式验�?
- 并发请求处理
- 异常场景下的流式响应
- graph/linear模式流式推�?
"""
import pytest
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from starlette.responses import StreamingResponse
from app.api.v1.endpoints.test_case_ai_stream import ai_enhanced_generate_stream
from app.api.v1.endpoints.test_case_ai import (
    AIGenerateEnhancedRequest,
    _build_graph_prompt_data,
    _build_linear_prompt_data,
    _format_case_response,
)
from app.schemas.test_case import FlowSortDataSchema, FlowNodeSchema, FlowEdgeSchema


class TestStreamEndpointFormat:
    """测试SSE事件流格�?""

    @pytest.mark.asyncio
    async def test_stream_events_format(self):
        """测试SSE事件格式符合规范"""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字�?
        )

        with patch('app.api.v1.endpoints.test_case_ai_stream.generate_test_case') as mock_gen:
            mock_gen.return_value = {
                'title': '测试用例',
                'steps': [{'step': '1', 'description': '步骤1'}]
            }

            response = await ai_enhanced_generate_stream(
                request=request,
                db=MagicMock(),
                current_user=MagicMock()
            )

            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"
            assert response.headers["Cache-Control"] == "no-cache"
            assert response.headers["Connection"] == "keep-alive"

    @pytest.mark.asyncio
    async def test_stream_graph_mode_events_sequence(self):
        """测试graph模式SSE事件序列"""
        flow_data = FlowSortDataSchema(
            nodes=[
                FlowNodeSchema(screen_id=1, screen_order=1, flow_type='main', screen_name='登录�?)
            ],
            edges=[]
        )
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字�?,
            mode='graph',
            flow_sort_data=flow_data
        )

        with patch('app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced') as mock_gen:
            mock_gen.return_value = {
                'title': '测试用例',
                'steps': [{'step': '1', 'description': '步骤1'}]
            }

            response = await ai_enhanced_generate_stream(
                request=request,
                db=MagicMock(),
                current_user=MagicMock()
            )

            body = b''
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

            content = body.decode('utf-8')
            assert 'started' in content
            assert 'building_prompt' in content
            assert 'generating' in content
            assert '生成完成' in content

    @pytest.mark.asyncio
    async def test_stream_linear_mode_events_sequence(self):
        """测试linear模式SSE事件序列"""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字�?,
            mode='linear',
            enhanced_mode=True
        )

        with patch('app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced') as mock_gen:
            mock_gen.return_value = {
                'title': '测试用例',
                'steps': [{'step': '1', 'description': '步骤1'}]
            }

            response = await ai_enhanced_generate_stream(
                request=request,
                db=MagicMock(),
                current_user=MagicMock()
            )

            body = b''
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

            content = body.decode('utf-8')
            assert 'started' in content
            assert 'building_prompt' in content
            assert 'generating' in content
            assert '生成完成' in content

    @pytest.mark.asyncio
    async def test_stream_error_handling(self):
        """测试流式端点异常处理"""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字�?,
            enhanced_mode=True
        )

        with patch('app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced') as mock_gen:
            mock_gen.side_effect = Exception("AI服务异常")

            response = await ai_enhanced_generate_stream(
                request=request,
                db=MagicMock(),
                current_user=MagicMock()
            )

            body = b''
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

            content = body.decode('utf-8')
            assert '生成失败' in content
            assert '500' in content


class TestStreamConcurrency:
    """测试并发请求处理"""

    @pytest.mark.asyncio
    async def test_multiple_stream_requests(self):
        """测试多个流式请求同时处理"""
        requests = [
            AIGenerateEnhancedRequest(
                project_id=1,
                description=f"测试描述{i}，至少需要五个字�?
            )
            for i in range(3)
        ]

        with patch('app.api.v1.endpoints.test_case_ai_stream.generate_test_case') as mock_gen:
            mock_gen.return_value = {
                'title': '测试用例',
                'steps': [{'step': '1', 'description': '步骤1'}]
            }

            async def fetch_stream(req):
                response = await ai_enhanced_generate_stream(
                    request=req,
                    db=MagicMock(),
                    current_user=MagicMock()
                )
                body = b''
                async for chunk in response.body_iterator:
                    body += chunk if isinstance(chunk, bytes) else chunk.encode()
                return body.decode('utf-8')

            results = await asyncio.gather(*[fetch_stream(req) for req in requests])

            for result in results:
                assert 'started' in result
                assert '生成完成' in result

    @pytest.mark.asyncio
    async def test_stream_with_large_flow_data(self):
        """测试大数据量流式请求"""
        nodes = [
            FlowNodeSchema(
                screen_id=i,
                screen_order=i,
                flow_type='main',
                screen_name=f'页面{i}'
            )
            for i in range(1, 51)
        ]
        edges = [
            FlowEdgeSchema(
                source=str(i),
                target=str(i + 1),
                edge_type='normal',
                label='正常流转'
            )
            for i in range(1, 50)
        ]
        flow_data = FlowSortDataSchema(nodes=nodes, edges=edges)

        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字�?,
            mode='graph',
            flow_sort_data=flow_data
        )

        with patch('app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced') as mock_gen:
            mock_gen.return_value = {
                'title': '大数据量测试',
                'steps': [{'step': '1', 'description': '步骤1'}]
            }

            response = await ai_enhanced_generate_stream(
                request=request,
                db=MagicMock(),
                current_user=MagicMock()
            )

            body = b''
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

            content = body.decode('utf-8')
            assert 'started' in content
            assert 'building_prompt' in content
            assert '生成完成' in content


class TestStreamEdgeCases:
    """测试流式端点边界场景"""

    @pytest.mark.asyncio
    async def test_stream_empty_flow_data(self):
        """测试空流程数据流式请�?- 使用linear模式（graph模式要求至少1个节点）"""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字�?,
            mode='linear',
            enhanced_mode=True
        )

        with patch('app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced') as mock_gen:
            mock_gen.return_value = {'title': '空数据测�?, 'steps': []}

            response = await ai_enhanced_generate_stream(
                request=request,
                db=MagicMock(),
                current_user=MagicMock()
            )

            body = b''
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

            content = body.decode('utf-8')
            assert '生成完成' in content

    @pytest.mark.asyncio
    async def test_stream_basic_mode(self):
        """测试基础模式（非增强）流式请�?""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字�?,
            enhanced_mode=False
        )

        with patch('app.api.v1.endpoints.test_case_ai_stream.generate_test_case') as mock_gen:
            mock_gen.return_value = {
                'title': '基础模式测试',
                'steps': [{'step': '1', 'description': '步骤1'}]
            }

            response = await ai_enhanced_generate_stream(
                request=request,
                db=MagicMock(),
                current_user=MagicMock()
            )

            body = b''
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

            content = body.decode('utf-8')
            assert 'generating' in content
            assert '生成完成' in content

    @pytest.mark.asyncio
    async def test_stream_invalid_project(self):
        """测试无效项目ID流式请求"""
        request = AIGenerateEnhancedRequest(
            project_id=99999,
            description="测试描述，至少需要五个字�?
        )

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await ai_enhanced_generate_stream(
                request=request,
                db=mock_db,
                current_user=MagicMock()
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_stream_json_encoding(self):
        """测试SSE事件JSON编码正确�?""
        request = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试描述，至少需要五个字�?,
            enhanced_mode=True
        )

        with patch('app.api.v1.endpoints.test_case_ai_stream.generate_test_case_enhanced') as mock_gen:
            mock_gen.return_value = {
                'title': '中文测试用例',
                'steps': [{'step': '1', 'description': '点击"确定"按钮'}]
            }

            response = await ai_enhanced_generate_stream(
                request=request,
                db=MagicMock(),
                current_user=MagicMock()
            )

            body = b''
            async for chunk in response.body_iterator:
                body += chunk if isinstance(chunk, bytes) else chunk.encode()

            content = body.decode('utf-8')
            assert '中文测试用例' in content
            # 验证步骤数据被正确转换（convert_steps_to_response将description映射为action�?
            assert '"step": "1"' in content or '"action": "点击"' in content
