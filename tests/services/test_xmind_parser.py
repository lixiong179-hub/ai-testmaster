"""XMind 解析器单元测试�?

覆盖场景:
    - 正常解析样例文件
    - 空文�?无子节点
    - 深层嵌套
    - 特殊字符
    - 无效文件格式
    - 缺失 content.xml
    - 字段映射正确�?
    - 优先级识�?
    - 字段超长截断
"""
import os
import zipfile
import xml.etree.ElementTree as ET
import pytest

from app.services.xmind_parser import XmindParser, XmindParseError


SAMPLE_XMIND = r"C:\Users\Administrator\Desktop\听写任务.xmind"
NS = "urn:xmind:xmap:xmlns:content:2.0"


def _create_xmind_file(
    path: str,
    content_xml: str,
    extra_files: dict | None = None,
) -> str:
    """创建测试�?XMind 文件�?

    Args:
        path: 输出文件路径�?
        content_xml: content.xml 内容字符串�?
        extra_files: 额外文件字典 {filename: content}�?

    Returns:
        创建的文件路径�?
    """
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.xml", content_xml)
        zf.writestr("meta.xml", '<?xml version="1.0" encoding="UTF-8"?>')
        if extra_files:
            for name, content in extra_files.items():
                zf.writestr(name, content)
    return path


def _build_content_xml(topics_xml: str) -> str:
    """构建 content.xml 字符串�?

    Args:
        topics_xml: 主题 XML 片段�?

    Returns:
        完整�?content.xml 字符串�?
    """
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<xmap-content xmlns="{NS}" version="2.0">
<sheet id="test-sheet">
<topic id="root" structure-class="org.xmind.ui.logic.right">
<title>根主�?/title>
<children><topics type="attached">
{topics_xml}
</topics></children>
</topic>
</sheet>
</xmap-content>"""


def _build_topic(
    title: str,
    topic_id: str = "",
    children_xml: str = "",
    marker_refs_xml: str = "",
    notes_xml: str = "",
) -> str:
    """构建单个 topic XML 片段�?

    Args:
        title: 主题标题�?
        topic_id: 主题 ID�?
        children_xml: 子主�?XML�?
        marker_refs_xml: 标记引用 XML�?
        notes_xml: 备注 XML�?

    Returns:
        topic XML 字符串�?
    """
    if not topic_id:
        topic_id = f"topic-{title}"
    children_part = f"<children><topics type='attached'>{children_xml}</topics></children>" if children_xml else ""
    marker_part = f"<marker-refs>{marker_refs_xml}</marker-refs>" if marker_refs_xml else ""
    notes_part = f"<notes><plain>{notes_xml}</plain></notes>" if notes_xml else ""
    return f"""<topic id="{topic_id}">
<title>{title}</title>
{children_part}{marker_part}{notes_part}
</topic>"""


@pytest.fixture
def parser() -> XmindParser:
    return XmindParser()


@pytest.fixture
def valid_xmind(tmp_path) -> str:
    """创建包含标准三级结构�?XMind 测试文件�?""
    l3_a = _build_topic("点击登录按钮", "l3-a")
    l3_b = _build_topic("输入密码", "l3-b")
    l2 = _build_topic("账号密码登录", "l2", children_xml=l3_a + l3_b)
    l1 = _build_topic("登录模块", "l1", children_xml=l2)
    content = _build_content_xml(l1)
    return _create_xmind_file(str(tmp_path / "valid.xmind"), content)


@pytest.fixture
def deep_nesting_xmind(tmp_path) -> str:
    """创建深层嵌套�?XMind 测试文件�?""
    inner = _build_topic("L6节点", "l6")
    l5 = _build_topic("L5节点", "l5", children_xml=inner)
    l4 = _build_topic("L4节点", "l4", children_xml=l5)
    l3 = _build_topic("L3节点", "l3", children_xml=l4)
    l2 = _build_topic("L2节点", "l2", children_xml=l3)
    l1 = _build_topic("L1模块", "l1", children_xml=l2)
    content = _build_content_xml(l1)
    return _create_xmind_file(str(tmp_path / "deep.xmind"), content)


@pytest.fixture
def empty_xmind(tmp_path) -> str:
    """创建只有根主题无子节点的 XMind 文件�?""
    content = _build_content_xml("")
    return _create_xmind_file(str(tmp_path / "empty.xmind"), content)


@pytest.fixture
def priority_xmind(tmp_path) -> str:
    """创建包含优先级标记的 XMind 文件�?""
    l3_high = _build_topic(
        "高优先级测试�?, "l3-h",
        marker_refs_xml='<marker-ref marker-id="priority-1"/>',
    )
    l3_low = _build_topic(
        "低优先级测试�?, "l3-l",
        marker_refs_xml='<marker-ref marker-id="priority-3"/>',
    )
    l3_default = _build_topic("默认优先级测试点", "l3-d")
    l2 = _build_topic(
        "功能模块", "l2",
        children_xml=l3_high + l3_low + l3_default,
    )
    l1 = _build_topic("模块A", "l1", children_xml=l2)
    content = _build_content_xml(l1)
    return _create_xmind_file(str(tmp_path / "priority.xmind"), content)


@pytest.fixture
def notes_xmind(tmp_path) -> str:
    """创建包含备注�?XMind 文件�?""
    l3 = _build_topic("有备注的测试�?, "l3", notes_xml="这是备注内容")
    l2 = _build_topic("功能A", "l2", children_xml=l3)
    l1 = _build_topic("模块A", "l1", children_xml=l2)
    content = _build_content_xml(l1)
    return _create_xmind_file(str(tmp_path / "notes.xmind"), content)


class TestXmindParserCore:
    """XmindParser 核心解析逻辑测试�?""

    def test_parse_valid_file(self, parser: XmindParser, valid_xmind: str) -> None:
        result = parser.parse(valid_xmind)
        assert len(result) == 2
        assert result[0]["module"] == "登录模块"
        assert result[0]["function"] == "账号密码登录"
        assert result[0]["point"] == "点击登录按钮"
        assert result[0]["priority"] == 2

    def test_parse_empty_file(self, parser: XmindParser, empty_xmind: str) -> None:
        result = parser.parse(empty_xmind)
        assert result == []

    def test_parse_deep_nesting(self, parser: XmindParser, deep_nesting_xmind: str) -> None:
        result = parser.parse(deep_nesting_xmind)
        assert len(result) == 1
        assert result[0]["module"] == "L1模块"
        assert result[0]["function"] == "L2节点"
        assert result[0]["point"] == "L6节点"

    def test_parse_invalid_zip(self, parser: XmindParser, tmp_path) -> None:
        invalid_file = tmp_path / "invalid.xmind"
        invalid_file.write_text("this is not a zip file")
        with pytest.raises(XmindParseError, match="无效�?XMind 文件格式"):
            parser.parse(str(invalid_file))

    def test_parse_missing_content_xml(self, parser: XmindParser, tmp_path) -> None:
        bad_file = tmp_path / "no_content.xmind"
        with zipfile.ZipFile(str(bad_file), "w") as zf:
            zf.writestr("meta.xml", '<?xml version="1.0"?>')
        with pytest.raises(XmindParseError, match="内容缺失"):
            parser.parse(str(bad_file))

    def test_parse_malformed_xml(self, parser: XmindParser, tmp_path) -> None:
        bad_file = tmp_path / "bad_xml.xmind"
        with zipfile.ZipFile(str(bad_file), "w") as zf:
            zf.writestr("content.xml", "this is not valid xml <<<")
        with pytest.raises(XmindParseError, match="无法解析"):
            parser.parse(str(bad_file))


class TestFieldMapping:
    """字段映射规则测试�?""

    def test_module_function_point_mapping(self, parser: XmindParser, valid_xmind: str) -> None:
        result = parser.parse(valid_xmind)
        for item in result:
            assert "module" in item
            assert "function" in item
            assert "point" in item
            assert "priority" in item
            assert item["module"] == "登录模块"
            assert item["function"] == "账号密码登录"

    def test_priority_detection(self, parser: XmindParser, priority_xmind: str) -> None:
        result = parser.parse(priority_xmind)
        priorities = {r["point"]: r["priority"] for r in result}
        assert priorities["高优先级测试�?] == 1
        assert priorities["低优先级测试�?] == 3
        assert priorities["默认优先级测试点"] == 2

    def test_notes_appended_to_point(self, parser: XmindParser, notes_xmind: str) -> None:
        result = parser.parse(notes_xmind)
        assert len(result) == 1
        assert "备注: 这是备注内容" in result[0]["point"]

    def test_deep_leaf_nodes_become_points(self, parser: XmindParser, deep_nesting_xmind: str) -> None:
        result = parser.parse(deep_nesting_xmind)
        assert len(result) == 1
        assert result[0]["point"] == "L6节点"
        assert " > " not in result[0]["point"]

    def test_second_level_leaf_becomes_test_point(self, parser: XmindParser, tmp_path) -> None:
        l2 = _build_topic("直接叶子功能", "l2")
        l1 = _build_topic("模块A", "l1", children_xml=l2)
        content = _build_content_xml(l1)
        xmind_file = _create_xmind_file(str(tmp_path / "second_level_leaf.xmind"), content)
        result = parser.parse(xmind_file)

        assert len(result) == 1
        assert result[0]["module"] == "模块A"
        assert result[0]["function"] == "直接叶子功能"
        assert result[0]["point"] == "直接叶子功能"

    def test_parent_priority_is_inherited_by_leaf(self, parser: XmindParser, tmp_path) -> None:
        leaf = _build_topic("最终测试点", "leaf")
        l3 = _build_topic(
            "分组节点",
            "l3",
            children_xml=leaf,
            marker_refs_xml='<marker-ref marker-id="priority-1"/>',
        )
        l2 = _build_topic("功能A", "l2", children_xml=l3)
        l1 = _build_topic("模块A", "l1", children_xml=l2)
        content = _build_content_xml(l1)
        xmind_file = _create_xmind_file(str(tmp_path / "inherit_priority.xmind"), content)
        result = parser.parse(xmind_file)

        assert len(result) == 1
        assert result[0]["point"] == "最终测试点"
        assert result[0]["priority"] == 1


class TestFieldTruncation:
    """字段超长截断测试�?""

    def test_module_truncation(self, parser: XmindParser, tmp_path) -> None:
        long_name = "A" * 150
        l2 = _build_topic("叶子测试�?, "l2")
        l1 = _build_topic(long_name, "l1", children_xml=l2)
        content = _build_content_xml(l1)
        xmind_file = _create_xmind_file(str(tmp_path / "long_module.xmind"), content)
        result = parser.parse(xmind_file)
        assert len(result[0]["module"]) == XmindParser.MODULE_MAX_LEN

    def test_point_truncation(self, parser: XmindParser, tmp_path) -> None:
        long_point = "B" * 600
        l3 = _build_topic(long_point, "l3")
        l2 = _build_topic("功能", "l2", children_xml=l3)
        l1 = _build_topic("模块", "l1", children_xml=l2)
        content = _build_content_xml(l1)
        xmind_file = _create_xmind_file(str(tmp_path / "long_point.xmind"), content)
        result = parser.parse(xmind_file)
        assert len(result[0]["point"]) <= XmindParser.POINT_MAX_LEN


class TestExtractPaths:
    """extract_paths 路径提取测试�?""

    def test_extract_paths_basic(self, parser: XmindParser, valid_xmind: str) -> None:
        paths = parser.extract_paths(valid_xmind)
        assert len(paths) == 2
        assert paths[0] == ["登录模块", "账号密码登录", "点击登录按钮"]
        assert paths[1] == ["登录模块", "账号密码登录", "输入密码"]

    def test_extract_paths_empty_file(self, parser: XmindParser, empty_xmind: str) -> None:
        paths = parser.extract_paths(empty_xmind)
        assert paths == []

    def test_extract_paths_deep_nesting(self, parser: XmindParser, deep_nesting_xmind: str) -> None:
        paths = parser.extract_paths(deep_nesting_xmind)
        assert len(paths) == 1
        assert paths[0] == ["L1模块", "L2节点", "L3节点", "L4节点", "L5节点", "L6节点"]

    def test_extract_paths_second_level_leaf(self, parser: XmindParser, tmp_path) -> None:
        l2 = _build_topic("直接叶子功能", "l2")
        l1 = _build_topic("模块A", "l1", children_xml=l2)
        content = _build_content_xml(l1)
        xmind_file = _create_xmind_file(str(tmp_path / "second_level_paths.xmind"), content)
        paths = parser.extract_paths(xmind_file)
        assert len(paths) == 1
        assert paths[0] == ["模块A", "直接叶子功能"]

    def test_extract_paths_skips_empty_module(self, parser: XmindParser, tmp_path) -> None:
        l2 = _build_topic("功能A", "l2")
        l1_empty = _build_topic("", "l1-empty", children_xml=l2)
        l1_valid = _build_topic("模块B", "l1-valid", children_xml=l2)
        content = _build_content_xml(l1_empty + l1_valid)
        xmind_file = _create_xmind_file(str(tmp_path / "skip_empty_module.xmind"), content)
        paths = parser.extract_paths(xmind_file)
        assert len(paths) == 1
        assert paths[0][0] == "模块B"


class TestSampleFile:
    """样例文件解析测试�?""

    @pytest.mark.skipif(
        not os.path.exists(SAMPLE_XMIND),
        reason="样例文件不存�?,
    )
    def test_parse_sample_file(self, parser: XmindParser) -> None:
        result = parser.parse(SAMPLE_XMIND)
        assert len(result) > 0
        modules = {r["module"] for r in result}
        assert "字词听写" in modules
        assert "单词听写" in modules
        assert "生词�? in modules

    @pytest.mark.skipif(
        not os.path.exists(SAMPLE_XMIND),
        reason="样例文件不存�?,
    )
    def test_sample_all_fields_valid(self, parser: XmindParser) -> None:
        result = parser.parse(SAMPLE_XMIND)
        for item in result:
            assert len(item["module"]) > 0
            assert 1 <= item["priority"] <= 3
            assert len(item["point"]) > 0 or len(item["function"]) > 0
