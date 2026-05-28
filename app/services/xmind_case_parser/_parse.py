import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.constants import DEFAULT_AI_FALLBACK_CASE_TYPE
from app.services.xmind_parser import XmindParseError
from app.services.xmind_case_parser._classify import TopicNode, _ClassifyMixin


class _ParseMixin:

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        root_topics = self._load_all_root_topics(file_path)
        cases: List[Dict[str, Any]] = []

        for root_topic in root_topics:
            module_nodes = self._get_child_topics(root_topic)
            for module_topic in module_nodes:
                module_name = self._extract_topic_text(module_topic)
                if not module_name:
                    continue
                module_name = self._truncate_field(module_name, self.MODULE_MAX_LEN)
                module_node = self._build_topic_tree(module_topic)
                for path in self._collect_leaf_paths(module_node):
                    case = self._build_case_from_path(module_name, path)
                    if case:
                        cases.append(case)

        deduped = self._dedupe_cases(cases)
        logger.info(f"XMind 场景解析完成，共提取 {len(deduped)} 条测试用例")
        return deduped

    def _load_all_root_topics(self, file_path: str) -> List[ET.Element]:
        from app.services.xmind_parser import XmindParser
        xml_loader = XmindParser()
        content = xml_loader._extract_content_xml(file_path)

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            logger.error(f"XML 解析失败: {exc}")
            raise XmindParseError("无法解析 XMind 文件内容，请确认文件格式正确") from exc

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

    def _build_topic_tree(self, topic: ET.Element) -> TopicNode:
        return TopicNode(
            title=self._extract_topic_text(topic),
            priority=self._extract_priority_marker(topic),
            notes=self._extract_topic_notes(topic),
            children=[self._build_topic_tree(child) for child in self._get_child_topics(topic)],
        )

    def _collect_leaf_paths(
        self,
        node: TopicNode,
        path: Optional[List[TopicNode]] = None,
    ) -> List[List[TopicNode]]:
        current_path = (path or []) + [node]
        if not node.children:
            return [current_path]

        leaf_paths: List[List[TopicNode]] = []
        for child in node.children:
            leaf_paths.extend(self._collect_leaf_paths(child, current_path))
        return leaf_paths

    def _build_case_from_path(
        self,
        module_name: str,
        path: List[TopicNode],
    ) -> Optional[Dict[str, Any]]:
        if len(path) < 2:
            return None

        segments = path[1:]
        texts = [segment.title.strip() for segment in segments if segment.title.strip()]
        if not texts:
            return None

        preconditions: List[str] = []
        actions: List[str] = []
        expectations: List[str] = []
        deferred_context: List[str] = []
        ignored_count = 0

        for text in texts:
            classification = self._classify_text(text)
            if classification == "ignore":
                ignored_count += 1
                continue
            if classification == "action":
                actions.append(text)
                continue
            if classification == "expected":
                expectations.append(text)
                continue
            if classification == "condition":
                if actions:
                    deferred_context.append(text)
                else:
                    preconditions.append(text)
                continue
            if actions:
                expectations.append(text)
            else:
                preconditions.append(text)

        preconditions.extend(deferred_context)

        if not actions and not expectations:
            return None

        expected_result = "；".join(expectations).strip()
        if not expected_result and actions:
            expected_result = f"{actions[-1]}后结果符合预期"
        if not actions:
            actions = [f"检查并确认：{expectations[0]}"]

        steps = self._build_steps(actions, expected_result)
        title = self._infer_case_title(texts, actions, expected_result, module_name)
        notes = [segment.notes.strip() for segment in segments if segment.notes.strip()]
        if notes:
            preconditions.extend(note for note in notes if note not in preconditions)

        priority = self._infer_priority(segments)
        return {
            "module": module_name,
            "function": self._infer_function_name(texts, module_name),
            "title": title,
            "point": title,
            "precondition": "\n".join(preconditions).strip(),
            "steps": steps,
            "expected_result": expected_result,
            "priority": priority,
            "case_type": DEFAULT_AI_FALLBACK_CASE_TYPE,
            "source_depth": len(segments),
            "action_count": len(actions),
            "expected_count": len(expectations),
            "condition_count": len(preconditions),
            "ignored_count": ignored_count,
        }

    def _dedupe_cases(self, cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: List[Dict[str, Any]] = []
        seen = set()
        for case in cases:
            step_signature = tuple(
                (step.get("action", ""), step.get("expected_result", ""))
                for step in case.get("steps", [])
                if isinstance(step, dict)
            )
            key = (
                case["module"],
                case["title"],
                case["precondition"],
                case["expected_result"],
                step_signature,
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(case)
        return unique
