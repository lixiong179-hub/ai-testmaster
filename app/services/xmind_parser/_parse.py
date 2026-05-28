import json
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from loguru import logger

from app.services.xmind_parser._util import _UtilMixin


class XmindParseError(Exception):
    pass


class _ParseMixin:

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        content_xml = self._extract_content_xml(file_path)
        root = self._parse_xml(content_xml)
        root_topics = self._get_all_root_topics(root)
        test_points: List[Dict[str, Any]] = []
        for root_topic in root_topics:
            test_points.extend(self._parse_topics(root_topic))
        logger.info(f"XMind 解析完成，共提取 {len(test_points)} 条测试点")
        return test_points

    def _extract_content_xml(self, file_path: str) -> bytes:
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                names = zf.namelist()
                if "content.xml" in names:
                    return zf.read("content.xml")
                if "content.json" in names:
                    return self._convert_json_to_xml(zf.read("content.json"))
                raise XmindParseError("XMind 文件内容缺失，文件可能已损坏")
        except zipfile.BadZipFile:
            raise XmindParseError("无效的 XMind 文件格式，请上传 .xmind 文件")
        except XmindParseError:
            raise
        except Exception as e:
            logger.error(f"读取 XMind 文件失败: {e}")
            raise XmindParseError("读取 XMind 文件失败，请检查文件是否损坏") from e

    def _convert_json_to_xml(self, content_json: bytes) -> bytes:
        try:
            sheets_data = json.loads(content_json)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error(f"content.json 解析失败: {exc}")
            raise XmindParseError("无法解析 XMind JSON 内容，请确认文件格式正确") from exc

        if not isinstance(sheets_data, list):
            sheets_data = [sheets_data]

        ns = self.XMAP_NS
        root = ET.Element(f"{{{ns}}}xmap-content")
        root.set("version", "2.0")

        for sheet_data in sheets_data:
            sheet_el = ET.SubElement(root, f"{{{ns}}}sheet")
            sheet_title = sheet_data.get("title", "")
            if sheet_title:
                title_el = ET.SubElement(sheet_el, f"{{{ns}}}title")
                title_el.text = sheet_title

            root_topic_data = sheet_data.get("rootTopic")
            if root_topic_data:
                topic_el = self._json_topic_to_xml(root_topic_data, ns)
                sheet_el.append(topic_el)

        return ET.tostring(root, encoding="UTF-8", xml_declaration=True)

    def _json_topic_to_xml(self, topic_data: dict, ns: str) -> ET.Element:
        topic_el = ET.Element(f"{{{ns}}}topic")
        topic_id = topic_data.get("id", "")
        if topic_id:
            topic_el.set("id", topic_id)

        title = topic_data.get("title", "")
        if title:
            title_el = ET.SubElement(topic_el, f"{{{ns}}}title")
            title_el.text = title

        notes_data = topic_data.get("notes")
        if notes_data:
            plain_data = notes_data.get("plain", {})
            note_content = plain_data.get("content", "")
            if note_content:
                notes_el = ET.SubElement(topic_el, f"{{{ns}}}notes")
                plain_el = ET.SubElement(notes_el, f"{{{ns}}}plain")
                plain_el.text = note_content

        markers_data = topic_data.get("markers", [])
        if markers_data:
            marker_refs_el = ET.SubElement(topic_el, f"{{{ns}}}marker-refs")
            for marker in markers_data:
                marker_id = marker.get("markerId", "")
                if marker_id:
                    ref_el = ET.SubElement(marker_refs_el, f"{{{ns}}}marker-ref")
                    ref_el.set("marker-id", marker_id)

        labels_data = topic_data.get("labels", [])
        if labels_data:
            labels_el = ET.SubElement(topic_el, f"{{{ns}}}labels")
            for label_text in labels_data:
                label_el = ET.SubElement(labels_el, f"{{{ns}}}label")
                label_el.text = label_text

        children_data = topic_data.get("children", {})
        attached = children_data.get("attached", [])
        detached = children_data.get("detached", [])
        all_children = attached + detached
        if all_children:
            children_el = ET.SubElement(topic_el, f"{{{ns}}}children")
            topics_el = ET.SubElement(children_el, f"{{{ns}}}topics")
            topics_el.set("type", "attached")
            for child_data in all_children:
                child_el = self._json_topic_to_xml(child_data, ns)
                topics_el.append(child_el)

        return topic_el

    def _parse_xml(self, content: bytes) -> ET.Element:
        try:
            root = ET.fromstring(content)
            return root
        except ET.ParseError as e:
            logger.error(f"XML 解析失败: {e}")
            raise XmindParseError("无法解析 XMind 文件内容，请确认文件格式正确") from e

    def _get_all_root_topics(self, root: ET.Element) -> List[ET.Element]:
        sheets = root.findall("xmap:sheet", self.NS)
        if not sheets:
            sheets = root.findall(f"{{{self.XMAP_NS}}}sheet")
        if not sheets:
            raise XmindParseError("XMind 文件中未找到 sheet 元素")
        topics: List[ET.Element] = []
        for sheet in sheets:
            topic = self._find_element(sheet, "topic")
            if topic is not None:
                topics.append(topic)
        if not topics:
            raise XmindParseError("XMind 文件中未找到根主题")
        return topics

    def _find_element(self, parent: ET.Element, tag: str) -> Optional[ET.Element]:
        elem = parent.find(f"xmap:{tag}", self.NS)
        if elem is None:
            elem = parent.find(f"{{{self.XMAP_NS}}}{tag}")
        return elem

    def _parse_topics(self, root_topic: ET.Element) -> List[Dict[str, Any]]:
        test_points: List[Dict[str, Any]] = []
        level1_topics = self._get_child_topics(root_topic)

        for l1_topic in level1_topics:
            module_name = self._extract_topic_text(l1_topic)
            if not module_name:
                logger.warning("跳过空文本的一级节点")
                continue
            module_name = self._truncate_field(module_name, "module", self.MODULE_MAX_LEN)

            level2_topics = self._get_child_topics(l1_topic)
            if not level2_topics:
                continue

            for l2_topic in level2_topics:
                l2_text = self._extract_topic_text(l2_topic)
                if not l2_text:
                    logger.warning("跳过空文本的二级节点（模块: %s）", module_name)
                    continue
                function_name = self._truncate_field(l2_text, "function", self.FUNCTION_MAX_LEN)
                test_points.extend(
                    self._collect_leaf_test_points(
                        topic=l2_topic,
                        module_name=module_name,
                        function_name=function_name,
                        inherited_priority=self._extract_priority_marker(l2_topic),
                        inherited_notes=self._collect_notes(l2_topic),
                        current_depth=0,
                    )
                )

        return test_points

    def _collect_leaf_test_points(
        self,
        topic: ET.Element,
        module_name: str,
        function_name: str,
        inherited_priority: Optional[int],
        inherited_notes: List[str],
        current_depth: int,
    ) -> List[Dict[str, Any]]:
        if current_depth >= self.MAX_DEPTH:
            logger.warning(f"递归深度达到上限 {self.MAX_DEPTH} 层，截断深层节点")
            return []

        child_topics = self._get_child_topics(topic)
        if not child_topics:
            point_text = self._extract_topic_text(topic)
            if not point_text:
                return []
            point_text = self._append_notes_to_point(point_text, inherited_notes)
            point_text = self._truncate_field(point_text, "point", self.POINT_MAX_LEN)
            priority = inherited_priority if inherited_priority is not None else 2
            return [
                self._build_test_point(module_name, function_name, point_text, priority)
            ]

        test_points: List[Dict[str, Any]] = []
        for child in child_topics:
            child_priority = self._extract_priority_marker(child)
            next_priority = (
                child_priority if child_priority is not None else inherited_priority
            )
            next_notes = inherited_notes + self._collect_notes(child)
            child_points = self._collect_leaf_test_points(
                topic=child,
                module_name=module_name,
                function_name=function_name,
                inherited_priority=next_priority,
                inherited_notes=next_notes,
                current_depth=current_depth + 1,
            )
            if not child_points and not self._extract_topic_text(child):
                logger.warning(
                    "跳过空文本的叶子节点（模块: %s）",
                    module_name,
                )
            test_points.extend(child_points)
        return test_points

    def _build_test_point(
        self, module: str, function: str, point: str, priority: int
    ) -> Dict[str, Any]:
        return {
            "module": module,
            "function": function,
            "point": point,
            "priority": priority,
        }
