import pytest
from datetime import datetime
from typing import Dict, Any

from app.utils.test_case_helpers import (
    _build_step_response,
    convert_steps_to_response,
    convert_ai_steps_to_response,
    build_test_case_response,
)


class TestBuildStepResponse:
    def test_basic_step_with_action(self):
        step = {"action": "click", "param": "btn_login", "expected_result": "clicked"}
        result = _build_step_response(step)
        assert result["step"] == "click"
        assert result["action"] == "click"
        assert result["param"] == "btn_login"
        assert result["expected_result"] == "clicked"

    def test_step_with_step_key(self):
        step = {"step": "输入用户名", "param": "admin"}
        result = _build_step_response(step)
        assert result["step"] == "输入用户名"
        assert result["action"] == "输入用户名"

    def test_step_with_description_key(self):
        step = {"description": "验证页面加载", "expected_result": "加载成功"}
        result = _build_step_response(step)
        assert result["step"] == "验证页面加载"
        assert result["action"] == "验证页面加载"

    def test_action_priority_over_step(self):
        step = {"action": "click", "step": "输入用户名"}
        result = _build_step_response(step)
        assert result["step"] == "click"
        assert result["action"] == "click"

    def test_step_priority_over_description(self):
        step = {"step": "输入密码", "description": "验证页面"}
        result = _build_step_response(step)
        assert result["step"] == "输入密码"

    def test_empty_step_uses_default(self):
        result = _build_step_response({})
        assert result["step"] == "执行"
        assert result["action"] == "执行"
        assert result["param"] == ""
        assert result["expected_result"] == ""
        assert result["test_data"] == {}
        assert result["action_type"] == ""
        assert result["input_value"] == ""
        assert result["target_element"] == ""

    def test_with_step_number_param(self):
        step = {"action": "click"}
        result = _build_step_response(step, step_number=3)
        assert result["step_number"] == 3

    def test_with_step_number_in_dict(self):
        step = {"action": "click", "step_number": 5}
        result = _build_step_response(step)
        assert result["step_number"] == 5

    def test_no_step_number(self):
        step = {"action": "click"}
        result = _build_step_response(step)
        assert "step_number" not in result

    def test_step_number_param_overrides_dict(self):
        step = {"action": "click", "step_number": 5}
        result = _build_step_response(step, step_number=3)
        assert result["step_number"] == 3

    def test_all_fields_populated(self):
        step = {
            "action": "input",
            "param": "username",
            "test_data": {"key": "val"},
            "expected_result": "entered",
            "action_type": "text_input",
            "input_value": "admin",
            "target_element": "#username",
        }
        result = _build_step_response(step)
        assert result["test_data"] == {"key": "val"}
        assert result["action_type"] == "text_input"
        assert result["input_value"] == "admin"
        assert result["target_element"] == "#username"


class TestConvertStepsToResponse:
    def test_normal_steps(self):
        steps = [
            {"step": "步骤1", "action": "click", "param": "btn"},
            {"step": "步骤2", "action": "input", "param": "field"},
        ]
        result = convert_steps_to_response(steps)
        assert len(result) == 2
        assert result[0]["step_number"] == 1
        assert result[1]["step_number"] == 2

    def test_empty_list(self):
        assert convert_steps_to_response([]) == []

    def test_none_input(self):
        assert convert_steps_to_response(None) == []

    def test_steps_with_existing_step_number(self):
        steps = [
            {"action": "click", "step_number": 10},
            {"action": "input", "step_number": 20},
        ]
        result = convert_steps_to_response(steps)
        assert result[0]["step_number"] == 10
        assert result[1]["step_number"] == 20

    def test_steps_without_step_number_auto_enumerate(self):
        steps = [
            {"action": "a"},
            {"action": "b"},
            {"action": "c"},
        ]
        result = convert_steps_to_response(steps)
        assert result[0]["step_number"] == 1
        assert result[1]["step_number"] == 2
        assert result[2]["step_number"] == 3


class TestConvertAiStepsToResponse:
    def test_normal_ai_steps(self):
        steps = [
            {"action": "click", "param": "btn1"},
            {"action": "input", "param": "field1"},
        ]
        result = convert_ai_steps_to_response(steps)
        assert len(result) == 2
        assert result[0]["action"] == "click"
        assert result[1]["action"] == "input"

    def test_empty_list(self):
        assert convert_ai_steps_to_response([]) == []

    def test_ai_steps_no_step_number(self):
        steps = [{"action": "click"}]
        result = convert_ai_steps_to_response(steps)
        assert "step_number" not in result[0]


class MockTestCase:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.project_id = kwargs.get("project_id", 100)
        self.case_no = kwargs.get("case_no", "TC-001")
        self.module = kwargs.get("module", "登录模块")
        self.title = kwargs.get("title", "登录测试")
        self.precondition = kwargs.get("precondition", "系统已启动")
        self.steps_json = kwargs.get("steps_json", [{"action": "click", "param": "btn"}])
        self.expected_result = kwargs.get("expected_result", "登录成功")
        self.priority = kwargs.get("priority", 1)
        self.case_type = kwargs.get("case_type", "UI")
        self.test_category = kwargs.get("test_category", None)
        self.exec_script = kwargs.get("exec_script", "")
        self.generate_status = kwargs.get("generate_status", 0)
        self.create_time = kwargs.get("create_time", datetime(2024, 1, 1, 12, 0, 0))


class TestBuildTestCaseResponse:
    def test_full_test_case(self):
        case = MockTestCase()
        result = build_test_case_response(case)
        assert result["id"] == 1
        assert result["project_id"] == 100
        assert result["case_no"] == "TC-001"
        assert result["module"] == "登录模块"
        assert result["title"] == "登录测试"
        assert result["precondition"] == "系统已启动"
        assert len(result["steps"]) == 1
        assert result["expected_result"] == "登录成功"
        assert result["priority"] == 1
        assert result["case_type"] == "UI"
        assert result["create_time"] == "2024-01-01T12:00:00"

    def test_none_create_time(self):
        case = MockTestCase(create_time=None)
        result = build_test_case_response(case)
        assert result["create_time"] is None

    def test_string_create_time(self):
        case = MockTestCase(create_time="2024-06-01")
        result = build_test_case_response(case)
        assert result["create_time"] == "2024-06-01"

    def test_missing_optional_fields(self):
        class MinimalCase:
            id = 1
            project_id = 200
            title = "最小用例"
            priority = 2

        result = build_test_case_response(MinimalCase())
        assert result["id"] == 1
        assert result["case_no"] == ""
        assert result["module"] == ""
        assert result["precondition"] == ""
        assert result["steps"] == []
        assert result["expected_result"] == ""
        assert result["case_type"] == ""
        assert result["test_category"] is None
        assert result["exec_script"] == ""
        assert result["generate_status"] == 0
        assert result["create_time"] is None

    def test_none_steps_json(self):
        case = MockTestCase(steps_json=None)
        result = build_test_case_response(case)
        assert result["steps"] == []

    def test_empty_steps_json(self):
        case = MockTestCase(steps_json=[])
        result = build_test_case_response(case)
        assert result["steps"] == []

    def test_test_category_value(self):
        case = MockTestCase(test_category="functional")
        result = build_test_case_response(case)
        assert result["test_category"] == "functional"
