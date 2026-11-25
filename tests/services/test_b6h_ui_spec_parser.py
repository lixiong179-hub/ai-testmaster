"""B6h 护栏：UI 规格解析的多屏流转、JSON 兜底提取与文本结构化。"""

from types import SimpleNamespace

import pytest

from app.services.ui_spec_parser.core_mixin import UISpecCoreMixin
from app.services.ui_spec_parser.flow_mixin import UISpecFlowMixin
from app.services.ui_spec_parser.ocr_mixin import UISpecOcrMixin


class FakeVisionModel:
    """按顺序返回文本响应；元素为异常时抛出。"""

    def __init__(self, responses: list):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def analyze_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeCompletions:
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=item))])


def make_text_model(responses: list) -> tuple[SimpleNamespace, FakeCompletions]:
    completions = FakeCompletions(responses)
    model = SimpleNamespace(model_name="deepseek-chat", chat=SimpleNamespace(completions=completions))
    return model, completions


class FakeParser(UISpecFlowMixin, UISpecOcrMixin, UISpecCoreMixin):
    def __init__(self, max_retries: int = 1):
        self.parse_mode = "text"
        self.max_retries = max_retries
        self.retry_delay = 0
        self.vision_model = None
        self._ocr_extractor = None
        self._text_model = None


SCREENS = [
    {
        "screen_id": "s1",
        "screen_name": "登录",
        "purpose": "用户登录",
        "elements": [
            {"interactive": True, "type": "button", "label": "登录"},
            {"interactive": True, "type": "link", "semantic": "忘记密码"},
            {"interactive": False, "type": "button", "label": "非交互文本"},
            {"interactive": True, "type": "text", "label": "纯文本"},
            {"interactive": True, "type": "icon", "label": ""},
        ],
        "navigation": {"back_button": {"visible": True}, "tab_bar": {"visible": True, "items": ["首页", "我的"]}},
        "flows": {"expected_next_screens": ["首页"], "trigger_actions": ["点击登录"]},
    },
    {"screen_id": "s2", "screen_name": "首页", "elements": []},
]


class TestParseMultipleScreenFlows:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("screens", [[], [{"screen_id": "s1"}]])
    async def test_less_than_two_screens_returns_none(self, screens):
        parser = FakeParser()

        assert await parser.parse_multiple_screen_flows(screens) is None

    @pytest.mark.asyncio
    async def test_prompt_contains_screen_facts(self):
        vision = FakeVisionModel(['{"entry_screen": "登录", "flows": []}'])
        parser = FakeParser()
        parser.vision_model = vision

        result = await parser.parse_multiple_screen_flows(SCREENS)

        assert result == {"entry_screen": "登录", "flows": []}
        prompt = vision.prompts[0]
        assert "共2张" in prompt
        assert "【屏幕1】登录" in prompt
        assert "目的: 用户登录" in prompt
        assert "可点击元素: 登录, 忘记密码" in prompt
        assert "非交互文本" not in prompt
        assert "纯文本" not in prompt
        assert "存在返回按钮" in prompt
        assert "Tab栏: 首页, 我的" in prompt
        assert "预期跳转: 首页" in prompt
        assert "触发动作: 点击登录" in prompt
        assert "【屏幕2】首页" in prompt

    @pytest.mark.asyncio
    async def test_interactive_elements_truncated_to_ten(self):
        elements = [{"interactive": True, "type": "button", "label": f"按钮{i}"} for i in range(12)]
        screens = [
            {"screen_name": "A", "elements": elements},
            {"screen_name": "B", "elements": []},
        ]
        vision = FakeVisionModel(['{"entry_screen": "A"}'])
        parser = FakeParser()
        parser.vision_model = vision

        await parser.parse_multiple_screen_flows(screens)

        prompt = vision.prompts[0]
        assert "按钮9" in prompt
        assert "按钮10" not in prompt
        assert "按钮11" not in prompt

    @pytest.mark.asyncio
    async def test_invalid_then_valid_retries(self):
        vision = FakeVisionModel(["不是 JSON", '{"entry_screen": "登录"}'])
        parser = FakeParser(max_retries=2)
        parser.vision_model = vision

        result = await parser.parse_multiple_screen_flows(SCREENS)

        assert result == {"entry_screen": "登录"}
        assert len(vision.prompts) == 2

    @pytest.mark.asyncio
    async def test_exhausted_retries_returns_none(self):
        vision = FakeVisionModel(["不是 JSON", "还不是 JSON"])
        parser = FakeParser(max_retries=2)
        parser.vision_model = vision

        assert await parser.parse_multiple_screen_flows(SCREENS) is None
        assert len(vision.prompts) == 2

    @pytest.mark.asyncio
    async def test_exception_then_success(self):
        vision = FakeVisionModel([RuntimeError("模型挂了"), '{"entry_screen": "登录"}'])
        parser = FakeParser(max_retries=2)
        parser.vision_model = vision

        assert await parser.parse_multiple_screen_flows(SCREENS) == {"entry_screen": "登录"}

    @pytest.mark.asyncio
    async def test_all_attempts_raise_returns_none(self):
        vision = FakeVisionModel([RuntimeError("1"), RuntimeError("2")])
        parser = FakeParser(max_retries=2)
        parser.vision_model = vision

        assert await parser.parse_multiple_screen_flows(SCREENS) is None


class TestParseJsonResponseFallback:
    def setup_method(self):
        self.parser = FakeParser()

    def test_balanced_braces_fallback_with_trailing_comma(self):
        content = '结果: {"foo": {"bar": 1}, "baz": [1, 2,]} 完成'

        assert self.parser._parse_json_response(content) == {"foo": {"bar": 1}, "baz": [1, 2]}

    def test_brace_inside_string_is_ignored(self):
        content = '结果: {"foo": "a\\"b}c", "n": 1} 完'

        assert self.parser._parse_json_response(content) == {"foo": 'a"b}c', "n": 1}

    def test_unbalanced_braces_returns_none(self):
        assert self.parser._parse_json_response('前缀 {"foo": {"bar": 1} 后缀') is None

    def test_unknown_object_without_keywords_uses_fallback(self):
        content = '输出：{"alpha": {"beta": 1}} 结束'

        assert self.parser._parse_json_response(content) == {"alpha": {"beta": 1}}


class TestStructureTextWithLlm:
    def test_success_passes_ocr_text_and_hint(self):
        model, completions = make_text_model(['{"screen_name": "登录"}'])
        parser = FakeParser()
        parser._get_text_model = lambda: model

        result = parser._structure_text_with_llm("[位置:10] 账号\n[位置:20] 密码", "登录页")

        assert result == {"screen_name": "登录"}
        content = completions.calls[0]["messages"][0]["content"]
        assert content.startswith("[提示：这是登录页]")
        assert "[位置:10] 账号" in content
        assert completions.calls[0]["model"] == "deepseek-chat"
        assert completions.calls[0]["timeout"] == 60.0

    def test_invalid_then_valid_retries(self):
        model, completions = make_text_model(["不是 JSON", '{"screen_name": "登录"}'])
        parser = FakeParser(max_retries=2)
        parser._get_text_model = lambda: model

        assert parser._structure_text_with_llm("文字") == {"screen_name": "登录"}
        assert len(completions.calls) == 2

    def test_exhausted_returns_none(self):
        model, completions = make_text_model(["不是 JSON", "还不是 JSON"])
        parser = FakeParser(max_retries=2)
        parser._get_text_model = lambda: model

        assert parser._structure_text_with_llm("文字") is None
        assert len(completions.calls) == 2

    @pytest.mark.parametrize(
        "message",
        ["401 Unauthorized", "429 Too Many Requests", "request timeout", "connection reset", "未知错误"],
    )
    def test_exception_branches_return_none(self, message):
        model, _ = make_text_model([RuntimeError(message)])
        parser = FakeParser()
        parser._get_text_model = lambda: model

        assert parser._structure_text_with_llm("文字") is None

    def test_exception_then_success(self):
        model, completions = make_text_model([RuntimeError("429 rate limit"), '{"screen_name": "登录"}'])
        parser = FakeParser(max_retries=2)
        parser._get_text_model = lambda: model

        assert parser._structure_text_with_llm("文字") == {"screen_name": "登录"}
        assert len(completions.calls) == 2

    def test_get_text_model_is_cached(self, monkeypatch):
        calls = []

        def _fake_client(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(name="text-model")

        monkeypatch.setattr("app.utils.ai_client_core.get_ai_client", _fake_client)
        parser = FakeParser()

        first = parser._get_text_model()
        second = parser._get_text_model()

        assert first is second
        assert len(calls) == 1
        assert set(calls[0]) == {"api_key", "base_url", "model_name"}
