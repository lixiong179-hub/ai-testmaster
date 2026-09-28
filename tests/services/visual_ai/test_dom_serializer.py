"""DOM 序列化与 Diff 报告单元测试。

覆盖：
    - serialize_dom: 解析 HTML / 解析失败返回空树
    - compare_doms: 相同 DOM 无差异 / 新增元素 / 删除元素 / 属性变更
    - generate_diff_report: Markdown 格式报告生成
"""
from __future__ import annotations

import pytest

from app.services.visual_ai.dom_serializer import (
    DOMDiffResult,
    DOMDiffEntry,
    DOMTreeNode,
    compare_doms,
    generate_diff_report,
    serialize_dom,
)


class TestSerializeDom:
    """DOM 序列化测试。"""

    def test_serialize_simple_html(self) -> None:
        """解析简单 HTML 结构。"""
        html = """
        <div id="app">
            <nav class="navbar">
                <a href="/home">Home</a>
            </nav>
        </div>
        """
        tree = serialize_dom(html)

        assert tree.tag == "root"
        assert len(tree.children) > 0
        # 找到 div 节点
        div = tree.children[0]
        assert div.tag == "div"
        assert div.attributes.get("id") == "app"

    def test_serialize_empty_html(self) -> None:
        """空 HTML 返回空树。"""
        tree = serialize_dom("")
        assert tree.tag == "root"
        assert len(tree.children) == 0

    def test_serialize_invalid_html(self) -> None:
        """无效 HTML 容错返回空树。"""
        tree = serialize_dom("<<<not html>>>")
        assert tree.tag == "root"

    def test_dom_tree_node_to_dict(self) -> None:
        """DOMTreeNode.to_dict 返回完整结构。"""
        node = DOMTreeNode(tag="div", attributes={"id": "test"})
        node.children.append(DOMTreeNode(tag="span"))

        d = node.to_dict()
        assert d["tag"] == "div"
        assert d["attributes"]["id"] == "test"
        assert len(d["children"]) == 1
        assert d["children"][0]["tag"] == "span"

    def test_dom_tree_node_to_json(self) -> None:
        """DOMTreeNode.to_json 返回有效 JSON。"""
        import json

        node = DOMTreeNode(tag="div", attributes={"class": "container"})
        j = node.to_json()
        parsed = json.loads(j)
        assert parsed["tag"] == "div"
        assert parsed["attributes"]["class"] == "container"


class TestCompareDoms:
    """DOM 对比测试。"""

    def test_identical_doms_no_diff(self) -> None:
        """相同 DOM 树无差异。"""
        tree1 = DOMTreeNode(tag="div", attributes={"id": "app"})
        tree1.children.append(DOMTreeNode(tag="span", attributes={"class": "label"}))

        tree2 = DOMTreeNode(tag="div", attributes={"id": "app"})
        tree2.children.append(DOMTreeNode(tag="span", attributes={"class": "label"}))

        result = compare_doms(tree1, tree2)

        assert not result.has_diff
        assert result.total_count == 0

    def test_added_element_detected(self) -> None:
        """新增元素被检测到。"""
        baseline = DOMTreeNode(tag="div")
        current = DOMTreeNode(tag="div")
        current.children.append(DOMTreeNode(tag="span", attributes={"id": "new"}))

        result = compare_doms(baseline, current)

        assert result.has_diff
        assert any(e.change_type == "added" for e in result.entries)

    def test_removed_element_detected(self) -> None:
        """删除元素被检测到。"""
        baseline = DOMTreeNode(tag="div")
        baseline.children.append(DOMTreeNode(tag="span", attributes={"id": "old"}))
        current = DOMTreeNode(tag="div")

        result = compare_doms(baseline, current)

        assert result.has_diff
        assert any(e.change_type == "removed" for e in result.entries)

    def test_attribute_change_detected(self) -> None:
        """属性变更被检测到。"""
        baseline = DOMTreeNode(tag="div", attributes={"class": "old"})
        current = DOMTreeNode(tag="div", attributes={"class": "new"})

        result = compare_doms(baseline, current)

        assert result.has_diff
        assert any(e.change_type == "attribute_changed" for e in result.entries)

    def test_tag_change_detected(self) -> None:
        """标签名变更被检测到。"""
        baseline = DOMTreeNode(tag="div")
        current = DOMTreeNode(tag="span")

        result = compare_doms(baseline, current)

        assert result.has_diff
        assert any(
            e.change_type == "attribute_changed" and "tag" in e.detail
            for e in result.entries
        )

    def test_diff_result_to_dict(self) -> None:
        """DOMDiffResult.to_dict 返回完整结构。"""
        result = DOMDiffResult()
        result.entries.append(
            DOMDiffEntry(change_type="added", path="div > span#new", detail="tag=span")
        )

        d = result.to_dict()
        assert d["total_count"] == 1
        assert d["has_diff"] is True
        assert d["entries"][0]["change_type"] == "added"


class TestGenerateDiffReport:
    """Diff 报告生成测试。"""

    def test_report_with_pixel_diff_only(self) -> None:
        """仅像素差异时生成基本报告。"""
        report = generate_diff_report(pixel_diff_percentage=5.5)

        assert "视觉差异报告" in report
        assert "5.50%" in report

    def test_report_with_dom_diff(self) -> None:
        """含 DOM 差异时生成表格。"""
        dom_diff = DOMDiffResult()
        dom_diff.entries.append(
            DOMDiffEntry(change_type="added", path="div > span", detail="tag=span")
        )

        report = generate_diff_report(
            pixel_diff_percentage=10.0,
            dom_diff=dom_diff,
        )

        assert "DOM 结构差异" in report
        assert "1 处变更" in report
        assert "| added |" in report

    def test_report_with_llm_description(self) -> None:
        """含 LLM 描述时包含语义分析。"""
        report = generate_diff_report(
            pixel_diff_percentage=15.0,
            llm_description="检测到登录表单元素错位",
        )

        assert "LLM 语义分析" in report
        assert "登录表单元素错位" in report

    def test_report_with_all_components(self) -> None:
        """所有组件同时存在。"""
        dom_diff = DOMDiffResult()
        dom_diff.entries.append(
            DOMDiffEntry(change_type="removed", path="div > nav", detail="tag=nav")
        )

        report = generate_diff_report(
            pixel_diff_percentage=20.0,
            dom_diff=dom_diff,
            llm_description="导航栏丢失",
        )

        assert "20.00%" in report
        assert "DOM 结构差异" in report
        assert "LLM 语义分析" in report
        assert "导航栏丢失" in report
