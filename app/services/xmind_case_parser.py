"""XMind 场景树解析器。

将更接近“测试用例脑图”的 XMind 结构解析为结构化测试用例。
适用场景:
    - 一级节点表示模块
    - 后续分支混合了前置条件、操作步骤、结果描述
    - 不要求显式存在“前置条件/步骤/预期结果”标题，而是根据文本语义推断
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from app.services.xmind_parser import XmindParseError


@dataclass
class TopicNode:
    """XMind 主题树节点。"""

    title: str
    priority: Optional[int] = None
    notes: str = ""
    children: List["TopicNode"] = field(default_factory=list)


class XmindCaseParser:
    """将场景树形式的 XMind 解析为测试用例。"""

    XMAP_NS = "urn:xmind:xmap:xmlns:content:2.0"
    NS = {"xmap": XMAP_NS}
    MODULE_MAX_LEN = 100
    TITLE_MAX_LEN = 255
    POINT_MAX_LEN = 500
    PRECONDITION_HINTS = (
        "有",
        "无",
        "未",
        "已",
        "默认",
        "从",
        "支持",
        "当前",
        "存在",
        "不存在",
        "有记录",
        "无记录",
        "有内容",
        "无内容",
        "有教材",
        "无网络",
    )
    ACTION_PATTERNS = (
        "点击",
        "选择",
        "勾选",
        "输入",
        "提交",
        "删除",
        "确认",
        "取消",
        "修改",
        "播放",
        "收藏",
        "切换",
        "清空",
        "关闭",
        "检查",
        "开始",
        "继续",
        "返回",
        "退出",
        "查看",
        "重试",
        "编辑",
    )
    EXPECTED_PATTERNS = (
        "界面显示",
        "界面提示",
        "提示",
        "显示",
        "置灰",
        "不可点击",
        "默认",
        "成功",
        "失败",
        "跳转",
        "进入",
        "仍然",
        "返回到",
        "toast",
        "弹窗",
        "自动",
        "不出现",
        "出现",
        "倒计时",
        "切换为",
    )
    IGNORE_PATTERNS = (
        "界面详见UI",
        "界面参照UI",
        "界面显示见UI",
        "详见UI",
        "参照UI",
    )

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        """解析 XMind 文件并返回结构化测试用例。"""
        root_topic = self._load_root_topic(file_path)
        module_nodes = self._get_child_topics(root_topic)
        cases: List[Dict[str, Any]] = []

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

    def _load_root_topic(self, file_path: str) -> ET.Element:
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                if "content.xml" not in zf.namelist():
                    raise XmindParseError("XMind 文件内容缺失，文件可能已损坏")
                content = zf.read("content.xml")
        except zipfile.BadZipFile:
            raise XmindParseError("无效的 XMind 文件格式，请上传 .xmind 文件")
        except XmindParseError:
            raise
        except Exception as exc:
            logger.error(f"读取 XMind 文件失败: {exc}")
            raise XmindParseError("读取 XMind 文件失败，请检查文件是否损坏") from exc

        try:
            root = ET.fromstring(content)
        except ET.ParseError as exc:
            logger.error(f"XML 解析失败: {exc}")
            raise XmindParseError("无法解析 XMind 文件内容，请确认文件格式正确") from exc

        sheet = self._find_element(root, "sheet")
        if sheet is None:
            raise XmindParseError("XMind 文件中未找到 sheet 元素")
        topic = self._find_element(sheet, "topic")
        if topic is None:
            raise XmindParseError("XMind 文件中未找到根主题")
        return topic

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
            "case_type": "manual",
            "source_depth": len(segments),
            "action_count": len(actions),
            "expected_count": len(expectations),
            "condition_count": len(preconditions),
            "ignored_count": ignored_count,
        }

    def _infer_function_name(self, texts: List[str], module_name: str) -> str:
        """推断功能名称（AI中间产物，不存库，仅作提示词上下文）。"""
        if len(texts) >= 2:
            return self._truncate_field(texts[1], self.TITLE_MAX_LEN)
        return ""

    def _infer_case_title(
        self,
        texts: List[str],
        actions: List[str],
        expected_result: str,
        module_name: str,
    ) -> str:
        if actions and expected_result:
            title = f"{actions[-1]}，{expected_result}"
        elif actions:
            title = actions[-1]
        elif expected_result:
            title = expected_result
        elif texts:
            title = texts[0]
        else:
            title = module_name
        return self._truncate_field(title, self.TITLE_MAX_LEN)

    def _build_steps(self, actions: List[str], overall_expected: str) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        for index, action in enumerate(actions, start=1):
            steps.append(
                {
                    "step": index,
                    "action": action,
                    "expected_result": overall_expected if index == len(actions) else "",
                    "param": "",
                }
            )
        return steps

    def _infer_priority(self, segments: List[TopicNode]) -> int:
        for segment in reversed(segments):
            if segment.priority is not None:
                return segment.priority
        return 2

    def _classify_text(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return "ignore"
        if any(pattern in normalized for pattern in self.IGNORE_PATTERNS):
            return "ignore"
        if any(pattern in normalized for pattern in self.ACTION_PATTERNS):
            return "action"
        if any(pattern in normalized for pattern in self.EXPECTED_PATTERNS):
            return "expected"
        if normalized.startswith(self.PRECONDITION_HINTS):
            return "condition"
        if re.match(r"^\d+[.、]", normalized):
            return "action"
        return "other"

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
