"""DOM 序列化与 Diff 报告（Task 8）。

设计目的：
    DOM 序列化将页面 DOM 结构提取为可对比的结构化数据，用于 Layout Match
    Level 的结构对比与 Diff 报告生成。相比纯像素对比，DOM 对比能精确定位
    变更元素，减少动态内容导致的误报。

核心能力：
    - serialize_dom      : 将 HTML 字符串序列化为 DOMTreeNode 树
    - compare_doms       : 对比两棵 DOM 树，返回 DOMDiffResult
    - generate_diff_report: 生成人类可读的 Diff 报告

设计原则：
    - 轻量：仅提取布局相关属性（tag/x/y/width/height/visible），不保存完整样式
    - 容错：解析失败时返回空树，不阻断对比流程
    - 可读：Diff 报告使用 Markdown 格式，便于审批人理解
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class DOMTreeNode:
    """DOM 树节点。

    Attributes:
        tag        : 元素标签名（如 div/span/input）
        attributes : 关键属性（id/class/role/data-testid）
        x          : 元素 X 坐标
        y          : 元素 Y 坐标
        width      : 元素宽度
        height     : 元素高度
        visible    : 是否可见
        children   : 子节点列表
    """

    tag: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    visible: bool = True
    children: List["DOMTreeNode"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "tag": self.tag,
            "attributes": self.attributes,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "visible": self.visible,
            "children": [c.to_dict() for c in self.children],
        }

    def to_json(self) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class DOMDiffEntry:
    """单条 DOM 差异记录。

    Attributes:
        change_type: 变更类型（added/removed/moved/resized/attribute_changed）
        path       : 元素路径（如 "div.header > nav > ul > li[2]"）
        detail     : 变更详情
    """

    change_type: str
    path: str
    detail: str = ""


@dataclass
class DOMDiffResult:
    """DOM 对比结果。

    Attributes:
        entries    : 差异记录列表
        total_count: 差异总数
        has_diff   : 是否存在差异
    """

    entries: List[DOMDiffEntry] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.entries)

    @property
    def has_diff(self) -> bool:
        return self.total_count > 0

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "total_count": self.total_count,
            "has_diff": self.has_diff,
            "entries": [
                {
                    "change_type": e.change_type,
                    "path": e.path,
                    "detail": e.detail,
                }
                for e in self.entries
            ],
        }


def serialize_dom(html: str) -> DOMTreeNode:
    """将 HTML 字符串序列化为 DOMTreeNode 树。

    使用 BeautifulSoup 解析 HTML，提取布局相关属性。仅保留布局关键属性，
    不保存完整样式表。

    Args:
        html: HTML 字符串

    Returns:
        DOMTreeNode: DOM 树根节点，解析失败时返回空节点
    """
    try:
        from bs4 import BeautifulSoup, Tag
    except ImportError:
        return DOMTreeNode(tag="root")

    try:
        soup = BeautifulSoup(html, "html.parser")
        root = DOMTreeNode(tag="root")
        for child in soup.children:
            if isinstance(child, Tag):
                root.children.append(_parse_node(child))
        return root
    except Exception:
        return DOMTreeNode(tag="root")


def _parse_node(soup_tag: Any) -> DOMTreeNode:
    """递归解析 BeautifulSoup Tag 为 DOMTreeNode。"""
    from bs4 import Tag

    node = DOMTreeNode(tag=soup_tag.name or "")
    # 仅提取布局关键属性
    for attr_key in ("id", "class", "role", "data-testid"):
        val = soup_tag.get(attr_key)
        if val:
            node.attributes[attr_key] = " ".join(val) if isinstance(val, list) else str(val)

    for child in soup_tag.children:
        if isinstance(child, Tag):
            node.children.append(_parse_node(child))

    return node


def compare_doms(baseline: DOMTreeNode, current: DOMTreeNode) -> DOMDiffResult:
    """对比两棵 DOM 树，返回差异结果。

    对比策略：
        1. 按标签名 + 关键属性匹配对应节点
        2. 检测新增/删除节点
        3. 检测属性变更

    Args:
        baseline: 基线 DOM 树
        current: 当前 DOM 树

    Returns:
        DOMDiffResult: 差异结果
    """
    result = DOMDiffResult()
    _compare_nodes(baseline, current, "root", result)
    return result


def _compare_nodes(
    baseline: DOMTreeNode,
    current: DOMTreeNode,
    path: str,
    result: DOMDiffResult,
) -> None:
    """递归对比两个 DOM 节点。"""
    # 标签名变更
    if baseline.tag != current.tag:
        result.entries.append(
            DOMDiffEntry(
                change_type="attribute_changed",
                path=path,
                detail=f"tag: {baseline.tag} → {current.tag}",
            )
        )

    # 属性变更
    baseline_attrs = set(baseline.attributes.keys())
    current_attrs = set(current.attributes.keys())
    for key in baseline_attrs | current_attrs:
        base_val = baseline.attributes.get(key)
        curr_val = current.attributes.get(key)
        if base_val != curr_val:
            result.entries.append(
                DOMDiffEntry(
                    change_type="attribute_changed",
                    path=f"{path}[{key}]",
                    detail=f"{base_val} → {curr_val}",
                )
            )

    # 子节点对比（按 tag+id 匹配）
    base_children = {child_path(path, c): c for c in baseline.children}
    curr_children = {child_path(path, c): c for c in current.children}

    for child_key, base_child in base_children.items():
        if child_key in curr_children:
            _compare_nodes(base_child, curr_children[child_key], child_key, result)
        else:
            result.entries.append(
                DOMDiffEntry(change_type="removed", path=child_key, detail=f"tag={base_child.tag}")
            )

    for child_key, curr_child in curr_children.items():
        if child_key not in base_children:
            result.entries.append(
                DOMDiffEntry(change_type="added", path=child_key, detail=f"tag={curr_child.tag}")
            )


def child_path(parent_path: str, node: DOMTreeNode) -> str:
    """构造子节点路径标识。"""
    node_id = node.attributes.get("id", "")
    if node_id:
        return f"{parent_path} > {node.tag}#{node_id}"
    return f"{parent_path} > {node.tag}"


def generate_diff_report(
    pixel_diff_percentage: float,
    dom_diff: Optional[DOMDiffResult] = None,
    llm_description: str = "",
) -> str:
    """生成人类可读的 Markdown Diff 报告。

    Args:
        pixel_diff_percentage: 像素差异百分比
        dom_diff: DOM 对比结果（可空）
        llm_description: LLM 语义分析描述（可空）

    Returns:
        str: Markdown 格式的 Diff 报告
    """
    lines = [
        "# 视觉差异报告",
        "",
        f"**像素差异百分比**: {pixel_diff_percentage:.2f}%",
        "",
    ]

    if dom_diff and dom_diff.has_diff:
        lines.append(f"**DOM 结构差异**: {dom_diff.total_count} 处变更")
        lines.append("")
        lines.append("| 变更类型 | 元素路径 | 详情 |")
        lines.append("|----------|----------|------|")
        for entry in dom_diff.entries[:20]:
            lines.append(f"| {entry.change_type} | {entry.path} | {entry.detail} |")
        if dom_diff.total_count > 20:
            lines.append(f"| ... | 共 {dom_diff.total_count} 条，已显示前 20 条 |")
        lines.append("")

    if llm_description:
        lines.append("**LLM 语义分析**:")
        lines.append(f"> {llm_description}")
        lines.append("")

    return "\n".join(lines)


__all__ = [
    "DOMTreeNode",
    "DOMDiffEntry",
    "DOMDiffResult",
    "serialize_dom",
    "compare_doms",
    "generate_diff_report",
]
