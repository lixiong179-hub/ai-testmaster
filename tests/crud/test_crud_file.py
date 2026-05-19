"""文件CRUD操作单元测试"""
import pytest
from app.crud.file import (
    create_project_file,
    update_file_content,
    update_file_resource_type,
    get_project_files,
    get_project_files_by_type,
    get_file_by_id,
    delete_file,
    permanent_delete_file,
    get_project_files_by_iteration,
)
from app.models.project import Project, ProjectFile


@pytest.fixture
def test_project(db, testUser):
    project = Project(
        name="file_test_project",
        user_id=testUser.id,
        description="project for file crud tests",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    yield project
    try:
        db.query(ProjectFile).filter(ProjectFile.project_id == project.id).delete()
        db.query(Project).filter(Project.id == project.id).delete()
        db.flush()
    except Exception:
        db.rollback()


class TestCreateProjectFile:
    def test_create_basic(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "test.pdf", "pdf", "/uploads/test.pdf"
        )
        assert f.id is not None
        assert f.project_id == test_project.id
        assert f.file_name == "test.pdf"
        assert f.file_type == "pdf"
        assert f.file_url == "/uploads/test.pdf"
        assert f.extract_status == "pending"
        assert f.is_active is True

    def test_create_with_optional_fields(self, db, test_project):
        f = create_project_file(
            db,
            test_project.id,
            "req.docx",
            "docx",
            "/uploads/req.docx",
            file_source="url",
            size=1024,
            resource_type="requirement",
            description="需求文档",
        )
        assert f.file_source == "url"
        assert f.size == 1024
        assert f.resource_type == "requirement"
        assert f.description == "需求文档"


class TestUpdateFileContent:
    def test_update_success(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "a.pdf", "pdf", "/uploads/a.pdf"
        )
        result = update_file_content(db, f.id, "extracted text", "completed")
        assert result is not None
        assert result.content == "extracted text"
        assert result.extract_status == "completed"
        assert result.extracted_at is not None

    def test_update_with_error(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "b.pdf", "pdf", "/uploads/b.pdf"
        )
        result = update_file_content(
            db, f.id, "", "failed", extract_error="parse error"
        )
        assert result.extract_status == "failed"
        assert result.extract_error == "parse error"

    def test_update_nonexistent(self, db, test_project):
        result = update_file_content(db, 99999, "text", "completed")
        assert result is None


class TestUpdateFileResourceType:
    def test_update_success(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "c.pdf", "pdf", "/uploads/c.pdf"
        )
        result = update_file_resource_type(
            db, f.id, test_project.id, "requirement"
        )
        assert result is not None
        assert result.resource_type == "requirement"

    def test_update_wrong_project(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "d.pdf", "pdf", "/uploads/d.pdf"
        )
        result = update_file_resource_type(db, f.id, 99999, "requirement")
        assert result is None

    def test_update_nonexistent(self, db, test_project):
        result = update_file_resource_type(db, 99999, test_project.id, "requirement")
        assert result is None


class TestGetProjectFiles:
    def test_get_all(self, db, test_project):
        create_project_file(db, test_project.id, "f1.pdf", "pdf", "/f1")
        create_project_file(db, test_project.id, "f2.docx", "docx", "/f2")
        files = get_project_files(db, test_project.id)
        assert len(files) == 2

    def test_get_active_only(self, db, test_project):
        f1 = create_project_file(db, test_project.id, "a1.pdf", "pdf", "/a1")
        f2 = create_project_file(db, test_project.id, "a2.pdf", "pdf", "/a2")
        f2.is_active = False
        db.commit()
        files = get_project_files(db, test_project.id, is_active=True)
        assert len(files) == 1
        assert files[0].is_active is True

    def test_get_iteration_null(self, db, test_project):
        create_project_file(
            db, test_project.id, "n1.pdf", "pdf", "/n1", iteration_id=None
        )
        files = get_project_files(db, test_project.id, iteration_id=0)
        assert all(f.iteration_id is None for f in files)

    def test_no_iteration_filter(self, db, test_project):
        create_project_file(
            db, test_project.id, "x1.pdf", "pdf", "/x1", iteration_id=None
        )
        files = get_project_files(db, test_project.id)
        assert len(files) >= 1


class TestGetProjectFilesByType:
    def test_filter_by_type(self, db, test_project):
        create_project_file(
            db,
            test_project.id,
            "r1.pdf",
            "pdf",
            "/r1",
            resource_type="requirement",
        )
        create_project_file(
            db,
            test_project.id,
            "o1.pdf",
            "pdf",
            "/o1",
            resource_type="other",
        )
        files = get_project_files_by_type(db, test_project.id, "requirement")
        assert len(files) == 1
        assert files[0].resource_type == "requirement"

    def test_excludes_inactive(self, db, test_project):
        f = create_project_file(
            db,
            test_project.id,
            "r2.pdf",
            "pdf",
            "/r2",
            resource_type="requirement",
        )
        f.is_active = False
        db.commit()
        files = get_project_files_by_type(db, test_project.id, "requirement")
        assert len(files) == 0


class TestGetFileById:
    def test_found(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "g1.pdf", "pdf", "/g1"
        )
        result = get_file_by_id(db, f.id, test_project.id)
        assert result is not None
        assert result.id == f.id

    def test_wrong_project(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "g2.pdf", "pdf", "/g2"
        )
        result = get_file_by_id(db, f.id, 99999)
        assert result is None

    def test_nonexistent(self, db, test_project):
        result = get_file_by_id(db, 99999, test_project.id)
        assert result is None


class TestDeleteFile:
    def test_soft_delete(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "d1.pdf", "pdf", "/d1"
        )
        result = delete_file(db, f.id, test_project.id)
        assert result is True
        db.refresh(f)
        assert f.is_active is False

    def test_hard_delete(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "d2.pdf", "pdf", "/d2"
        )
        result = delete_file(db, f.id, test_project.id, permanent=True)
        assert result is True
        assert get_file_by_id(db, f.id, test_project.id) is None

    def test_delete_nonexistent(self, db, test_project):
        result = delete_file(db, 99999, test_project.id)
        assert result is False


class TestPermanentDeleteFile:
    def test_permanent_delete(self, db, test_project):
        f = create_project_file(
            db, test_project.id, "p1.pdf", "pdf", "/p1"
        )
        result = permanent_delete_file(db, f.id, test_project.id)
        assert result is True
        assert get_file_by_id(db, f.id, test_project.id) is None


class TestGetProjectFilesByIteration:
    def test_filter_no_match(self, db, test_project):
        create_project_file(
            db, test_project.id, "it1.pdf", "pdf", "/it1", iteration_id=None
        )
        files = get_project_files_by_iteration(db, test_project.id, 99999)
        assert len(files) == 0
