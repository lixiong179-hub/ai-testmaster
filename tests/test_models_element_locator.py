import pytest
from app.models.element_locator import ElementLocator
from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="loc_test_user",
        email="loc_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(ElementLocator).filter(ElementLocator.step_id.in_(
        db.query(TestStep.id).filter(TestStep.test_case_id.in_(
            db.query(TestCase.id).filter(TestCase.project_id.in_(
                db.query(Project.id).filter(Project.user_id == user.id)
            ))
        ))
    )).delete(synchronize_session=False)
    db.query(TestStep).filter(TestStep.test_case_id.in_(
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
    project = Project(name="定位测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture
def test_case(db, test_project):
    tc = TestCase(
        case_no="TC-LOC-001",
        project_id=test_project.id,
        module="模块",
        title="定位用例",
        precondition="前置",
        steps_json=[],
        expected_result="预期",
        priority=1,
        case_type="UI"
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    yield tc


@pytest.fixture
def test_step(db, test_case):
    step = TestStep(
        test_case_id=test_case.id,
        step_number=1,
        action="点击按钮",
        expected_result="按钮被点�?
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    yield step


class TestElementLocatorModel:
    def test_create_locator(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            element_description="登录按钮",
            element_type="button",
            css_selector="#login-btn"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.id is not None
        assert locator.step_id == test_step.id
        assert locator.element_description == "登录按钮"
        assert locator.element_type == "button"
        assert locator.css_selector == "#login-btn"
        assert locator.created_at is not None
        assert locator.updated_at is not None
        db.delete(locator)
        db.commit()

    def test_locator_default_values(self, db, test_step):
        locator = ElementLocator(step_id=test_step.id)
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.precondition_step_id is None
        assert locator.element_description is None
        assert locator.element_type is None
        assert locator.css_selector is None
        assert locator.xpath is None
        assert locator.element_id is None
        assert locator.element_name is None
        assert locator.element_class is None
        assert locator.element_text is None
        assert locator.ai_coordinate is None
        assert locator.ai_confidence == 0.0
        assert locator.success_count == 0
        assert locator.fail_count == 0
        assert locator.last_used_at is None
        assert locator.source == "ai"
        assert locator.version == 0
        db.delete(locator)
        db.commit()

    def test_locator_with_all_strategies(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            css_selector="#btn",
            xpath="//button[@id='btn']",
            element_id="btn",
            element_name="submit",
            element_class="btn-primary",
            element_text="提交",
            ai_coordinate={"x": 100, "y": 200, "width": 80, "height": 30},
            ai_confidence=0.95
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.css_selector == "#btn"
        assert locator.xpath == "//button[@id='btn']"
        assert locator.element_id == "btn"
        assert locator.element_name == "submit"
        assert locator.ai_confidence == 0.95
        db.delete(locator)
        db.commit()

    def test_priority_order_all(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            css_selector="#btn",
            xpath="//button",
            element_id="btn",
            element_name="submit",
            ai_coordinate={"x": 1, "y": 2, "width": 3, "height": 4}
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.priority_order == ["css", "xpath", "id", "name", "ai"]
        db.delete(locator)
        db.commit()

    def test_priority_order_partial(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            xpath="//button"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.priority_order == ["xpath"]
        db.delete(locator)
        db.commit()

    def test_priority_order_empty(self, db, test_step):
        locator = ElementLocator(step_id=test_step.id)
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.priority_order == []
        db.delete(locator)
        db.commit()

    def test_to_dict(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            css_selector="#btn",
            xpath="//button",
            element_id="btn",
            element_name="submit",
            element_class="cls",
            element_text="文本",
            ai_coordinate={"x": 1, "y": 2, "width": 3, "height": 4},
            ai_confidence=0.9
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        d = locator.to_dict()
        assert d["step_id"] == test_step.id
        assert d["css_selector"] == "#btn"
        assert d["xpath"] == "//button"
        assert d["element_id"] == "btn"
        assert d["element_name"] == "submit"
        assert d["element_class"] == "cls"
        assert d["element_text"] == "文本"
        assert d["ai_confidence"] == 0.9
        assert "priority_order" in d
        db.delete(locator)
        db.commit()

    def test_record_success(self, db, test_step):
        locator = ElementLocator(step_id=test_step.id)
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_success()
        assert locator.success_count == 1
        assert locator.last_used_at is not None
        assert locator.version == 1
        db.delete(locator)
        db.commit()

    def test_record_failure(self, db, test_step):
        locator = ElementLocator(step_id=test_step.id)
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_failure()
        assert locator.fail_count == 1
        assert locator.last_used_at is not None
        assert locator.version == 1
        db.delete(locator)
        db.commit()

    def test_success_rate_zero(self, db, test_step):
        locator = ElementLocator(step_id=test_step.id)
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.success_rate == 0.0
        db.delete(locator)
        db.commit()

    def test_success_rate_calculation(self, db, test_step):
        locator = ElementLocator(step_id=test_step.id, success_count=3, fail_count=1)
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.success_rate == 0.75
        db.delete(locator)
        db.commit()

    def test_get_best_locator_css(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            css_selector="#btn",
            xpath="//button"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        best = locator.get_best_locator()
        assert best == {"type": "css", "value": "#btn"}
        db.delete(locator)
        db.commit()

    def test_get_best_locator_xpath(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            xpath="//button"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        best = locator.get_best_locator()
        assert best == {"type": "xpath", "value": "//button"}
        db.delete(locator)
        db.commit()

    def test_get_best_locator_id(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            element_id="btn"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        best = locator.get_best_locator()
        assert best == {"type": "id", "value": "btn"}
        db.delete(locator)
        db.commit()

    def test_get_best_locator_name(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            element_name="submit"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        best = locator.get_best_locator()
        assert best == {"type": "name", "value": "submit"}
        db.delete(locator)
        db.commit()

    def test_get_best_locator_ai(self, db, test_step):
        locator = ElementLocator(
            step_id=test_step.id,
            ai_coordinate={"x": 100, "y": 200, "width": 80, "height": 30}
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        best = locator.get_best_locator()
        assert best is not None
        assert best["type"] == "ai"
        db.delete(locator)
        db.commit()

    def test_get_best_locator_none(self, db, test_step):
        locator = ElementLocator(step_id=test_step.id)
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.get_best_locator() is None
        db.delete(locator)
        db.commit()

    def test_validate_coordinate_valid(self):
        assert ElementLocator.validate_coordinate({"x": 100, "y": 200, "width": 80, "height": 30}) is True

    def test_validate_coordinate_negative(self):
        assert ElementLocator.validate_coordinate({"x": -1}) is False

    def test_validate_coordinate_non_numeric(self):
        assert ElementLocator.validate_coordinate({"x": "abc"}) is False

    def test_validate_coordinate_not_dict(self):
        assert ElementLocator.validate_coordinate("not a dict") is False

    def test_validate_coordinate_none_value(self):
        assert ElementLocator.validate_coordinate({"x": None}) is True

    def test_validate_coordinate_empty_dict(self):
        assert ElementLocator.validate_coordinate({}) is True

    def test_source_values(self, db, test_step):
        for source in ["ai", "manual", "auto"]:
            locator = ElementLocator(step_id=test_step.id, source=source)
            db.add(locator)
            db.commit()
            db.refresh(locator)
            assert locator.source == source
            db.delete(locator)
            db.commit()

    def test_repr(self, db, test_step):
        locator = ElementLocator(step_id=test_step.id, css_selector="#btn")
        db.add(locator)
        db.commit()
        db.refresh(locator)
        repr_str = repr(locator)
        assert "ElementLocator" in repr_str
        assert str(locator.id) in repr_str
        db.delete(locator)
        db.commit()

    def test_precondition_step_locator(self, db, test_case):
        pre_step = TestCasePreconditionStep(
            test_case_id=test_case.id,
            step_number=1,
            action="打开页面"
        )
        db.add(pre_step)
        db.commit()
        db.refresh(pre_step)
        locator = ElementLocator(
            precondition_step_id=pre_step.id,
            css_selector=".page"
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.precondition_step_id == pre_step.id
        assert locator.step_id is None
        db.delete(locator)
        db.delete(pre_step)
        db.commit()
