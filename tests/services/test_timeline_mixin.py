import pytest
from app.services.execution_replay.timeline_mixin import TimelineMixin
from app.services.execution_replay.models import ReplayEventType


class TestMapActionToEventType:
    def test_navigate_chinese(self):
        assert TimelineMixin._map_action_to_event_type("导航到首页") == ReplayEventType.NAVIGATE

    def test_navigate_english(self):
        assert TimelineMixin._map_action_to_event_type("navigate to page") == ReplayEventType.NAVIGATE

    def test_visit_chinese(self):
        assert TimelineMixin._map_action_to_event_type("访问页面") == ReplayEventType.NAVIGATE

    def test_input_chinese(self):
        assert TimelineMixin._map_action_to_event_type("输入用户名") == ReplayEventType.INPUT

    def test_fill_chinese(self):
        assert TimelineMixin._map_action_to_event_type("填写密码") == ReplayEventType.INPUT

    def test_input_english(self):
        assert TimelineMixin._map_action_to_event_type("input text") == ReplayEventType.INPUT

    def test_verify_chinese(self):
        assert TimelineMixin._map_action_to_event_type("验证结果") == ReplayEventType.VERIFY

    def test_check_chinese(self):
        assert TimelineMixin._map_action_to_event_type("检查状态") == ReplayEventType.VERIFY

    def test_verify_english(self):
        assert TimelineMixin._map_action_to_event_type("verify result") == ReplayEventType.VERIFY

    def test_wait_chinese(self):
        assert TimelineMixin._map_action_to_event_type("等待加载") == ReplayEventType.WAIT

    def test_wait_english(self):
        assert TimelineMixin._map_action_to_event_type("wait for element") == ReplayEventType.WAIT

    def test_scroll_chinese(self):
        assert TimelineMixin._map_action_to_event_type("滚动页面") == ReplayEventType.SCROLL

    def test_scroll_english(self):
        assert TimelineMixin._map_action_to_event_type("scroll down") == ReplayEventType.SCROLL

    def test_hover_chinese(self):
        assert TimelineMixin._map_action_to_event_type("悬停菜单") == ReplayEventType.HOVER

    def test_hover_english(self):
        assert TimelineMixin._map_action_to_event_type("hover element") == ReplayEventType.HOVER

    def test_select_chinese(self):
        assert TimelineMixin._map_action_to_event_type("选择选项") == ReplayEventType.SELECT

    def test_select_english(self):
        assert TimelineMixin._map_action_to_event_type("select option") == ReplayEventType.SELECT

    def test_click_chinese(self):
        assert TimelineMixin._map_action_to_event_type("点击按钮") == ReplayEventType.CLICK

    def test_click_english(self):
        assert TimelineMixin._map_action_to_event_type("click button") == ReplayEventType.CLICK

    def test_unknown_defaults_to_click(self):
        assert TimelineMixin._map_action_to_event_type("拖拽元素") == ReplayEventType.CLICK

    def test_empty_action(self):
        assert TimelineMixin._map_action_to_event_type("") == ReplayEventType.CLICK
