import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.services.ui_spec_parser.core_mixin import UISpecCoreMixin


class _ConcreteParser(UISpecCoreMixin):
    def __init__(self):
        self.parse_mode = "text"
        self._ocr_extractor = None
        self.vision_model = None
        self.max_retries = 1
        self.retry_delay = 0

    def _extract_positioned_text(self, image_bytes: bytes):
        return None

    def _extract_text_with_ocr(self, image_bytes: bytes):
        return ""

    def _structure_text_with_llm(self, ocr_text: str, screen_name_hint=None):
        return None


class TestEncodeImageToBase64:
    def test_encode_success(self, tmp_path):
        parser = _ConcreteParser()
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024)
        result = parser._encode_image_to_base64(str(img_path))
        assert result is not None

    def test_encode_nonexistent_file(self):
        parser = _ConcreteParser()
        result = parser._encode_image_to_base64("/nonexistent/file.png")
        assert result is None


class TestReadImageBytes:
    def test_path_traversal_blocked(self):
        parser = _ConcreteParser()
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = "/safe/uploads"
            mock_settings.UI_PROTOTYPE_UPLOAD_DIR = "/safe/ui"
            result = parser._read_image_bytes("/etc/passwd")
            assert result is None

    def test_file_too_small(self, tmp_path):
        parser = _ConcreteParser()
        small_file = tmp_path / "small.png"
        small_file.write_bytes(b"\x89PNG" + b"\x00" * 100)
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.UPLOAD_DIR = str(tmp_path)
            mock_settings.UI_PROTOTYPE_UPLOAD_DIR = str(tmp_path)
            result = parser._read_image_bytes(str(small_file))
            assert result is None


class TestParseJsonResponse:
    def test_valid_json(self):
        parser = _ConcreteParser()
        result = parser._parse_json_response('{"screen_name": "Login"}')
        assert result == {"screen_name": "Login"}

    def test_json_in_markdown_block(self):
        parser = _ConcreteParser()
        content = '```json\n{"screen_name": "Login"}\n```'
        result = parser._parse_json_response(content)
        assert result == {"screen_name": "Login"}

    def test_json_in_plain_code_block(self):
        parser = _ConcreteParser()
        content = '```\n{"screen_name": "Login"}\n```'
        result = parser._parse_json_response(content)
        assert result == {"screen_name": "Login"}

    def test_json_with_trailing_comma(self):
        parser = _ConcreteParser()
        content = '{"screen_name": "Login", "elements": [1, 2,]}'
        result = parser._parse_json_response(content)
        assert result is not None

    def test_json_with_screen_name_pattern(self):
        parser = _ConcreteParser()
        content = 'Here is the result: {"screen_name": "Home", "elements": []}'
        result = parser._parse_json_response(content)
        assert result is not None

    def test_json_with_entry_screen_pattern(self):
        parser = _ConcreteParser()
        content = 'Result: {"entry_screen": "Main", "flows": []}'
        result = parser._parse_json_response(content)
        assert result is not None

    def test_json_with_purpose_pattern(self):
        parser = _ConcreteParser()
        content = 'Result: {"purpose": "Login page", "elements": []}'
        result = parser._parse_json_response(content)
        assert result is not None

    def test_json_array_pattern(self):
        parser = _ConcreteParser()
        content = 'Result: [{"name": "A"}, {"name": "B"}]'
        result = parser._parse_json_response(content)
        assert result is not None

    def test_invalid_json(self):
        parser = _ConcreteParser()
        result = parser._parse_json_response("not json at all")
        assert result is None

    def test_empty_string(self):
        parser = _ConcreteParser()
        result = parser._parse_json_response("")
        assert result is None


class TestParseSingleScreen:
    @pytest.mark.asyncio
    async def test_image_read_failure(self):
        parser = _ConcreteParser()
        with patch.object(parser, "_read_image_bytes", return_value=None):
            success, data, error = await parser.parse_single_screen("/fake/path.png")
            assert success is False
            assert "图片读取失败" in error

    @pytest.mark.asyncio
    async def test_text_mode_success(self):
        parser = _ConcreteParser()
        parser.parse_mode = "text"
        with patch.object(parser, "_read_image_bytes", return_value=b"fake_image_data"), \
             patch.object(parser, "_parse_with_text_mode", return_value=(True, {"screen_name": "Login"}, "")):
            success, data, error = await parser.parse_single_screen("/fake/path.png")
            assert success is True
            assert data["screen_name"] == "Login"

    @pytest.mark.asyncio
    async def test_vision_mode_success(self):
        parser = _ConcreteParser()
        parser.parse_mode = "vision"
        with patch.object(parser, "_read_image_bytes", return_value=b"fake_image_data"), \
             patch.object(parser, "_parse_with_vision_mode", return_value=(True, {"screen_name": "Home"}, "")):
            success, data, error = await parser.parse_single_screen("/fake/path.png")
            assert success is True

    @pytest.mark.asyncio
    async def test_with_screen_name_hint(self):
        parser = _ConcreteParser()
        parser.parse_mode = "text"
        with patch.object(parser, "_read_image_bytes", return_value=b"fake_image_data"), \
             patch.object(parser, "_parse_with_text_mode", return_value=(True, {}, "")) as mock:
            await parser.parse_single_screen("/fake/path.png", screen_name_hint="登录页")
            mock.assert_called_once()


class TestParseWithTextMode:
    @pytest.mark.asyncio
    async def test_positioned_text_success(self):
        parser = _ConcreteParser()
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = [
                "positioned text result",
                {"screen_name": "Login"},
            ]
            success, data, error = await parser._parse_with_text_mode(b"image_data")
            assert success is True

    @pytest.mark.asyncio
    async def test_fallback_to_plain_ocr(self):
        parser = _ConcreteParser()
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = [
                None,
                "plain text result",
                {"screen_name": "Home"},
            ]
            success, data, error = await parser._parse_with_text_mode(b"image_data")
            assert success is True

    @pytest.mark.asyncio
    async def test_ocr_empty(self):
        parser = _ConcreteParser()
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = [None, ""]
            success, data, error = await parser._parse_with_text_mode(b"image_data")
            assert success is False
            assert "OCR" in error

    @pytest.mark.asyncio
    async def test_structure_failure(self):
        parser = _ConcreteParser()
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.side_effect = [
                "positioned text",
                None,
            ]
            success, data, error = await parser._parse_with_text_mode(b"image_data")
            assert success is False
            assert "结构化" in error


class TestParseWithVisionMode:
    @pytest.mark.asyncio
    async def test_vision_success(self):
        parser = _ConcreteParser()
        parser.vision_model = MagicMock()
        parser.vision_model.analyze_image = MagicMock(return_value='{"screen_name": "Home"}')
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value='{"screen_name": "Home"}'):
            success, data, error = await parser._parse_with_vision_mode(b"image_data")
            assert success is True

    @pytest.mark.asyncio
    async def test_vision_parse_failure(self):
        parser = _ConcreteParser()
        parser.max_retries = 1
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value="invalid json"):
            success, data, error = await parser._parse_with_vision_mode(b"image_data")
            assert success is False

    @pytest.mark.asyncio
    async def test_vision_exception(self):
        parser = _ConcreteParser()
        parser.max_retries = 1
        with patch("asyncio.to_thread", new_callable=AsyncMock, side_effect=Exception("model error")):
            success, data, error = await parser._parse_with_vision_mode(b"image_data")
            assert success is False
            assert "异常" in error

    @pytest.mark.asyncio
    async def test_vision_with_screen_hint(self):
        parser = _ConcreteParser()
        parser.vision_model = MagicMock()
        parser.max_retries = 1
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value='{"screen_name": "Home"}'):
            success, data, error = await parser._parse_with_vision_mode(b"image_data", screen_name_hint="首页")
            assert success is True
