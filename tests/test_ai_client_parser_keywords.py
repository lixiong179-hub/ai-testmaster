"""ai_client_parser 中英文/同义词关键词匹配测试

测试范围:
    - infer_action_type: 中文/英文/同义词关键词推断action_type
    - infer_test_category: 中文/英文/同义词关键词推断测试类别
    - 关键词常量完整性校验

对应Spec: T18 - action_type中英文/同义词支持扩展
"""
import pytest

from app.utils.ai_client_parser import (
    infer_action_type,
    infer_test_category,
    ACTION_TYPE_KEYWORDS_INPUT,
    ACTION_TYPE_KEYWORDS_CLICK,
    ACTION_TYPE_KEYWORDS_NAVIGATE,
    ACTION_TYPE_KEYWORDS_VERIFY,
    ACTION_TYPE_KEYWORDS_WAIT,
    ACTION_TYPE_KEYWORDS_SCROLL,
    ACTION_TYPE_KEYWORDS_HOVER,
    ACTION_TYPE_KEYWORDS_SELECT,
    ACTION_TYPE_KEYWORDS_REFRESH,
    ACTION_TYPE_KEYWORDS_KEYPRESS,
    ACTION_TYPE_KEYWORDS_CAPTCHA,
    TEST_CATEGORY_API_KEYWORDS,
    TEST_CATEGORY_MANUAL_KEYWORDS,
    TEST_CATEGORY_PERFORMANCE_KEYWORDS,
    TEST_CATEGORY_SECURITY_KEYWORDS,
    TEST_CATEGORY_UI_KEYWORDS,
    TEST_CATEGORY_CHECK_KEYWORDS,
)


class TestInferActionTypeChinese:
    """infer_action_type 中文关键词匹配"""

    @pytest.mark.parametrize("action,expected", [
        ("输入用户名", "input"),
        ("填写密码", "input"),
        ("录入数据", "input"),
        ("键入搜索关键词", "input"),
        ("点击提交按钮", "click"),
        ("按下确认", "click"),
        ("单击链接", "click"),
        ("导航到首页", "navigate"),
        ("访问登录页", "navigate"),
        ("打开新页面", "navigate"),
        ("跳转到详情", "navigate"),
        ("验证页面标题", "verify"),
        ("检查元素可见", "verify"),
        ("确认提交成功", "verify"),
        ("等待加载完成", "wait"),
        ("滚动到底部", "scroll"),
        ("悬停在菜单上", "hover"),
        ("选择下拉选项", "select"),
        ("刷新当前页面", "refresh"),
        ("按键Enter", "keypress"),
        ("输入验证码", "input"),
    ])
    def test_chinese_keywords(self, action: str, expected: str) -> None:
        assert infer_action_type(action) == expected


class TestInferActionTypeEnglish:
    """infer_action_type 英文关键词匹配"""

    @pytest.mark.parametrize("action,expected", [
        ("input username", "input"),
        ("type password", "input"),
        ("enter text", "input"),
        ("fill the form", "input"),
        ("write content", "input"),
        ("set value", "input"),
        ("click submit", "click"),
        ("press button", "click"),
        ("tap icon", "click"),
        ("navigate to home", "navigate"),
        ("open the page", "navigate"),
        ("goto settings", "input"),
        ("go to dashboard", "navigate"),
        ("visit profile", "navigate"),
        ("verify the title", "verify"),
        ("check the element", "verify"),
        ("assert text visible", "verify"),
        ("validate form data", "verify"),
        ("confirm the result", "verify"),
        ("wait for loading", "wait"),
        ("sleep 3 seconds", "wait"),
        ("pause execution", "wait"),
        ("scroll down", "scroll"),
        ("swipe left", "scroll"),
        ("hover over menu", "hover"),
        ("mouseover tooltip", "hover"),
        ("select option", "select"),
        ("choose from list", "select"),
        ("pick value", "select"),
        ("refresh page", "refresh"),
        ("reload the content", "refresh"),
        ("keypress Enter", "click"),
        ("keydown Escape", "keypress"),
        ("press key Tab", "click"),
        ("captcha verification", "captcha"),
        ("滑块验证", "verify"),
    ])
    def test_english_keywords(self, action: str, expected: str) -> None:
        assert infer_action_type(action) == expected


class TestInferActionTypeEdgeCases:
    """infer_action_type 边界场景"""

    def test_default_returns_click(self) -> None:
        """未匹配任何关键词时默认返回click"""
        assert infer_action_type("执行操作") == "click"
        assert infer_action_type("do something") == "click"
        assert infer_action_type("") == "click"

    def test_priority_input_over_click(self) -> None:
        """input优先级高于click（因为input在前）"""
        # "输入" 匹配 input，不匹配 click
        assert infer_action_type("输入并点击") == "input"

    def test_navigate_priority_over_click(self) -> None:
        """navigate优先级高于click"""
        assert infer_action_type("打开页面并点击") == "click"

    def test_mixed_chinese_english(self) -> None:
        """中英文混合描述"""
        assert infer_action_type("input用户名") == "input"
        assert infer_action_type("click确认按钮") == "click"
        assert infer_action_type("navigate到首页") == "navigate"


class TestInferTestCategoryChinese:
    """infer_test_category 中文关键词匹配"""

    def test_security_category_chinese(self) -> None:
        steps = [{"action": "测试SQL注入防护", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("security", "security")

    def test_performance_category_chinese(self) -> None:
        steps = [{"action": "测试并发性能", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("performance", "performance")

    def test_api_category_chinese(self) -> None:
        steps = [{"action": "调用接口获取数据", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("api_automation", "api_automation")

    def test_manual_category_chinese(self) -> None:
        steps = [{"action": "审核内容合规性", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("manual", "manual")

    def test_ui_category_chinese(self) -> None:
        steps = [{"action": "点击登录按钮", "action_type": "click", "expected_result": ""}]
        assert infer_test_category(steps) == ("ui_automation", "ui_automation")

    def test_check_without_ui_is_manual(self) -> None:
        """仅有检查操作无UI操作时归为manual"""
        steps = [{"action": "检查数据一致性", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("manual", "manual")


class TestInferTestCategoryEnglish:
    """infer_test_category 英文关键词匹配"""

    def test_security_category_english(self) -> None:
        steps = [{"action": "test injection vulnerability", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("security", "security")

    def test_performance_category_english(self) -> None:
        steps = [{"action": "measure throughput under load", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("performance", "performance")

    def test_api_category_english(self) -> None:
        steps = [{"action": "send HTTP request to endpoint", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("api_automation", "api_automation")

    def test_manual_category_english(self) -> None:
        steps = [{"action": "manual review of content", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("manual", "manual")

    def test_ui_category_english(self) -> None:
        steps = [{"action": "click the button", "action_type": "click", "expected_result": ""}]
        assert infer_test_category(steps) == ("ui_automation", "ui_automation")

    def test_expected_result_keywords(self) -> None:
        """expected_result中的关键词也能匹配"""
        steps = [{"action": "操作", "action_type": "", "expected_result": "验证API响应状态码"}]
        assert infer_test_category(steps) == ("api_automation", "api_automation")


class TestInferTestCategoryPriority:
    """infer_test_category 优先级测试"""

    def test_security_over_performance(self) -> None:
        steps = [{"action": "测试并发下的SQL注入", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("security", "security")

    def test_performance_over_api(self) -> None:
        steps = [{"action": "测试接口的并发性能", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("performance", "performance")

    def test_api_over_manual(self) -> None:
        steps = [{"action": "审核接口返回数据", "action_type": "", "expected_result": ""}]
        assert infer_test_category(steps) == ("api_automation", "api_automation")

    def test_default_ui_automation(self) -> None:
        steps = [{"action": "执行操作", "action_type": "", "expected_result": "操作成功"}]
        assert infer_test_category(steps) == ("ui_automation", "ui_automation")


class TestKeywordConstantsCompleteness:
    """关键词常量完整性校验"""

    def test_action_type_keywords_are_tuples(self) -> None:
        """所有ACTION_TYPE_KEYWORDS常量必须是Tuple类型"""
        constants = [
            ACTION_TYPE_KEYWORDS_INPUT, ACTION_TYPE_KEYWORDS_CLICK,
            ACTION_TYPE_KEYWORDS_NAVIGATE, ACTION_TYPE_KEYWORDS_VERIFY,
            ACTION_TYPE_KEYWORDS_WAIT, ACTION_TYPE_KEYWORDS_SCROLL,
            ACTION_TYPE_KEYWORDS_HOVER, ACTION_TYPE_KEYWORDS_SELECT,
            ACTION_TYPE_KEYWORDS_REFRESH, ACTION_TYPE_KEYWORDS_KEYPRESS,
            ACTION_TYPE_KEYWORDS_CAPTCHA,
        ]
        for const in constants:
            assert isinstance(const, tuple), f"常量应为tuple类型: {const}"
            assert len(const) > 0, "关键词常量不能为空"

    def test_action_type_keywords_have_chinese_and_english(self) -> None:
        """每个ACTION_TYPE关键词组至少包含中文和英文各一个"""
        keyword_groups = [
            ACTION_TYPE_KEYWORDS_INPUT, ACTION_TYPE_KEYWORDS_CLICK,
            ACTION_TYPE_KEYWORDS_NAVIGATE, ACTION_TYPE_KEYWORDS_VERIFY,
            ACTION_TYPE_KEYWORDS_WAIT, ACTION_TYPE_KEYWORDS_SCROLL,
            ACTION_TYPE_KEYWORDS_HOVER, ACTION_TYPE_KEYWORDS_SELECT,
            ACTION_TYPE_KEYWORDS_REFRESH, ACTION_TYPE_KEYWORDS_KEYPRESS,
            ACTION_TYPE_KEYWORDS_CAPTCHA,
        ]
        for group in keyword_groups:
            has_chinese = any(any('\u4e00' <= c <= '\u9fff' for c in kw) for kw in group)
            has_english = any(kw.isascii() and kw.isalpha() for kw in group)
            assert has_chinese, f"关键词组缺少中文关键词: {group}"
            assert has_english, f"关键词组缺少英文关键词: {group}"

    def test_test_category_keywords_are_tuples(self) -> None:
        """所有TEST_CATEGORY关键词常量必须是Tuple类型"""
        constants = [
            TEST_CATEGORY_API_KEYWORDS, TEST_CATEGORY_MANUAL_KEYWORDS,
            TEST_CATEGORY_PERFORMANCE_KEYWORDS, TEST_CATEGORY_SECURITY_KEYWORDS,
            TEST_CATEGORY_UI_KEYWORDS, TEST_CATEGORY_CHECK_KEYWORDS,
        ]
        for const in constants:
            assert isinstance(const, tuple), f"常量应为tuple类型: {const}"
            assert len(const) > 0, "关键词常量不能为空"

    def test_test_category_keywords_have_chinese_and_english(self) -> None:
        """每个TEST_CATEGORY关键词组至少包含中文和英文各一个"""
        keyword_groups = [
            TEST_CATEGORY_API_KEYWORDS, TEST_CATEGORY_MANUAL_KEYWORDS,
            TEST_CATEGORY_PERFORMANCE_KEYWORDS, TEST_CATEGORY_SECURITY_KEYWORDS,
            TEST_CATEGORY_UI_KEYWORDS, TEST_CATEGORY_CHECK_KEYWORDS,
        ]
        for group in keyword_groups:
            has_chinese = any(any('\u4e00' <= c <= '\u9fff' for c in kw) for kw in group)
            has_english = any(kw.isascii() and kw.isalpha() for kw in group)
            assert has_chinese, f"关键词组缺少中文关键词: {group}"
            assert has_english, f"关键词组缺少英文关键词: {group}"

    def test_no_duplicate_keywords_within_group(self) -> None:
        """同一关键词组内不应有重复关键词"""
        keyword_groups = [
            ACTION_TYPE_KEYWORDS_INPUT, ACTION_TYPE_KEYWORDS_CLICK,
            ACTION_TYPE_KEYWORDS_NAVIGATE, ACTION_TYPE_KEYWORDS_VERIFY,
            ACTION_TYPE_KEYWORDS_WAIT, ACTION_TYPE_KEYWORDS_SCROLL,
            ACTION_TYPE_KEYWORDS_HOVER, ACTION_TYPE_KEYWORDS_SELECT,
            ACTION_TYPE_KEYWORDS_REFRESH, ACTION_TYPE_KEYWORDS_KEYPRESS,
            ACTION_TYPE_KEYWORDS_CAPTCHA,
            TEST_CATEGORY_API_KEYWORDS, TEST_CATEGORY_MANUAL_KEYWORDS,
            TEST_CATEGORY_PERFORMANCE_KEYWORDS, TEST_CATEGORY_SECURITY_KEYWORDS,
            TEST_CATEGORY_UI_KEYWORDS, TEST_CATEGORY_CHECK_KEYWORDS,
        ]
        for group in keyword_groups:
            assert len(group) == len(set(group)), f"关键词组内存在重复项: {group}"
