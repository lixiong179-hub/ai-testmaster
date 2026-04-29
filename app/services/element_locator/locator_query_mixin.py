"""定位查询Mixin - 查询步骤的元素定位信息。
"""
from typing import Optional, Dict, Any, Generator
from contextlib import contextmanager
from loguru import logger

from app.models.element_locator import ElementLocator
from app.utils.db_time import utcnow


class LocatorQueryMixin:

    @contextmanager
    def transaction(self) -> Generator[None, None, None]:
        try:
            yield
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"数据库事务失败: {str(e)}")
            raise

    def get_locator(self, step_id: int) -> Optional[ElementLocator]:
        return self.db.query(ElementLocator).filter(
            ElementLocator.step_id == step_id
        ).first()

    def has_locator(self, step_id: int) -> bool:
        return self.get_locator(step_id) is not None

    def record_locator_success(self, step_id: int) -> None:
        locator = self.get_locator(step_id)
        if locator:
            locator.record_success()
            self.db.commit()
            logger.debug(f"步骤 {step_id}: 记录定位成功")

    def record_locator_failure(self, step_id: int) -> None:
        locator = self.get_locator(step_id)
        if locator:
            locator.record_failure()
            self.db.commit()
            logger.debug(f"步骤 {step_id}: 记录定位失败")

    def update_locator(
        self,
        step_id: int,
        css_selector: Optional[str] = None,
        xpath: Optional[str] = None,
        element_id: Optional[str] = None
    ) -> bool:
        locator = self.get_locator(step_id)
        if not locator:
            return False

        if css_selector:
            locator.css_selector = css_selector
        if xpath:
            locator.xpath = xpath
        if element_id:
            locator.element_id = element_id

        locator.updated_at = utcnow()
        self.db.commit()

        logger.info(f"步骤 {step_id}: 元素定位信息已更新")
        return True

    def delete_locator(self, step_id: int) -> bool:
        locator = self.get_locator(step_id)
        if not locator:
            return False

        self.db.delete(locator)
        self.db.commit()

        logger.info(f"步骤 {step_id}: 元素定位信息已删除")
        return True

    def get_locator_stats(self, step_id: int) -> Optional[Dict[str, Any]]:
        locator = self.get_locator(step_id)
        if not locator:
            return None

        return {
            "step_id": step_id,
            "success_count": locator.success_count,
            "fail_count": locator.fail_count,
            "success_rate": locator.success_rate,
            "last_used_at": locator.last_used_at,
            "priority_order": locator.priority_order
        }
