"""视图配置Mixin - 提供视图可见性配置和统计功能。

包含:
    - update_step_view_config: 更新单个步骤的视图可见性
    - batch_update_view_config: 批量更新视图可见性
    - get_view_statistics: 获取视图统计信息
    - get_locator_coverage: 获取定位覆盖率统计
"""
from typing import Dict, Any, Optional
from loguru import logger

from app.models.test_case import TestStep
from app.models.enums import LocatorStatus


class ViewConfigMixin:

    def update_step_view_config(
        self,
        step_id: int,
        is_business_view: Optional[int] = None,
        is_technical_view: Optional[int] = None
    ) -> bool:
        """更新单个步骤的视图可见性配置。

        Args:
            step_id: 步骤ID。
            is_business_view: 是否在业务视图显示（0/1），可选。
            is_technical_view: 是否在技术视图显示（0/1），可选。

        Returns:
            更新成功返回True，步骤不存在返回False。
        """
        step = self.db.query(TestStep).filter(TestStep.id == step_id).first()
        if not step:
            logger.warning(f"步骤不存在: {step_id}")
            return False

        if is_business_view is not None:
            step.is_business_view = is_business_view
        if is_technical_view is not None:
            step.is_technical_view = is_technical_view

        self.db.commit()
        logger.info(f"更新步骤 {step_id} 视图配置成功")
        return True

    def batch_update_view_config(
        self,
        test_case_id: int,
        view_type: str,
        visible: bool
    ) -> int:
        """批量更新测试用例所有步骤的视图可见性配置。

        Args:
            test_case_id: 测试用例ID。
            view_type: 视图类型，'business'或'technical'。
            visible: 是否可见。

        Returns:
            更新的步骤数量，视图类型无效时返回0。
        """
        value = 1 if visible else 0

        if view_type == "business":
            count = self.db.query(TestStep).filter(
                TestStep.test_case_id == test_case_id
            ).update({"is_business_view": value})
        elif view_type == "technical":
            count = self.db.query(TestStep).filter(
                TestStep.test_case_id == test_case_id
            ).update({"is_technical_view": value})
        else:
            logger.error(f"未知的视图类型: {view_type}")
            return 0

        self.db.commit()
        logger.info(f"批量更新测试用例 {test_case_id} 的 {view_type} 视图配置: {count} 个步骤")
        return count

    def get_view_statistics(self, test_case_id: int) -> Dict[str, Any]:
        """获取测试用例的视图统计信息。"""
        steps = self.db.query(TestStep).filter(
            TestStep.test_case_id == test_case_id
        ).all()

        total = len(steps)
        business_visible = sum(1 for s in steps if s.is_business_view == 1)
        technical_visible = sum(1 for s in steps if s.is_technical_view == 1)
        has_locator_count = sum(1 for s in steps if s.has_locator == 1)

        return {
            "total_steps": total,
            "business_view_steps": business_visible,
            "technical_view_steps": technical_visible,
            "located_steps": has_locator_count,
            "locator_coverage": f"{has_locator_count / total * 100:.1f}%" if total > 0 else "0%"
        }

    def get_locator_coverage(self, test_case_id: int) -> Dict[str, Any]:
        """获取测试用例的定位覆盖率统计。"""
        steps = self.db.query(TestStep).filter(
            TestStep.test_case_id == test_case_id
        ).all()

        total = len(steps)
        located = sum(1 for s in steps if s.has_locator == 1)
        pending = sum(1 for s in steps if s.locator_status == LocatorStatus.PENDING.value)
        failed = sum(1 for s in steps if s.locator_status == LocatorStatus.FAILED.value)

        return {
            "total_steps": total,
            "located_steps": located,
            "pending_steps": pending,
            "failed_steps": failed,
            "coverage_percentage": (located / total * 100) if total > 0 else 0.0
        }
