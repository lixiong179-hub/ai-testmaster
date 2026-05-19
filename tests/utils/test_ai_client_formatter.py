import pytest
from app.utils.ai_client_formatter import normalize_new_format, normalize_old_format


def _make_new_case(**overrides):
    base = {
        "title": "测试用例1",
        "module": "登录模块",
        "precondition": "已打开登录页",
        "case_type": "",
        "test_category": None,
        "priority": "P2",
        "expected_result": "",
        "test_data": {},
        "steps": [
            {
                "step": "1",
                "action": "输入用户名",
                "action_type": "input",
                "input_value": "admin",
                "target_element": "用户名输入框",
                "expected_result": "用户名显示对应值",
            }
        ],
        "expected_results": ["用户名显示对应值"],
    }
    base.update(overrides)
    return base


def _make_old_case(**overrides):
    base = {
        "title": "旧格式用例",
        "module": "注册模块",
        "precondition": "已打开注册页",
        "case_type": "",
        "test_category": None,
        "priority": 2,
        "expected_result": "注册成功",
        "test_data": {},
        "steps": [
            {
                "step": 1,
                "action": "输入邮箱",
                "description": "",
                "expected_result": "邮箱显示对应值",
            }
        ],
    }
    base.update(overrides)
    return base


class TestNormalizeNewFormatBasic:
    def test_basic_normalization(self):
        case = _make_new_case()
        result = normalize_new_format(case)
        assert result["title"] == "测试用例1"
        assert result["module"] == "登录模块"
        assert result["precondition"] == "已打开登录页"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["action_type"] == "input"
        assert result["steps"][0]["input_value"] == "admin"

    def test_empty_steps(self):
        case = _make_new_case(steps=[], expected_results=[])
        result = normalize_new_format(case)
        assert result["steps"] == []

    def test_missing_optional_fields(self):
        case = {"title": "最小用例"}
        result = normalize_new_format(case)
        assert result["title"] == "最小用例"
        assert result["module"] == ""
        assert result["precondition"] == ""
        assert result["priority"] == "P2"
        assert result["steps"] == []


class TestNormalizeNewFormatActionType:
    def test_action_type_preserved_when_present(self):
        case = _make_new_case(steps=[{"step": "1", "action": "点击按钮", "action_type": "click"}])
        result = normalize_new_format(case)
        assert result["steps"][0]["action_type"] == "click"

    def test_action_type_inferred_when_empty(self):
        case = _make_new_case(steps=[{"step": "1", "action": "输入用户名", "action_type": ""}])
        result = normalize_new_format(case)
        assert result["steps"][0]["action_type"] == "input"

    def test_action_type_inferred_when_missing(self):
        case = _make_new_case(steps=[{"step": "1", "action": "点击提交"}])
        result = normalize_new_format(case)
        assert result["steps"][0]["action_type"] == "click"


class TestNormalizeNewFormatInputValue:
    def test_input_value_extracted_from_expected(self):
        case = _make_new_case(
            steps=[{"step": "1", "action": "输入用户名", "action_type": "input", "input_value": ""}],
            expected_results=["用户名：admin"],
        )
        result = normalize_new_format(case)
        assert result["steps"][0]["input_value"] == "admin"

    def test_input_value_from_action_text(self):
        case = _make_new_case(
            steps=[{"step": "1", "action": "输入：'hello'", "action_type": "input", "input_value": ""}],
            expected_results=[""],
        )
        result = normalize_new_format(case)
        assert result["steps"][0]["input_value"] == "hello"

    def test_select_input_value_from_action_text(self):
        case = _make_new_case(
            steps=[{"step": "1", "action": "选择'选项A'", "action_type": "select", "input_value": ""}],
            expected_results=[""],
        )
        result = normalize_new_format(case)
        assert result["steps"][0]["input_value"] == "选项A"


class TestNormalizeNewFormatExpectedResults:
    def test_expected_results_joined(self):
        case = _make_new_case(
            steps=[
                {"step": "1", "action": "步骤1"},
                {"step": "2", "action": "步骤2"},
            ],
            expected_results=["结果1", "结果2"],
        )
        result = normalize_new_format(case)
        assert "结果1" in result["expected_result"]
        assert "结果2" in result["expected_result"]

    def test_fallback_to_step_expected_result(self):
        case = _make_new_case(
            steps=[{"step": "1", "action": "步骤1", "expected_result": "步骤级预期"}],
            expected_results=[],
        )
        result = normalize_new_format(case)
        assert "步骤级预期" in result["expected_result"]

    def test_step_number_added_to_expected(self):
        case = _make_new_case(
            steps=[{"step": "1", "action": "步骤1"}],
            expected_results=["验证成功"],
        )
        result = normalize_new_format(case)
        assert "1." in result["expected_result"]

    def test_existing_number_not_duplicated(self):
        case = _make_new_case(
            steps=[{"step": "1", "action": "步骤1"}],
            expected_results=["1. 已有编号"],
        )
        result = normalize_new_format(case)
        assert result["expected_result"].strip() == "1. 已有编号"


class TestNormalizeNewFormatCaseType:
    def test_legacy_case_type_converted(self):
        case = _make_new_case(case_type="功能测试")
        result = normalize_new_format(case)
        assert result["case_type"] in ("ui_automation", "manual", "api_automation", "performance", "security")

    def test_valid_case_type_preserved(self):
        case = _make_new_case(case_type="ui_automation", test_category="ui_automation")
        result = normalize_new_format(case)
        assert result["case_type"] == "ui_automation"

    def test_empty_case_type_inferred(self):
        case = _make_new_case(case_type="")
        result = normalize_new_format(case)
        assert result["case_type"] in ("ui_automation", "manual", "api_automation", "performance", "security")

    def test_none_case_type_inferred(self):
        case = _make_new_case(case_type=None)
        result = normalize_new_format(case)
        assert result["case_type"] in ("ui_automation", "manual", "api_automation", "performance", "security")


class TestNormalizeNewFormatDescription:
    def test_description_from_step(self):
        case = _make_new_case(steps=[{"step": "1", "action": "点击按钮", "description": "自定义描述"}])
        result = normalize_new_format(case)
        assert result["steps"][0]["description"] == "自定义描述"

    def test_description_auto_generated(self):
        case = _make_new_case(steps=[{"step": "1", "action": "点击按钮", "description": None}])
        result = normalize_new_format(case)
        assert "点击按钮" in result["steps"][0]["description"]


class TestNormalizeOldFormatBasic:
    def test_basic_normalization(self):
        case = _make_old_case()
        result = normalize_old_format(case)
        assert result["title"] == "旧格式用例"
        assert result["module"] == "注册模块"
        assert len(result["steps"]) == 1

    def test_priority_mapping(self):
        case = _make_old_case(priority=1)
        result = normalize_old_format(case)
        assert result["priority"] == "P0"

    def test_priority_default(self):
        case = _make_old_case(priority=2)
        result = normalize_old_format(case)
        assert result["priority"] == "P2"

    def test_priority_low(self):
        case = _make_old_case(priority=3)
        result = normalize_old_format(case)
        assert result["priority"] == "P3"

    def test_empty_steps(self):
        case = _make_old_case(steps=[])
        result = normalize_old_format(case)
        assert result["steps"] == []


class TestNormalizeOldFormatActionFallback:
    def test_action_fallback_to_description(self):
        case = _make_old_case(steps=[{"step": 1, "action": "", "description": "从描述获取操作", "expected_result": ""}])
        result = normalize_old_format(case)
        assert result["steps"][0]["action"] == "从描述获取操作"

    def test_action_used_when_present(self):
        case = _make_old_case(steps=[{"step": 1, "action": "输入邮箱", "description": "备用描述", "expected_result": ""}])
        result = normalize_old_format(case)
        assert result["steps"][0]["action"] == "输入邮箱"


class TestNormalizeOldFormatInputValue:
    def test_input_value_from_action_text(self):
        case = _make_old_case(steps=[{"step": 1, "action": '输入"用户名"为：admin', "description": "", "expected_result": ""}])
        result = normalize_old_format(case)
        assert result["steps"][0]["input_value"] != ""
        assert "用户名" in result["steps"][0]["input_value"]

    def test_input_value_from_expected(self):
        case = _make_old_case(steps=[{"step": 1, "action": "enter username", "description": "", "expected_result": "用户名：testuser"}])
        result = normalize_old_format(case)
        assert result["steps"][0]["input_value"] == "testuser"


class TestNormalizeOldFormatTargetElement:
    def test_target_element_from_quotes(self):
        case = _make_old_case(steps=[{"step": 1, "action": '点击"提交"按钮', "description": "", "expected_result": ""}])
        result = normalize_old_format(case)
        assert result["steps"][0]["target_element"] == "提交"


class TestNormalizeOldFormatCaseType:
    def test_legacy_case_type_converted(self):
        case = _make_old_case(case_type="接口测试")
        result = normalize_old_format(case)
        assert result["case_type"] in ("ui_automation", "manual", "api_automation", "performance", "security")

    def test_valid_case_type_preserved(self):
        case = _make_old_case(case_type="ui_automation", test_category="ui_automation")
        result = normalize_old_format(case)
        assert result["case_type"] == "ui_automation"


class TestNormalizeOldFormatDescription:
    def test_description_auto_generated(self):
        case = _make_old_case(steps=[{"step": 1, "action": "输入邮箱", "description": "", "expected_result": ""}])
        result = normalize_old_format(case)
        assert "输入邮箱" in result["steps"][0]["description"]

    def test_description_preserved(self):
        case = _make_old_case(steps=[{"step": 1, "action": "输入邮箱", "description": "自定义描述", "expected_result": ""}])
        result = normalize_old_format(case)
        assert result["steps"][0]["description"] == "自定义描述"
