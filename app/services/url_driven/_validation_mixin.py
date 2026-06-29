"""网址驱动快速测试 - 元素锚定校验 Mixin。

复用已落地的 TestCase.element_verified_ratio 字段，对 AI 生成用例的步骤
target_element 与被测页面 PageSnapshot 真实元素做锚定校验，量化可执行性。

校验策略：
- target_element 精确匹配：与页面元素 name 精确相等记一次命中（含 locator 反查）；
- action 语义匹配：action_type 必须与元素 role 兼容（如 input 只能锚定可输入角色），
  语义不符视为未命中，从源头阻断"对 button 执行 input"这类不可执行用例；
- 无 target_element 的步骤（navigate/verify 纯文本）不计入分母，避免拉低 ratio；
- 返回 0.0-1.0 校验比例，钳制到合法区间，0.0 表示无任何锚定但不阻断生成。

设计要点：单文件聚焦校验算法，与生成主流程/Prompt 文案解耦，便于独立单测与调优。
"""
from typing import TYPE_CHECKING, Any, Dict, List

from loguru import logger

if TYPE_CHECKING:
    from app.services.url_driven.site_explorer import PageSnapshot

# 可输入角色：action_type=input 仅能锚定这些角色的元素
_INPUT_ROLES = frozenset({"textbox", "searchbox", "combobox", "textbox"})
# 可点击角色：action_type=click 仅能锚定这些角色的元素
_CLICK_ROLES = frozenset({"button", "link", "menuitem", "tab", "treeitem", "checkbox", "radio"})
# action_type → 兼容角色集合映射，未列出的 action_type 默认接受任意元素
_ACTION_ROLE_COMPAT: Dict[str, frozenset] = {
    "input": _INPUT_ROLES,
    "click": _CLICK_ROLES,
}


class ValidationMixin:
    """元素锚定校验 Mixin。

    提供 _validate_elements 计算单用例的 element_verified_ratio，自身不持有
    状态，依赖宿主传入 case 字典与 PageSnapshot。算法常量集中在本模块。
    """

    def _validate_elements(self, case: Dict[str, Any], page_snapshot: "PageSnapshot") -> float:
        """计算用例的 element_verified_ratio（0.0-1.0）。

        校验对象为 case["steps"] 中每个含 target_element 的步骤：
        - target_element 精确匹配页面元素 name 或 locator 命中元素记一次命中；
        - 命中后进一步校验 action_type 与元素 role 语义兼容，不符则降为未命中；
        - ratio = 命中步骤数 / 可校验步骤数，可校验步骤数=0 时返回 0.0。

        Args:
            case: AI 生成的单条用例字典，含 steps 列表。
            page_snapshot: 测试点目标页快照，提供真实元素清单。

        Returns:
            float: 0.0-1.0 的校验比例，钳制到合法区间。
        """
        steps = case.get("steps") or []
        if not isinstance(steps, list):
            return 0.0
        element_index = self._build_element_index(page_snapshot.elements)
        if not element_index:
            # 页面无元素清单：所有引用元素的步骤均无法锚定，ratio=0.0 不阻断生成
            return 0.0

        checked = 0
        hit = 0
        for step in steps:
            if not isinstance(step, dict):
                continue
            target = step.get("target_element")
            if not target:
                # 无 target_element 的步骤（navigate/verify 纯文本）不计入分母
                continue
            checked += 1
            matched_element = self._match_element(str(target), element_index)
            if matched_element is None:
                continue
            if self._action_role_compatible(step.get("action_type"), matched_element.get("role")):
                hit += 1
        if checked == 0:
            return 0.0
        ratio = hit / checked
        return max(0.0, min(1.0, ratio))

    def _build_element_index(
        self, elements: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """以小写 name 为主键构建元素索引，locator 作为副键反查。

        name 为空元素不进索引（避免空键碰撞），同名元素后写覆盖（取首条更稳定）。
        """
        index: Dict[str, Dict[str, Any]] = {}
        for element in elements or []:
            if not isinstance(element, dict):
                continue
            name = str(element.get("name", "")).strip()
            if not name:
                continue
            key = name.lower()
            if key not in index:
                index[key] = element
        return index

    def _match_element(
        self, target: str, element_index: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """精确匹配 target_element 到页面元素，命中返回元素字典否则 None。

        匹配优先级：
        1. target 精确等于元素 name（大小写不敏感）；
        2. target 精确等于元素 locator 字符串（AI 偶尔直接引用 locator）。
        """
        target_stripped = target.strip()
        if not target_stripped:
            return None
        key = target_stripped.lower()
        element = element_index.get(key)
        if element is not None:
            return element
        # locator 反查：AI 偶尔直接引用 locator 字符串
        for element in element_index.values():
            locator = str(element.get("locator", ""))
            if locator and locator == target_stripped:
                return element
        return None

    def _action_role_compatible(
        self, action_type: Any, role: Any
    ) -> bool:
        """校验 action_type 与元素 role 语义兼容。

        兼容规则：
        - input 仅兼容可输入角色（textbox/searchbox/combobox）；
        - click 仅兼容可点击角色（button/link/menuitem 等）；
        - 其他 action_type（navigate/verify/未指定）默认兼容，不阻断 ratio。

        Args:
            action_type: 步骤动作类型，可能为 None/空。
            role: 命中元素的 role，可能为空。

        Returns:
            True 表示语义兼容，False 表示不兼容（如对 button 执行 input）。
        """
        if not action_type or not role:
            return True
        action_str = str(action_type).strip().lower()
        role_str = str(role).strip().lower()
        compatible_roles = _ACTION_ROLE_COMPAT.get(action_str)
        if compatible_roles is None:
            # 未约束的 action_type 默认兼容，避免过度拦截
            return True
        compatible = role_str in compatible_roles
        if not compatible:
            logger.debug(
                f"元素语义不兼容: action_type={action_str} role={role_str}"
            )
        return compatible
