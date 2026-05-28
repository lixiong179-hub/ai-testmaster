import os
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import pytest
from app.services.xmind_case_parser._classify import TopicNode, _ClassifyMixin
from app.services.xmind_case_parser._parse import _ParseMixin
from app.services.xmind_case_parser._util import _UtilMixin
from app.services.xmind_parser import XmindParseError


XMAP_NS = "urn:xmind:xmap:xmlns:content:2.0"


def _make_xmind_file(content_xml_bytes: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=".xmind")
    os.close(fd)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("content.xml", content_xml_bytes)
    return path


def _build_content_xml(topics_xml: str) -> bytes:
    template = f"""<?xml version="1.0" encoding="UTF-8"?>
    <xmap-content xmlns="{XMAP_NS}">
        <sheet>
            <topic>
                {topics_xml}
            </topic>
        </sheet>
    </xmap-content>"""
    return template.encode("utf-8")


class _ConcreteParser(_ClassifyMixin, _ParseMixin, _UtilMixin):
    MODULE_MAX_LEN = 100
    TITLE_MAX_LEN = 255
    POINT_MAX_LEN = 500


parser = _ConcreteParser()


class TestClassifyTextExtended:
    def test_action_delete(self):
        assert parser._classify_text("删除记录") == "action"

    def test_action_submit(self):
        assert parser._classify_text("提交表单") == "action"

    def test_action_switch(self):
        assert parser._classify_text("切换标签") == "action"

    def test_action_edit(self):
        assert parser._classify_text("编辑内容") == "action"

    def test_action_retry(self):
        assert parser._classify_text("重试操作") == "action"

    def test_expected_success(self):
        assert parser._classify_text("操作成功") == "expected"

    def test_expected_jump(self):
        assert parser._classify_text("跳转到首页") == "expected"

    def test_expected_popup(self):
        assert parser._classify_text("弹窗提示确认") == "action"

    def test_expected_countdown(self):
        assert parser._classify_text("倒计时结束") == "expected"

    def test_condition_default(self):
        assert parser._classify_text("默认配置") == "condition"

    def test_condition_from(self):
        assert parser._classify_text("从首页进入") == "condition"

    def test_condition_support(self):
        assert parser._classify_text("支持多语言") == "condition"

    def test_ignore_see_ui(self):
        assert parser._classify_text("参照UI设计") == "ignore"

    def test_ignore_display_see_ui(self):
        assert parser._classify_text("界面显示见UI") == "ignore"

    def test_numbered_action(self):
        assert parser._classify_text("2、输入密码") == "action"


class TestBuildCaseFromPathExtended:
    def test_only_actions_no_expected(self):
        result = parser._build_case_from_path(
            "模块",
            [TopicNode(title="根"), TopicNode(title="点击按钮")],
        )
        assert result is not None
        assert "结果符合预期" in result["expected_result"]

    def test_only_expected_no_actions(self):
        result = parser._build_case_from_path(
            "模块",
            [TopicNode(title="根"), TopicNode(title="界面显示成功")],
        )
        assert result is not None
        assert "检查并确认" in result["steps"][0]["action"]

    def test_with_notes_in_segments(self):
        result = parser._build_case_from_path(
            "模块",
            [
                TopicNode(title="根"),
                TopicNode(title="点击登录", notes="需要先注册"),
                TopicNode(title="界面显示首页"),
            ],
        )
        assert result is not None
        assert "需要先注册" in result["precondition"]

    def test_condition_before_action(self):
        result = parser._build_case_from_path(
            "模块",
            [
                TopicNode(title="根"),
                TopicNode(title="已登录用户"),
                TopicNode(title="点击退出"),
                TopicNode(title="界面显示登录页"),
            ],
        )
        assert result is not None
        assert "已登录用户" in result["precondition"]

    def test_condition_after_action_deferred(self):
        result = parser._build_case_from_path(
            "模块",
            [
                TopicNode(title="根"),
                TopicNode(title="点击提交"),
                TopicNode(title="有网络连接"),
                TopicNode(title="提交成功"),
            ],
        )
        assert result is not None
        assert "有网络连接" in result["precondition"]

    def test_ignored_text(self):
        result = parser._build_case_from_path(
            "模块",
            [
                TopicNode(title="根"),
                TopicNode(title="界面详见UI"),
                TopicNode(title="点击按钮"),
                TopicNode(title="显示成功"),
            ],
        )
        assert result is not None
        assert result["ignored_count"] == 1

    def test_other_text_before_action(self):
        result = parser._build_case_from_path(
            "模块",
            [
                TopicNode(title="根"),
                TopicNode(title="普通描述文本"),
                TopicNode(title="点击按钮"),
                TopicNode(title="显示成功"),
            ],
        )
        assert result is not None
        assert "普通描述文本" in result["precondition"]

    def test_other_text_after_action(self):
        result = parser._build_case_from_path(
            "模块",
            [
                TopicNode(title="根"),
                TopicNode(title="点击按钮"),
                TopicNode(title="普通描述文本"),
            ],
        )
        assert result is not None
        assert "普通描述文本" in result["expected_result"]

    def test_with_priority(self):
        result = parser._build_case_from_path(
            "模块",
            [
                TopicNode(title="根"),
                TopicNode(title="点击按钮", priority=1),
                TopicNode(title="显示成功"),
            ],
        )
        assert result is not None
        assert result["priority"] == 1

    def test_notes_not_duplicated_in_precondition(self):
        result = parser._build_case_from_path(
            "模块",
            [
                TopicNode(title="根"),
                TopicNode(title="点击按钮", notes="备注A"),
                TopicNode(title="显示成功", notes="备注A"),
            ],
        )
        assert result is not None
        count = result["precondition"].count("备注A")
        assert count == 1


class TestParseWithRealFile:
    def test_parse_simple_case(self):
        topics_xml = f"""
        <children><topics>
            <topic xmlns="{XMAP_NS}"><title>登录模块</title>
                <children><topics>
                    <topic><title>登录功能</title>
                        <children><topics>
                            <topic><title>点击登录按钮</title></topic>
                            <topic><title>界面显示首页</title></topic>
                        </topics></children>
                    </topic>
                </topics></children>
            </topic>
        </topics></children>
        """
        content = _build_content_xml(topics_xml)
        path = _make_xmind_file(content)
        try:
            result = parser.parse(path)
            assert isinstance(result, list)
            assert len(result) >= 1
        finally:
            os.unlink(path)

    def test_parse_bad_zip(self):
        fd, path = tempfile.mkstemp(suffix=".xmind")
        os.write(fd, b"not a zip")
        os.close(fd)
        try:
            with pytest.raises(XmindParseError):
                parser.parse(path)
        finally:
            os.unlink(path)

    def test_parse_missing_content_xml(self):
        fd, path = tempfile.mkstemp(suffix=".xmind")
        os.close(fd)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("other.xml", "<root/>")
        try:
            with pytest.raises(XmindParseError):
                parser.parse(path)
        finally:
            os.unlink(path)

    def test_parse_no_sheet(self):
        content = f'<?xml version="1.0" encoding="UTF-8"?><xmap-content xmlns="{XMAP_NS}"></xmap-content>'
        path = _make_xmind_file(content.encode())
        try:
            with pytest.raises(XmindParseError, match="未找到 sheet"):
                parser.parse(path)
        finally:
            os.unlink(path)

    def test_parse_no_topic(self):
        content = f'<?xml version="1.0" encoding="UTF-8"?><xmap-content xmlns="{XMAP_NS}"><sheet></sheet></xmap-content>'
        path = _make_xmind_file(content.encode())
        try:
            with pytest.raises(XmindParseError, match="未找到根主题"):
                parser.parse(path)
        finally:
            os.unlink(path)

    def test_parse_empty_module(self):
        topics_xml = f"""
        <children><topics>
            <topic xmlns="{XMAP_NS}"><title></title></topic>
        </topics></children>
        """
        content = _build_content_xml(topics_xml)
        path = _make_xmind_file(content)
        try:
            result = parser.parse(path)
            assert result == []
        finally:
            os.unlink(path)


class TestBuildTopicTree:
    def test_simple_tree(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>根</title></topic>'
        topic = ET.fromstring(xml)
        result = parser._build_topic_tree(topic)
        assert result.title == "根"
        assert result.children == []

    def test_tree_with_children(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>根</title><children><topics><topic><title>子</title></topic></topics></children></topic>'
        topic = ET.fromstring(xml)
        result = parser._build_topic_tree(topic)
        assert len(result.children) == 1
        assert result.children[0].title == "子"


class TestLoadAllRootTopics:
    def test_invalid_xml_content(self):
        fd, path = tempfile.mkstemp(suffix=".xmind")
        os.close(fd)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("content.xml", "not valid xml <><>")
        try:
            with pytest.raises(XmindParseError, match="无法解析"):
                parser._load_all_root_topics(path)
        finally:
            os.unlink(path)


class TestInferFunctionNameExtended:
    def test_truncation(self):
        long_text = "a" * 300
        result = parser._infer_function_name(["模块", long_text], "模块")
        assert len(result) <= parser.TITLE_MAX_LEN


class TestInferCaseTitleExtended:
    def test_truncation(self):
        long_action = "a" * 300
        title = parser._infer_case_title(
            ["文本"], [long_action], "预期结果", "模块"
        )
        assert len(title) <= parser.TITLE_MAX_LEN
