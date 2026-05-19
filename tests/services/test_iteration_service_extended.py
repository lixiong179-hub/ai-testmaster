import pytest
from app.services.iteration_service import (
    create_iteration,
    add_input,
    list_iterations,
    get_iteration,
    finalize_iteration,
    transition_iteration_status,
    IterationStatusTransitionError,
    BaseIterationValidationError,
    DuplicateInputHashError,
    IterationInputValidationError,
    ITERATION_STATUS_TRANSITIONS,
    VALID_INPUT_KINDS,
)
from app.models.enums import IterationPipelineStatus, IterationInputKind


class TestCreateIteration:
    def test_create_basic(self, db, testProject):
        it = create_iteration(db, testProject.id, "iter_1")
        assert it.id is not None
        assert it.name == "iter_1"
        assert it.status == IterationPipelineStatus.DRAFT.value

    def test_duplicate_name_raises(self, db, testProject):
        create_iteration(db, testProject.id, "dup_iter")
        with pytest.raises(ValueError, match="同名迭代"):
            create_iteration(db, testProject.id, "dup_iter")

    def test_with_base_iteration(self, db, testProject):
        base = create_iteration(db, testProject.id, "base_iter")
        transition_iteration_status(db, base.id, IterationPipelineStatus.IN_PIPELINE.value)
        transition_iteration_status(db, base.id, IterationPipelineStatus.IN_REVIEW.value)
        transition_iteration_status(db, base.id, IterationPipelineStatus.FINALIZED.value)
        child = create_iteration(
            db, testProject.id, "child_iter", base_iteration_id=base.id,
        )
        assert child.base_iteration_id == base.id

    def test_base_iteration_wrong_project(self, db, testProject):
        from app.models.project import Project
        other_project = Project(name="other_proj", user_id=testProject.user_id, status=1, project_type="web")
        db.add(other_project)
        db.flush()
        base = create_iteration(db, other_project.id, "other_base")
        transition_iteration_status(db, base.id, IterationPipelineStatus.IN_PIPELINE.value)
        transition_iteration_status(db, base.id, IterationPipelineStatus.IN_REVIEW.value)
        transition_iteration_status(db, base.id, IterationPipelineStatus.FINALIZED.value)
        with pytest.raises(BaseIterationValidationError, match="不属于项目"):
            create_iteration(db, testProject.id, "bad_base", base_iteration_id=base.id)

    def test_base_iteration_not_finalized(self, db, testProject):
        base = create_iteration(db, testProject.id, "non_final_base")
        with pytest.raises(BaseIterationValidationError, match="必须为 finalized"):
            create_iteration(db, testProject.id, "bad_child", base_iteration_id=base.id)

    def test_base_iteration_nonexistent(self, db, testProject):
        with pytest.raises(BaseIterationValidationError, match="不存在"):
            create_iteration(db, testProject.id, "bad_child", base_iteration_id=99999)


class TestAddInput:
    def test_add_basic_input(self, db, testProject):
        it = create_iteration(db, testProject.id, "input_iter")
        inp = add_input(db, it.id, IterationInputKind.PRD.value, hash_value="abc123")
        assert inp.id is not None
        assert inp.kind == IterationInputKind.PRD.value
        assert inp.content_hash == "abc123"

    def test_empty_hash_raises(self, db, testProject):
        it = create_iteration(db, testProject.id, "hash_iter")
        with pytest.raises(IterationInputValidationError, match="hash_value"):
            add_input(db, it.id, IterationInputKind.PRD.value, hash_value="")

    def test_invalid_kind_raises(self, db, testProject):
        it = create_iteration(db, testProject.id, "kind_iter")
        with pytest.raises(IterationInputValidationError, match="不合法"):
            add_input(db, it.id, "invalid_kind", hash_value="abc")

    def test_duplicate_hash_raises(self, db, testProject):
        it = create_iteration(db, testProject.id, "dup_hash_iter")
        add_input(db, it.id, IterationInputKind.PRD.value, hash_value="dup_hash")
        with pytest.raises(DuplicateInputHashError):
            add_input(db, it.id, IterationInputKind.PRD.value, hash_value="dup_hash")

    def test_nonexistent_iteration_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            add_input(db, 99999, IterationInputKind.PRD.value, hash_value="abc")

    def test_nonexistent_file_id_raises(self, db, testProject):
        it = create_iteration(db, testProject.id, "file_iter")
        with pytest.raises(IterationInputValidationError, match="file_id"):
            add_input(db, it.id, IterationInputKind.PRD.value, hash_value="abc", file_id=99999)


class TestListIterations:
    def test_list_returns_iterations(self, db, testProject):
        create_iteration(db, testProject.id, "list_iter_1")
        create_iteration(db, testProject.id, "list_iter_2")
        result = list_iterations(db, testProject.id)
        assert len(result) >= 2

    def test_list_empty_project(self, db, testProject):
        from app.models.project import Project
        empty_proj = Project(name="empty_proj", user_id=testProject.user_id, status=1, project_type="web")
        db.add(empty_proj)
        db.flush()
        result = list_iterations(db, empty_proj.id)
        assert len(result) == 0


class TestGetIteration:
    def test_get_existing(self, db, testProject):
        it = create_iteration(db, testProject.id, "get_iter")
        result = get_iteration(db, it.id)
        assert result is not None
        assert result.id == it.id

    def test_get_nonexistent(self, db):
        result = get_iteration(db, 99999)
        assert result is None


class TestTransitionStatus:
    def test_draft_to_in_pipeline(self, db, testProject):
        it = create_iteration(db, testProject.id, "trans_iter")
        result = transition_iteration_status(db, it.id, IterationPipelineStatus.IN_PIPELINE.value)
        assert result.status == IterationPipelineStatus.IN_PIPELINE.value

    def test_invalid_transition_raises(self, db, testProject):
        it = create_iteration(db, testProject.id, "bad_trans_iter")
        with pytest.raises(IterationStatusTransitionError):
            transition_iteration_status(db, it.id, IterationPipelineStatus.FINALIZED.value)

    def test_nonexistent_iteration_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            transition_iteration_status(db, 99999, IterationPipelineStatus.IN_PIPELINE.value)

    def test_finalize_sets_finalized_at(self, db, testProject):
        it = create_iteration(db, testProject.id, "final_iter")
        transition_iteration_status(db, it.id, IterationPipelineStatus.IN_PIPELINE.value)
        transition_iteration_status(db, it.id, IterationPipelineStatus.IN_REVIEW.value)
        result = transition_iteration_status(db, it.id, IterationPipelineStatus.FINALIZED.value)
        assert result.finalized_at is not None


class TestFinalizeIteration:
    def test_finalize_from_in_review(self, db, testProject):
        it = create_iteration(db, testProject.id, "fin_iter")
        transition_iteration_status(db, it.id, IterationPipelineStatus.IN_PIPELINE.value)
        transition_iteration_status(db, it.id, IterationPipelineStatus.IN_REVIEW.value)
        result = finalize_iteration(db, it.id)
        assert result.status == IterationPipelineStatus.FINALIZED.value

    def test_finalize_from_draft_raises(self, db, testProject):
        it = create_iteration(db, testProject.id, "fin_draft_iter")
        with pytest.raises(IterationStatusTransitionError):
            finalize_iteration(db, it.id)


class TestValidInputKinds:
    def test_contains_expected_kinds(self):
        assert IterationInputKind.PRD.value in VALID_INPUT_KINDS
