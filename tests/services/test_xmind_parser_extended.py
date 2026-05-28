import os
import tempfile
import zipfile
import xml.etree.ElementTree as ET
import pytest
from app.services.xmind_parser import XmindParser, XmindParseError
from app.services.xmind_parser._parse import _ParseMixin
from app.services.xmind_parser._util import _UtilMixin


XMAP_NS = "urn:xmind:xmap:xmlns:content:2.0"
NS = {"xmap": XMAP_NS}


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


class _ConcreteParser(_ParseMixin, _UtilMixin):
    pass


parser = _ConcreteParser()


class TestXmindParserWithRealFile:
    def test_parse_simple_xmind(self):
        topics_xml = """
        <children><topics>
            <topic><title>模块A</title>
                <children><topics>
                    <topic><title>测试点1</title></topic>
                    <topic><title>测试点2</title></topic>
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
            assert result[0]["module"] == "模块A"
        finally:
            os.unlink(path)

    def test_parse_empty_module(self):
        topics_xml = """
        <children><topics>
            <topic><title></title></topic>
            <topic><title>有效模块</title>
                <children><topics>
                    <topic><title>测试点</title></topic>
                </topics></children>
            </topic>
        </topics></children>
        """
        content = _build_content_xml(topics_xml)
        path = _make_xmind_file(content)
        try:
            result = parser.parse(path)
            assert all(r["module"] != "" for r in result)
        finally:
            os.unlink(path)

    def test_parse_module_without_children(self):
        topics_xml = """
        <children><topics>
            <topic><title>空模块</title></topic>
        </topics></children>
        """
        content = _build_content_xml(topics_xml)
        path = _make_xmind_file(content)
        try:
            result = parser.parse(path)
            assert result == []
        finally:
            os.unlink(path)

    def test_parse_deep_hierarchy(self):
        topics_xml = """
        <children><topics>
            <topic><title>模块</title>
                <children><topics>
                    <topic><title>功能</title>
                        <children><topics>
                            <topic><title>子功能</title>
                                <children><topics>
                                    <topic><title>叶子测试点</title></topic>
                                </topics></children>
                            </topic>
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
            assert len(result) >= 1
        finally:
            os.unlink(path)

    def test_parse_with_priority_markers(self):
        topics_xml = f"""
        <children><topics>
            <topic><title>模块</title>
                <children><topics>
                    <topic><title>测试点</title>
                        <marker-refs><marker-ref xmlns="{XMAP_NS}" marker-id="priority-1"/></marker-refs>
                    </topic>
                </topics></children>
            </topic>
        </topics></children>
        """
        content = _build_content_xml(topics_xml)
        path = _make_xmind_file(content)
        try:
            result = parser.parse(path)
            assert len(result) >= 1
            assert result[0]["priority"] == 1
        finally:
            os.unlink(path)

    def test_parse_with_notes(self):
        topics_xml = f"""
        <children><topics>
            <topic><title>模块</title>
                <children><topics>
                    <topic><title>测试点</title>
                        <notes><plain>这是备注</plain></notes>
                    </topic>
                </topics></children>
            </topic>
        </topics></children>
        """
        content = _build_content_xml(topics_xml)
        path = _make_xmind_file(content)
        try:
            result = parser.parse(path)
            assert len(result) >= 1
            assert "备注" in result[0]["point"]
        finally:
            os.unlink(path)


class TestExtractContentXml:
    def test_bad_zip_file(self):
        fd, path = tempfile.mkstemp(suffix=".xmind")
        os.write(fd, b"not a zip file")
        os.close(fd)
        try:
            with pytest.raises(XmindParseError, match="无效的 XMind 文件格式"):
                parser._extract_content_xml(path)
        finally:
            os.unlink(path)

    def test_missing_content_xml(self):
        fd, path = tempfile.mkstemp(suffix=".xmind")
        os.close(fd)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("other.xml", "<root/>")
        try:
            with pytest.raises(XmindParseError, match="内容缺失"):
                parser._extract_content_xml(path)
        finally:
            os.unlink(path)


class TestParseXml:
    def test_valid_xml(self):
        xml = b'<root xmlns="urn:xmind:xmap:xmlns:content:2.0"><sheet><topic/></sheet></root>'
        result = parser._parse_xml(xml)
        assert result is not None

    def test_invalid_xml(self):
        with pytest.raises(XmindParseError):
            parser._parse_xml(b"<invalid><>")


class TestGetAllRootTopics:
    def test_no_sheet(self):
        root = ET.fromstring(b'<root xmlns="urn:xmind:xmap:xmlns:content:2.0"/>')
        with pytest.raises(XmindParseError, match="未找到 sheet"):
            parser._get_all_root_topics(root)

    def test_no_topic_in_sheet(self):
        root = ET.fromstring(f'<root xmlns="{XMAP_NS}"><sheet/></root>')
        with pytest.raises(XmindParseError, match="未找到根主题"):
            parser._get_all_root_topics(root)


class TestFindElement:
    def test_find_with_namespace_prefix(self):
        root = ET.fromstring(f'<root xmlns="{XMAP_NS}"><sheet id="s1"/></root>')
        result = parser._find_element(root, "sheet")
        assert result is not None
        assert result.get("id") == "s1"

    def test_find_missing_element(self):
        root = ET.fromstring(f'<root xmlns="{XMAP_NS}"/>')
        result = parser._find_element(root, "nonexistent")
        assert result is None


class TestGetChildTopics:
    def test_with_children(self):
        xml = f'<topic xmlns="{XMAP_NS}"><children><topics><topic><title>A</title></topic><topic><title>B</title></topic></topics></children></topic>'
        topic = ET.fromstring(xml)
        children = parser._get_child_topics(topic)
        assert len(children) == 2

    def test_no_children_element(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>test</title></topic>'
        topic = ET.fromstring(xml)
        children = parser._get_child_topics(topic)
        assert children == []

    def test_no_topics_in_children(self):
        xml = f'<topic xmlns="{XMAP_NS}"><children></children></topic>'
        topic = ET.fromstring(xml)
        children = parser._get_child_topics(topic)
        assert children == []


class TestExtractTopicText:
    def test_with_title(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>标题文本</title></topic>'
        topic = ET.fromstring(xml)
        result = parser._extract_topic_text(topic)
        assert result == "标题文本"

    def test_with_whitespace_title(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>  空格  </title></topic>'
        topic = ET.fromstring(xml)
        result = parser._extract_topic_text(topic)
        assert result == "空格"

    def test_no_title(self):
        xml = f'<topic xmlns="{XMAP_NS}"/>'
        topic = ET.fromstring(xml)
        result = parser._extract_topic_text(topic)
        assert result == ""


class TestExtractTopicNotes:
    def test_with_notes(self):
        xml = f'<topic xmlns="{XMAP_NS}"><notes><plain>备注内容</plain></notes></topic>'
        topic = ET.fromstring(xml)
        result = parser._extract_topic_notes(topic)
        assert result == "备注内容"

    def test_no_plain_in_notes(self):
        xml = f'<topic xmlns="{XMAP_NS}"><notes><html>html content</html></notes></topic>'
        topic = ET.fromstring(xml)
        result = parser._extract_topic_notes(topic)
        assert result == ""


class TestExtractPriorityMarker:
    def test_with_priority_marker(self):
        xml = f'<topic xmlns="{XMAP_NS}"><marker-refs><marker-ref marker-id="priority-1"/></marker-refs></topic>'
        topic = ET.fromstring(xml)
        result = parser._extract_priority_marker(topic)
        assert result == 1

    def test_with_smiley_marker(self):
        xml = f'<topic xmlns="{XMAP_NS}"><marker-refs><marker-ref marker-id="smiley-smile"/></marker-refs></topic>'
        topic = ET.fromstring(xml)
        result = parser._extract_priority_marker(topic)
        assert result == 1

    def test_no_marker_refs(self):
        xml = f'<topic xmlns="{XMAP_NS}"/>'
        topic = ET.fromstring(xml)
        result = parser._extract_priority_marker(topic)
        assert result is None

    def test_unknown_marker(self):
        xml = f'<topic xmlns="{XMAP_NS}"><marker-refs><marker-ref marker-id="unknown-marker"/></marker-refs></topic>'
        topic = ET.fromstring(xml)
        result = parser._extract_priority_marker(topic)
        assert result is None


class TestCollectLeafTestPoints:
    def test_leaf_node(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>叶子</title></topic>'
        topic = ET.fromstring(xml)
        result = parser._collect_leaf_test_points(topic, "模块", "功能", None, [], 0)
        assert len(result) == 1
        assert result[0]["point"] == "叶子"
        assert result[0]["function"] == "功能"

    def test_empty_leaf(self):
        xml = f'<topic xmlns="{XMAP_NS}"/>'
        topic = ET.fromstring(xml)
        result = parser._collect_leaf_test_points(topic, "模块", "功能", None, [], 0)
        assert result == []

    def test_max_depth_exceeded(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>深层</title></topic>'
        topic = ET.fromstring(xml)
        result = parser._collect_leaf_test_points(topic, "模块", "功能", None, [], parser.MAX_DEPTH)
        assert result == []

    def test_with_inherited_priority(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>叶子</title></topic>'
        topic = ET.fromstring(xml)
        result = parser._collect_leaf_test_points(topic, "模块", "功能", 1, [], 0)
        assert result[0]["priority"] == 1

    def test_default_priority(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>叶子</title></topic>'
        topic = ET.fromstring(xml)
        result = parser._collect_leaf_test_points(topic, "模块", "功能", None, [], 0)
        assert result[0]["priority"] == 2


class TestBuildTestPoint:
    def test_build(self):
        result = parser._build_test_point("模块", "功能", "测试点", 1)
        assert result["module"] == "模块"
        assert result["function"] == "功能"
        assert result["point"] == "测试点"
        assert result["priority"] == 1


class TestExtractPaths:
    def test_extract_paths_simple(self):
        topics_xml = f"""
        <children><topics>
            <topic xmlns="{XMAP_NS}"><title>模块A</title>
                <children><topics>
                    <topic><title>功能1</title></topic>
                </topics></children>
            </topic>
        </topics></children>
        """
        content = _build_content_xml(topics_xml)
        path = _make_xmind_file(content)
        try:
            result = parser.extract_paths(path)
            assert isinstance(result, list)
        finally:
            os.unlink(path)

    def test_extract_paths_no_children(self):
        topics_xml = f"""
        <children><topics>
            <topic xmlns="{XMAP_NS}"><title>独立模块</title></topic>
        </topics></children>
        """
        content = _build_content_xml(topics_xml)
        path = _make_xmind_file(content)
        try:
            result = parser.extract_paths(path)
            assert len(result) >= 1
        finally:
            os.unlink(path)


class TestCollectPaths:
    def test_collect_paths_with_children(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>根</title><children><topics><topic><title>子1</title></topic></topics></children></topic>'
        root = ET.fromstring(xml)
        result = parser._collect_paths(root)
        assert len(result) >= 1

    def test_collect_paths_empty_child_text(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>根</title><children><topics><topic><title></title></topic></topics></children></topic>'
        root = ET.fromstring(xml)
        result = parser._collect_paths(root)
        assert isinstance(result, list)


class TestCollectLeafPaths:
    def test_leaf_path(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>叶子</title></topic>'
        topic = ET.fromstring(xml)
        result = parser._collect_leaf_paths(topic, ["根", "叶子"])
        assert len(result) == 1
        assert len(result[0]) == 2

    def test_branch_path(self):
        xml = f'<topic xmlns="{XMAP_NS}"><title>分支</title><children><topics><topic><title>叶子</title></topic></topics></children></topic>'
        topic = ET.fromstring(xml)
        result = parser._collect_leaf_paths(topic, ["根", "分支"])
        assert len(result) == 1
        assert len(result[0]) == 3
