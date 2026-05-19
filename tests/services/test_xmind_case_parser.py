import pytest
from app.services.xmind_case_parser._classify import (
    TopicNode,
    _ClassifyMixin,
)
from app.services.xmind_case_parser._parse import _ParseMixin
from app.services.xmind_case_parser._util import _UtilMixin


class _ConcreteParser(_ClassifyMixin, _ParseMixin, _UtilMixin):
    MODULE_MAX_LEN = 100
    TITLE_MAX_LEN = 255
    POINT_MAX_LEN = 500


parser = _ConcreteParser()


class TestTopicNode:
    def test_defaults(self):
        node = TopicNode(title="根")
        assert node.title == "根"
        assert node.priority is None
        assert node.notes == ""
        assert node.children == []

    def test_with_children(self):
        child = TopicNode(title="子")
        node = TopicNode(title="根", children=[child])
        assert len(node.children) == 1
        assert node.children[0].title == "子"


class TestClassifyText:
    def test_action_click(self):
        assert parser._classify_text("点击登录按钮") == "action"

    def test_action_input(self):
        assert parser._classify_text("输入用户名") == "action"

    def test_action_numbered(self):
        assert parser._classify_text("1. 打开页面") == "action"

    def test_expected_display(self):
        assert parser._classify_text("界面显示登录成功") == "expected"

    def test_expected_toast(self):
        assert parser._classify_text("toast提示保存成功") == "expected"

    def test_condition(self):
        assert parser._classify_text("已登录用户") == "condition"

    def test_condition_exists(self):
        assert parser._classify_text("存在订单记录") == "condition"

    def test_ignore_ui_ref(self):
        assert parser._classify_text("界面详见UI设计稿") == "ignore"

    def test_other(self):
        assert parser._classify_text("普通文本描述") == "other"

    def test_empty(self):
        assert parser._classify_text("") == "ignore"

    def test_whitespace(self):
        assert parser._classify_text("   ") == "ignore"


class TestInferCaseTitle:
    def test_with_actions_and_expected(self):
        title = parser._infer_case_title(
            ["文本"], ["点击登录"], "界面显示首页", "模块",
        )
        assert "点击登录" in title
        assert "界面显示首页" in title

    def test_actions_only(self):
        title = parser._infer_case_title(["文本"], ["点击按钮"], "", "模块")
        assert "点击按钮" in title

    def test_expected_only(self):
        title = parser._infer_case_title(["文本"], [], "显示成功", "模块")
        assert "显示成功" in title

    def test_fallback_to_texts(self):
        title = parser._infer_case_title(["回退标题"], [], "", "模块")
        assert "回退标题" in title

    def test_fallback_to_module(self):
        title = parser._infer_case_title([], [], "", "模块名")
        assert "模块名" in title


class TestInferFunctionName:
    def test_with_enough_texts(self):
        result = parser._infer_function_name(["模块", "功能名"], "模块")
        assert result == "功能名"

    def test_insufficient_texts(self):
        result = parser._infer_function_name(["仅一个"], "模块")
        assert result == ""


class TestBuildSteps:
    def test_single_action(self):
        steps = parser._build_steps(["点击登录"], "登录成功")
        assert len(steps) == 1
        assert steps[0]["step"] == 1
        assert steps[0]["action"] == "点击登录"
        assert steps[0]["expected_result"] == "登录成功"

    def test_multiple_actions(self):
        steps = parser._build_steps(["步骤1", "步骤2"], "最终结果")
        assert len(steps) == 2
        assert steps[0]["expected_result"] == ""
        assert steps[1]["expected_result"] == "最终结果"

    def test_empty_actions(self):
        steps = parser._build_steps([], "")
        assert steps == []


class TestInferPriority:
    def test_with_priority(self):
        segments = [TopicNode(title="A"), TopicNode(title="B", priority=1)]
        assert parser._infer_priority(segments) == 1

    def test_no_priority(self):
        segments = [TopicNode(title="A"), TopicNode(title="B")]
        assert parser._infer_priority(segments) == 2

    def test_empty_segments(self):
        assert parser._infer_priority([]) == 2

    def test_last_priority_wins(self):
        segments = [
            TopicNode(title="A", priority=3),
            TopicNode(title="B", priority=1),
        ]
        assert parser._infer_priority(segments) == 1


class TestDedupeCases:
    def test_deduplication(self):
        cases = [
            {
                "module": "M", "title": "T", "precondition": "P",
                "expected_result": "E",
                "steps": [{"action": "A", "expected_result": "E"}],
            },
            {
                "module": "M", "title": "T", "precondition": "P",
                "expected_result": "E",
                "steps": [{"action": "A", "expected_result": "E"}],
            },
        ]
        result = parser._dedupe_cases(cases)
        assert len(result) == 1

    def test_different_cases_kept(self):
        cases = [
            {
                "module": "M1", "title": "T1", "precondition": "P",
                "expected_result": "E",
                "steps": [{"action": "A1", "expected_result": "E"}],
            },
            {
                "module": "M2", "title": "T2", "precondition": "P",
                "expected_result": "E",
                "steps": [{"action": "A2", "expected_result": "E"}],
            },
        ]
        result = parser._dedupe_cases(cases)
        assert len(result) == 2

    def test_empty_list(self):
        result = parser._dedupe_cases([])
        assert result == []


class TestCollectLeafPaths:
    def test_single_node(self):
        node = TopicNode(title="根")
        result = parser._collect_leaf_paths(node)
        assert len(result) == 1
        assert len(result[0]) == 1

    def test_with_children(self):
        node = TopicNode(
            title="根",
            children=[TopicNode(title="子1"), TopicNode(title="子2")],
        )
        result = parser._collect_leaf_paths(node)
        assert len(result) == 2

    def test_deep_tree(self):
        node = TopicNode(
            title="L1",
            children=[TopicNode(title="L2", children=[TopicNode(title="L3")])],
        )
        result = parser._collect_leaf_paths(node)
        assert len(result) == 1
        assert len(result[0]) == 3


class TestBuildCaseFromPath:
    def test_short_path_returns_none(self):
        result = parser._build_case_from_path("模块", [TopicNode(title="仅一个")])
        assert result is None

    def test_empty_titles(self):
        result = parser._build_case_from_path(
            "模块",
            [TopicNode(title=""), TopicNode(title="  ")],
        )
        assert result is None

    def test_normal_path(self):
        result = parser._build_case_from_path(
            "登录模块",
            [TopicNode(title="登录"), TopicNode(title="点击登录"), TopicNode(title="界面显示成功")],
        )
        assert result is not None
        assert result["module"] == "登录模块"
        assert "steps" in result
        assert result["priority"] in (1, 2, 3)


class TestUtilMixin:
    def test_truncate_short(self):
        result = parser._truncate_field("短文本", 100)
        assert result == "短文本"

    def test_truncate_over(self):
        result = parser._truncate_field("a" * 200, 100)
        assert len(result) == 100

    def test_extract_topic_text_no_title(self):
        import xml.etree.ElementTree as ET
        topic = ET.Element("topic")
        result = parser._extract_topic_text(topic)
        assert result == ""

    def test_get_child_topics_no_children(self):
        import xml.etree.ElementTree as ET
        topic = ET.Element("topic")
        result = parser._get_child_topics(topic)
        assert result == []

    def test_extract_priority_no_marker(self):
        import xml.etree.ElementTree as ET
        topic = ET.Element("topic")
        result = parser._extract_priority_marker(topic)
        assert result is None
