import pytest
from app.pipelines.steps._scoring import (
    _score_title,
    _score_steps,
    _score_expected_result,
    _score_precondition,
    _extract_step_number,
)


class TestScoreTitle:
    def test_empty_title(self):
        assert _score_title("") == 0.0

    def test_whitespace_title(self):
        assert _score_title("   ") == 0.0

    def test_vague_title_function_test(self):
        assert _score_title("功能验证") == 5.0

    def test_vague_title_ui_test(self):
        assert _score_title("UI测试") == 5.0

    def test_vague_title_interface_test(self):
        assert _score_title("接口测试") == 5.0

    def test_short_good_title(self):
        result = _score_title("登录验证")
        assert result >= 5.0

    def test_medium_good_title(self):
        result = _score_title("验证用户登录后跳转首页")
        assert result >= 5.0

    def test_long_title(self):
        result = _score_title("这是一个非常长的测试用例标题超过四十个字符的测试用例标题")
        assert result >= 5.0

    def test_none_title(self):
        assert _score_title(None) == 0.0


class TestExtractStepNumber:
    def test_none_step(self):
        assert _extract_step_number({}) is None

    def test_int_step(self):
        assert _extract_step_number({"step": 3}) == 3

    def test_string_step(self):
        assert _extract_step_number({"step": "5"}) == 5

    def test_string_with_prefix(self):
        assert _extract_step_number({"step": "步骤3"}) == 3

    def test_invalid_string(self):
        assert _extract_step_number({"step": "abc"}) is None


class TestScoreSteps:
    def test_empty_steps(self):
        assert _score_steps([]) == 0.0

    def test_none_steps(self):
        assert _score_steps(None) == 0.0

    def test_string_steps(self):
        assert _score_steps("step1: click") == 5.0

    def test_single_step(self):
        assert _score_steps([{"action": "click", "expected_result": "ok"}]) == 5.0

    def test_two_complete_steps(self):
        steps = [
            {"action": "click", "expected_result": "ok"},
            {"action": "input", "expected_result": "done"},
        ]
        result = _score_steps(steps)
        assert result > 0

    def test_incomplete_steps(self):
        steps = [
            {"action": "click"},
            {"expected_result": "ok"},
        ]
        result = _score_steps(steps)
        assert result >= 0

    def test_many_complete_steps(self):
        steps = [
            {"action": f"action{i}", "expected_result": f"result{i}"}
            for i in range(5)
        ]
        result = _score_steps(steps)
        assert result > 15

    def test_missing_step_numbers(self):
        steps = [
            {"action": "a1", "expected_result": "r1", "step": 1},
            {"action": "a2", "expected_result": "r2", "step": 5},
        ]
        result = _score_steps(steps)
        assert result >= 0

    def test_ui_automation_manual_judgment(self):
        steps = [
            {
                "action": "人工判断页面是否美观",
                "expected_result": "ok",
            },
        ]
        result = _score_steps(steps, case_type="ui_automation")
        assert result >= 0


class TestScoreExpectedResult:
    def test_empty(self):
        assert _score_expected_result("") == 0.0

    def test_whitespace(self):
        assert _score_expected_result("   ") == 0.0

    def test_vague_result(self):
        assert _score_expected_result("页面正常") == 5.0

    def test_vague_normal(self):
        assert _score_expected_result("功能正常") == 5.0

    def test_quantifiable_result(self):
        assert _score_expected_result("显示3条记录") == 25.0

    def test_specific_result(self):
        result = _score_expected_result("跳转到首页")
        assert result == 25.0

    def test_error_code_result(self):
        assert _score_expected_result("返回错误码404") == 25.0

    def test_generic_result(self):
        result = _score_expected_result("按钮变为可用状态")
        assert 0 < result <= 25.0


class TestScorePrecondition:
    def test_empty(self):
        assert _score_precondition("") == 0.0

    def test_whitespace(self):
        assert _score_precondition("   ") == 0.0

    def test_network_only(self):
        result = _score_precondition("设备网络正常")
        assert result >= 10.0

    def test_login_only(self):
        assert _score_precondition("账号已登录") == 15.0

    def test_network_and_login(self):
        assert _score_precondition("已登录、网络正常") == 20.0

    def test_all_three(self):
        assert _score_precondition("已登录、网络正常、管理员权限") == 25.0

    def test_with_env_info(self):
        result = _score_precondition("Chrome浏览器、已登录")
        assert result >= 15.0

    def test_no_keywords(self):
        assert _score_precondition("测试数据准备") == 5.0
