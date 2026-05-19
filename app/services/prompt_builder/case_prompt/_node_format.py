"""共享节点格式化工具 - 供 _graph_prompt 和 _flow_builder 共同使用。

提取到独立模块以避免 _graph_prompt 与 _flow_builder 之间的循环导入。
"""
from typing import Any, Dict, List, Optional


def _format_node_elements(elements: Optional[List[Dict[str, Any]]]) -> str:
    """格式化节点的 UI 元素列表为结构化描述。"""
    if not elements:
        return ""
    parts = []
    for e in elements:
        label = e.get('label', '') or e.get('semantic', '') or e.get('description', '')
        if not label:
            continue
        etype = e.get('type', '')
        segments = [f"{etype}:{label}"]
        state = e.get('state', '') or 'normal'
        segments.append(f"状态:{state}")
        interactive = e.get('interactive')
        if interactive is True:
            segments.append("可交互")
        elif interactive is False:
            segments.append("不可交互")
        desc = e.get('description') or e.get('semantic', '')
        if desc and isinstance(desc, str) and desc.strip():
            segments.append(desc.strip())
        parts.append('[' + '|'.join(segments) + ']')
    return '; '.join(parts)


def _build_image_ref(node: Dict[str, Any], include_images: bool) -> str:
    """构建节点的图片 URL 引用文本。"""
    if include_images and node.get('image_url'):
        return f" [图片URL: {node.get('image_url', '')}]"
    return ""
