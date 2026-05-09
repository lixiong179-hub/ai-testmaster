"""文件工具单元测试 - file_utils"""
import os
import tempfile
import time
import threading
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler

from app.utils.file_utils import (
    validate_file_format, detect_resource_type, validate_file_mime,
    get_file_size, ensure_dir, clean_old_files, parse_file, parse_url,
    validate_url, SUPPORTED_FILE_TYPES, DANGEROUS_MIMES,
)


class TestValidateFileFormat:
    def test_valid_formats(self):
        for ext in ["docx", "pdf", "png", "xlsx", "yaml", "json", "zip"]:
            result = validate_file_format(f"test.{ext}")
            assert result == ext

    def test_invalid_format(self):
        assert validate_file_format("test.exe") is None

    def test_no_extension(self):
        assert validate_file_format("noext") is None

    def test_empty_string(self):
        assert validate_file_format("") is None

    def test_none_input(self):
        assert validate_file_format(None) is None

    def test_case_insensitive(self):
        assert validate_file_format("test.PDF") == "pdf"


class TestDetectResourceType:
    def test_keyword_requirement(self):
        assert detect_resource_type("需求文�?docx", "docx") == "requirement"

    def test_keyword_ui(self):
        assert detect_resource_type("UI设计.png", "png") == "ui_mockup"

    def test_keyword_api(self):
        assert detect_resource_type("api接口.yaml", "yaml") == "api_doc"

    def test_keyword_test_data(self):
        assert detect_resource_type("测试数据.xlsx", "xlsx") == "test_data"

    def test_extension_fallback(self):
        assert detect_resource_type("random.docx", "docx") == "requirement"

    def test_archive_no_keyword(self):
        assert detect_resource_type("archive.zip", "zip") == "other"

    def test_unknown_extension(self):
        assert detect_resource_type("file.xyz", "xyz") == "other"


class TestValidateFileMime:
    def test_dangerous_mime(self):
        for mime in DANGEROUS_MIMES:
            result = validate_file_mime("exe", mime)
            assert result is not None
            assert "危险" in result

    def test_matching_mime(self):
        result = validate_file_mime("pdf", "application/pdf")
        assert result is None

    def test_zip_mime_variants(self):
        for mime in ["application/zip", "application/x-zip-compressed"]:
            result = validate_file_mime("zip", mime)
            assert result is None

    def test_zip_invalid_mime(self):
        result = validate_file_mime("zip", "application/pdf")
        assert result is not None
        assert "压缩�? in result

    def test_mismatched_mime(self):
        result = validate_file_mime("pdf", "image/png")
        assert result is not None
        assert "不匹�? in result

    def test_unknown_extension_valid(self):
        result = validate_file_mime("xyz", "application/octet-stream")
        assert result is None


class TestGetFileSize:
    def test_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"x" * 2048)
            path = f.name
        try:
            size = get_file_size(path)
            assert size == 2
        finally:
            os.unlink(path)

    def test_nonexistent_file(self):
        assert get_file_size("/nonexistent/file.txt") == 0


class TestEnsureDir:
    def test_creates_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "subdir", "nested")
            ensure_dir(path)
            assert os.path.isdir(path)

    def test_existing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            ensure_dir(tmp)
            assert os.path.isdir(tmp)


class TestCleanOldFiles:
    def test_removes_old_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_file = os.path.join(tmp, "old.txt")
            with open(old_file, "w") as f:
                f.write("old")
            old_time = time.time() - 2 * 24 * 60 * 60
            os.utime(old_file, (old_time, old_time))
            removed = clean_old_files(tmp, max_age_seconds=24 * 60 * 60)
            assert removed == 1
            assert not os.path.exists(old_file)

    def test_keeps_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            new_file = os.path.join(tmp, "new.txt")
            with open(new_file, "w") as f:
                f.write("new")
            removed = clean_old_files(tmp, max_age_seconds=24 * 60 * 60)
            assert removed == 0
            assert os.path.exists(new_file)

    def test_nonexistent_dir(self):
        assert clean_old_files("/nonexistent/dir") == 0


class TestParseFile:
    def test_parse_existing_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"hello")
            path = f.name
        try:
            result = parse_file(path, "txt")
            assert result["file_path"] == path
            assert result["file_type"] == "txt"
            assert result["file_size"] >= 0
        finally:
            os.unlink(path)


class TestParseUrl:
    def test_parse_invalid_url(self):
        result = parse_url("not-a-valid-url")
        assert result["url"] == "not-a-valid-url"
        assert result["is_accessible"] is False


class _OKHandler(BaseHTTPRequestHandler):
    """返回 200 的本�?HTTP 处理器�?""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.end_headers()
        self.wfile.write(b"%PDF-1.4 test content")

    def log_message(self, format, *args):
        pass


class _RedirectHandler(BaseHTTPRequestHandler):
    """返回 302 重定向的本地 HTTP 处理器�?""

    def do_GET(self):
        self.send_response(302)
        self.send_header("Location", "/redirected")
        self.end_headers()

    def log_message(self, format, *args):
        pass


class TestValidateUrl:
    def test_ftp_scheme_rejected(self):
        assert validate_url("ftp://evil.com/file") is False

    def test_javascript_scheme_rejected(self):
        assert validate_url("javascript:alert(1)") is False

    def test_no_hostname_rejected(self):
        assert validate_url("http:///path") is False

    def test_private_ip_rejected(self):
        assert validate_url("http://192.168.1.1/secret") is False

    def test_loopback_rejected(self):
        assert validate_url("http://127.0.0.1/secret") is False

    def test_valid_local_http_server(self):
        server = HTTPServer(("127.0.0.1", 0), _OKHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        result = validate_url(f"http://127.0.0.1:{port}/file.pdf")
        server.server_close()
        assert result is False

    def test_redirect_rejected(self):
        server = HTTPServer(("127.0.0.1", 0), _RedirectHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        result = validate_url(f"http://127.0.0.1:{port}/redirect")
        server.server_close()
        assert result is False
