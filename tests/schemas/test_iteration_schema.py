import pytest
from app.schemas.iteration import (
    IterationPipelineStatus,
    IterationInputKind,
    IterationCreate,
    IterationUpdate,
    IterationInputCreate,
    IterationInputResponse,
    IterationResponse,
)


class TestIterationPipelineStatus:
    def test_values(self):
        assert IterationPipelineStatus.DRAFT.value == "draft"
        assert IterationPipelineStatus.IN_PIPELINE.value == "in_pipeline"
        assert IterationPipelineStatus.IN_REVIEW.value == "in_review"
        assert IterationPipelineStatus.FINALIZED.value == "finalized"
        assert IterationPipelineStatus.ARCHIVED.value == "archived"


class TestIterationInputKind:
    def test_values(self):
        assert IterationInputKind.PRD.value == "prd"
        assert IterationInputKind.PROTOTYPE.value == "prototype"
        assert IterationInputKind.XMIND.value == "xmind"
        assert IterationInputKind.TESTPOINT.value == "testpoint"
        assert IterationInputKind.SUPPLEMENT_FORM.value == "supplement_form"
        assert IterationInputKind.CHANGE_NOTES.value == "change_notes"


class TestIterationCreate:
    def test_required_fields(self):
        create = IterationCreate(project_id=1, name="迭代1")
        assert create.version == "v1.0"
        assert create.description is None
        assert create.base_iteration_id is None

    def test_all_fields(self):
        from datetime import date
        create = IterationCreate(
            project_id=1, name="迭代2", version="v2.0",
            description="描述", base_iteration_id=3,
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        )
        assert create.version == "v2.0"
        assert create.base_iteration_id == 3

    def test_empty_name_raises(self):
        with pytest.raises(Exception):
            IterationCreate(project_id=1, name="")

    def test_name_too_long(self):
        with pytest.raises(Exception):
            IterationCreate(project_id=1, name="x" * 201)


class TestIterationUpdate:
    def test_all_optional(self):
        update = IterationUpdate()
        assert update.name is None
        assert update.version is None

    def test_partial(self):
        update = IterationUpdate(name="新名称")
        assert update.name == "新名称"


class TestIterationInputCreate:
    def test_required_fields(self):
        create = IterationInputCreate(kind=IterationInputKind.PRD, hash="abc123")
        assert create.file_id is None
        assert create.payload is None

    def test_with_file_id(self):
        create = IterationInputCreate(kind=IterationInputKind.XMIND, hash="abc", file_id=1)
        assert create.file_id == 1

    def test_with_payload(self):
        create = IterationInputCreate(
            kind=IterationInputKind.SUPPLEMENT_FORM, hash="abc",
            payload={"key": "value"},
        )
        assert create.payload == {"key": "value"}

    def test_empty_hash_raises(self):
        with pytest.raises(Exception):
            IterationInputCreate(kind=IterationInputKind.PRD, hash="")

    def test_hash_too_long(self):
        with pytest.raises(Exception):
            IterationInputCreate(kind=IterationInputKind.PRD, hash="x" * 65)


class TestIterationInputResponse:
    def test_create(self):
        from datetime import datetime
        resp = IterationInputResponse(
            id=1, iteration_id=1, kind="prd",
            file_id=None, payload=None, content_hash="abc",
            uploaded_at=datetime.now(),
        )
        assert resp.kind == "prd"


class TestIterationResponse:
    def test_create(self):
        from datetime import datetime
        resp = IterationResponse(
            id=1, project_id=1, name="迭代1",
            version="v1.0", description=None, status="draft",
            start_date=None, end_date=None, base_iteration_id=None,
            created_by=1, finalized_at=None,
            create_time=datetime.now(), update_time=datetime.now(),
        )
        assert resp.status == "draft"
        assert resp.inputs is None
