import pytest
from app.services.file_content_extractor import (
    FileContentExtractor,
    get_file_content,
    has_extracted_content,
    TEXT_EXTENSIONS,
    DOCX_EXTENSIONS,
    PDF_EXTENSIONS,
    EXCEL_EXTENSIONS,
    IMAGE_EXTENSIONS,
)


class TestExtensionSets:
    def test_text_extensions(self):
        assert "txt" in TEXT_EXTENSIONS
        assert "md" in TEXT_EXTENSIONS
        assert "json" in TEXT_EXTENSIONS

    def test_docx_extensions(self):
        assert "docx" in DOCX_EXTENSIONS

    def test_pdf_extensions(self):
        assert "pdf" in PDF_EXTENSIONS

    def test_excel_extensions(self):
        assert "xlsx" in EXCEL_EXTENSIONS
        assert "xls" in EXCEL_EXTENSIONS

    def test_image_extensions(self):
        assert "png" in IMAGE_EXTENSIONS
        assert "jpg" in IMAGE_EXTENSIONS


class TestGetFileContent:
    def test_with_content(self):
        class FakeFile:
            content = "hello"
            extract_status = "completed"
        assert get_file_content(FakeFile()) == "hello"

    def test_no_content(self):
        class FakeFile:
            content = None
            extract_status = "pending"
        assert get_file_content(FakeFile()) is None

    def test_not_completed(self):
        class FakeFile:
            content = "hello"
            extract_status = "processing"
        assert get_file_content(FakeFile()) is None


class TestHasExtractedContent:
    def test_has_content(self):
        class FakeFile:
            content = "hello"
            extract_status = "completed"
        assert has_extracted_content(FakeFile()) is True

    def test_no_content(self):
        class FakeFile:
            content = None
            extract_status = "completed"
        assert has_extracted_content(FakeFile()) is False

    def test_not_completed(self):
        class FakeFile:
            content = "hello"
            extract_status = "pending"
        assert has_extracted_content(FakeFile()) is False


class TestFileContentExtractor:
    @pytest.mark.asyncio
    async def test_extract_cached_content(self, db, testProject):
        from app.crud.file import create_project_file, update_file_content
        f = create_project_file(db, testProject.id, "cached.txt", "txt", "/tmp/cached.txt")
        update_file_content(db, f.id, "cached content", "completed")
        db.refresh(f)
        extractor = FileContentExtractor(db)
        result = await extractor.extract_file_content(f)
        assert result["success"] is True
        assert result["from_cache"] is True

    @pytest.mark.asyncio
    async def test_extract_image_file(self, db, testProject):
        from app.crud.file import create_project_file
        f = create_project_file(db, testProject.id, "test.png", "png", "/tmp/test.png")
        extractor = FileContentExtractor(db)
        result = await extractor._extract_image(f)
        assert "图片文件" in result

    @pytest.mark.asyncio
    async def test_extract_archive_nonexistent(self, db, testProject):
        from app.crud.file import create_project_file
        f = create_project_file(db, testProject.id, "test.zip", "zip", "/nonexistent/path.zip")
        extractor = FileContentExtractor(db)
        result = await extractor._extract_archive(f)
        assert result is None
