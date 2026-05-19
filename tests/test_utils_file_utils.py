import pytest
import os
import socket
import tempfile
from unittest.mock import patch, MagicMock

from app.utils.file_utils import (
    SUPPORTED_FILE_TYPES,
    ARCHIVE_EXTENSIONS,
    ARCHIVE_MIME_VARIANTS,
    DANGEROUS_MIMES,
    RESOURCE_TYPE_KEYWORDS,
    EXTENSION_RESOURCE_MAP,
    validate_file_format,
    detect_resource_type,
    validate_file_mime,
    validate_url,
    get_file_size,
    parse_file,
    parse_url,
)


class TestValidateFileFormat:
    def test_supported_docx(self):
        assert validate_file_format("test.docx") == "docx"

    def test_supported_pdf(self):
        assert validate_file_format("report.pdf") == "pdf"

    def test_supported_xlsx(self):
        assert validate_file_format("data.xlsx") == "xlsx"

    def test_supported_png(self):
        assert validate_file_format("image.png") == "png"

    def test_supported_zip(self):
        assert validate_file_format("archive.zip") == "zip"

    def test_unsupported_extension(self):
        assert validate_file_format("malware.exe") is None

    def test_no_extension(self):
        assert validate_file_format("noextension") is None

    def test_empty_string(self):
        assert validate_file_format("") is None

    def test_none_input(self):
        assert validate_file_format(None) is None

    def test_case_insensitive(self):
        assert validate_file_format("test.DOCX") == "docx"
        assert validate_file_format("photo.JPG") == "jpg"

    def test_multiple_dots(self):
        assert validate_file_format("my.test.file.xlsx") == "xlsx"

    def test_dot_only(self):
        assert validate_file_format(".gitignore") is None


class TestDetectResourceType:
    def test_requirement_by_filename_keyword(self):
        assert detect_resource_type("需求文档.docx", "docx") == "requirement"
        assert detect_resource_type("requirement_spec.pdf", "pdf") == "requirement"
        assert detect_resource_type("PRD_v2.docx", "docx") == "requirement"

    def test_ui_mockup_by_filename_keyword(self):
        assert detect_resource_type("UI设计稿.png", "png") == "ui_mockup"
        assert detect_resource_type("mockup_home.jpg", "jpg") == "ui_mockup"
        assert detect_resource_type("figma_export.png", "png") == "ui_mockup"

    def test_api_doc_by_filename_keyword(self):
        assert detect_resource_type("api接口文档.yaml", "yaml") == "api_doc"
        assert detect_resource_type("接口swagger.yaml", "yaml") == "api_doc"

    def test_test_data_by_filename_keyword(self):
        assert detect_resource_type("测试数据.xlsx", "xlsx") == "test_data"
        assert detect_resource_type("testdata.csv", "csv") == "test_data"

    def test_requirement_by_extension_mapping(self):
        assert detect_resource_type("randomname.docx", "docx") == "requirement"
        assert detect_resource_type("randomname.pdf", "pdf") == "requirement"

    def test_ui_mockup_by_extension_mapping(self):
        assert detect_resource_type("randomname.png", "png") == "ui_mockup"
        assert detect_resource_type("randomname.jpg", "jpg") == "ui_mockup"

    def test_api_doc_by_extension_mapping(self):
        assert detect_resource_type("randomname.yaml", "yaml") == "api_doc"
        assert detect_resource_type("randomname.json", "json") == "api_doc"

    def test_test_data_by_extension_mapping(self):
        assert detect_resource_type("randomname.xlsx", "xlsx") == "test_data"
        assert detect_resource_type("randomname.csv", "csv") == "test_data"

    def test_archive_extension_returns_other(self):
        assert detect_resource_type("archive.zip", "zip") == "other"
        assert detect_resource_type("archive.rar", "rar") == "other"

    def test_archive_no_keyword_returns_other(self):
        assert detect_resource_type("data.zip", "zip") == "other"

    def test_unknown_extension_returns_other(self):
        assert detect_resource_type("file.xyz", "xyz") == "other"

    def test_empty_filename(self):
        assert detect_resource_type("", "docx") == "requirement"


class TestValidateFileMime:
    def test_dangerous_mime_rejected(self):
        result = validate_file_mime("exe", "application/x-executable")
        assert result is not None
        assert "危险" in result

    def test_dangerous_shellscript_rejected(self):
        result = validate_file_mime("sh", "application/x-shellscript")
        assert result is not None

    def test_dangerous_javascript_rejected(self):
        result = validate_file_mime("js", "application/javascript")
        assert result is not None

    def test_dangerous_php_rejected(self):
        result = validate_file_mime("php", "text/x-php")
        assert result is not None

    def test_dangerous_bat_rejected(self):
        result = validate_file_mime("bat", "application/x-bat")
        assert result is not None

    def test_dangerous_msdownload_rejected(self):
        result = validate_file_mime("exe", "application/x-msdownload")
        assert result is not None

    def test_zip_valid_mime(self):
        result = validate_file_mime("zip", "application/zip")
        assert result is None

    def test_zip_variant_mime(self):
        result = validate_file_mime("zip", "application/x-zip-compressed")
        assert result is None

    def test_zip_invalid_mime(self):
        result = validate_file_mime("zip", "application/pdf")
        assert result is not None
        assert "MIME" in result

    def test_rar_valid_mime(self):
        result = validate_file_mime("rar", "application/vnd.rar")
        assert result is None

    def test_rar_variant_mime(self):
        result = validate_file_mime("rar", "application/x-rar-compressed")
        assert result is None

    def test_rar_invalid_mime(self):
        result = validate_file_mime("rar", "text/plain")
        assert result is not None

    def test_normal_file_matching_mime(self):
        result = validate_file_mime("pdf", "application/pdf")
        assert result is None

    def test_normal_file_mismatched_mime(self):
        result = validate_file_mime("pdf", "image/png")
        assert result is not None
        assert "MIME" in result

    def test_unknown_extension_no_expected_mime(self):
        result = validate_file_mime("xyz", "application/octet-stream")
        assert result is None

    def test_empty_detected_mime(self):
        result = validate_file_mime("pdf", "")
        assert result is not None
        assert "无法检测" in result


class TestValidateUrl:
    def test_invalid_scheme(self):
        assert validate_url("ftp://example.com") is False

    def test_no_hostname(self):
        assert validate_url("http://") is False

    def test_empty_string(self):
        assert validate_url("") is False

    def test_private_ip_rejected(self):
        assert validate_url("http://192.168.1.1") is False

    def test_loopback_rejected(self):
        assert validate_url("http://127.0.0.1") is False

    def test_unresolvable_hostname(self):
        assert validate_url("http://this-domain-definitely-does-not-exist-xyz123.com") is False

    def test_redirect_rejected(self):
        mock_response = MagicMock()
        mock_response.is_redirect = True
        mock_response.status_code = 302
        with patch("app.utils.file_utils.requests.get", return_value=mock_response):
            assert validate_url("http://example.com") is False

    def test_redirect_status_code_rejected(self):
        mock_response = MagicMock()
        mock_response.is_redirect = False
        mock_response.status_code = 301
        with patch("app.utils.file_utils.requests.get", return_value=mock_response):
            assert validate_url("http://example.com") is False

    def test_successful_request(self):
        mock_response = MagicMock()
        mock_response.is_redirect = False
        mock_response.status_code = 200
        with patch("app.utils.file_utils.requests.get", return_value=mock_response):
            with patch("app.utils.file_utils.socket.getaddrinfo", return_value=[(2, 1, 6, '', ('93.184.216.34', 0))]):
                with patch("app.utils.file_utils.ipaddress.ip_address") as mock_ip:
                    mock_ip.return_value.is_private = False
                    mock_ip.return_value.is_loopback = False
                    mock_ip.return_value.is_reserved = False
                    mock_ip.return_value.is_link_local = False
                    assert validate_url("http://example.com") is True

    def test_server_error_returns_false(self):
        mock_response = MagicMock()
        mock_response.is_redirect = False
        mock_response.status_code = 500
        with patch("app.utils.file_utils.requests.get", return_value=mock_response):
            with patch("app.utils.file_utils.socket.getaddrinfo", return_value=[(2, 1, 6, '', ('93.184.216.34', 0))]):
                with patch("app.utils.file_utils.ipaddress.ip_address") as mock_ip:
                    mock_ip.return_value.is_private = False
                    mock_ip.return_value.is_loopback = False
                    mock_ip.return_value.is_reserved = False
                    mock_ip.return_value.is_link_local = False
                    assert validate_url("http://example.com") is False

    def test_request_exception_returns_false(self):
        with patch("app.utils.file_utils.requests.get", side_effect=Exception("network error")):
            with patch("app.utils.file_utils.socket.getaddrinfo", return_value=[(2, 1, 6, '', ('93.184.216.34', 0))]):
                with patch("app.utils.file_utils.ipaddress.ip_address") as mock_ip:
                    mock_ip.return_value.is_private = False
                    mock_ip.return_value.is_loopback = False
                    mock_ip.return_value.is_reserved = False
                    mock_ip.return_value.is_link_local = False
                    assert validate_url("http://example.com") is False

    def test_dns_resolution_failure(self):
        with patch("app.utils.file_utils.socket.getaddrinfo", side_effect=socket.gaierror("DNS error")):
            assert validate_url("http://example.com") is False


class TestGetFileSize:
    def test_existing_file(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        size = get_file_size(str(test_file))
        assert size >= 0

    def test_nonexistent_file(self):
        size = get_file_size("/nonexistent/path/file.txt")
        assert size == 0

    def test_empty_file(self, tmp_path):
        test_file = tmp_path / "empty.txt"
        test_file.write_text("")
        size = get_file_size(str(test_file))
        assert size == 0


class TestParseFile:
    def test_parse_file_returns_dict(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        result = parse_file(str(test_file), "txt")
        assert result["file_type"] == "txt"
        assert result["file_path"] == str(test_file)
        assert "file_size" in result


class TestParseUrl:
    def test_parse_url_returns_dict(self):
        result = parse_url("http://example.com")
        assert result["url"] == "http://example.com"
        assert "is_accessible" in result


class TestConstants:
    def test_supported_file_types_not_empty(self):
        assert len(SUPPORTED_FILE_TYPES) > 0

    def test_archive_extensions(self):
        assert "zip" in ARCHIVE_EXTENSIONS
        assert "rar" in ARCHIVE_EXTENSIONS

    def test_archive_mime_variants(self):
        assert "zip" in ARCHIVE_MIME_VARIANTS
        assert "rar" in ARCHIVE_MIME_VARIANTS

    def test_dangerous_mimes_not_empty(self):
        assert len(DANGEROUS_MIMES) > 0

    def test_resource_type_keywords(self):
        assert "requirement" in RESOURCE_TYPE_KEYWORDS
        assert "ui_mockup" in RESOURCE_TYPE_KEYWORDS

    def test_extension_resource_map(self):
        assert EXTENSION_RESOURCE_MAP["docx"] == "requirement"
        assert EXTENSION_RESOURCE_MAP["png"] == "ui_mockup"
