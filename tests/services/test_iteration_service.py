"""
M1-T06 IterationService 单元测试

覆盖范围：
1. create_iteration 正常创建 + 同名校验
2. base_iteration_id 校验：不存在 / 不同项目 / 非 finalized
3. add_input 正常添加 + 幂等校验（重复 hash）
4. add_input 迭代不存在
5. list_iterations 按项目查询
6. get_iteration 详情
7. finalize_iteration 正常定稿 + 状态校验
8. transition_iteration_status 所有合法路径 + 非法路径
9. IterationPipelineStatus 枚举值正确性
10. IterationInput 枚举值正确性
"""
import pytest
from datetime import datetime, timezone

from app.models.enums import IterationPipelineStatus, IterationInputKind
from app.models.iteration import Iteration, IterationInput
from app.models.project import Project
from app.models.user import User
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
)


# ==================== Fixtures ====================

@pytest.fixture
def test_user(db):
    user = User(username="iter_test_user", email="iter_test@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user
    db.query(IterationInput).filter(
        IterationInput.iteration_id.in_(
            db.query(Iteration.id).filter(Iteration.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            ))
        )
    ).delete(synchronize_session=False)
    db.query(Iteration).filter(Iteration.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.flush()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="迭代测试项目", user_id=test_user.id)
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


def _create_iteration(db, project_id, name="Sprint 1", **kwargs):
    """辅助函数：直接创建迭代（绕过 service 层）"""
    it = Iteration(
        project_id=project_id,
        name=name,
        version=kwargs.get("version", "v1.0"),
        status=kwargs.get("status", IterationPipelineStatus.DRAFT.value),
        created_by=kwargs.get("created_by"),
        base_iteration_id=kwargs.get("base_iteration_id"),
    )
    db.add(it)
    db.flush()
    db.refresh(it)
    return it


# ==================== create_iteration ====================

class TestCreateIteration:
    """迭代创建测试"""

    def test_create_success(self, db, test_project, test_user):
        it = create_iteration(
            db, test_project.id, "Sprint 1",
            version="v1.0", created_by=test_user.id,
        )
        assert it.id is not None
        assert it.project_id == test_project.id
        assert it.name == "Sprint 1"
        assert it.status == IterationPipelineStatus.DRAFT.value
        assert it.created_by == test_user.id
        assert it.base_iteration_id is None

    def test_create_duplicate_name(self, db, test_project, test_user):
        create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        with pytest.raises(ValueError, match="已存在同名迭代"):
            create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)

    def test_create_with_base_iteration(self, db, test_project, test_user):
        # 先创建一个 finalized 的基线迭代
        base = _create_iteration(db, test_project.id, "Base Sprint",
                                 status=IterationPipelineStatus.FINALIZED.value)
        it = create_iteration(
            db, test_project.id, "Sprint 2",
            base_iteration_id=base.id,
            created_by=test_user.id,
        )
        assert it.base_iteration_id == base.id

    def test_base_iteration_not_found(self, db, test_project, test_user):
        with pytest.raises(BaseIterationValidationError, match="不存在"):
            create_iteration(
                db, test_project.id, "Sprint 1",
                base_iteration_id=99999,
                created_by=test_user.id,
            )

    def test_base_iteration_different_project(self, db, test_user):
        """基线迭代属于不同项目"""
        proj_a = Project(name="项目A", user_id=test_user.id)
        proj_b = Project(name="项目B", user_id=test_user.id)
        db.add_all([proj_a, proj_b])
        db.flush()

        base = _create_iteration(db, proj_a.id, "Base",
                                 status=IterationPipelineStatus.FINALIZED.value)
        with pytest.raises(BaseIterationValidationError, match="不属于项目"):
            create_iteration(
                db, proj_b.id, "Sprint 1",
                base_iteration_id=base.id,
                created_by=test_user.id,
            )

    def test_base_iteration_not_finalized(self, db, test_project, test_user):
        base = _create_iteration(db, test_project.id, "Base Sprint",
                                 status=IterationPipelineStatus.DRAFT.value)
        with pytest.raises(BaseIterationValidationError, match="必须为 finalized"):
            create_iteration(
                db, test_project.id, "Sprint 2",
                base_iteration_id=base.id,
                created_by=test_user.id,
            )


# ==================== add_input ====================

class TestAddInput:
    """迭代输入添加测试"""

    def test_add_file_input(self, db, test_project, test_user):
        it = create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        # 创建真实 ProjectFile 以满足 FK 约束
        from app.models.project import ProjectFile
        pf = ProjectFile(
            project_id=test_project.id,
            file_name="test_prd.docx",
            file_type="docx",
            file_url="/uploads/test_prd.docx",
            file_source="file",
        )
        db.add(pf)
        db.flush()
        inp = add_input(
            db, it.id, IterationInputKind.PRD.value,
            file_id=pf.id, hash_value="abc123",
        )
        assert inp.id is not None
        assert inp.iteration_id == it.id
        assert inp.kind == IterationInputKind.PRD.value
        assert inp.file_id == pf.id
        assert inp.content_hash == "abc123"

    def test_add_payload_input(self, db, test_project, test_user):
        it = create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        payload = {"form_field": "value", "priority": "high"}
        inp = add_input(
            db, it.id, IterationInputKind.SUPPLEMENT_FORM.value,
            payload=payload, hash_value="def456",
        )
        assert inp.payload == payload
        assert inp.file_id is None

    def test_add_input_duplicate_hash(self, db, test_project, test_user):
        it = create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        add_input(db, it.id, IterationInputKind.PRD.value, hash_value="same_hash")
        with pytest.raises(DuplicateInputHashError, match="same_hash"):
            add_input(db, it.id, IterationInputKind.XMIND.value, hash_value="same_hash")

    def test_add_input_iteration_not_found(self, db):
        with pytest.raises(ValueError, match="not found"):
            add_input(db, 99999, IterationInputKind.PRD.value, hash_value="xyz")

    def test_add_input_invalid_kind(self, db, test_project, test_user):
        it = create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        with pytest.raises(IterationInputValidationError, match="不合法"):
            add_input(db, it.id, "invalid_kind", hash_value="h1")

    def test_add_input_empty_hash(self, db, test_project, test_user):
        it = create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        with pytest.raises(IterationInputValidationError, match="不能为空"):
            add_input(db, it.id, IterationInputKind.PRD.value, hash_value="")

    def test_add_input_file_id_not_found(self, db, test_project, test_user):
        it = create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        with pytest.raises(IterationInputValidationError, match="不存在于 project_files"):
            add_input(db, it.id, IterationInputKind.PRD.value, file_id=99999, hash_value="h1")

    def test_add_input_different_iteration_same_hash(self, db, test_project, test_user):
        """不同迭代允许相同 hash"""
        it1 = create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        it2 = create_iteration(db, test_project.id, "Sprint 2", created_by=test_user.id)
        add_input(db, it1.id, IterationInputKind.PRD.value, hash_value="shared_hash")
        inp2 = add_input(db, it2.id, IterationInputKind.PRD.value, hash_value="shared_hash")
        assert inp2.iteration_id == it2.id


# ==================== list_iterations / get_iteration ====================

class TestListAndGetIteration:
    """迭代查询测试"""

    def test_list_iterations(self, db, test_project, test_user):
        create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        create_iteration(db, test_project.id, "Sprint 2", created_by=test_user.id)
        iters = list_iterations(db, test_project.id)
        assert len(iters) >= 2

    def test_list_iterations_pagination(self, db, test_project, test_user):
        for i in range(5):
            create_iteration(db, test_project.id, f"Sprint {i+1}", created_by=test_user.id)
        page1 = list_iterations(db, test_project.id, skip=0, limit=2)
        page2 = list_iterations(db, test_project.id, skip=2, limit=2)
        assert len(page1) == 2
        assert len(page2) == 2
        page1_ids = {it.id for it in page1}
        page2_ids = {it.id for it in page2}
        assert len(page1_ids & page2_ids) == 0

    def test_get_iteration_with_inputs(self, db, test_project, test_user):
        it = create_iteration(db, test_project.id, "Sprint 1", created_by=test_user.id)
        add_input(db, it.id, IterationInputKind.PRD.value, hash_value="h1")
        add_input(db, it.id, IterationInputKind.XMIND.value, hash_value="h2")

        found = get_iteration(db, it.id)
        assert found is not None
        assert found.id == it.id
        # inputs 通过 relationship 加载
        inputs = found.inputs
        assert len(inputs) == 2

    def test_get_iteration_not_found(self, db):
        assert get_iteration(db, 99999) is None


# ==================== finalize_iteration ====================

class TestFinalizeIteration:
    """迭代定稿测试"""

    def test_finalize_success(self, db, test_project, test_user):
        it = _create_iteration(db, test_project.id, "Sprint 1",
                               status=IterationPipelineStatus.IN_REVIEW.value)
        result = finalize_iteration(db, it.id)
        assert result.status == IterationPipelineStatus.FINALIZED.value
        assert result.finalized_at is not None

    def test_finalize_wrong_status_draft(self, db, test_project, test_user):
        it = _create_iteration(db, test_project.id, "Sprint 1",
                               status=IterationPipelineStatus.DRAFT.value)
        with pytest.raises(IterationStatusTransitionError):
            finalize_iteration(db, it.id)

    def test_finalize_wrong_status_in_pipeline(self, db, test_project, test_user):
        it = _create_iteration(db, test_project.id, "Sprint 1",
                               status=IterationPipelineStatus.IN_PIPELINE.value)
        with pytest.raises(IterationStatusTransitionError):
            finalize_iteration(db, it.id)

    def test_finalize_already_finalized(self, db, test_project, test_user):
        it = _create_iteration(db, test_project.id, "Sprint 1",
                               status=IterationPipelineStatus.FINALIZED.value)
        with pytest.raises(IterationStatusTransitionError):
            finalize_iteration(db, it.id)

    def test_finalize_not_found(self, db):
        with pytest.raises(ValueError, match="not found"):
            finalize_iteration(db, 99999)


# ==================== transition_iteration_status ====================

class TestTransitionIterationStatus:
    """迭代状态迁移测试"""

    def test_draft_to_in_pipeline(self, db, test_project):
        it = _create_iteration(db, test_project.id, "Sprint 1")
        result = transition_iteration_status(db, it.id, IterationPipelineStatus.IN_PIPELINE.value)
        assert result.status == IterationPipelineStatus.IN_PIPELINE.value

    def test_in_pipeline_to_in_review(self, db, test_project):
        it = _create_iteration(db, test_project.id, "Sprint 1",
                               status=IterationPipelineStatus.IN_PIPELINE.value)
        result = transition_iteration_status(db, it.id, IterationPipelineStatus.IN_REVIEW.value)
        assert result.status == IterationPipelineStatus.IN_REVIEW.value

    def test_in_review_to_finalized(self, db, test_project):
        it = _create_iteration(db, test_project.id, "Sprint 1",
                               status=IterationPipelineStatus.IN_REVIEW.value)
        result = transition_iteration_status(db, it.id, IterationPipelineStatus.FINALIZED.value)
        assert result.status == IterationPipelineStatus.FINALIZED.value
        assert result.finalized_at is not None

    def test_finalized_to_archived(self, db, test_project):
        it = _create_iteration(db, test_project.id, "Sprint 1",
                               status=IterationPipelineStatus.FINALIZED.value)
        result = transition_iteration_status(db, it.id, IterationPipelineStatus.ARCHIVED.value)
        assert result.status == IterationPipelineStatus.ARCHIVED.value

    def test_illegal_draft_to_finalized(self, db, test_project):
        it = _create_iteration(db, test_project.id, "Sprint 1")
        with pytest.raises(IterationStatusTransitionError):
            transition_iteration_status(db, it.id, IterationPipelineStatus.FINALIZED.value)

    def test_illegal_in_pipeline_to_archived(self, db, test_project):
        it = _create_iteration(db, test_project.id, "Sprint 1",
                               status=IterationPipelineStatus.IN_PIPELINE.value)
        with pytest.raises(IterationStatusTransitionError):
            transition_iteration_status(db, it.id, IterationPipelineStatus.ARCHIVED.value)

    def test_illegal_reverse_transition(self, db, test_project):
        it = _create_iteration(db, test_project.id, "Sprint 1",
                               status=IterationPipelineStatus.IN_PIPELINE.value)
        with pytest.raises(IterationStatusTransitionError):
            transition_iteration_status(db, it.id, IterationPipelineStatus.DRAFT.value)

    def test_not_found(self, db):
        with pytest.raises(ValueError, match="not found"):
            transition_iteration_status(db, 99999, IterationPipelineStatus.IN_PIPELINE.value)


# ==================== Enum ====================

class TestEnums:
    """枚举值正确性测试"""

    def test_iteration_pipeline_status_values(self):
        assert IterationPipelineStatus.DRAFT.value == "draft"
        assert IterationPipelineStatus.IN_PIPELINE.value == "in_pipeline"
        assert IterationPipelineStatus.IN_REVIEW.value == "in_review"
        assert IterationPipelineStatus.FINALIZED.value == "finalized"
        assert IterationPipelineStatus.ARCHIVED.value == "archived"

    def test_iteration_input_kind_values(self):
        assert IterationInputKind.PRD.value == "prd"
        assert IterationInputKind.PROTOTYPE.value == "prototype"
        assert IterationInputKind.XMIND.value == "xmind"
        assert IterationInputKind.TESTPOINT.value == "testpoint"
        assert IterationInputKind.SUPPLEMENT_FORM.value == "supplement_form"
