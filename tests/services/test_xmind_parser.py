import pytest
from app.services.xmind_parser import XmindParser, XmindParseError
from app.services.xmind_parser._parse import _ParseMixin
from app.services.xmind_parser._util import _UtilMixin


class _ConcreteParser(_ParseMixin, _UtilMixin):
    pass


parser = _ConcreteParser()


class TestXmindParseError:
    def test_is_exception(self):
        assert issubclass(XmindParseError, Exception)

    def test_raise(self):
        with pytest.raises(XmindParseError):
            raise XmindParseError("解析失败")


class TestXmindParser:
    def test_instantiation(self):
        p = XmindParser()
        assert p is not None

    def test_has_parse_method(self):
        p = XmindParser()
        assert hasattr(p, "parse")

    def test_has_extract_paths(self):
        p = XmindParser()
        assert hasattr(p, "extract_paths")


class TestUtilMixinConstants:
    def test_namespace(self):
        assert parser.XMAP_NS == "urn:xmind:xmap:xmlns:content:2.0"

    def test_max_depth(self):
        assert parser.MAX_DEPTH == 10

    def test_max_lengths(self):
        assert parser.MODULE_MAX_LEN == 100
        assert parser.POINT_MAX_LEN == 500

    def test_priority_map(self):
        assert parser.PRIORITY_MAP["priority-1"] == 1
        assert parser.PRIORITY_MAP["priority-2"] == 2
        assert parser.PRIORITY_MAP["priority-3"] == 3


class TestTruncateField:
    def test_short_value(self):
        result = parser._truncate_field("短文本", "field", 100)
        assert result == "短文本"

    def test_exact_length(self):
        value = "a" * 100
        result = parser._truncate_field(value, "field", 100)
        assert len(result) == 100

    def test_over_length(self):
        value = "a" * 200
        result = parser._truncate_field(value, "field", 100)
        assert len(result) == 100

    def test_empty_value(self):
        result = parser._truncate_field("", "field", 100)
        assert result == ""


class TestAppendNotesToPoint:
    def test_no_notes(self):
        result = parser._append_notes_to_point("测试点", [])
        assert result == "测试点"

    def test_with_notes(self):
        result = parser._append_notes_to_point("测试点", ["备注1"])
        assert "备注1" in result

    def test_dedup_notes(self):
        result = parser._append_notes_to_point("测试点", ["备注1", "备注1"])
        assert result.count("备注1") == 1

    def test_empty_notes_filtered(self):
        result = parser._append_notes_to_point("测试点", ["", "有效备注"])
        assert "有效备注" in result


class TestDetectPriority:
    def test_default_priority(self):
        import xml.etree.ElementTree as ET
        topic = ET.Element("topic")
        result = parser._detect_priority(topic)
        assert result == 2


class TestExtractTopicText:
    def test_no_title_element(self):
        import xml.etree.ElementTree as ET
        topic = ET.Element("topic")
        result = parser._extract_topic_text(topic)
        assert result == ""


class TestExtractTopicNotes:
    def test_no_notes_element(self):
        import xml.etree.ElementTree as ET
        topic = ET.Element("topic")
        result = parser._extract_topic_notes(topic)
        assert result == ""


class TestCollectNotes:
    def test_no_notes(self):
        import xml.etree.ElementTree as ET
        topic = ET.Element("topic")
        result = parser._collect_notes(topic)
        assert result == []


class TestGetChildTopics:
    def test_no_children(self):
        import xml.etree.ElementTree as ET
        topic = ET.Element("topic")
        result = parser._get_child_topics(topic)
        assert result == []


class TestExtractContentXml:
    def test_nonexistent_file(self):
        with pytest.raises(XmindParseError):
            parser._extract_content_xml("nonexistent_file.xmind")


class TestParseXml:
    def test_invalid_xml(self):
        with pytest.raises(XmindParseError):
            parser._parse_xml(b"not valid xml <><>")
