import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.ai.client import AIResponse, TokenUsage
from app.services.ai_analysis_service._extract import _ExtractMixin
from app.services.ai_analysis_service._service import AIAnalysisService


class TestAiCallTimeoutProtection:
    """验证 AI 分析服务调用启用超时保护（P-1 修复）。

    修复前：3 处 AI 调用使用 `await self.ai_client.complete(...)` 无超时
    修复后：统一走 `complete_async(..., timeout=settings.AI_CALL_TIMEOUT_SECONDS)`
    """

    @pytest.mark.asyncio
    async def test_extract_test_points_times_out_returns_empty(self):
        """AI 调用超时时返回空列表，不抛异常。"""
        mixin = _ExtractMixin()
        mock_client = MagicMock()
        # 模拟超时：complete_async 抛 asyncio.TimeoutError
        mock_client.complete_async = AsyncMock(side_effect=asyncio.TimeoutError())
        mixin.ai_client = mock_client

        result = await mixin.extract_test_points_from_content("需求内容测试")

        assert result == []
        mock_client.complete_async.assert_awaited_once()
        # 验证传入了 timeout 参数
        _args, kwargs = mock_client.complete_async.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] > 0

    @pytest.mark.asyncio
    async def test_extract_ui_specs_times_out_returns_empty(self):
        """UI 测试点提取超时时返回空列表。"""
        mixin = _ExtractMixin()
        mock_client = MagicMock()
        mock_client.complete_async = AsyncMock(side_effect=asyncio.TimeoutError())
        mixin.ai_client = mock_client

        result = await mixin.extract_test_points_from_ui_specs(
            [{"screen_name": "首页", "ui_spec": {"elements": [{"text": "按钮", "type": "button"}]}}]
        )

        assert result == []
        _args, kwargs = mock_client.complete_async.call_args
        assert "timeout" in kwargs

    @pytest.mark.asyncio
    async def test_generate_summary_times_out_returns_empty_string(self):
        """_generate_summary 超时返回空字符串。"""
        mock_client = MagicMock()
        mock_client.complete_async = AsyncMock(side_effect=asyncio.TimeoutError())
        service = AIAnalysisService(ai_client=mock_client)

        result = await service._generate_summary("需求内容")

        assert result == ""
        _args, kwargs = mock_client.complete_async.call_args
        assert "timeout" in kwargs

    @pytest.mark.asyncio
    async def test_extract_skips_when_ai_client_none(self):
        """ai_client 为 None 时跳过 AI 调用，返回空列表。"""
        mixin = _ExtractMixin()
        mixin.ai_client = None

        result = await mixin.extract_test_points_from_content("需求内容")
        assert result == []

        ui_result = await mixin.extract_test_points_from_ui_specs(
            [{"screen_name": "页面", "ui_spec": {"elements": []}}]
        )
        assert ui_result == []

    @pytest.mark.asyncio
    async def test_summary_skips_when_ai_client_none(self):
        """_generate_summary 在 ai_client 为 None 时返回空字符串。"""
        service = AIAnalysisService(ai_client=None)
        result = await service._generate_summary("内容")
        assert result == ""

    @pytest.mark.asyncio
    async def test_extract_passes_timeout_setting_to_client(self):
        """验证 complete_async 收到 settings.AI_CALL_TIMEOUT_SECONDS 作为 timeout。"""
        from app.core.config import settings

        mixin = _ExtractMixin()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "[]"
        mock_client.complete_async = AsyncMock(return_value=mock_response)
        mixin.ai_client = mock_client

        await mixin.extract_test_points_from_content("内容")

        _args, kwargs = mock_client.complete_async.call_args
        assert kwargs["timeout"] == float(settings.AI_CALL_TIMEOUT_SECONDS)

    @pytest.mark.asyncio
    async def test_get_ai_analysis_service_uses_async_client(self):
        """get_ai_analysis_service 返回的实例应使用 AsyncOpenAIClient。"""
        from app.ai.openai_client import AsyncOpenAIClient
        from app.services.ai_analysis_service._service import get_ai_analysis_service

        service = get_ai_analysis_service()
        assert isinstance(service.ai_client, AsyncOpenAIClient)


class TestBuildExtractPrompt:
    def setup_method(self):
        self.mixin = _ExtractMixin()
        self.mixin.ai_client = None

    def test_basic_prompt(self):
        prompt = self.mixin._build_extract_prompt("需求内容测试")
        assert "需求内容测试" in prompt
        assert "JSON" in prompt

    def test_prompt_with_context(self):
        prompt = self.mixin._build_extract_prompt(
            "需求内容",
            context={"extra_instructions": "重点关注登录模块"},
        )
        assert "重点关注登录模块" in prompt

    def test_prompt_without_context(self):
        prompt = self.mixin._build_extract_prompt("需求内容", context=None)
        assert "额外要求" not in prompt

    def test_prompt_with_empty_context(self):
        prompt = self.mixin._build_extract_prompt("需求内容", context={})
        assert "额外要求" not in prompt


class TestBuildUiExtractContent:
    def setup_method(self):
        self.mixin = _ExtractMixin()
        self.mixin.ai_client = None

    def test_basic_ui_specs(self):
        specs = [
            {
                "screen_name": "登录页",
                "ui_spec": {
                    "elements": [
                        {"text": "用户名", "type": "input"},
                        {"text": "密码", "type": "input"},
                    ]
                },
            }
        ]
        content = self.mixin._build_ui_extract_content(specs)
        assert "登录页" in content
        assert "用户名" in content
        assert "密码" in content

    def test_empty_ui_specs(self):
        content = self.mixin._build_ui_extract_content([])
        assert content == ""

    def test_no_text_elements(self):
        specs = [
            {
                "screen_name": "页面",
                "ui_spec": {
                    "elements": [
                        {"text": "", "type": "button"},
                    ]
                },
            }
        ]
        content = self.mixin._build_ui_extract_content(specs)
        assert "页面" in content

    def test_missing_ui_spec(self):
        specs = [{"screen_name": "页面"}]
        content = self.mixin._build_ui_extract_content(specs)
        assert "页面" in content


class TestBuildUiExtractPrompt:
    def setup_method(self):
        self.mixin = _ExtractMixin()
        self.mixin.ai_client = None

    def test_contains_ui_content(self):
        prompt = self.mixin._build_ui_extract_prompt("UI设计信息内容")
        assert "UI设计信息内容" in prompt
        assert "JSON" in prompt


class TestParseTestPointsResponse:
    def setup_method(self):
        self.mixin = _ExtractMixin()
        self.mixin.ai_client = None

    def test_valid_json_list(self):
        content = '[{"module": "登录", "point": "验证登录"}]'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_valid_json_dict_with_key(self):
        content = '{"test_points": [{"module": "登录", "point": "验证"}]}'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_valid_json_dict_with_data_key(self):
        content = '{"data": [{"module": "登录"}]}'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_valid_json_dict_with_items_key(self):
        content = '{"items": [{"module": "登录"}]}'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_valid_json_dict_with_points_key(self):
        content = '{"points": [{"module": "登录"}]}'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_invalid_json_with_array(self):
        content = '结果如下：[{"module": "登录"}] 结束'
        result = self.mixin._parse_test_points_response(content)
        assert len(result) == 1

    def test_empty_content(self):
        result = self.mixin._parse_test_points_response("")
        assert result == []

    def test_completely_invalid(self):
        result = self.mixin._parse_test_points_response("no json at all")
        assert result == []

    def test_plain_dict_without_known_key(self):
        content = '{"module": "登录", "point": "验证"}'
        result = self.mixin._parse_test_points_response(content)
        assert isinstance(result, (list, dict))
