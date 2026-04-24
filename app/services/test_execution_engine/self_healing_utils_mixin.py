"""自愈工具Mixin - 提供选择器构建、定位器回写、统计等工具方法。

包含:
    - _get_nl_description: 获取步骤自然语言描述
    - _sanitize_css_identifier: CSS标识符清理
    - _build_healed_selector: 根据元素属性构建选择器
    - _update_locator_after_healing: 自愈后回写定位器（乐观锁）
    - get_self_healing_summary: 自愈统计摘要
"""
from typing import Optional, Dict, Any
from loguru import logger
from sqlalchemy import text as sql_text

from app.models.element_locator import ElementLocator


class SelfHealingUtilsMixin:

    async def _get_nl_description(self, step_id: int) -> str:
        """获取步骤的自然语言描述。"""
        from app.models.test_case import TestStep
        try:
            test_step = self.db.query(TestStep).filter(
                TestStep.id == step_id
            ).first()

            if test_step:
                parts = []
                if test_step.action:
                    parts.append(test_step.action)
                if hasattr(test_step, 'input_value') and test_step.input_value:
                    parts.append(test_step.input_value)
                desc = " ".join(parts).strip()
                if desc:
                    return desc

            locator = self.db.query(ElementLocator).filter(
                ElementLocator.step_id == step_id
            ).first()

            if locator and locator.element_description:
                return locator.element_description

            logger.warning(f"未找到步骤 {step_id} 的自然语言描述")
            return ""
        except Exception as e:
            logger.warning(f"获取步骤 {step_id} 自然语言描述失败: {e}")
            return ""

    @staticmethod
    def _sanitize_css_identifier(value: str) -> str:
        """清理CSS标识符中的特殊字符，防止选择器注入。"""
        import re as _re
        sanitized = _re.sub(r"[^a-zA-Z0-9_\-]", "", value)
        sanitized = _re.sub(r"-{2,}", "-", sanitized)
        sanitized = sanitized.strip("-_")
        return sanitized

    def _build_healed_selector(self, element_attrs: Dict[str, Any]) -> Optional[str]:
        """根据元素属性构建自愈后的CSS选择器。

        优先级: id > name > placeholder > class组合 > tag+type
        """
        elem_id = element_attrs.get("id")
        if elem_id:
            safe_id = self._sanitize_css_identifier(elem_id)
            if safe_id:
                return f"#{safe_id}"

        elem_name = element_attrs.get("name")
        if elem_name:
            safe_name = self._sanitize_css_identifier(elem_name)
            if safe_name:
                return f"[name='{safe_name}']"

        placeholder = element_attrs.get("placeholder")
        if placeholder:
            truncated = placeholder[:10].replace("'", "")
            safe_ph = self._sanitize_css_identifier(truncated)
            if safe_ph:
                return f"[placeholder*='{safe_ph}']"

        elem_class = element_attrs.get("class")
        tag = self._sanitize_css_identifier(element_attrs.get("tag", ""))
        elem_type = self._sanitize_css_identifier(element_attrs.get("type", ""))

        if elem_class:
            classes = [self._sanitize_css_identifier(c) for c in elem_class.split()[:2]]
            classes = [c for c in classes if c]
            if classes:
                class_selector = "." + ".".join(classes)
                if tag:
                    return f"{tag}{class_selector}"
                return class_selector

        if tag and elem_type:
            return f"{tag}[type='{elem_type}']"
        if tag:
            return tag

        return None

    async def _update_locator_after_healing(
        self,
        locator_record_id: int,
        new_selector: str,
        old_selector: Optional[str] = None
    ) -> bool:
        """自愈成功后回写新定位器到数据库（含乐观锁 + 审计历史）。"""
        if not new_selector:
            logger.warning("新选择器为空，跳过回写")
            return False

        try:
            locator = self.db.query(ElementLocator).filter(
                ElementLocator.id == locator_record_id
            ).first()

            if not locator:
                logger.warning(f"定位器记录不存在: {locator_record_id}")
                return False

            current_version = locator.version
            old_css = locator.css_selector

            result = self.db.execute(sql_text(
                "UPDATE element_locators SET css_selector = :new_selector, "
                "source = 'ai_self_healing', "
                "updated_at = UTC_TIMESTAMP(), version = version + 1 "
                "WHERE id = :id AND version = :version"
            ), {
                "new_selector": new_selector,
                "id": locator_record_id,
                "version": current_version
            })
            self.db.commit()

            if result.rowcount > 0:
                logger.info(
                    f"定位器回写成功 | ID: {locator_record_id} | "
                    f"旧选择器: {old_css or old_selector} | 新选择器: {new_selector} | "
                    f"版本: {current_version} -> {current_version + 1}"
                )
                return True
            else:
                logger.warning(
                    f"定位器回写失败（乐观锁冲突）| ID: {locator_record_id} | "
                    f"当前版本: {current_version}，可能已被其他进程更新"
                )
                return False

        except Exception as e:
            self.db.rollback()
            logger.error(f"定位器回写异常 | ID: {locator_record_id} | 错误: {e}")
            return False

    def get_self_healing_summary(self) -> Dict[str, Any]:
        """获取自愈统计摘要。"""
        from app.core.config import settings
        success_rate = 0.0
        if self._self_healing_attempts > 0:
            success_rate = self._self_healing_successes / self._self_healing_attempts

        return {
            "self_healing_attempts": self._self_healing_attempts,
            "self_healing_successes": self._self_healing_successes,
            "self_healing_success_rate": round(success_rate, 4),
            "self_healing_enabled": settings.AI_SELF_HEALING_ENABLED,
            "stagehand_available": bool(settings.BROWSERBASE_API_KEY and settings.BROWSERBASE_PROJECT_ID)
        }
