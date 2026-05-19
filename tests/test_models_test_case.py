import pytest
from datetime import datetime
from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep, TestCaseExecution
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(username="tc_test_user", email="tc_test@example.com", password_hash="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(TestCaseExecution).filter(TestCaseExecution.test_case_id.in_(
        db.query(TestCase.id).filter(TestCase.project_id.in_(
            db.query(Project.id).filter(Project.user_id == user.id)
        ))
    )).delete(synchronize_session=False)
    db.query(TestStep).filter(TestStep.test_case_id.in_(
        db.query(TestCase.id).filter(TestCase.project_id.in_(
            db.query(Project.id).filter(Project.user_id == user.id)
        ))
    )).delete(synchronize_session=False)
    db.query(TestCasePreconditionStep).filter(TestCasePreconditionStep.test_case_id.in_(
        db.query(TestCase.id).filter(TestCase.project_id.in_(
            db.query(Project.id).filter(Project.user_id == user.id)
        ))
    )).delete(synchronize_session=False)
    db.query(TestCase).filter(TestCase.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="用例测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


class TestTestCaseModel:
    def test_create_test_case(self, db, test_project):
        tc = TestCase(
            case_no="TC-MODEL-001", project_id=test_project.id, module="登录模块",
            title="登录测试", precondition="用户已注册",
            steps_json=[{"step": "1", "action": "操作"}], expected_result="登录成功",
            priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        assert tc.id is not None
        assert tc.case_no == "TC-MODEL-001"
        assert tc.priority == 1
        assert tc.case_type == "UI"
        db.delete(tc)
        db.commit()

    def test_test_case_default_values(self, db, test_project):
        tc = TestCase(
            case_no="TC-MODEL-DEFAULT", project_id=test_project.id, module="模块",
            title="默认值用例", precondition="前置", steps_json=[],
            expected_result="预期", priority=2, case_type="API"
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        assert tc.generate_status == 0
        assert tc.is_deleted is False
        assert tc.review_status == "pending"
        assert tc.correction_status is None
        assert tc.exec_script is None
        db.delete(tc)
        db.commit()

    def test_test_case_unique_case_no(self, db, test_project):
        tc1 = TestCase(
            case_no="TC-UNIQUE-001", project_id=test_project.id, module="模块",
            title="唯一1", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc1)
        db.commit()
        nested = db.begin_nested()
        tc2 = TestCase(
            case_no="TC-UNIQUE-001", project_id=test_project.id, module="模块",
            title="唯一2", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc2)
        with pytest.raises(Exception):
            db.commit()
        nested.rollback()

    def test_test_case_priority_values(self, db, test_project):
        for p in [1, 2, 3]:
            tc = TestCase(
                case_no=f"TC-PRI-{p}", project_id=test_project.id, module="模块",
                title=f"优先级{p}", precondition="前置", steps_json=[],
                expected_result="预期", priority=p, case_type="UI"
            )
            db.add(tc)
            db.commit()
            db.refresh(tc)
            assert tc.priority == p
            db.delete(tc)
            db.commit()

    def test_test_case_review_status_values(self, db, test_project):
        for s in ["pending", "approved", "rejected", "needs_optimization"]:
            tc = TestCase(
                case_no=f"TC-REV-{s}", project_id=test_project.id, module="模块",
                title=f"审核{s}", precondition="前置", steps_json=[],
                expected_result="预期", priority=1, case_type="UI", review_status=s
            )
            db.add(tc)
            db.commit()
            db.refresh(tc)
            assert tc.review_status == s
            db.delete(tc)
            db.commit()

    def test_test_case_soft_delete(self, db, test_project):
        tc = TestCase(
            case_no="TC-SOFT-DEL", project_id=test_project.id, module="模块",
            title="软删除", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI",
            is_deleted=True, deleted_at=datetime(2024, 6, 1)
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        assert tc.is_deleted is True
        assert tc.deleted_at == datetime(2024, 6, 1)
        db.delete(tc)
        db.commit()

    def test_test_case_relationships(self):
        assert hasattr(TestCase, 'project')
        assert hasattr(TestCase, 'test_steps')
        assert hasattr(TestCase, 'test_point')
        assert hasattr(TestCase, 'parent_case')
        assert hasattr(TestCase, 'last_review')

    def test_test_case_lifecycle_status_default(self, db, test_project):
        tc = TestCase(
            case_no="TC-LS-DEFAULT", project_id=test_project.id, module="模块",
            title="生命周期默认", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        assert tc.lifecycle_status == "draft"
        db.delete(tc)
        db.commit()

    def test_test_case_lifecycle_status_values(self, db, test_project):
        for s in ["draft", "active", "pending_review", "needs_modify", "locator_broken", "deprecated", "archived"]:
            tc = TestCase(
                case_no=f"TC-LS-{s}", project_id=test_project.id, module="模块",
                title=f"状态{s}", precondition="前置", steps_json=[],
                expected_result="预期", priority=1, case_type="UI", lifecycle_status=s
            )
            db.add(tc)
            db.commit()
            db.refresh(tc)
            assert tc.lifecycle_status == s
            db.delete(tc)
            db.commit()

    def test_test_case_summary_fields(self, db, test_project):
        tc = TestCase(
            case_no="TC-SUM-001", project_id=test_project.id, module="模块",
            title="摘要测试", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI",
            summary="AI生成的摘要", summary_version=1, summary_model_version="gpt-4o"
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        assert tc.summary == "AI生成的摘要"
        assert tc.summary_version == 1
        assert tc.summary_model_version == "gpt-4o"
        db.delete(tc)
        db.commit()

    def test_test_case_summary_default_values(self, db, test_project):
        tc = TestCase(
            case_no="TC-SUM-DEF", project_id=test_project.id, module="模块",
            title="摘要默认", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        assert tc.summary is None
        assert tc.summary_version == 0
        assert tc.summary_model_version is None
        assert tc.parent_case_id is None
        assert tc.last_review_id is None
        db.delete(tc)
        db.commit()

    def test_test_case_parent_case_lineage(self, db, test_project):
        parent = TestCase(
            case_no="TC-PARENT-001", project_id=test_project.id, module="模块",
            title="父用例", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(parent)
        db.commit()
        db.refresh(parent)

        child = TestCase(
            case_no="TC-CHILD-001", project_id=test_project.id, module="模块",
            title="子用例", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI",
            parent_case_id=parent.id
        )
        db.add(child)
        db.commit()
        db.refresh(child)

        assert child.parent_case_id == parent.id
        assert child.parent_case.id == parent.id
        assert len(parent.child_cases) == 1
        assert parent.child_cases[0].id == child.id

        db.delete(child)
        db.delete(parent)
        db.commit()

    def test_test_case_last_review_relationship(self, db, test_project, test_user):
        from app.models.code_review import CodeReview

        review = CodeReview(
            title="用例评审", repository="https://example.com/repo",
            branch="main", reviewer_id=test_user.id, author_id=test_user.id,
        )
        db.add(review)
        db.commit()
        db.refresh(review)

        tc = TestCase(
            case_no="TC-REVIEW-001", project_id=test_project.id, module="模块",
            title="评审测试", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI",
            last_review_id=review.id,
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)

        assert tc.last_review_id == review.id
        assert tc.last_review.id == review.id
        assert tc.last_review.title == "用例评审"

        db.delete(tc)
        db.delete(review)
        db.commit()


class TestTestStepModel:
    def test_create_test_step(self, db, test_project):
        tc = TestCase(
            case_no="TC-STEP-001", project_id=test_project.id, module="模块",
            title="步骤测试", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        step = TestStep(test_case_id=tc.id, step_number=1, action="输入用户名", expected_result="显示")
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.id is not None
        assert step.action == "输入用户名"
        db.delete(step)
        db.delete(tc)
        db.commit()

    def test_test_step_default_values(self, db, test_project):
        tc = TestCase(
            case_no="TC-STEP-DEF", project_id=test_project.id, module="模块",
            title="步骤默认", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        step = TestStep(test_case_id=tc.id, step_number=1, action="操作", expected_result="预期")
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.is_business_view == 1
        assert step.has_locator == 0
        assert step.locator_status == "pending"
        assert step.action_type is None
        db.delete(step)
        db.delete(tc)
        db.commit()

    def test_test_step_with_locator(self, db, test_project):
        tc = TestCase(
            case_no="TC-STEP-LOC", project_id=test_project.id, module="模块",
            title="定位步骤", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        step = TestStep(
            test_case_id=tc.id, step_number=1, action="点击登录",
            expected_result="跳转首页", has_locator=1, locator_status="recorded",
            action_type="click", target_element="登录按钮"
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.has_locator == 1
        assert step.locator_status == "recorded"
        assert step.action_type == "click"
        db.delete(step)
        db.delete(tc)
        db.commit()


class TestTestCasePreconditionStepModel:
    def test_create_precondition_step(self, db, test_project):
        tc = TestCase(
            case_no="TC-PRE-001", project_id=test_project.id, module="模块",
            title="前置步骤", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        step = TestCasePreconditionStep(
            test_case_id=tc.id, step_number=1, action="打开登录页",
            expected_result="页面加载完成"
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.id is not None
        assert step.action == "打开登录页"
        db.delete(step)
        db.delete(tc)
        db.commit()

    def test_precondition_step_default_values(self, db, test_project):
        tc = TestCase(
            case_no="TC-PRE-DEF", project_id=test_project.id, module="模块",
            title="前置默认", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        step = TestCasePreconditionStep(test_case_id=tc.id, step_number=1, action="操作")
        db.add(step)
        db.commit()
        db.refresh(step)
        assert step.expected_result == ""
        assert step.has_locator == 0
        assert step.locator_status == "pending"
        db.delete(step)
        db.delete(tc)
        db.commit()


class TestTestCaseExecutionModel:
    def test_create_execution(self, db, test_project):
        tc = TestCase(
            case_no="TC-EXEC-001", project_id=test_project.id, module="模块",
            title="执行记录", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        execution = TestCaseExecution(test_case_id=tc.id, status="pending")
        db.add(execution)
        db.commit()
        db.refresh(execution)
        assert execution.id is not None
        assert execution.status == "pending"
        db.delete(execution)
        db.delete(tc)
        db.commit()

    def test_execution_default_values(self, db, test_project):
        tc = TestCase(
            case_no="TC-EXEC-DEF", project_id=test_project.id, module="模块",
            title="执行默认", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        execution = TestCaseExecution(test_case_id=tc.id)
        db.add(execution)
        db.commit()
        db.refresh(execution)
        assert execution.status == "pending"
        assert execution.actual_result is None
        assert execution.started_at is None
        assert execution.completed_at is None
        db.delete(execution)
        db.delete(tc)
        db.commit()

    def test_execution_status_values(self, db, test_project):
        tc = TestCase(
            case_no="TC-EXEC-STA", project_id=test_project.id, module="模块",
            title="执行状态", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        for status in ["pending", "running", "passed", "failed", "blocked"]:
            execution = TestCaseExecution(test_case_id=tc.id, status=status)
            db.add(execution)
            db.commit()
            db.refresh(execution)
            assert execution.status == status
            db.delete(execution)
            db.commit()
        db.delete(tc)
        db.commit()

    def test_execution_with_timestamps(self, db, test_project):
        tc = TestCase(
            case_no="TC-EXEC-TS", project_id=test_project.id, module="模块",
            title="执行时间", precondition="前置", steps_json=[],
            expected_result="预期", priority=1, case_type="UI"
        )
        db.add(tc)
        db.commit()
        execution = TestCaseExecution(
            test_case_id=tc.id, status="passed",
            started_at=datetime(2024, 1, 1, 10, 0, 0),
            completed_at=datetime(2024, 1, 1, 10, 5, 0)
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        assert execution.started_at == datetime(2024, 1, 1, 10, 0, 0)
        assert execution.completed_at == datetime(2024, 1, 1, 10, 5, 0)
        db.delete(execution)
        db.delete(tc)
        db.commit()
