import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from loguru import logger


class _UtilMixin:

    XMAP_NS = "urn:xmind:xmap:xmlns:content:2.0"
    NS = {"xmap": XMAP_NS}
    MAX_DEPTH = 10
    MODULE_MAX_LEN = 100
    FUNCTION_MAX_LEN = 200
    POINT_MAX_LEN = 500
    PRIORITY_MAP = {
        "priority-1": 1,
        "priority-2": 2,
        "priority-3": 3,
        "smiley-smile": 1,
        "smiley-neutral": 2,
        "smiley-cry": 3,
        "task-done": 1,
        "task-start": 2,
        "task-undo": 3,
    }

    def _get_child_topics(self, topic: ET.Element) -> List[ET.Element]:
        children = topic.find("xmap:children", self.NS)
        if children is None:
            children = topic.find("{%(ns)s}children" % {"ns": self.XMAP_NS})
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

    def _collect_notes(self, topic: ET.Element) -> List[str]:
        notes = self._extract_topic_notes(topic)
        return [notes] if notes else []

    def _detect_priority(self, topic: ET.Element) -> int:
        priority = self._extract_priority_marker(topic)
        return priority if priority is not None else 2

    def _extract_priority_marker(self, topic: ET.Element) -> Optional[int]:
        marker_refs = self._find_element(topic, "marker-refs")
        if marker_refs is None:
            return None
        for ref in marker_refs.findall("xmap:marker-ref", self.NS):
            marker_id = ref.get("marker-id", "")
            if marker_id in self.PRIORITY_MAP:
                return self.PRIORITY_MAP[marker_id]
        return None

    def _append_notes_to_point(self, point_text: str, notes_list: List[str]) -> str:
        if not notes_list:
            return point_text
        unique_notes = list(dict.fromkeys(note for note in notes_list if note))
        if not unique_notes:
            return point_text
        return point_text + "".join(f"\n备注: {note}" for note in unique_notes)

    def extract_paths(self, file_path: str) -> List[List[str]]:
        content_xml = self._extract_content_xml(file_path)
        root = self._parse_xml(content_xml)
        root_topic = self._get_root_topic(root)
        return self._collect_paths(root_topic)

    def _collect_paths(self, root_topic: ET.Element) -> List[List[str]]:
        paths: List[List[str]] = []
        level1_topics = self._get_child_topics(root_topic)

        for l1_topic in level1_topics:
            module_name = self._extract_topic_text(l1_topic)
            if not module_name:
                continue
            l1_children = self._get_child_topics(l1_topic)
            for child in l1_children:
                child_text = self._extract_topic_text(child)
                if not child_text:
                    continue
                for path in self._collect_leaf_paths(child, [module_name, child_text]):
                    paths.append(path)
            if not l1_children:
                if module_name:
                    paths.append([module_name])

        return paths

    def _collect_leaf_paths(
        self, topic: ET.Element, prefix: List[str]
    ) -> List[List[str]]:
        child_topics = self._get_child_topics(topic)
        if not child_topics:
            return [prefix]

        paths: List[List[str]] = []
        for child in child_topics:
            text = self._extract_topic_text(child)
            if not text:
                continue
            paths.extend(self._collect_leaf_paths(child, prefix + [text]))
        return paths

    def _truncate_field(self, value: str, field_name: str, max_len: int) -> str:
        if len(value) <= max_len:
            return value
        logger.warning(
            f"字段 {field_name} 超长（{len(value)} > {max_len}），已截断: {value[:30]}...",
        )
        return value[:max_len]
