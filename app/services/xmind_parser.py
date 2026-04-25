"""XMind 文件解析器 - 将 .xmind 文件解析为测试点数据。

支持 XMind R3.x 标准格式（.xmind 文件为 ZIP 压缩包）。
解析规则:
    - 根主题: 忽略
    - 一级子主题: module
    - 二级子主题: function
    - 二级子主题以下的最末级叶子节点: point

依赖关系:
    - Python 标准库: zipfile, xml.etree.ElementTree
"""
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from loguru import logger


class XmindParseError(Exception):
    """XMind 解析异常基类。"""
    pass


class XmindParser:
    """XMind 文件解析器。

    支持 XMind R3.x 标准格式，将思维导图层级结构映射为
    module/function/point/priority 测试点数据。

    字段映射规则:
        - 根主题 → 忽略
        - 一级子主题 → module（最大100字符）
        - 二级子主题 → function（最大200字符）
        - 二级子主题以下的最末级叶子节点 → point（最大500字符）
        - 优先级标记 → priority（1高/2中/3低，默认2）

    异常处理:
        - 文件非ZIP格式 → XmindParseError
        - content.xml缺失 → XmindParseError
        - XML解析失败 → XmindParseError
        - 节点文本为空 → 跳过并记录WARNING
        - 字段超长 → 截断并记录WARNING
    """

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

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        """解析 XMind 文件，返回测试点列表。

        Args:
            file_path: .xmind 文件绝对路径。

        Returns:
            测试点字典列表，每条包含 module/function/point/priority 字段。

        Raises:
            XmindParseError: 文件格式错误或解析失败时抛出。
        """
        content_xml = self._extract_content_xml(file_path)
        root = self._parse_xml(content_xml)
        root_topic = self._get_root_topic(root)
        return self._parse_topics(root_topic)

    def _extract_content_xml(self, file_path: str) -> bytes:
        """从 .xmind 文件中提取 content.xml。

        Args:
            file_path: .xmind 文件路径。

        Returns:
            content.xml 的原始字节数据。

        Raises:
            XmindParseError: 文件非ZIP格式或content.xml缺失时抛出。
        """
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                if "content.xml" not in zf.namelist():
                    raise XmindParseError("XMind 文件内容缺失，文件可能已损坏")
                return zf.read("content.xml")
        except zipfile.BadZipFile:
            raise XmindParseError("无效的 XMind 文件格式，请上传 .xmind 文件")
        except XmindParseError:
            raise
        except Exception as e:
            raise XmindParseError(f"读取 XMind 文件失败: {e}") from e

    def _parse_xml(self, content: bytes) -> ET.Element:
        """解析 XML 内容，自动处理命名空间。

        Args:
            content: XML 原始字节数据。

        Returns:
            XML 根元素。

        Raises:
            XmindParseError: XML 解析失败时抛出。
        """
        try:
            root = ET.fromstring(content)
            return root
        except ET.ParseError as e:
            raise XmindParseError(f"无法解析 XMind 文件内容: {e}") from e

    def _get_root_topic(self, root: ET.Element) -> ET.Element:
        """获取 sheet 下的根主题元素。

        Args:
            root: XML 根元素。

        Returns:
            根主题 topic 元素。

        Raises:
            XmindParseError: 未找到 sheet 或 topic 时抛出。
        """
        sheet = self._find_element(root, "sheet")
        if sheet is None:
            raise XmindParseError("XMind 文件中未找到 sheet 元素")

        topic = self._find_element(sheet, "topic")
        if topic is None:
            raise XmindParseError("XMind 文件中未找到根主题")

        return topic

    def _find_element(self, parent: ET.Element, tag: str) -> Optional[ET.Element]:
        """在父元素中查找指定标签的元素，支持两种命名空间写法。

        Args:
            parent: 父元素。
            tag: 标签名称。

        Returns:
            找到的元素，未找到返回 None。
        """
        elem = parent.find(f"xmap:{tag}", self.NS)
        if elem is None:
            elem = parent.find(f"{{{self.XMAP_NS}}}{tag}")
        return elem

    def _parse_topics(self, root_topic: ET.Element) -> List[Dict[str, Any]]:
        """递归解析主题层级，提取测试点数据。

        遍历根主题的子节点，按层级映射为 module/function/point。
        规则调整为: 二级功能节点以下，每个最末级叶子节点单独生成一条测试点。

        Args:
            root_topic: 根主题元素。

        Returns:
            测试点字典列表。
        """
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
                function_name = self._extract_topic_text(l2_topic)
                if not function_name:
                    logger.warning("跳过空文本的二级节点（模块: %s）", module_name)
                    continue
                function_name = self._truncate_field(
                    function_name, "function", self.FUNCTION_MAX_LEN
                )
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

        logger.info(f"XMind 解析完成，共提取 {len(test_points)} 条测试点")
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
        """收集指定主题下所有叶子节点，并映射为测试点。

        规则:
            - 二级功能节点本身如果就是叶子，则也视为一条测试点
            - 更深层级仅取最末级叶子节点标题作为 point
            - 优先级沿父链继承，叶子节点自身标记优先
            - 备注沿父链累积，并追加到最终 point 文本
        """
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
                    "跳过空文本的叶子节点（模块: %s, 功能: %s）",
                    module_name,
                    function_name,
                )
            test_points.extend(child_points)
        return test_points

    def _build_test_point(
        self, module: str, function: str, point: str, priority: int
    ) -> Dict[str, Any]:
        """构建测试点字典。

        Args:
            module: 模块名称。
            function: 功能名称。
            point: 测试点描述。
            priority: 优先级（1-3）。

        Returns:
            测试点字典。
        """
        return {
            "module": module,
            "function": function,
            "point": point,
            "priority": priority,
        }

    def _get_child_topics(self, topic: ET.Element) -> List[ET.Element]:
        """获取 topic 元素的子主题列表。

        Args:
            topic: 父主题元素。

        Returns:
            子主题元素列表。
        """
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
        """提取主题节点的文本内容。

        Args:
            topic: 主题元素。

        Returns:
            节点文本，无文本时返回空字符串。
        """
        title = self._find_element(topic, "title")
        if title is None:
            return ""
        return (title.text or "").strip()

    def _extract_topic_notes(self, topic: ET.Element) -> str:
        """提取主题节点的备注文本。

        Args:
            topic: 主题元素。

        Returns:
            备注文本，无备注时返回空字符串。
        """
        notes = self._find_element(topic, "notes")
        if notes is None:
            return ""

        plain = self._find_element(notes, "plain")
        if plain is not None and plain.text:
            return plain.text.strip()
        return ""

    def _collect_notes(self, topic: ET.Element) -> List[str]:
        """提取当前节点备注，并以列表形式返回。"""
        notes = self._extract_topic_notes(topic)
        return [notes] if notes else []

    def _detect_priority(self, topic: ET.Element) -> int:
        """识别主题节点的优先级标记。

        优先级映射规则:
            - priority-1 / smiley-smile / task-done → 1（高）
            - priority-2 / smiley-neutral / task-start → 2（中）
            - priority-3 / smiley-cry / task-undo → 3（低）
            - 无标记 → 2（默认中）

        Args:
            topic: 主题元素。

        Returns:
            优先级数值（1-3）。
        """
        priority = self._extract_priority_marker(topic)
        return priority if priority is not None else 2

    def _extract_priority_marker(self, topic: ET.Element) -> Optional[int]:
        """提取节点上显式设置的优先级标记。"""
        marker_refs = self._find_element(topic, "marker-refs")
        if marker_refs is None:
            return None

        for ref in marker_refs.findall("xmap:marker-ref", self.NS):
            marker_id = ref.get("marker-id", "")
            if marker_id in self.PRIORITY_MAP:
                return self.PRIORITY_MAP[marker_id]
        return None

    def _append_notes_to_point(self, point_text: str, notes_list: List[str]) -> str:
        """将路径上的备注信息追加到最终测试点文本。"""
        if not notes_list:
            return point_text
        unique_notes = list(dict.fromkeys(note for note in notes_list if note))
        if not unique_notes:
            return point_text
        return point_text + "".join(f"\n备注: {note}" for note in unique_notes)

    def extract_paths(self, file_path: str) -> List[List[str]]:
        """提取 XMind 中从模块到叶子的完整路径列表。

        用于 AI 增强模式，将原始路径交给 LLM 进行语义解析。

        Args:
            file_path: .xmind 文件绝对路径。

        Returns:
            路径列表，每条路径是节点文本的字符串列表。
        """
        content_xml = self._extract_content_xml(file_path)
        root = self._parse_xml(content_xml)
        root_topic = self._get_root_topic(root)
        return self._collect_paths(root_topic)

    def _collect_paths(self, root_topic: ET.Element) -> List[List[str]]:
        """收集所有从一级模块节点到叶子节点的完整路径。"""
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
        """递归收集从当前节点到叶子的所有路径。"""
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
        """截断超长字段并记录警告日志。

        Args:
            value: 原始字段值。
            field_name: 字段名称（用于日志）。
            max_len: 最大允许长度。

        Returns:
            截断后的字段值。
        """
        if len(value) <= max_len:
            return value
        logger.warning(
            f"字段 {field_name} 超长（{len(value)} > {max_len}），已截断: {value[:30]}...",
        )
        return value[:max_len]
