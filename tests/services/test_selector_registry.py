import pytest
from app.services.selector_registry import SelectorRegistry


class TestSelectorRegistrySingleton:
    def test_singleton_returns_same_instance(self):
        a = SelectorRegistry()
        b = SelectorRegistry()
        assert a is b


class TestMatchKeyword:
    def setup_method(self):
        self.registry = SelectorRegistry()

    def test_match_username(self):
        result = self.registry._match_keyword("输入用户名")
        assert result == "用户名"

    def test_match_password(self):
        result = self.registry._match_keyword("输入密码")
        assert result == "密码"

    def test_match_login_button(self):
        result = self.registry._match_keyword("点击登录")
        assert result == "登录按钮"

    def test_match_english_username(self):
        result = self.registry._match_keyword("enter username")
        assert result == "用户名"

    def test_match_english_password(self):
        result = self.registry._match_keyword("enter password")
        assert result == "密码"

    def test_no_match(self):
        result = self.registry._match_keyword("随机操作")
        assert result is None

    def test_match_captcha(self):
        result = self.registry._match_keyword("输入验证码")
        assert result == "验证码"

    def test_match_submit(self):
        result = self.registry._match_keyword("点击提交")
        assert result == "提交按钮"

    def test_match_save(self):
        result = self.registry._match_keyword("保存数据")
        assert result == "保存按钮"


class TestGetSelector:
    def setup_method(self):
        self.registry = SelectorRegistry()

    def test_get_selector_known_page(self):
        result = self.registry.get_selector("洪恩管理系统", "输入用户名")
        assert result is not None
        assert "input" in result

    def test_get_selector_default_page(self):
        result = self.registry.get_selector(None, "输入用户名")
        assert result is not None

    def test_get_selector_unknown_page_falls_to_default(self):
        result = self.registry.get_selector("未知页面", "输入用户名")
        assert result is not None

    def test_get_selector_unknown_action(self):
        result = self.registry.get_selector("洪恩管理系统", "随机操作")
        assert result is None


class TestGetAllSelectors:
    def setup_method(self):
        self.registry = SelectorRegistry()

    def test_get_all_default(self):
        result = self.registry.get_all_selectors()
        assert "用户名" in result
        assert "密码" in result

    def test_get_all_known_page_merges_default(self):
        result = self.registry.get_all_selectors("洪恩管理系统")
        assert "用户名" in result
        assert "密码" in result

    def test_get_all_unknown_page_returns_default(self):
        result = self.registry.get_all_selectors("不存在的页面")
        assert "用户名" in result


class TestRegisterSelector:
    def setup_method(self):
        self.registry = SelectorRegistry()

    def test_register_new_page(self):
        self.registry.register_selector("新页面", "搜索框", "input[type=search]")
        result = self.registry.get_selector("新页面", "搜索框")
        assert result is None

    def test_register_overwrites_existing(self):
        self.registry.register_selector("default", "用户名", "input[new]")
        result = self.registry.get_selector("default", "输入用户名")
        assert result == "input[new]"


class TestRegisterKeywordAlias:
    def setup_method(self):
        self.registry = SelectorRegistry()

    def test_register_new_alias(self):
        self.registry.register_keyword_alias("用户名", "账号名")
        result = self.registry._match_keyword("输入账号名")
        assert result == "用户名"

    def test_register_duplicate_alias_ignored(self):
        self.registry.register_keyword_alias("用户名", "账号")
        self.registry.register_keyword_alias("用户名", "账号")
        result = self.registry._match_keyword("输入账号")
        assert result == "用户名"
