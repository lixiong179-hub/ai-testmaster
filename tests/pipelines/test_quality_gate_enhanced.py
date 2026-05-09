"""T8 评分函数增强 单元测试

覆盖:
    - _score_title: 堆砌词检测
    - _score_steps: 步骤序号连续性检查
    - _score_expected_result: 量化模式扩充（数值范围/最多最少）
    - _score_precondition: 环境声明检测
"""
import pytest

from app.pipelines.steps.quality_gate import (
    _score_title,
    _score_steps,
    _score_expected_result,
    _score_precondition,
)


# ── _score_title 堆砌词检测 ──


class TestScoreTitleVerbStacking:
    def test_normal_title_no_stacking(self):
        """正常标题不受堆砌词影响。"""
        score = _score_title("登录页面输入账号密码验证身份信息")  # 16字 → 25分
        assert score == 25.0

    def test_stacking_long_title(self):
        """连续3个动词短语 + 长度>30字 → 降为15分。"""
        title = "验证登录点击提交弹出确认与关闭交互流程测试用例完整详细步骤描述"
        assert len(title) > 30
        score = _score_title(title)
        assert score == 15.0

    def test_stacking_short_title(self):
        """堆砌词但长度<=30字 → 不触发降分。"""
        title = "验证点击弹出交互"
        assert len(title) <= 30
        score = _score_title(title)
        # 长度<15字 → 10分，不受堆砌影响
        assert score == 10.0

    def test_no_stacking_vague_title(self):
        """模糊标题仍为5分，不受堆砌影响。"""
        score = _score_title("功能验证")
        assert score == 5.0

    def test_empty_title(self):
        score = _score_title("")
        assert score == 0.0

    def test_long_title_no_stacking(self):
        """超长标题(>40字)但无堆砌 → 15分（过长）。"""
        title = "用户在登录页面输入正确的账号和密码后点击登录按钮完成身份认证并进入系统首页查看个人信息和操作记录"
        assert len(title) > 40
        score = _score_title(title)
        assert score == 15.0


# ── _score_steps 步骤序号连续性 ──


class TestScoreStepsSequence:
    def test_continuous_steps(self):
        """步骤序号从1连续递增 → 不扣分。"""
        steps = [
            {"step": 1, "action": "打开页面", "expected_result": "页面显示"},
            {"step": 2, "action": "输入账号", "expected_result": "输入成功"},
            {"step": 3, "action": "点击登录", "expected_result": "登录成功"},
        ]
        score = _score_steps(steps)
        # 3步全完整: 15 + 10*1.0 = 25
        assert score == 25.0

    def test_gap_in_steps(self):
        """步骤序号有缺失 → 扣分。"""
        steps = [
            {"step": 1, "action": "打开页面", "expected_result": "页面显示"},
            {"step": 3, "action": "点击登录", "expected_result": "登录成功"},
        ]
        score = _score_steps(steps)
        # 缺失1个序号 → 扣1分
        assert score < 25.0

    def test_no_step_numbers(self):
        """步骤无序号 → 不扣分（无法检测连续性）。"""
        steps = [
            {"action": "打开页面", "expected_result": "页面显示"},
            {"action": "输入账号", "expected_result": "输入成功"},
            {"action": "点击登录", "expected_result": "登录成功"},
        ]
        score = _score_steps(steps)
        assert score == 25.0

    def test_string_step_numbers(self):
        """步骤序号为字符串格式 "步骤1" → 正确提取。"""
        steps = [
            {"step": "步骤1", "action": "打开页面", "expected_result": "页面显示"},
            {"step": "步骤2", "action": "输入账号", "expected_result": "输入成功"},
        ]
        score = _score_steps(steps)
        # 2步全完整: 10 + 10*1.0 = 20
        assert score == 20.0

    def test_empty_steps(self):
        assert _score_steps([]) == 0.0
        assert _score_steps(None) == 0.0


# ── _score_expected_result 量化模式扩充 ──


class TestScoreExpectedResultQuantifiable:
    def test_numeric_range(self):
        """数值范围 "X~Y之间" → 量化标记 → 25分。"""
        score = _score_expected_result("价格在10~50之间")
        assert score == 25.0

    def test_max_limit(self):
        """最多/不超过 → 量化标记 → 25分。"""
        score = _score_expected_result("最多输入20个字符")
        assert score == 25.0

    def test_min_limit(self):
        """最少/不少于 → 量化标记 → 25分。"""
        score = _score_expected_result("不少于3条记录")
        assert score == 25.0

    def test_not_exceed(self):
        """不超过 → 量化标记 → 25分。"""
        score = _score_expected_result("不超过5次重试")
        assert score == 25.0

    def test_at_least(self):
        """至少 → 量化标记 → 25分。"""
        score = _score_expected_result("至少返回1条数据")
        assert score == 25.0

    def test_vague_result(self):
        """模糊预期 "页面正常" → 5分。"""
        score = _score_expected_result("页面正常显示")
        assert score == 5.0

    def test_empty(self):
        assert _score_expected_result("") == 0.0

    def test_interaction_without_quantifiable(self):
        """有交互描述但无量化 → 15分。"""
        score = _score_expected_result("列表按创建时间排序展示")
        assert score == 15.0

    def test_specific_value(self):
        """具体数值 → 量化标记 → 25分。"""
        score = _score_expected_result("状态码为200")
        assert score == 25.0


# ── _score_precondition 环境声明检测 ──


class TestScorePreconditionEnvDeclaration:
    def test_env_browser(self):
        """声明浏览器类型 → 加2分。"""
        score = _score_precondition("账号已登录，使用Chrome浏览器")
        # has_login=True(15) + env(+2) = 17
        assert score == 17.0

    def test_env_device(self):
        """声明设备型号 → 加2分。"""
        score = _score_precondition("账号已登录，iPhone设备")
        assert score == 17.0

    def test_env_os(self):
        """声明操作系统 → 加2分。"""
        score = _score_precondition("账号已登录，Windows操作系统")
        assert score == 17.0

    def test_no_env(self):
        """无环境声明 → 不加分。"""
        score = _score_precondition("账号已登录，网络正常")
        # has_login + has_network = 20
        assert score == 20.0

    def test_full_precondition_with_env(self):
        """网络+登录+权限+环境 → 25分（已达上限）。"""
        score = _score_precondition("账号已登录，网络正常，管理员权限，Chrome浏览器")
        assert score == 25.0

    def test_env_without_login(self):
        """仅有环境声明无登录 → 5+2=7分。"""
        score = _score_precondition("使用Chrome浏览器打开页面")
        # 无login/network → 5 + env(+2) = 7
        assert score == 7.0

    def test_empty(self):
        assert _score_precondition("") == 0.0
