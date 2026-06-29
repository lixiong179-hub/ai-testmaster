"""网址驱动快速测试 - 用例生成 Prompt 构建 Mixin。

将测试点与被测页面真实 DOM 元素组织为 DeepSeek Prompt，核心约束是
"禁止编造元素，只能使用表格中列出的元素"，从源头保证用例可执行性。

设计要点：
- 元素清单以 Markdown 表格注入（role/name/locator），AI 可直接引用 locator；
- 用户 description 用于聚焦测试范围（如"重点测试购物车"），为空时不注入聚焦段；
- 输出格式约束为 JSON，每测试点生成 3-5 条用例（正向+边界+异常）；
- 单文件聚焦 Prompt 文案，与生成主流程/校验逻辑解耦，便于随 Prompt 演进独立调整。
"""
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from app.services.url_driven.site_explorer import PageSnapshot

# 单测试点用例数量上下限（spec：每测试点生成 3-5 条）
_CASES_MIN_PER_POINT = 3
_CASES_MAX_PER_POINT = 5

# 元素清单 Markdown 表格列定义，与 _render_elements_table 输出保持一致
_ELEMENT_TABLE_HEADER = "| 序号 | role | name | locator |\n|------|------|------|---------|"

# 禁编造强约束文案，独立常量便于测试断言与统一调整
_NO_FABRICATION_RULE = (
    "⚠️ 严禁编造元素：步骤中引用的所有 target_element 必须且只能来自"
    "上方元素清单表格，禁止使用表格中不存在的元素名称或 locator。"
    "若无合适元素，改用导航类步骤或显式标注\"无可用元素\"，不得臆造控件。"
)

# AI 输出 JSON Schema 描述（写入 prompt 约束格式，schema 参数亦同时传入）
_OUTPUT_JSON_SPEC = (
    "请以纯 JSON 输出（不要包裹 markdown 代码块、不要解释文字），结构如下：\n"
    "{\n"
    '  "cases": [\n'
    "    {\n"
    '      "title": "用例标题",\n'
    '      "case_category": "positive|boundary|exception",\n'
    '      "precondition": "前置条件",\n'
    '      "priority": 1,\n'
    '      "steps": [\n'
    '        {"action": "操作描述", "action_type": "click|input|navigate|verify", '
    '"target_element": "必须等于元素清单中的 name", "input_value": "可选"}\n'
    "      ],\n"
    '      "expected_result": "预期结果"\n'
    "    }\n"
    "  ]\n"
    "}"
)

# 禁 JS 表达式强约束：AI 偶发把 "a".repeat(500) 当 JSON 值导致解析失败 → 0 用例
# 解析层已有 strip_js_string_methods 兜底，此处从源头约束减少发生
_NO_JS_EXPRESSION_RULE = (
    "⚠️ 所有值必须是 JSON 字面量：禁止使用任何 JavaScript 表达式，"
    "如 \"a\".repeat(500)、\"x\".padEnd(100, \"0\")、Array(10).fill(0) 等。"
    "字符串值直接写字面量（如 \"test_input\"），数值直接写数字。"
)


class PromptMixin:
    """用例生成 Prompt 构建 Mixin。

    提供 _build_prompt 与元素清单渲染能力，自身不持有状态，依赖宿主传入
    test_point 与 PageSnapshot。Prompt 文案常量集中在本模块，便于统一调优。
    """

    def _build_prompt(
        self,
        test_point: Dict[str, Any],
        page_snapshot: "PageSnapshot",
        description: Optional[str],
    ) -> str:
        """构建单测试点的 AI 生成 Prompt。

        Prompt 结构（自上而下）：
        1. 角色与任务概述（专业测试工程师，基于真实页面元素生成可执行用例）；
        2. 被测页面信息（URL/标题/测试点类型/相关元素摘要）；
        3. 元素清单 Markdown 表格（role/name/locator）+ 禁编造强约束；
        4. 用户 description 聚焦段（可选，聚焦测试范围）；
        5. 用例数量与覆盖要求（3-5 条，正向+边界+异常）；
        6. 输出 JSON 格式约束。

        Args:
            test_point: 测试点字典，含 test_point_type/target_page_url/related_elements。
            page_snapshot: 测试点目标页快照，提供真实元素清单。
            description: 用户自然语言描述，用于聚焦测试范围，None 表示无聚焦。

        Returns:
            str: 拼装完成的 Prompt 文本。
        """
        element_table = self._render_elements_table(page_snapshot.elements)
        related_summary = self._summarize_related_elements(test_point)
        focus_section = self._render_focus_section(description)
        return (
            f"你是一名资深的 Web 自动化测试工程师。请基于下方被测页面的真实可交互元素清单，"
            f"为指定测试点生成可执行的测试用例。\n\n"
            f"## 被测页面\n"
            f"- URL: {page_snapshot.url}\n"
            f"- 页面标题: {page_snapshot.title}\n"
            f"- 测试点类型: {test_point.get('test_point_type', 'unknown')}\n"
            f"- 相关元素: {related_summary}\n\n"
            f"## 被测页面实际元素清单\n"
            f"{element_table}\n\n"
            f"{_NO_FABRICATION_RULE}\n\n"
            f"{focus_section}"
            f"## 用例要求\n"
            f"- 为该测试点生成 {_CASES_MIN_PER_POINT}-{_CASES_MAX_PER_POINT} 条用例，"
            f"覆盖正向（positive）、边界（boundary）、异常（exception）三类场景；\n"
            f"- 每条用例的 steps 中 target_element 必须严格取自上方元素清单的 name 列；\n"
            f"- action_type 仅可选 click/input/navigate/verify，需与元素角色语义匹配"
            f"（如 textbox 适合 input，button/link 适合 click）；\n"
            f"- priority 取 1（高）/2（中）/3（低）。\n\n"
            f"## 输出格式\n"
            f"{_OUTPUT_JSON_SPEC}\n\n"
            f"{_NO_JS_EXPRESSION_RULE}\n"
        )

    def _render_elements_table(self, elements: List[Dict[str, Any]]) -> str:
        """渲染元素清单为 Markdown 表格（序号/role/name/locator）。

        空元素清单时返回占位提示，避免 AI 在空表上臆造元素。
        """
        if not elements:
            return _ELEMENT_TABLE_HEADER + "\n| （无可用元素） | - | - | - |"
        rows = [_ELEMENT_TABLE_HEADER]
        for idx, element in enumerate(elements, start=1):
            role = str(element.get("role", "")).replace("|", "\\|")
            name = str(element.get("name", "")).replace("|", "\\|")
            locator = str(element.get("locator", "")).replace("|", "\\|")
            rows.append(f"| {idx} | {role} | {name} | {locator} |")
        return "\n".join(rows)

    def _summarize_related_elements(self, test_point: Dict[str, Any]) -> str:
        """生成测试点相关元素摘要（name 列表），无相关元素时返回提示。"""
        related = test_point.get("related_elements") or []
        names = [
            str(element.get("name", "")).strip()
            for element in related
            if isinstance(element, dict) and element.get("name")
        ]
        if not names:
            return "（未识别到强相关元素，请结合整页清单选择）"
        return "、".join(names)

    def _render_focus_section(self, description: Optional[str]) -> str:
        """渲染用户 description 聚焦段，为空时返回空串不注入聚焦约束。"""
        if not description or not description.strip():
            return ""
        return (
            "## 用户聚焦范围\n"
            f"用户希望重点测试：{description.strip()}\n"
            "请在生成时优先覆盖用户聚焦的功能点，但仍须遵守禁编造约束。\n\n"
        )
