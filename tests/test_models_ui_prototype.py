import pytest
from datetime import datetime
from app.models.ui_prototype import UIPrototypeScreen, UIPrototypeProject, UIScreenTestCaseLink, UIPrototypeSource
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="ui_test_user",
        email="ui_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(UIScreenTestCaseLink).filter(UIScreenTestCaseLink.screen_id.in_(
        db.query(UIPrototypeScreen.id).filter(UIPrototypeScreen.project_id.in_(
            db.query(Project.id).filter(Project.user_id == user.id)
        ))
    )).delete(synchronize_session=False)
    db.query(UIPrototypeScreen).filter(UIPrototypeScreen.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(UIPrototypeProject).filter(UIPrototypeProject.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="UI原型测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


class TestUIPrototypeSource:
    def test_source_values(self):
        assert UIPrototypeSource.MOCKINGBOT == "mockingbot"
        assert UIPrototypeSource.LANNHU == "lannhu"
        assert UIPrototypeSource.FIGMA == "figma"
        assert UIPrototypeSource.AXURE == "axure"
        assert UIPrototypeSource.SKETCH == "sketch"
        assert UIPrototypeSource.ADOBE_XD == "adobe_xd"
        assert UIPrototypeSource.MANUAL == "manual"
        assert UIPrototypeSource.OTHER == "other"


class TestUIPrototypeScreenModel:
    def test_create_screen(self, db, test_project, test_user):
        screen = UIPrototypeScreen(
            project_id=test_project.id,
            prototype_name="登录原型",
            source="figma",
            screen_name="登录页",
            created_by=test_user.id
        )
        db.add(screen)
        db.commit()
        db.refresh(screen)
        assert screen.id is not None
        assert screen.project_id == test_project.id
        assert screen.prototype_name == "登录原型"
        assert screen.source == "figma"
        assert screen.screen_name == "登录页"
        assert screen.created_by == test_user.id
        assert screen.create_time is not None
        db.delete(screen)
        db.commit()

    def test_screen_default_values(self, db, test_project):
        screen = UIPrototypeScreen(
            project_id=test_project.id,
            prototype_name="默认原型",
            screen_name="默认页"
        )
        db.add(screen)
        db.commit()
        db.refresh(screen)
        assert screen.source == "manual"
        assert screen.screen_order == 0
        assert screen.file_type == "png"
        assert screen.ui_spec_version == "1.0"
        assert screen.parse_status == "pending"
        assert screen.element_count == 0
        assert screen.button_count == 0
        assert screen.input_count == 0
        assert screen.is_entry_point is False
        assert screen.is_end_point is False
        assert screen.review_status == "pending"
        assert screen.original_file_path is None
        assert screen.original_file_name is None
        assert screen.file_size is None
        assert screen.ui_spec is None
        assert screen.parse_error is None
        assert screen.parse_model is None
        assert screen.parent_screen_id is None
        assert screen.related_screens is None
        assert screen.navigation_flow is None
        assert screen.layout_checks is None
        assert screen.summary is None
        assert screen.reviewed_by is None
        assert screen.reviewed_at is None
        assert screen.review_comment is None
        db.delete(screen)
        db.commit()

    def test_screen_source_values(self, db, test_project):
        for source in ["mockingbot", "lannhu", "figma", "axure", "manual", "other"]:
            screen = UIPrototypeScreen(
                project_id=test_project.id,
                prototype_name=f"原型-{source}",
                source=source,
                screen_name=f"页面-{source}"
            )
            db.add(screen)
            db.commit()
            db.refresh(screen)
            assert screen.source == source
            db.delete(screen)
            db.commit()

    def test_screen_parse_status_values(self, db, test_project):
        for status in ["pending", "running", "completed", "failed"]:
            screen = UIPrototypeScreen(
                project_id=test_project.id,
                prototype_name=f"解析-{status}",
                screen_name=f"页-{status}",
                parse_status=status
            )
            db.add(screen)
            db.commit()
            db.refresh(screen)
            assert screen.parse_status == status
            db.delete(screen)
            db.commit()

    def test_screen_review_status_values(self, db, test_project):
        for status in ["pending", "approved", "rejected"]:
            screen = UIPrototypeScreen(
                project_id=test_project.id,
                prototype_name=f"审核-{status}",
                screen_name=f"审-{status}",
                review_status=status
            )
            db.add(screen)
            db.commit()
            db.refresh(screen)
            assert screen.review_status == status
            db.delete(screen)
            db.commit()

    def test_screen_with_ui_spec(self, db, test_project):
        screen = UIPrototypeScreen(
            project_id=test_project.id,
            prototype_name="规格原型",
            screen_name="规格页",
            ui_spec={"elements": [{"type": "button", "text": "提交"}]},
            element_count=5,
            button_count=2,
            input_count=1
        )
        db.add(screen)
        db.commit()
        db.refresh(screen)
        assert screen.ui_spec == {"elements": [{"type": "button", "text": "提交"}]}
        assert screen.element_count == 5
        assert screen.button_count == 2
        assert screen.input_count == 1
        db.delete(screen)
        db.commit()

    def test_screen_parent_child(self, db, test_project):
        parent = UIPrototypeScreen(
            project_id=test_project.id,
            prototype_name="父原型",
            screen_name="父页面"
        )
        db.add(parent)
        db.commit()
        db.refresh(parent)
        child = UIPrototypeScreen(
            project_id=test_project.id,
            prototype_name="子原型",
            screen_name="子页面",
            parent_screen_id=parent.id
        )
        db.add(child)
        db.commit()
        db.refresh(child)
        assert child.parent_screen_id == parent.id
        db.delete(child)
        db.delete(parent)
        db.commit()

    def test_screen_relationships(self):
        assert hasattr(UIPrototypeScreen, 'project')
        assert hasattr(UIPrototypeScreen, 'creator')
        assert hasattr(UIPrototypeScreen, 'parent')
        assert hasattr(UIPrototypeScreen, 'linked_test_cases')


class TestUIPrototypeProjectModel:
    def test_create_prototype_project(self, db, test_project):
        pp = UIPrototypeProject(
            project_id=test_project.id,
            name="原型项目1"
        )
        db.add(pp)
        db.commit()
        db.refresh(pp)
        assert pp.id is not None
        assert pp.project_id == test_project.id
        assert pp.name == "原型项目1"
        assert pp.source == "manual"
        assert pp.screen_count == 0
        assert pp.parsed_count == 0
        assert pp.parse_status == "pending"
        assert pp.create_time is not None
        db.delete(pp)
        db.commit()

    def test_prototype_project_default_values(self, db, test_project):
        pp = UIPrototypeProject(
            project_id=test_project.id,
            name="默认原型项目"
        )
        db.add(pp)
        db.commit()
        db.refresh(pp)
        assert pp.description is None
        assert pp.merged_flow is None
        assert pp.created_by is None
        assert pp.iteration_id is None
        db.delete(pp)
        db.commit()

    def test_prototype_project_source_values(self, db, test_project):
        for source in ["mockingbot", "lannhu", "figma", "axure", "manual", "other"]:
            pp = UIPrototypeProject(
                project_id=test_project.id,
                name=f"来源-{source}",
                source=source
            )
            db.add(pp)
            db.commit()
            db.refresh(pp)
            assert pp.source == source
            db.delete(pp)
            db.commit()

    def test_prototype_project_with_iteration(self, db, test_project):
        from app.models.iteration import Iteration
        iteration = Iteration(
            project_id=test_project.id,
            name="原型迭代"
        )
        db.add(iteration)
        db.commit()
        db.refresh(iteration)
        pp = UIPrototypeProject(
            project_id=test_project.id,
            name="迭代原型项目",
            iteration_id=iteration.id
        )
        db.add(pp)
        db.commit()
        db.refresh(pp)
        assert pp.iteration_id == iteration.id
        db.delete(pp)
        db.delete(iteration)
        db.commit()


class TestUIScreenTestCaseLinkModel:
    def test_create_link(self, db, test_project):
        from app.models.test_case import TestCase
        screen = UIPrototypeScreen(
            project_id=test_project.id,
            prototype_name="链接原型",
            screen_name="链接页"
        )
        db.add(screen)
        db.commit()
        db.refresh(screen)
        tc = TestCase(
            case_no="TC-UI-LINK-001",
            project_id=test_project.id,
            module="模块",
            title="链接用例",
            precondition="前置",
            steps_json=[],
            expected_result="预期",
            priority=1,
            case_type="UI"
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        link = UIScreenTestCaseLink(
            screen_id=screen.id,
            test_case_id=tc.id,
            link_type="source"
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        assert link.id is not None
        assert link.screen_id == screen.id
        assert link.test_case_id == tc.id
        assert link.link_type == "source"
        assert link.create_time is not None
        db.delete(link)
        db.delete(tc)
        db.delete(screen)
        db.commit()

    def test_link_default_type(self, db, test_project):
        from app.models.test_case import TestCase
        screen = UIPrototypeScreen(
            project_id=test_project.id,
            prototype_name="默认链接原型",
            screen_name="默认链接页"
        )
        db.add(screen)
        db.commit()
        db.refresh(screen)
        tc = TestCase(
            case_no="TC-UI-DEF-001",
            project_id=test_project.id,
            module="模块",
            title="默认链接用例",
            precondition="前置",
            steps_json=[],
            expected_result="预期",
            priority=1,
            case_type="UI"
        )
        db.add(tc)
        db.commit()
        db.refresh(tc)
        link = UIScreenTestCaseLink(
            screen_id=screen.id,
            test_case_id=tc.id
        )
        db.add(link)
        db.commit()
        db.refresh(link)
        assert link.link_type == "source"
        db.delete(link)
        db.delete(tc)
        db.delete(screen)
        db.commit()
