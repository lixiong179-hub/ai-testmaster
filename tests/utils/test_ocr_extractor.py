import pytest
from unittest.mock import patch, MagicMock
from app.utils.ocr_extractor import OCRExtractor, OCRExtractorError, create_ocr_extractor, _ocr_available


class TestOCRExtractorInit:
    def test_init_ocr_not_none(self):
        extractor = OCRExtractor()
        extractor._ocr = MagicMock()
        extractor._init_ocr()
        assert extractor._ocr is not None

    def test_init_ocr_not_available(self):
        extractor = OCRExtractor()
        with patch("app.utils.ocr_extractor._ocr_available", False):
            with pytest.raises(OCRExtractorError, match="RapidOCR未安装"):
                extractor._init_ocr()

    def test_init_ocr_available(self):
        extractor = OCRExtractor()
        mock_rapid = MagicMock()
        with patch("app.utils.ocr_extractor._ocr_available", True), \
             patch("app.utils.ocr_extractor.RapidOCR", return_value=mock_rapid, create=True):
            extractor._init_ocr()
            assert extractor._ocr is not None


class TestOCRExtractorRunOcr:
    def test_run_ocr_invalid_image(self):
        extractor = OCRExtractor()
        extractor._ocr = MagicMock()
        with patch("app.utils.ocr_extractor._ocr_available", True):
            extractor._init_ocr()
        with patch("cv2.imdecode", return_value=None):
            with pytest.raises(OCRExtractorError, match="图片解码失败"):
                extractor._run_ocr(b"invalid_image_data")

    def test_run_ocr_success(self):
        extractor = OCRExtractor()
        mock_result = [
            [[[0, 0], [100, 0], [100, 30], [0, 30]], "hello", 0.95],
        ]
        mock_ocr = MagicMock(return_value=(mock_result, 0.1))
        extractor._ocr = mock_ocr
        with patch("cv2.imdecode") as mock_decode, \
             patch("numpy.frombuffer") as mock_frombuf:
            import numpy as np
            fake_img = np.zeros((100, 100, 3), dtype=np.uint8)
            mock_decode.return_value = fake_img
            result = extractor._run_ocr(b"fake_image")
            assert len(result) == 1

    def test_run_ocr_empty_result(self):
        extractor = OCRExtractor()
        mock_ocr = MagicMock(return_value=(None, 0.1))
        extractor._ocr = mock_ocr
        import numpy as np
        fake_img = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch("cv2.imdecode", return_value=fake_img):
            result = extractor._run_ocr(b"fake_image")
            assert result == []


class TestOCRExtractorExtractText:
    def test_extract_text_success(self):
        extractor = OCRExtractor()
        mock_result = [
            [[[0, 0], [100, 0], [100, 30], [0, 30]], "hello", 0.95],
            [[[0, 40], [100, 40], [100, 70], [0, 70]], "world", 0.90],
        ]
        with patch.object(extractor, "_run_ocr", return_value=mock_result):
            text = extractor.extract_text(b"fake_image")
            assert "hello" in text
            assert "world" in text

    def test_extract_text_empty_result(self):
        extractor = OCRExtractor()
        with patch.object(extractor, "_run_ocr", return_value=[]):
            text = extractor.extract_text(b"fake_image")
            assert text == ""

    def test_extract_text_ocr_error(self):
        extractor = OCRExtractor()
        with patch.object(extractor, "_run_ocr", side_effect=OCRExtractorError("RapidOCR未安装")):
            with pytest.raises(OCRExtractorError):
                extractor.extract_text(b"fake_image")

    def test_extract_text_general_exception(self):
        extractor = OCRExtractor()
        with patch.object(extractor, "_run_ocr", side_effect=RuntimeError("unexpected")):
            text = extractor.extract_text(b"fake_image")
            assert text == ""


class TestOCRExtractorExtractTextWithPosition:
    def test_extract_text_with_position_success(self):
        extractor = OCRExtractor()
        mock_result = [
            [[[10, 20], [100, 20], [100, 50], [10, 50]], "hello", 0.95],
        ]
        with patch.object(extractor, "_run_ocr", return_value=mock_result):
            items = extractor.extract_text_with_position(b"fake_image")
            assert len(items) == 1
            assert items[0]["text"] == "hello"
            assert items[0]["x"] == 10
            assert items[0]["y"] == 20
            assert items[0]["confidence"] == 0.95

    def test_extract_text_with_position_empty(self):
        extractor = OCRExtractor()
        with patch.object(extractor, "_run_ocr", return_value=[]):
            items = extractor.extract_text_with_position(b"fake_image")
            assert items == []

    def test_extract_text_with_position_ocr_error(self):
        extractor = OCRExtractor()
        with patch.object(extractor, "_run_ocr", side_effect=OCRExtractorError("RapidOCR未安装")):
            with pytest.raises(OCRExtractorError):
                extractor.extract_text_with_position(b"fake_image")

    def test_extract_text_with_position_general_exception(self):
        extractor = OCRExtractor()
        with patch.object(extractor, "_run_ocr", side_effect=RuntimeError("unexpected")):
            items = extractor.extract_text_with_position(b"fake_image")
            assert items == []


class TestCreateOcrExtractor:
    def test_create_ocr_extractor(self):
        extractor = create_ocr_extractor()
        assert isinstance(extractor, OCRExtractor)
