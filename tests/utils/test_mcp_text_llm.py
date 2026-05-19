import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.utils.mcp_text_llm import MCPAwareLLM, get_mcp_llm, LOCATOR_UNDERSTANDING_PROMPT


class TestParseLocatorResult:
    def test_parse_valid_json(self):
        response = '{"locator_type": "text", "locator_value": "登录", "confidence": 0.9, "reasoning": "test"}'
        result = MCPAwareLLM.parse_locator_result(response)
        assert result is not None
        assert result["locator_type"] == "text"
        assert result["locator_value"] == "登录"
        assert result["confidence"] == 0.9

    def test_parse_empty_response(self):
        result = MCPAwareLLM.parse_locator_result("")
        assert result is None

    def test_parse_none_response(self):
        result = MCPAwareLLM.parse_locator_result(None)
        assert result is None

    def test_parse_no_json(self):
        result = MCPAwareLLM.parse_locator_result("no json here")
        assert result is None

    def test_parse_missing_locator_type(self):
        response = '{"locator_value": "登录", "confidence": 0.9}'
        result = MCPAwareLLM.parse_locator_result(response)
        assert result is None

    def test_parse_missing_locator_value(self):
        response = '{"locator_type": "text", "confidence": 0.9}'
        result = MCPAwareLLM.parse_locator_result(response)
        assert result is None

    def test_parse_json_with_surrounding_text(self):
        response = 'Here is the result: {"locator_type": "css", "locator_value": "#btn", "confidence": 0.8} end'
        result = MCPAwareLLM.parse_locator_result(response)
        assert result is not None
        assert result["locator_type"] == "css"

    def test_parse_invalid_json(self):
        response = '{"locator_type": "text", "locator_value": "登录"'
        result = MCPAwareLLM.parse_locator_result(response)
        assert result is None

    def test_parse_with_element_description(self):
        response = '{"locator_type": "role", "locator_value": "button[提交]", "element_description": "提交按钮", "confidence": 0.95}'
        result = MCPAwareLLM.parse_locator_result(response)
        assert result is not None
        assert result["element_description"] == "提交按钮"

    def test_parse_empty_locator_type_and_value(self):
        response = '{"locator_type": "", "locator_value": "", "confidence": 0}'
        result = MCPAwareLLM.parse_locator_result(response)
        assert result is None


class TestMCPAwareLLMVisionModel:
    def test_vision_model_lazy_init(self):
        mock_model = MagicMock()
        llm = MCPAwareLLM(vision_model=mock_model)
        assert llm.vision_model is mock_model

    def test_vision_model_default_init(self):
        llm = MCPAwareLLM()
        with patch("app.utils.mcp_text_llm.get_default_vision_model") as mock_get:
            mock_get.return_value = MagicMock()
            model = llm.vision_model
            assert model is not None
            mock_get.assert_called_once()


class TestMCPAwareLLMUnderstandOperation:
    @pytest.mark.asyncio
    async def test_understand_operation_success(self):
        mock_model = MagicMock()
        mock_model.analyze_text.return_value = '{"locator_type": "text", "locator_value": "登录", "confidence": 0.9}'
        llm = MCPAwareLLM(vision_model=mock_model)
        result = await llm.understand_operation("accessibility tree", "点击登录按钮")
        assert result is not None
        assert result["locator_type"] == "text"

    @pytest.mark.asyncio
    async def test_understand_operation_with_action_type(self):
        mock_model = MagicMock()
        mock_model.analyze_text.return_value = '{"locator_type": "css", "locator_value": "#input", "confidence": 0.8}'
        llm = MCPAwareLLM(vision_model=mock_model)
        result = await llm.understand_operation("tree", "输入用户名", action_type="input")
        assert result is not None

    @pytest.mark.asyncio
    async def test_understand_operation_exception(self):
        mock_model = MagicMock()
        mock_model.analyze_text.side_effect = RuntimeError("model error")
        llm = MCPAwareLLM(vision_model=mock_model)
        result = await llm.understand_operation("tree", "操作")
        assert result is None

    @pytest.mark.asyncio
    async def test_understand_operation_parse_failure(self):
        mock_model = MagicMock()
        mock_model.analyze_text.return_value = "invalid response"
        llm = MCPAwareLLM(vision_model=mock_model)
        result = await llm.understand_operation("tree", "操作")
        assert result is None


class TestMCPAwareLLMBatchUnderstand:
    @pytest.mark.asyncio
    async def test_batch_string_operations(self):
        mock_model = MagicMock()
        mock_model.analyze_text.return_value = '{"locator_type": "text", "locator_value": "按钮", "confidence": 0.9}'
        llm = MCPAwareLLM(vision_model=mock_model)
        results = await llm.batch_understand_operations("tree", ["点击按钮", "输入文本"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_batch_dict_operations(self):
        mock_model = MagicMock()
        mock_model.analyze_text.return_value = '{"locator_type": "text", "locator_value": "按钮", "confidence": 0.9}'
        llm = MCPAwareLLM(vision_model=mock_model)
        ops = [
            {"description": "点击按钮", "action_type": "click"},
            {"description": "输入文本"},
        ]
        results = await llm.batch_understand_operations("tree", ops)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_batch_invalid_operation_type(self):
        mock_model = MagicMock()
        llm = MCPAwareLLM(vision_model=mock_model)
        results = await llm.batch_understand_operations("tree", [123])
        assert results == [None]

    @pytest.mark.asyncio
    async def test_batch_empty_operations(self):
        mock_model = MagicMock()
        llm = MCPAwareLLM(vision_model=mock_model)
        results = await llm.batch_understand_operations("tree", [])
        assert results == []


class TestGetMcpLlm:
    def test_get_mcp_llm_creates_instance(self):
        import app.utils.mcp_text_llm as mod
        original = mod._mcp_llm
        mod._mcp_llm = None
        try:
            llm = get_mcp_llm()
            assert isinstance(llm, MCPAwareLLM)
        finally:
            mod._mcp_llm = original

    def test_get_mcp_llm_returns_same_instance(self):
        import app.utils.mcp_text_llm as mod
        original = mod._mcp_llm
        mod._mcp_llm = None
        try:
            llm1 = get_mcp_llm()
            llm2 = get_mcp_llm()
            assert llm1 is llm2
        finally:
            mod._mcp_llm = original


class TestLocatorUnderstandingPrompt:
    def test_prompt_template_exists(self):
        assert "{accessibility_tree}" in LOCATOR_UNDERSTANDING_PROMPT
        assert "{operation_description}" in LOCATOR_UNDERSTANDING_PROMPT
