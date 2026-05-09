"""ai_recognition_mixin SelectorRegistry 缓存行为测试。
"""
import pytest


class TestSelectorRegistryCache:
    """测试 _get_element_selector 的 SelectorRegistry 缓存行为。"""

    @pytest.fixture
    def mixin(self):
        from app.services.test_execution_engine.ai_recognition_mixin import (
            AIRecognitionMixin,
        )

        instance = AIRecognitionMixin()
        if hasattr(instance, '_selector_registry'):
            del instance._selector_registry
        return instance

    def test_first_call_creates_cache(self, mixin):
        assert not hasattr(mixin, '_selector_registry')
        mixin._get_element_selector("用户名")
        assert hasattr(mixin, '_selector_registry')
        assert mixin._selector_registry is not None

    def test_second_call_reuses_same_instance(self, mixin):
        first_result = mixin._get_element_selector("用户名")
        first_instance = mixin._selector_registry
        second_result = mixin._get_element_selector("密码")
        assert mixin._selector_registry is first_instance
        assert second_result is not None

    def test_cache_persists_across_multiple_calls(self, mixin):
        results = []
        for _ in range(5):
            results.append(mixin._get_element_selector("用户名"))
        instance = mixin._selector_registry
        assert all(r == results[0] for r in results)
        assert instance is not None

    def test_selector_returns_correct_value_for_login(self, mixin):
        selector = mixin._get_element_selector("登录")
        assert selector is not None
        assert "submit" in selector.lower() or "login" in selector.lower()

    def test_selector_returns_none_for_unmatched_text(self, mixin):
        selector = mixin._get_element_selector("不存在的元素描述xyz123")
        assert selector is None
