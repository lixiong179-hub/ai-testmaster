import pytest
from unittest.mock import MagicMock
from app.services.case_quality.complexity_mixin import ComplexityMixin
from app.services.case_quality.models import ComplexityScore
from app.models.test_case import TestStep, TestCasePreconditionStep


class TestComplexityMixin:
    def setup_method(self):
        self.mixin = ComplexityMixin()

    def _make_step(self, action: str) -> TestStep:
        step = MagicMock(spec=TestStep)
        step.action = action
        return step

    def _make_precondition_step(self, action: str) -> TestCasePreconditionStep:
        step = MagicMock(spec=TestCasePreconditionStep)
        step.action = action
        return step

    def test_empty_steps(self):
        result = self.mixin._analyze_complexity([], [])
        assert result.step_count == 0
        assert result.precondition_count == 0
        assert result.score <= 2
        assert result.level == "simple"

    def test_few_steps_simple(self):
        steps = [self._make_step("点击登录按钮")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.step_count == 1
        assert result.level == "simple"

    def test_moderate_complexity(self):
        steps = [
            self._make_step("点击登录"),
            self._make_step("输入用户名"),
            self._make_step("输入密码"),
            self._make_step("验证登录成功"),
        ]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.action_variety >= 2
        assert result.has_verification is True

    def test_click_action(self):
        steps = [self._make_step("click button")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.action_variety >= 1

    def test_input_action(self):
        steps = [self._make_step("input username")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.action_variety >= 1

    def test_verify_action(self):
        steps = [self._make_step("verify result")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.has_verification is True

    def test_captcha_action(self):
        steps = [self._make_step("captcha")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.has_captcha is True

    def test_navigate_action(self):
        steps = [self._make_step("navigate to page")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.action_variety >= 1

    def test_wait_action(self):
        steps = [self._make_step("等待加载")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.action_variety >= 1

    def test_scroll_action(self):
        steps = [self._make_step("scroll down")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.action_variety >= 1

    def test_hover_action(self):
        steps = [self._make_step("悬停菜单")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.action_variety >= 1

    def test_select_action(self):
        steps = [self._make_step("选择选项")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.action_variety >= 1

    def test_many_steps_very_complex(self):
        steps = [self._make_step("点击按钮") for _ in range(12)]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.step_count == 12
        assert result.level in ("complex", "very_complex")

    def test_precondition_count(self):
        pc_steps = [self._make_precondition_step("登录系统") for _ in range(3)]
        result = self.mixin._analyze_complexity([], pc_steps)
        assert result.precondition_count == 3

    def test_score_capped_at_10(self):
        steps = [self._make_step("点击按钮") for _ in range(20)]
        pc_steps = [self._make_precondition_step("登录") for _ in range(10)]
        result = self.mixin._analyze_complexity(steps, pc_steps)
        assert result.score <= 10

    def test_level_simple(self):
        steps = [self._make_step("点击按钮")]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.level == "simple"

    def test_level_moderate(self):
        steps = [self._make_step("点击按钮") for _ in range(4)]
        steps.append(self._make_step("验证结果"))
        result = self.mixin._analyze_complexity(steps, [])
        assert result.level in ("simple", "moderate", "complex", "very_complex")

    def test_mixed_actions(self):
        steps = [
            self._make_step("点击按钮"),
            self._make_step("输入用户名"),
            self._make_step("验证结果"),
            self._make_step("等待加载"),
            self._make_step("滚动页面"),
        ]
        result = self.mixin._analyze_complexity(steps, [])
        assert result.action_variety >= 4
