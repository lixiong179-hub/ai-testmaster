"""B6d 前置护栏：`xmind` 三处解析拆分前后的行为锁定。

覆盖 AI 响应「代码块 → 原文 → 抠取 → 修复 → 残片」五级容错、XMind 叶子路径到用例的
分类归集（condition/other 依赖「动作是否已出现」）、JSON 主题到 XML 的节点构造。
"""

import xml.etree.ElementTree as ET

import pytest

from app.services.xmind_ai_parser._parsing import _parse_ai_response
from app.services.xmind_case_parser import XmindCaseParser
from app.services.xmind_case_parser._classify import TopicNode
from app.services.xmind_parser import XmindParser

NS = "urn:xmind:xmap:xmlns:content:2.0"


def _node(title, notes="", children=None, priority=None):
    return TopicNode(title=title, priority=priority, notes=notes, children=children or [])


class TestParseAIResponse:
    def test_empty_and_whitespace(self):
        assert _parse_ai_response("", 1) is None
        assert _parse_ai_response("   ", 1) is None

    def test_fenced_block(self):
        assert _parse_ai_response('```json\n[{"title": "A"}]\n```', 1) == [{"title": "A"}]

    def test_embedded_in_prose(self):
        text = '好的，结果如下：\n[{"title": "A"}, {"title": "B"}]\n以上。'
        assert _parse_ai_response(text, 2) == [{"title": "A"}, {"title": "B"}]

    def test_repair_trailing_comma(self):
        assert _parse_ai_response('[{"title": "A"},]', 1) == [{"title": "A"}]

    def test_repair_missing_comma(self):
        assert _parse_ai_response('[{"title": "A"} {"title": "B"}]', 2) == [{"title": "A"}, {"title": "B"}]

    def test_truncated_payload_salvages_partial(self):
        # 尾部被截断时退回「残片抽取」，能救回的用例不丢弃
        assert _parse_ai_response('{"cases": [{"title": "A"}, {"title": "B"', 2) == [{"title": "A"}]

    def test_dict_wrapper_keys(self):
        for key in ("cases", "items", "data", "results"):
            assert _parse_ai_response(f'{{"{key}": [{{"title": "R"}}]}}', 1) == [{"title": "R"}]

    def test_dict_without_wrapper_is_none(self):
        assert _parse_ai_response('{"foo": [1, 2]}', 1) is None

    def test_plain_text_is_none(self):
        assert _parse_ai_response("no json here", 1) is None

    def test_count_mismatch_keeps_data(self):
        # 数量不符只告警，不丢数据（上层依赖「拿回多少算多少」重试）
        assert len(_parse_ai_response('[{"title": "A"}]', 5)) == 1


class TestBuildCaseFromPath:
    def setup_method(self):
        self.parser = XmindCaseParser()

    def test_short_path_returns_none(self):
        assert self.parser._build_case_from_path("M", [_node("root")]) is None

    def test_blank_titles_returns_none(self):
        assert self.parser._build_case_from_path("M", [_node("root"), _node("   ")]) is None

    def test_only_ignored_returns_none(self):
        assert self.parser._build_case_from_path("M", [_node("root"), _node("界面详见UI")]) is None

    def test_condition_before_action_is_precondition(self):
        case = self.parser._build_case_from_path(
            "登录模块", [_node("r"), _node("已有账号"), _node("点击登录"), _node("显示首页")]
        )
        assert case["precondition"] == "已有账号"
        assert case["steps"][0]["action"] == "点击登录"
        assert case["expected_result"] == "显示首页"
        assert case["condition_count"] == 1

    def test_condition_after_action_also_lands_in_precondition(self):
        # 动作出现后的条件先入「延后队列」，最终仍并入前置条件
        case = self.parser._build_case_from_path(
            "登录模块", [_node("r"), _node("点击登录"), _node("已登录状态"), _node("显示首页")]
        )
        assert "已登录状态" in case["precondition"]

    def test_other_text_before_action_is_precondition(self):
        case = self.parser._build_case_from_path(
            "登录模块", [_node("r"), _node("账号密码"), _node("点击登录"), _node("显示首页")]
        )
        assert case["precondition"] == "账号密码"

    def test_no_actions_derives_check_action(self):
        case = self.parser._build_case_from_path("登录模块", [_node("r"), _node("显示首页")])
        assert case["steps"][0]["action"] == "检查并确认：显示首页"
        assert case["expected_result"] == "显示首页"

    def test_no_expectations_uses_fallback_result(self):
        case = self.parser._build_case_from_path("登录模块", [_node("r"), _node("点击登录")])
        assert case["expected_result"] == "点击登录后结果符合预期"

    def test_notes_do_not_duplicate_precondition(self):
        case = self.parser._build_case_from_path(
            "登录模块",
            [_node("r"), _node("已有账号"), _node("点击登录", notes="已有账号"), _node("显示首页")],
        )
        assert case["precondition"] == "已有账号"


class TestJsonTopicToXml:
    def setup_method(self):
        self.parser = XmindParser()

    def test_full_topic(self):
        data = {
            "id": "t1",
            "title": "根",
            "notes": {"plain": {"content": "备注内容"}},
            "markers": [{"markerId": "priority-1"}, {"markerId": ""}],
            "labels": ["L1"],
            "children": {"attached": [{"title": "子1"}], "detached": [{"title": "游离"}]},
        }
        el = self.parser._json_topic_to_xml(data, NS)
        assert el.get("id") == "t1"
        assert el.findtext(f"{{{NS}}}title") == "根"
        assert el.findtext(f"{{{NS}}}notes/{{{NS}}}plain") == "备注内容"
        refs = el.findall(f"{{{NS}}}marker-refs/{{{NS}}}marker-ref")
        assert [r.get("marker-id") for r in refs] == ["priority-1"]  # 空 markerId 被跳过
        assert el.findtext(f"{{{NS}}}labels/{{{NS}}}label") == "L1"
        topics = el.find(f"{{{NS}}}children/{{{NS}}}topics")
        assert topics.get("type") == "attached"
        assert [t.findtext(f"{{{NS}}}title") for t in topics] == ["子1", "游离"]  # attached 在前

    def test_empty_topic(self):
        el = self.parser._json_topic_to_xml({}, NS)
        assert list(el) == []
        assert el.get("id") is None

    def test_notes_without_content_skipped(self):
        el = self.parser._json_topic_to_xml({"notes": {"plain": {}}}, NS)
        assert el.find(f"{{{NS}}}notes") is None

    def test_no_children_element(self):
        el = self.parser._json_topic_to_xml({"title": "T"}, NS)
        assert el.find(f"{{{NS}}}children") is None

    def test_detached_only_children(self):
        el = self.parser._json_topic_to_xml({"children": {"detached": [{"title": "D"}]}}, NS)
        topics = el.find(f"{{{NS}}}children/{{{NS}}}topics")
        assert topics is not None
        assert ET.tostring(topics, encoding="unicode").count("topic") >= 2
