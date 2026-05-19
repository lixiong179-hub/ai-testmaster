import xml.etree.ElementTree as ET
from typing import List, Optional
from loguru import logger


class _UtilMixin:

    XMAP_NS = "urn:xmind:xmap:xmlns:content:2.0"
    NS = {"xmap": XMAP_NS}
    MODULE_MAX_LEN = 100
    TITLE_MAX_LEN = 255
    POINT_MAX_LEN = 500

    def _find_element(self, parent: ET.Element, tag: str) -> Optional[ET.Element]:
        elem = parent.find(f"xmap:{tag}", self.NS)
        if elem is None:
            elem = parent.find(f"{{{self.XMAP_NS}}}{tag}")
        return elem

    def _get_child_topics(self, topic: ET.Element) -> List[ET.Element]:
        children = self._find_element(topic, "children")
        if children is None:
            return []
        topics = self._find_element(children, "topics")
        if topics is None:
            return []
        result = topics.findall("xmap:topic", self.NS)
        if not result:
            result = topics.findall(f"{{{self.XMAP_NS}}}topic")
        return result

    def _extract_topic_text(self, topic: ET.Element) -> str:
        title = self._find_element(topic, "title")
        if title is None:
            return ""
        return (title.text or "").strip()

    def _extract_topic_notes(self, topic: ET.Element) -> str:
        notes = self._find_element(topic, "notes")
        if notes is None:
            return ""
        plain = self._find_element(notes, "plain")
        if plain is not None and plain.text:
            return plain.text.strip()
        return ""

    def _extract_priority_marker(self, topic: ET.Element) -> Optional[int]:
        marker_refs = self._find_element(topic, "marker-refs")
        if marker_refs is None:
            return None

        priority_map = {
            "priority-1": 1, "priority-2": 2, "priority-3": 3,
            "smiley-smile": 1, "smiley-neutral": 2, "smiley-cry": 3,
            "task-done": 1, "task-start": 2, "task-undo": 3,
        }
        for ref in marker_refs.findall("xmap:marker-ref", self.NS):
            marker_id = ref.get("marker-id", "")
            if marker_id in priority_map:
                return priority_map[marker_id]
        return None

    def _truncate_field(self, value: str, max_len: int) -> str:
        if len(value) <= max_len:
            return value
        logger.warning(f"XMind 字段超长（{len(value)} > {max_len}），已截断: {value[:30]}...")
        return value[:max_len]
