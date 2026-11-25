"""B5h 拆分件护栏：步骤级质量校验与 UI 元素名采集。

`validate_steps` 与 `_collect_ui_element_names` 此前只被集成/端到端用例间接覆盖，
拆分（逐步骤校验拆分、递归遍历拆成两个 classmethod）后对其分支直接加锁。
"""

import pytest

from app.services.test_case_generation._quality_step_validators import validate_steps
from app.services.test_case_generation._validator_ui_elements import UIElementValidationMixin as UIElementValidator


def _step(action="点击【登录】按钮", expected="进入首页"):
    return {"action": action, "expected_result": expected}


class TestValidateStepsCount:
    def test_empty_steps(self):
        assert validate_steps([]) == (False, "步骤列表为空")

    def test_single_step_rejected(self):
        ok, reason = validate_steps([_step()])
        assert ok is False
        assert "步骤数不足" in reason

    def test_too_many_steps_rejected(self):
        ok, reason = validate_steps([_step() for _ in range(9)])
        assert ok is False
        assert "步骤数过多" in reason

    def test_minimal_two_steps_pass(self):
        assert validate_steps([_step(), _step()]) == (True, "")

    def test_eight_steps_allowed(self):
        assert validate_steps([_step() for _ in range(8)])[0] is True


class TestValidateStepsText:
    def test_missing_action_reports_step_number(self):
        ok, reason = validate_steps([{"action": " ", "expected_result": "ok"}, _step()])
        assert ok is False
        assert reason == "第1步的 action 为空"

    def test_missing_expected(self):
        ok, reason = validate_steps([{"action": "点击【登录】", "expected_result": ""}, _step()])
        assert ok is False
        assert reason == "第1步的 expected_result 为空"

    def test_reference_to_other_step(self):
        ok, reason = validate_steps([_step(action="参见上一步操作"), _step()])
        assert ok is False
        assert "引用其他步骤或用例" in reason

    def test_uncertain_wording(self):
        ok, reason = validate_steps([_step(action="点击登录或者点击注册"), _step()])
        assert ok is False
        assert "操作不确定" in reason

    def test_inferred_action(self):
        ok, reason = validate_steps([_step(action="可能存在弹窗"), _step()])
        assert ok is False
        assert "推断性措辞" in reason

    def test_inferred_expected(self):
        ok, reason = validate_steps([_step(expected="大概是成功提示"), _step()])
        assert ok is False
        assert "预期结果含推断性措辞" in reason

    def test_action_falls_back_to_description(self):
        ok, reason = validate_steps([{"description": "点击【登录】", "expected_result": "成功"}, _step()])
        assert ok is True


class TestValidateStepsActions:
    def test_click_and_input_mixed(self):
        ok, reason = validate_steps([_step(action="点击用户名输入框并输入admin"), _step()])
        assert ok is False
        assert "混合点击和输入操作" in reason

    def test_manual_judgment_conflicts_with_ui_automation(self):
        ok, reason = validate_steps([_step(action="人工确认提示文案"), _step()], case_type="ui_automation")
        assert ok is False
        assert "人工判断描述" in reason

    def test_manual_judgment_allowed_for_manual_type(self):
        ok, _ = validate_steps([_step(action="人工确认提示文案"), _step()], case_type="manual")
        assert ok is True


class TestCollectUiElementNames:
    def test_screen_name_and_named_elements(self):
        names = UIElementValidator._collect_ui_element_names(
            [
                {
                    "screen_name": "登录页",
                    "ui_spec": {"elements": [{"name": "用户名输入框"}, {"type": "button", "text": "立即登录"}]},
                }
            ]
        )
        assert {"登录页", "用户名输入框", "立即登录"} <= names

    def test_generic_and_short_values_skipped(self):
        names = UIElementValidator._collect_ui_element_names(
            [{"ui_spec": {"elements": [{"name": "按钮"}, {"name": "a"}, {"name": "提交"}]}}]
        )
        assert names == {"提交"}

    def test_nested_lists_and_key_hint(self):
        names = UIElementValidator._collect_ui_element_names(
            [{"ui_spec": {"components": [{"placeholder": "请输入手机号"}]}}]
        )
        assert "请输入手机号" in names

    def test_non_dict_entries_ignored(self):
        assert UIElementValidator._collect_ui_element_names(["bad", 1, None]) == set()

    def test_none_input(self):
        assert UIElementValidator._collect_ui_element_names(None) == set()

    @pytest.mark.parametrize(
        "spec",
        [
            {"ui_spec": {"elements": [{"label": "账号"}]}},
            {"ui_spec": [{"text": "忘记密码"}]},
        ],
    )
    def test_list_and_dict_variants(self, spec):
        assert UIElementValidator._collect_ui_element_names([spec])
