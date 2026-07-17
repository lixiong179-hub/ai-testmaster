"""测试用例视图异步操作 Mixin。

从 sync 版本（TechnicalViewMixin / BusinessViewMixin / ViewConfigMixin）镜像出 async 方法，
供 async 端点直接调用，消除 db.run_sync 线程池桥接开销。

设计要点：
    - 与 sync mixin 共存（hybrid 模式），sync 端点继续用 sync 方法；
    - async 方法使用 AsyncSession + select()/await db.execute()；
    - _build_technical_steps 等纯计算方法复用 sync 版本（TechnicalViewMixin）；
    - 方法名加 _async 后缀避免与 sync 方法冲突；
    - 由 TestCaseViewService 类继承，self.db 运行时为 AsyncSession。

使用方式：
    async def endpoint(..., db: AsyncSession):
        service = TestCaseViewService(db)  # db 为 AsyncSession
        view = await service.get_technical_view_async(test_case_id)
"""
from typing import Optional, Dict, Any, List

from loguru import logger
from sqlalchemy import select

from app.models.test_case import TestCase, TestStep, TestCasePreconditionStep
from app.models.element_locator import ElementLocator
from app.models.test_data import TestData
from app.models.enums import LocatorStatus
from app.services.test_case_view.models import BusinessStepView, BusinessTestCaseView


class TestCaseViewAsyncMixin:
    """测试用例视图异步操作 Mixin，供 TestCaseViewService 继承。

    要求 self.db 为 AsyncSession 实例。
    _build_technical_steps 等纯计算方法复用 sync 版本（TechnicalViewMixin）。
    """

    async def get_technical_view_async(
        self, test_case_id: int
    ) -> Optional[Dict[str, Any]]:
        """获取测试用例的技术视图（异步版本）。

        组装流程与 sync 版本一致：
            1. 查询 is_technical_view=1 的步骤；
            2. 批量查询步骤关联的定位信息与测试数据；
            3. 查询前置条件步骤及其定位信息；
            4. 计算定位覆盖率并组装结果。
        """
        test_case_result = await self.db.execute(
            select(TestCase).where(
                TestCase.id == test_case_id,
                TestCase.is_deleted.is_(False),
            )
        )
        test_case = test_case_result.scalars().first()
        if not test_case:
            logger.warning(f"测试用例不存在: {test_case_id}")
            return None

        steps_result = await self.db.execute(
            select(TestStep).where(
                TestStep.test_case_id == test_case_id,
                TestStep.is_technical_view == 1,
            ).order_by(TestStep.step_number)
        )
        steps = steps_result.scalars().all()

        step_ids = [s.id for s in steps]
        locators, test_data_map = await self._batch_query_step_data_async(step_ids)

        # _build_technical_steps 为纯计算方法，直接复用 sync 版本
        technical_steps, located_count = self._build_technical_steps(
            steps, locators, test_data_map
        )
        locator_coverage = float(
            (located_count / len(steps) * 100) if steps else 0.0
        )

        precondition_steps_data = await self._build_precondition_steps_async(
            test_case_id
        )

        return {
            "case_id": int(test_case.id),
            "case_no": str(test_case.case_no),
            "title": str(test_case.title),
            "module": str(test_case.module) if test_case.module else None,
            "precondition": str(test_case.precondition) if test_case.precondition else None,
            "expected_result": str(test_case.expected_result) if test_case.expected_result else None,
            "priority": int(test_case.priority) if test_case.priority else None,
            "case_type": str(test_case.case_type) if test_case.case_type else None,
            "precondition_steps": precondition_steps_data,
            "steps": technical_steps,
            "locator_coverage": locator_coverage,
            "execution_history": []
        }

    async def _batch_query_step_data_async(
        self, step_ids: List[int]
    ) -> tuple:
        """批量查询步骤的定位信息和测试数据（异步版本），避免N+1查询。"""
        locators: Dict[int, ElementLocator] = {}
        test_data_map: Dict[int, list] = {}
        if not step_ids:
            return locators, test_data_map

        locator_result = await self.db.execute(
            select(ElementLocator).where(ElementLocator.step_id.in_(step_ids))
        )
        locator_list = locator_result.scalars().all()
        locators = {loc.step_id: loc for loc in locator_list}

        td_result = await self.db.execute(
            select(TestData).where(
                TestData.step_id.in_(step_ids)
            ).order_by(TestData.sort_order)
        )
        td_list = td_result.scalars().all()
        for td in td_list:
            if td.step_id not in test_data_map:
                test_data_map[td.step_id] = []
            test_data_map[td.step_id].append(td.to_dict())

        return locators, test_data_map

    async def _build_precondition_steps_async(
        self, test_case_id: int
    ) -> List[Dict[str, Any]]:
        """构建前置条件步骤数据（异步版本）。"""
        pc_result = await self.db.execute(
            select(TestCasePreconditionStep).where(
                TestCasePreconditionStep.test_case_id == test_case_id
            ).order_by(TestCasePreconditionStep.step_number)
        )
        pc_steps = pc_result.scalars().all()

        pc_step_ids = [s.id for s in pc_steps]
        pc_locators: Dict[int, ElementLocator] = {}
        if pc_step_ids:
            pc_locator_result = await self.db.execute(
                select(ElementLocator).where(
                    ElementLocator.precondition_step_id.in_(pc_step_ids)
                )
            )
            pc_locator_list = pc_locator_result.scalars().all()
            pc_locators = {loc.precondition_step_id: loc for loc in pc_locator_list}

        precondition_steps_data: List[Dict[str, Any]] = []
        for pc_step in pc_steps:
            pc_locator = pc_locators.get(pc_step.id)
            pc_step_data: Dict[str, Any] = {
                "id": pc_step.id,
                "step_number": int(pc_step.step_number),
                "action": str(pc_step.action),
                "expected_result": str(pc_step.expected_result),
                "action_type": str(pc_step.action_type) if pc_step.action_type else "",
                "input_value": str(pc_step.input_value) if pc_step.input_value else "",
                "target_element": str(pc_step.target_element) if pc_step.target_element else "",
                "has_locator": bool(pc_step.has_locator == 1),
                "locator_status": str(pc_step.locator_status),
                "locator": None
            }
            if pc_locator:
                pc_best = pc_locator.get_best_locator()
                pc_step_data["locator"] = {
                    "css_selector": str(pc_locator.css_selector) if pc_locator.css_selector else None,
                    "xpath": str(pc_locator.xpath) if pc_locator.xpath else None,
                    "element_type": str(pc_locator.element_type) if pc_locator.element_type else None,
                    "ai_coordinate": pc_locator.ai_coordinate,
                    "confidence": float(pc_locator.ai_confidence) if pc_locator.ai_confidence else None,
                    "locator_type": pc_best.get("type") if pc_best else None,
                    "locator_value": str(pc_best.get("value")) if pc_best and pc_best.get("value") is not None else None
                }
            precondition_steps_data.append(pc_step_data)

        return precondition_steps_data

    async def get_business_view_async(
        self, test_case_id: int
    ) -> Optional[BusinessTestCaseView]:
        """获取测试用例的业务视图（异步版本），仅展示 is_business_view=1 的步骤。"""
        test_case_result = await self.db.execute(
            select(TestCase).where(
                TestCase.id == test_case_id,
                TestCase.is_deleted.is_(False),
            )
        )
        test_case = test_case_result.scalars().first()
        if not test_case:
            logger.warning(f"测试用例不存在: {test_case_id}")
            return None

        steps_result = await self.db.execute(
            select(TestStep).where(
                TestStep.test_case_id == test_case_id,
                TestStep.is_business_view == 1,
            ).order_by(TestStep.step_number)
        )
        steps = steps_result.scalars().all()

        business_steps = [
            BusinessStepView(
                step_number=int(s.step_number),
                action=str(s.action),
                expected_result=str(s.expected_result)
            )
            for s in steps
        ]

        return BusinessTestCaseView(
            case_id=int(test_case.id),
            case_no=str(test_case.case_no),
            title=str(test_case.title),
            description=str(getattr(test_case, 'description', test_case.title)),
            precondition=str(test_case.precondition) if test_case.precondition else None,
            steps=business_steps
        )

    async def get_locator_coverage_async(
        self, test_case_id: int
    ) -> Dict[str, Any]:
        """获取测试用例的定位覆盖率统计（异步版本）。"""
        steps_result = await self.db.execute(
            select(TestStep).where(TestStep.test_case_id == test_case_id)
        )
        steps = steps_result.scalars().all()

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

    async def get_view_statistics_async(
        self, test_case_id: int
    ) -> Dict[str, Any]:
        """获取测试用例的视图统计信息（异步版本）。"""
        steps_result = await self.db.execute(
            select(TestStep).where(TestStep.test_case_id == test_case_id)
        )
        steps = steps_result.scalars().all()

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

    async def batch_update_view_config_async(
        self,
        test_case_id: int,
        view_type: str,
        visible: bool
    ) -> int:
        """批量更新测试用例所有步骤的视图可见性配置（异步版本）。

        Args:
            test_case_id: 测试用例ID。
            view_type: 视图类型，'business'或'technical'。
            visible: 是否可见。

        Returns:
            更新的步骤数量，视图类型无效时返回0。
        """
        value = 1 if visible else 0

        if view_type == "business":
            field_name = "is_business_view"
        elif view_type == "technical":
            field_name = "is_technical_view"
        else:
            logger.error(f"未知的视图类型: {view_type}")
            return 0

        steps_result = await self.db.execute(
            select(TestStep).where(TestStep.test_case_id == test_case_id)
        )
        steps = steps_result.scalars().all()
        for step in steps:
            setattr(step, field_name, value)
        await self.db.commit()
        count = len(steps)
        logger.info(
            f"批量更新测试用例 {test_case_id} 的 {view_type} 视图配置: {count} 个步骤"
        )
        return count

    async def update_step_view_config_async(
        self,
        step_id: int,
        is_business_view: Optional[int] = None,
        is_technical_view: Optional[int] = None
    ) -> bool:
        """更新单个步骤的视图可见性配置（异步版本）。

        Args:
            step_id: 步骤ID。
            is_business_view: 是否在业务视图显示（0/1），可选。
            is_technical_view: 是否在技术视图显示（0/1），可选。

        Returns:
            更新成功返回True，步骤不存在返回False。
        """
        step_result = await self.db.execute(
            select(TestStep).where(TestStep.id == step_id)
        )
        step = step_result.scalars().first()
        if not step:
            logger.warning(f"步骤不存在: {step_id}")
            return False

        if is_business_view is not None:
            step.is_business_view = is_business_view
        if is_technical_view is not None:
            step.is_technical_view = is_technical_view

        await self.db.commit()
        logger.info(f"更新步骤 {step_id} 视图配置成功")
        return True
