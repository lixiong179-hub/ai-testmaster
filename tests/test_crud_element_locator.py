import pytest
from app.models.element_locator import ElementLocator
from app.models.test_case import TestCase, TestStep
from app.crud.test_case_mutate import create_test_case
from tests.helpers import createTestProject, createTestUser
import uuid


class TestElementLocatorModel:
    def test_create_locator_with_css(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-LOC-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="locator",
            title="locator test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click button",
            expected_result="button clicked",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            element_description="login button",
            element_type="button",
            css_selector="#login-btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.id is not None
        assert locator.css_selector == "#login-btn"
        assert locator.source == "manual"

    def test_create_locator_with_xpath(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-XPATH-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="xpath",
            title="xpath test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click link",
            expected_result="link clicked",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            element_description="navigation link",
            element_type="link",
            xpath="//a[@class='nav-link']",
            source="ai",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.xpath == "//a[@class='nav-link']"

    def test_create_locator_with_element_id(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-ELEMID-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="elemid",
            title="element id test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="input text",
            expected_result="text entered",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            element_description="username input",
            element_type="input",
            element_id="username",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.element_id == "username"

    def test_create_locator_with_ai_coordinate(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-AICOORD-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="aicoord",
            title="ai coordinate test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click area",
            expected_result="area clicked",
        )
        db.add(step)
        db.flush()
        coordinate = {"x": 100, "y": 200, "width": 50, "height": 30}
        locator = ElementLocator(
            step_id=step.id,
            element_description="clickable area",
            element_type="button",
            ai_coordinate=coordinate,
            ai_confidence=0.95,
            source="ai",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.ai_coordinate == coordinate
        assert locator.ai_confidence == 0.95

    def test_locator_default_values(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-DEFAULT-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="default",
            title="default values test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="do something",
            expected_result="done",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            element_description="test element",
            element_type="div",
            source="ai",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.success_count == 0
        assert locator.fail_count == 0
        assert locator.version == 0
        assert locator.source == "ai"


class TestElementLocatorPriorityOrder:
    def test_priority_order_css_and_xpath(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-PRI1-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="priority",
            title="priority order 1",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            xpath="//button",
            element_id="submit",
            element_name="action",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        order = locator.priority_order
        assert "css" in order
        assert "xpath" in order
        assert "id" in order
        assert "name" in order
        assert order[0] == "css"

    def test_priority_order_ai_only(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-PRI2-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="priority",
            title="priority order 2",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            ai_coordinate={"x": 10, "y": 20, "width": 30, "height": 40},
            source="ai",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        order = locator.priority_order
        assert order == ["ai"]

    def test_priority_order_empty(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-PRI3-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="priority",
            title="priority order 3",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            element_description="no locator info",
            element_type="unknown",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        order = locator.priority_order
        assert order == []


class TestElementLocatorRecordSuccessFailure:
    def test_record_success(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-SUCC-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="success",
            title="record success test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_success()
        db.commit()
        db.refresh(locator)
        assert locator.success_count == 1
        assert locator.version == 1
        assert locator.last_used_at is not None

    def test_record_failure(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-FAIL-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="failure",
            title="record failure test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_failure()
        db.commit()
        db.refresh(locator)
        assert locator.fail_count == 1
        assert locator.version == 1

    def test_multiple_success_and_failure(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-MULTI-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="multi",
            title="multi record test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_success()
        locator.record_success()
        locator.record_failure()
        db.commit()
        db.refresh(locator)
        assert locator.success_count == 2
        assert locator.fail_count == 1
        assert locator.version == 3


class TestElementLocatorSuccessRate:
    def test_success_rate_no_usage(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-RATE0-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="rate",
            title="success rate 0",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        assert locator.success_rate == 0.0

    def test_success_rate_all_success(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-RATE1-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="rate",
            title="success rate 100",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_success()
        locator.record_success()
        db.commit()
        db.refresh(locator)
        assert locator.success_rate == 1.0

    def test_success_rate_mixed(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-RATE2-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="rate",
            title="success rate mixed",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        locator.record_success()
        locator.record_failure()
        db.commit()
        db.refresh(locator)
        assert locator.success_rate == 0.5


class TestElementLocatorGetBestLocator:
    def test_best_locator_css(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-BEST1-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="best",
            title="best locator css",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            xpath="//button",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        best = locator.get_best_locator()
        assert best is not None
        assert best["type"] == "css"
        assert best["value"] == ".btn"

    def test_best_locator_xpath_fallback(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-BEST2-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="best",
            title="best locator xpath",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            xpath="//button[@id='x']",
            element_id="x",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        best = locator.get_best_locator()
        assert best is not None
        assert best["type"] == "xpath"

    def test_best_locator_none(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-BEST3-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="best",
            title="best locator none",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            element_description="no locator",
            element_type="unknown",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        best = locator.get_best_locator()
        assert best is None


class TestElementLocatorValidateCoordinate:
    def test_validate_valid_coordinate(self):
        result = ElementLocator.validate_coordinate({"x": 100, "y": 200, "width": 50, "height": 30})
        assert result is True

    def test_validate_coordinate_partial(self):
        result = ElementLocator.validate_coordinate({"x": 100})
        assert result is True

    def test_validate_coordinate_negative(self):
        result = ElementLocator.validate_coordinate({"x": -1})
        assert result is False

    def test_validate_coordinate_non_numeric(self):
        result = ElementLocator.validate_coordinate({"x": "abc"})
        assert result is False

    def test_validate_coordinate_not_dict(self):
        result = ElementLocator.validate_coordinate("not a dict")
        assert result is False

    def test_validate_coordinate_none_values(self):
        result = ElementLocator.validate_coordinate({"x": None, "y": 100})
        assert result is True

    def test_validate_coordinate_empty_dict(self):
        result = ElementLocator.validate_coordinate({})
        assert result is True


class TestElementLocatorToDict:
    def test_to_dict(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-TODICT-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="todict",
            title="to dict test",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            xpath="//button",
            element_id="submit",
            element_name="action",
            element_class="primary",
            element_text="Submit",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        d = locator.to_dict()
        assert d["css_selector"] == ".btn"
        assert d["xpath"] == "//button"
        assert d["element_id"] == "submit"
        assert d["element_name"] == "action"
        assert "priority_order" in d


class TestElementLocatorAtomicOperations:
    def test_atomic_record_success(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-ATOMS-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="atomic",
            title="atomic success",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        result = ElementLocator.atomic_record_success(db, locator.id, locator.version)
        assert result is True
        db.refresh(locator)
        assert locator.success_count == 1

    def test_atomic_record_success_version_mismatch(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-ATOMV-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="atomic",
            title="atomic version mismatch",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        result = ElementLocator.atomic_record_success(db, locator.id, locator.version + 999)
        assert result is False

    def test_atomic_record_failure(self, db, testProject):
        case = create_test_case(
            db=db,
            case_no=f"CASE-ATOMF-{uuid.uuid4().hex[:8]}",
            project_id=testProject.id,
            module="atomic",
            title="atomic failure",
            precondition="none",
            steps=[],
            expected_result="ok",
            priority=2,
            case_type="UI",
        )
        step = TestStep(
            test_case_id=case.id,
            step_number=1,
            action="click",
            expected_result="ok",
        )
        db.add(step)
        db.flush()
        locator = ElementLocator(
            step_id=step.id,
            css_selector=".btn",
            source="manual",
        )
        db.add(locator)
        db.commit()
        db.refresh(locator)
        result = ElementLocator.atomic_record_failure(db, locator.id, locator.version)
        assert result is True
        db.refresh(locator)
        assert locator.fail_count == 1
