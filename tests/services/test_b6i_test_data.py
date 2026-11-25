"""B6i 护栏：测试数据生成的 AI 请求、响应解析兜底与类型分派。"""

import re

import httpx
import pytest

from app.core.config import settings
from app.models.test_data import DataType
from app.services.test_data.generator_mixin import GeneratorMixin
from app.services.test_data.response_handler import parse_ai_response
from app.services.test_data_generator import DataConstraints, TestDataGenerator

FIELD_DEFINITIONS = [{"name": "name", "type": "string", "required": True}]


class FakePostResponse:
    def __init__(self, payload=None, status_error: Exception | None = None, json_error: Exception | None = None):
        self.payload = payload
        self.status_error = status_error
        self.json_error = json_error

    def raise_for_status(self) -> None:
        if self.status_error is not None:
            raise self.status_error

    def json(self):
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class FakeAsyncClient:
    def __init__(self, responses: list):
        self.responses = list(responses)
        self.posts: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc) -> bool:
        return False

    async def post(self, url, headers=None, json=None):
        self.posts.append({"url": url, "headers": headers, "json": json})
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def patch_httpx(monkeypatch, responses: list) -> FakeAsyncClient:
    client = FakeAsyncClient(responses)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: client)
    return client


def chat_payload(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


@pytest.fixture
def fast_sleep(monkeypatch):
    async def _noop(_seconds):
        return None

    monkeypatch.setattr("asyncio.sleep", _noop)


class TestGenerateTestData:
    @pytest.mark.asyncio
    async def test_success_returns_validated_list(self, monkeypatch):
        client = patch_httpx(monkeypatch, [FakePostResponse(chat_payload('[{"name": "张三"}]'))])
        generator = GeneratorMixin()

        result = await generator.generate_test_data(FIELD_DEFINITIONS, count=2, context="登录页")

        assert result == [{"name": "张三"}]
        posted = client.posts[0]
        assert posted["url"] == settings.DEEPSEEK_API_URL
        assert posted["json"]["model"] == settings.DEEPSEEK_MODEL
        assert posted["headers"]["Content-Type"] == "application/json"
        assert posted["headers"]["Authorization"].startswith("Bearer ")
        assert "登录页" in posted["json"]["messages"][0]["content"]

    @pytest.mark.asyncio
    async def test_dict_response_is_wrapped_in_list(self, monkeypatch):
        patch_httpx(monkeypatch, [FakePostResponse(chat_payload('{"name": "李四"}'))])

        result = await GeneratorMixin().generate_test_data(FIELD_DEFINITIONS)

        assert result == [{"name": "李四"}]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload,expected_message",
        [
            ({"data": []}, "缺少choices字段"),
            ({"choices": []}, "返回结果为空"),
            ({"choices": [{"message": {"content": ""}}]}, "AI响应内容为空"),
        ],
    )
    async def test_invalid_payload_raises(self, monkeypatch, payload, expected_message):
        patch_httpx(monkeypatch, [FakePostResponse(payload)])

        with pytest.raises(ValueError, match=expected_message):
            await GeneratorMixin().generate_test_data(FIELD_DEFINITIONS)

    @pytest.mark.asyncio
    async def test_unparsable_content_raises_without_retry(self, monkeypatch):
        client = patch_httpx(monkeypatch, [FakePostResponse(chat_payload("完全不是 JSON"))])

        with pytest.raises(ValueError, match="无法解析AI响应内容"):
            await GeneratorMixin().generate_test_data(FIELD_DEFINITIONS)
        assert len(client.posts) == 1

    @pytest.mark.asyncio
    async def test_validation_failure_raises(self, monkeypatch):
        patch_httpx(monkeypatch, [FakePostResponse(chat_payload('[{"other": 1}]'))])

        with pytest.raises(ValueError, match="必填字段"):
            await GeneratorMixin().generate_test_data(FIELD_DEFINITIONS)

    @pytest.mark.asyncio
    async def test_timeout_then_success(self, monkeypatch, fast_sleep):
        responses = [httpx.ReadTimeout("slow"), FakePostResponse(chat_payload('[{"name": "王五"}]'))]
        client = patch_httpx(monkeypatch, responses)

        result = await GeneratorMixin().generate_test_data(FIELD_DEFINITIONS)

        assert result == [{"name": "王五"}]
        assert len(client.posts) == 2

    @pytest.mark.asyncio
    async def test_timeout_exhausted_retries(self, monkeypatch, fast_sleep):
        client = patch_httpx(
            monkeypatch,
            [httpx.ReadTimeout("1"), httpx.ReadTimeout("2"), httpx.ReadTimeout("3")],
        )

        with pytest.raises(ValueError, match="AI生成失败: .*超时"):
            await GeneratorMixin().generate_test_data(FIELD_DEFINITIONS)
        assert len(client.posts) == 3

    @pytest.mark.asyncio
    async def test_http_status_exhausted_retries(self, monkeypatch, fast_sleep):
        error = httpx.HTTPStatusError("500", request=httpx.Request("POST", "http://test"), response=httpx.Response(500))
        client = patch_httpx(
            monkeypatch,
            [
                FakePostResponse(status_error=error),
                FakePostResponse(status_error=error),
                FakePostResponse(status_error=error),
            ],
        )

        with pytest.raises(ValueError, match="HTTP错误: 500"):
            await GeneratorMixin().generate_test_data(FIELD_DEFINITIONS)
        assert len(client.posts) == 3


class TestParseAiResponseFallback:
    def test_object_with_trailing_comma(self):
        assert parse_ai_response('结论: {"a": 1,} 完') == {"a": 1}

    def test_array_with_trailing_comma(self):
        assert parse_ai_response('[{"a": 1,}]') == [{"a": 1}]

    def test_array_block_invalid_falls_back_to_object(self):
        assert parse_ai_response('坏 [x] 好 {"a": 1}') == {"a": 1}

    def test_invalid_bracket_block_raises(self):
        with pytest.raises(ValueError, match="无法解析AI响应内容"):
            parse_ai_response("prefix [broken] suffix")

    def test_fixer_repairs_missing_value(self):
        assert parse_ai_response('text {"a": } end') == {"a": " "}

    def test_fixer_returning_invalid_json_is_skipped(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.test_data.response_handler._JSON_FIXERS",
            ((lambda _raw: "{"),),
        )

        assert parse_ai_response('前缀 {"a": 1} 后缀') == {"a": 1}


class TestGenerateTestDataBatch:
    @pytest.mark.asyncio
    async def test_failed_type_falls_back_to_empty_list(self):
        class _BatchGenerator(GeneratorMixin):
            async def generate_test_data(self, field_definitions, count=1, context=None, data_type="normal"):
                if data_type == "invalid":
                    raise ValueError("生成失败")
                return [{"name": data_type}]

        result = await _BatchGenerator().generate_test_data_batch(FIELD_DEFINITIONS, {"normal": 1, "invalid": 1})

        assert result == {"normal": [{"name": "normal"}], "invalid": []}


class TestGenerateRandomDispatch:
    def _generate(self, field_type, field_name="field", constraints=None) -> str:
        return TestDataGenerator(seed=7)._generate_random(field_type, field_name, constraints or DataConstraints())

    def test_text(self):
        assert self._generate(DataType.TEXT)

    def test_number_in_default_range(self):
        assert 0 <= int(self._generate(DataType.NUMBER)) <= 100

    def test_date_format(self):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", self._generate(DataType.DATE))

    def test_datetime_format(self):
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", self._generate(DataType.DATETIME))

    def test_email_format(self):
        assert re.fullmatch(r"[a-z0-9]{8}@[^@]+", self._generate(DataType.EMAIL))

    def test_phone_is_eleven_digits(self):
        assert re.fullmatch(r"\d{11}", self._generate(DataType.PHONE))

    def test_enum_uses_allowed_values(self):
        constraints = DataConstraints(enum_values=["red", "green"])

        assert self._generate(DataType.ENUM, constraints=constraints) in {"red", "green"}

    def test_enum_without_values_returns_empty(self):
        assert self._generate(DataType.ENUM) == ""

    def test_boolean(self):
        assert self._generate(DataType.BOOLEAN) in {"true", "false"}

    def test_url(self):
        assert self._generate(DataType.URL).startswith("https://example.com/")

    def test_id_card_is_eighteen_digits(self):
        assert re.fullmatch(r"\d{18}", self._generate(DataType.ID_CARD))

    def test_bank_card_length(self):
        assert 16 <= len(self._generate(DataType.BANK_CARD)) <= 19

    def test_unknown_type_returns_empty(self):
        assert self._generate("unsupported") == ""

    def test_plain_string_type_is_recognized(self):
        assert self._generate(DataType.TEXT.value, field_name="address")
