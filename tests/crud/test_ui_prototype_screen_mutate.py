import pytest

from app.crud.ui_prototype_screen import (
    get_ui_screen_by_id,
    get_ui_screens_by_project,
    get_ui_screens_count,
    get_test_cases_by_screen,
    get_parsed_ui_screens_for_case_generation,
    _apply_iteration_filter,
)
from app.models.ui_prototype import UIPrototypeScreen, UIPrototypeProject, UIScreenTestCaseLink
from app.models.iteration import Iteration
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def ui_user(db):
    user = User(username="ui_screen_user", email="ui_screen@test.com", password_hash="hash", is_active=True)
    db.add(user)
    db.flush()
    db.refresh(user)
    yield user
    try:
        db.query(UIScreenTestCaseLink).filter(
            UIScreenTestCaseLink.screen_id.in_(
                db.query(UIPrototypeScreen.id).filter(
                    UIPrototypeScreen.project_id.in_(
                        db.query(Project.id).filter(Project.user_id == user.id)
                    )
                )
            )
        ).delete(synchronize_session=False)
        db.query(UIPrototypeScreen).filter(
            UIPrototypeScreen.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            )
        ).delete(synchronize_session=False)
        db.query(UIPrototypeProject).filter(
            UIPrototypeProject.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            )
        ).delete(synchronize_session=False)
        db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
        db.delete(user)
        db.flush()
    except Exception:
        db.rollback()


@pytest.fixture
def ui_project(db, ui_user):
    project = Project(name="ui_screen_project", user_id=ui_user.id, description="ui screen test", status=1, project_type="web")
    db.add(project)
    db.flush()
    db.refresh(project)
    yield project


def _make_screen(db, project_id, **kwargs):
    defaults = {
        "project_id": project_id,
        "prototype_name": "测试原型",
        "screen_name": "测试页面",
        "screen_order": 0,
        "parse_status": "pending",
    }
    defaults.update(kwargs)
    screen = UIPrototypeScreen(**defaults)
    db.add(screen)
    db.flush()
    db.refresh(screen)
    return screen


def _make_proto_project(db, project_id, iteration_id=None, **kwargs):
    proto = UIPrototypeProject(
        project_id=project_id,
        name=kwargs.get("name", "原型项目"),
        iteration_id=iteration_id,
    )
    db.add(proto)
    db.flush()
    db.refresh(proto)
    return proto


class TestGetUiScreenById:

    def test_found(self, db, ui_project):
        screen = _make_screen(db, ui_project.id)
        result = get_ui_screen_by_id(db, screen.id)
        assert result is not None
        assert result.id == screen.id

    def test_with_project_filter(self, db, ui_project):
        screen = _make_screen(db, ui_project.id)
        result = get_ui_screen_by_id(db, screen.id, ui_project.id)
        assert result is not None
        result2 = get_ui_screen_by_id(db, screen.id, 99999)
        assert result2 is None

    def test_not_found(self, db):
        result = get_ui_screen_by_id(db, 99999)
        assert result is None


class TestGetUiScreensByProject:

    def test_basic_query(self, db, ui_project, ui_user):
        _make_screen(db, ui_project.id, screen_name="S1")
        _make_screen(db, ui_project.id, screen_name="S2")
        screens = get_ui_screens_by_project(db, ui_project.id, ui_user.id)
        assert len(screens) == 2

    def test_filter_by_parse_status(self, db, ui_project, ui_user):
        _make_screen(db, ui_project.id, parse_status="completed", screen_name="SC")
        _make_screen(db, ui_project.id, parse_status="pending", screen_name="SP")
        screens = get_ui_screens_by_project(db, ui_project.id, ui_user.id, parse_status="completed")
        assert len(screens) == 1
        assert screens[0].parse_status == "completed"

    def test_filter_by_prototype_project(self, db, ui_project, ui_user):
        proto = _make_proto_project(db, ui_project.id)
        _make_screen(db, ui_project.id, prototype_project_id=proto.id, screen_name="SP")
        _make_screen(db, ui_project.id, prototype_project_id=None, screen_name="SN")
        screens = get_ui_screens_by_project(db, ui_project.id, ui_user.id, prototype_project_id=proto.id)
        assert len(screens) == 1

    def test_pagination(self, db, ui_project, ui_user):
        for i in range(5):
            _make_screen(db, ui_project.id, screen_name=f"P{i}", screen_order=i)
        screens = get_ui_screens_by_project(db, ui_project.id, ui_user.id, skip=0, limit=2)
        assert len(screens) == 2

    def test_filter_by_iteration_id(self, db, ui_project, ui_user):
        iteration = Iteration(project_id=ui_project.id, name="UI迭代", status="draft")
        db.add(iteration)
        db.flush()
        proto = _make_proto_project(db, ui_project.id, iteration_id=iteration.id)
        _make_screen(db, ui_project.id, prototype_project_id=proto.id, screen_name="SI")
        _make_screen(db, ui_project.id, prototype_project_id=None, screen_name="SN")
        screens = get_ui_screens_by_project(db, ui_project.id, ui_user.id, iteration_id=iteration.id)
        assert len(screens) == 1

    def test_filter_unlinked_iteration(self, db, ui_project, ui_user):
        proto = _make_proto_project(db, ui_project.id, iteration_id=None)
        _make_screen(db, ui_project.id, prototype_project_id=proto.id, screen_name="SU")
        _make_screen(db, ui_project.id, prototype_project_id=None, screen_name="SN")
        screens = get_ui_screens_by_project(db, ui_project.id, ui_user.id, iteration_id=-1)
        assert len(screens) == 2


class TestGetUiScreensCount:

    def test_count(self, db, ui_project, ui_user):
        _make_screen(db, ui_project.id, screen_name="C1")
        _make_screen(db, ui_project.id, screen_name="C2")
        count = get_ui_screens_count(db, ui_project.id, ui_user.id)
        assert count == 2

    def test_count_with_filter(self, db, ui_project, ui_user):
        _make_screen(db, ui_project.id, parse_status="completed", screen_name="CC")
        _make_screen(db, ui_project.id, parse_status="pending", screen_name="CP")
        count = get_ui_screens_count(db, ui_project.id, ui_user.id, parse_status="completed")
        assert count == 1


class TestGetTestCasesByScreen:

    def test_no_links(self, db, ui_project):
        screen = _make_screen(db, ui_project.id)
        result = get_test_cases_by_screen(db, screen.id)
        assert result == []

    def test_with_links(self, db, ui_project):
        screen = _make_screen(db, ui_project.id)
        case = TestCase(
            project_id=ui_project.id,
            case_no=f"UI-LINK-{id(db)}",
            module="UI模块",
            title="UI链接用例",
            precondition="前置",
            steps_json=[],
            expected_result="预期",
            priority=1,
            case_type="UI",
        )
        db.add(case)
        db.flush()
        link = UIScreenTestCaseLink(screen_id=screen.id, test_case_id=case.id)
        db.add(link)
        db.flush()
        result = get_test_cases_by_screen(db, screen.id)
        assert case.id in result


class TestGetParsedUiScreensForCaseGeneration:

    def test_completed_screens(self, db, ui_project, ui_user):
        _make_screen(db, ui_project.id, parse_status="completed", review_status="approved", screen_name="GC")
        _make_screen(db, ui_project.id, parse_status="pending", screen_name="GP")
        screens = get_parsed_ui_screens_for_case_generation(db, ui_project.id, ui_user.id)
        assert len(screens) == 1

    def test_approved_only_false(self, db, ui_project, ui_user):
        _make_screen(db, ui_project.id, parse_status="completed", review_status="rejected", screen_name="GR")
        screens = get_parsed_ui_screens_for_case_generation(db, ui_project.id, ui_user.id, approved_only=False)
        assert len(screens) == 1

    def test_approved_only_true_excludes_rejected(self, db, ui_project, ui_user):
        _make_screen(db, ui_project.id, parse_status="completed", review_status="rejected", screen_name="GR2")
        screens = get_parsed_ui_screens_for_case_generation(db, ui_project.id, ui_user.id, approved_only=True)
        assert len(screens) == 0

    def test_pending_review_included_when_approved_only(self, db, ui_project, ui_user):
        _make_screen(db, ui_project.id, parse_status="completed", review_status="pending", screen_name="GPR")
        screens = get_parsed_ui_screens_for_case_generation(db, ui_project.id, ui_user.id, approved_only=True)
        assert len(screens) == 1

    def test_filter_by_prototype_project(self, db, ui_project, ui_user):
        proto = _make_proto_project(db, ui_project.id)
        _make_screen(db, ui_project.id, parse_status="completed", review_status="approved",
                     prototype_project_id=proto.id, screen_name="GPP")
        _make_screen(db, ui_project.id, parse_status="completed", review_status="approved",
                     prototype_project_id=None, screen_name="GPN")
        screens = get_parsed_ui_screens_for_case_generation(db, ui_project.id, ui_user.id, prototype_project_id=proto.id)
        assert len(screens) == 1


class TestApplyIterationFilter:

    def test_none_iteration_no_filter(self, db, ui_project):
        query = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.project_id == ui_project.id)
        result = _apply_iteration_filter(query, None)
        assert result is query

    def test_positive_iteration_id(self, db, ui_project):
        iteration = Iteration(project_id=ui_project.id, name="FI迭代", status="draft")
        db.add(iteration)
        db.flush()
        proto = _make_proto_project(db, ui_project.id, iteration_id=iteration.id)
        _make_screen(db, ui_project.id, prototype_project_id=proto.id, screen_name="FI")
        query = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.project_id == ui_project.id)
        result = _apply_iteration_filter(query, iteration.id)
        screens = result.all()
        assert len(screens) == 1

    def test_negative_iteration_id(self, db, ui_project):
        proto = _make_proto_project(db, ui_project.id, iteration_id=None)
        _make_screen(db, ui_project.id, prototype_project_id=proto.id, screen_name="FU")
        _make_screen(db, ui_project.id, prototype_project_id=None, screen_name="FNU")
        query = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.project_id == ui_project.id)
        result = _apply_iteration_filter(query, -1)
        screens = result.all()
        assert len(screens) == 2
