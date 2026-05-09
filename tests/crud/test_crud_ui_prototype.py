"""UI原型CRUD操作单元测试"""
import pytest
from app.crud.ui_prototype_project import (
    create_ui_prototype_project,
    get_ui_prototype_projects_by_project,
    get_ui_prototype_projects_count,
    update_prototype_project_stats,
    update_prototype_project_merged_flow,
)
from app.crud.ui_prototype_screen import (
    get_ui_screen_by_id,
    get_ui_screens_by_project,
    get_ui_screens_count,
    get_test_cases_by_screen,
    get_parsed_ui_screens_for_case_generation,
)
from app.crud.ui_prototype_screen_mutate import (
    create_ui_screen,
    update_ui_screen_parse_result,
    update_ui_screen_parse_status,
    update_ui_screen_review,
    delete_ui_screen,
    link_ui_screen_to_test_case,
    update_ui_screen_order,
    batch_create_ui_screens,
)
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.ui_prototype import (
    UIPrototypeProject,
    UIPrototypeScreen,
    UIScreenTestCaseLink,
)


@pytest.fixture
def test_project(db, testUser):
    project = Project(
        name="ui_proto_test_project",
        user_id=testUser.id,
        description="project for ui prototype tests",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    yield project


@pytest.fixture
def proto_project(db, test_project, testUser):
    pp = create_ui_prototype_project(
        db, test_project.id, "原型项目1", created_by=testUser.id
    )
    return pp


@pytest.fixture
def test_case_obj(db, test_project):
    """Create a valid TestCase for FK constraints in link tests."""
    tc = TestCase(
        case_no="UI-TC-001",
        project_id=test_project.id,
        module="UI模块",
        title="UI测试用例",
        precondition="�?,
        steps_json=[{"step": "步骤1", "action": "操作", "param": ""}],
        expected_result="预期结果",
        priority=2,
        case_type="UI",
    )
    db.add(tc)
    db.flush()
    return tc


# ================= UI Prototype Project =================


class TestCreateUIPrototypeProject:
    def test_create_basic(self, db, test_project):
        pp = create_ui_prototype_project(db, test_project.id, "测试原型")
        assert pp.id is not None
        assert pp.name == "测试原型"
        assert pp.source == "mockingbot"

    def test_create_without_iteration(self, db, test_project):
        pp = create_ui_prototype_project(
            db, test_project.id, "无迭代原�?, iteration_id=None
        )
        assert pp.iteration_id is None


class TestGetUIPrototypeProjectsByProject:
    def test_basic_query(self, db, test_project, testUser, proto_project):
        pps = get_ui_prototype_projects_by_project(
            db, test_project.id, testUser.id
        )
        assert len(pps) >= 1

    def test_iteration_null_filter(self, db, test_project, testUser):
        create_ui_prototype_project(
            db, test_project.id, "无迭�?, iteration_id=None
        )
        pps = get_ui_prototype_projects_by_project(
            db, test_project.id, testUser.id, iteration_id=0
        )
        assert all(pp.iteration_id is None for pp in pps)


class TestGetUIPrototypeProjectsCount:
    def test_count(self, db, test_project, testUser):
        create_ui_prototype_project(db, test_project.id, "P1")
        create_ui_prototype_project(db, test_project.id, "P2")
        count = get_ui_prototype_projects_count(db, test_project.id, testUser.id)
        assert count >= 2


class TestUpdatePrototypeProjectStats:
    def test_update_with_screens(self, db, test_project, proto_project):
        create_ui_screen(
            db, test_project.id, "原型1", "页面1",
            prototype_project_id=proto_project.id
        )
        screen2 = create_ui_screen(
            db, test_project.id, "原型1", "页面2",
            prototype_project_id=proto_project.id
        )
        screen2.parse_status = "completed"
        db.commit()
        result = update_prototype_project_stats(db, proto_project.id)
        assert result is not None
        assert result.screen_count == 2
        assert result.parsed_count == 1
        assert result.parse_status == "partial"

    def test_all_completed(self, db, test_project, proto_project):
        s1 = create_ui_screen(
            db, test_project.id, "原型1", "页面1",
            prototype_project_id=proto_project.id
        )
        s1.parse_status = "completed"
        db.commit()
        result = update_prototype_project_stats(db, proto_project.id)
        assert result.parse_status == "completed"

    def test_none_completed(self, db, test_project, proto_project):
        create_ui_screen(
            db, test_project.id, "原型1", "页面1",
            prototype_project_id=proto_project.id
        )
        result = update_prototype_project_stats(db, proto_project.id)
        assert result.parse_status == "pending"

    def test_nonexistent_project(self, db, test_project):
        result = update_prototype_project_stats(db, 99999)
        assert result is None


class TestUpdatePrototypeProjectMergedFlow:
    def test_update_flow(self, db, test_project, proto_project):
        flow = {"nodes": ["A", "B"], "edges": [["A", "B"]]}
        result = update_prototype_project_merged_flow(db, proto_project.id, flow)
        assert result is not None
        assert result.merged_flow == flow

    def test_nonexistent(self, db, test_project):
        result = update_prototype_project_merged_flow(db, 99999, {})
        assert result is None


# ================= UI Prototype Screen Query =================


class TestGetUIScreenById:
    def test_found(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "页面A")
        result = get_ui_screen_by_id(db, screen.id)
        assert result is not None

    def test_with_project_filter(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "页面B")
        result = get_ui_screen_by_id(db, screen.id, test_project.id)
        assert result is not None
        result2 = get_ui_screen_by_id(db, screen.id, 99999)
        assert result2 is None


class TestGetUIScreensByProject:
    def test_basic_query(self, db, test_project, testUser):
        create_ui_screen(db, test_project.id, "原型", "页面1")
        create_ui_screen(db, test_project.id, "原型", "页面2")
        screens = get_ui_screens_by_project(db, test_project.id, testUser.id)
        assert len(screens) == 2

    def test_filter_by_parse_status(self, db, test_project, testUser):
        s1 = create_ui_screen(db, test_project.id, "原型", "已完�?)
        s1.parse_status = "completed"
        db.commit()
        create_ui_screen(db, test_project.id, "原型", "待解�?)
        screens = get_ui_screens_by_project(
            db, test_project.id, testUser.id, parse_status="completed"
        )
        assert len(screens) == 1


class TestGetUIScreensCount:
    def test_count(self, db, test_project, testUser):
        create_ui_screen(db, test_project.id, "原型", "页面1")
        create_ui_screen(db, test_project.id, "原型", "页面2")
        count = get_ui_screens_count(db, test_project.id, testUser.id)
        assert count == 2


class TestGetTestCasesByScreen:
    def test_empty(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "空页�?)
        case_ids = get_test_cases_by_screen(db, screen.id)
        assert case_ids == []

    def test_with_links(self, db, test_project, test_case_obj):
        screen = create_ui_screen(db, test_project.id, "原型", "有链接页�?)
        link_ui_screen_to_test_case(db, screen.id, test_case_obj.id)
        case_ids = get_test_cases_by_screen(db, screen.id)
        assert test_case_obj.id in case_ids


class TestGetParsedUIScreensForCaseGeneration:
    def test_returns_parsed_only(self, db, test_project, testUser):
        s1 = create_ui_screen(db, test_project.id, "原型", "已解�?)
        s1.parse_status = "completed"
        s1.review_status = "approved"
        db.commit()
        create_ui_screen(db, test_project.id, "原型", "待解�?)
        screens = get_parsed_ui_screens_for_case_generation(
            db, test_project.id, testUser.id
        )
        assert len(screens) == 1

    def test_approved_only(self, db, test_project, testUser):
        s1 = create_ui_screen(db, test_project.id, "原型", "已审�?)
        s1.parse_status = "completed"
        s1.review_status = "approved"
        db.commit()
        s2 = create_ui_screen(db, test_project.id, "原型", "已拒�?)
        s2.parse_status = "completed"
        s2.review_status = "rejected"
        db.commit()
        screens = get_parsed_ui_screens_for_case_generation(
            db, test_project.id, testUser.id, approved_only=True
        )
        assert len(screens) == 1

    def test_all_including_rejected(self, db, test_project, testUser):
        s1 = create_ui_screen(db, test_project.id, "原型", "已拒�?)
        s1.parse_status = "completed"
        s1.review_status = "rejected"
        db.commit()
        screens = get_parsed_ui_screens_for_case_generation(
            db, test_project.id, testUser.id, approved_only=False
        )
        assert len(screens) == 1


# ================= UI Prototype Screen Mutate =================


class TestCreateUIScreen:
    def test_create_basic(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "页面")
        assert screen.id is not None
        assert screen.parse_status == "pending"
        assert screen.file_type == "png"

    def test_create_with_all_fields(self, db, test_project, proto_project, testUser):
        screen = create_ui_screen(
            db, test_project.id, "原型", "完整页面",
            original_file_path="/screens/1.png",
            original_file_name="1.png",
            file_type="jpg",
            file_size=2048,
            screen_order=5,
            created_by=testUser.id,
            prototype_project_id=proto_project.id,
        )
        assert screen.file_type == "jpg"
        assert screen.file_size == 2048
        assert screen.screen_order == 5


class TestUpdateUIScreenParseResult:
    def test_update_success(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "解析页面")
        result = update_ui_screen_parse_result(
            db, screen.id,
            ui_spec={"elements": []},
            parse_model="gpt-4o",
            summary="登录页面",
            element_count=5,
            button_count=2,
            input_count=1,
        )
        assert result is not None
        assert result.parse_status == "completed"
        assert result.parse_model == "gpt-4o"
        assert result.parse_error is None
        assert result.element_count == 5

    def test_nonexistent(self, db, test_project):
        result = update_ui_screen_parse_result(
            db, 99999, ui_spec={}, parse_model="gpt-4o"
        )
        assert result is None


class TestUpdateUIScreenParseStatus:
    def test_set_processing(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "处理�?)
        result = update_ui_screen_parse_status(db, screen.id, "processing")
        assert result.parse_status == "processing"

    def test_set_failed(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "失败")
        result = update_ui_screen_parse_status(
            db, screen.id, "failed", error_message="timeout"
        )
        assert result.parse_status == "failed"
        assert result.parse_error == "timeout"

    def test_nonexistent(self, db, test_project):
        result = update_ui_screen_parse_status(db, 99999, "processing")
        assert result is None


class TestUpdateUIScreenReview:
    def test_approve(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "审核页面")
        result = update_ui_screen_review(
            db, screen.id, "approved", reviewer="admin"
        )
        assert result.review_status == "approved"
        assert result.reviewed_by == "admin"

    def test_reject_with_comment(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "拒绝页面")
        result = update_ui_screen_review(
            db, screen.id, "rejected",
            reviewer="admin", review_comment="解析不准�?
        )
        assert result.review_status == "rejected"
        assert result.review_comment == "解析不准�?

    def test_nonexistent(self, db, test_project):
        result = update_ui_screen_review(db, 99999, "approved")
        assert result is None


class TestDeleteUIScreen:
    def test_delete_success(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "删除页面")
        result = delete_ui_screen(db, screen.id)
        assert result is True
        assert get_ui_screen_by_id(db, screen.id) is None

    def test_delete_cascades_links(self, db, test_project, test_case_obj):
        screen = create_ui_screen(db, test_project.id, "原型", "级联删除")
        link_ui_screen_to_test_case(db, screen.id, test_case_obj.id)
        result = delete_ui_screen(db, screen.id)
        assert result is True
        case_ids = get_test_cases_by_screen(db, screen.id)
        assert case_ids == []

    def test_delete_nonexistent(self, db, test_project):
        result = delete_ui_screen(db, 99999)
        assert result is False


class TestLinkUIScreenToTestCase:
    def test_create_link(self, db, test_project, test_case_obj):
        screen = create_ui_screen(db, test_project.id, "原型", "链接页面")
        link = link_ui_screen_to_test_case(db, screen.id, test_case_obj.id)
        assert link.screen_id == screen.id
        assert link.test_case_id == test_case_obj.id
        assert link.link_type == "source"

    def test_idempotent_update(self, db, test_project, test_case_obj):
        screen = create_ui_screen(db, test_project.id, "原型", "幂等页面")
        link1 = link_ui_screen_to_test_case(db, screen.id, test_case_obj.id, "source")
        link2 = link_ui_screen_to_test_case(db, screen.id, test_case_obj.id, "verified")
        assert link2.link_type == "verified"
        case_ids = get_test_cases_by_screen(db, screen.id)
        assert len(case_ids) == 1


class TestUpdateUIScreenOrder:
    def test_update_order(self, db, test_project):
        screen = create_ui_screen(db, test_project.id, "原型", "排序页面")
        result = update_ui_screen_order(db, screen.id, 5)
        assert result is not None
        assert result.screen_order == 5

    def test_nonexistent(self, db, test_project):
        result = update_ui_screen_order(db, 99999, 5)
        assert result is None


class TestBatchCreateUIScreens:
    def test_batch_create(self, db, test_project):
        screens_data = [
            {"prototype_name": "原型1", "screen_name": "页面1", "file_path": "/1.png"},
            {"prototype_name": "原型1", "screen_name": "页面2", "file_path": "/2.png"},
        ]
        screens = batch_create_ui_screens(db, test_project.id, screens_data)
        assert len(screens) == 2
        for s in screens:
            assert s.id is not None
            assert s.parse_status == "pending"

    def test_batch_with_defaults(self, db, test_project):
        screens_data = [{}]
        screens = batch_create_ui_screens(db, test_project.id, screens_data)
        assert len(screens) == 1
        assert screens[0].prototype_name == "未命�?
        assert screens[0].screen_name == "屏幕"
        assert screens[0].file_type == "png"

    def test_batch_with_file_name_default(self, db, test_project):
        screens_data = [{"file_name": "login.png"}]
        screens = batch_create_ui_screens(db, test_project.id, screens_data)
        assert screens[0].screen_name == "login.png"

    def test_batch_empty(self, db, test_project):
        screens = batch_create_ui_screens(db, test_project.id, [])
        assert len(screens) == 0
