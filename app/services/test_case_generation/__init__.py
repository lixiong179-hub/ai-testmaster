"""
Test Case Generation Service - 聚合入口（组合模式）

整合需求文档（文件）、UI原型图（文件）和测试点，生成高质量测试用例。
TestCaseGenerationService 采用组合模式持有 4 个内聚组件：
    - ContextBuilder: 上下文构建（需求/UI/测试点加载、历史用例信任度评分）
    - AiGenerator: AI 生成（Prompt 构建、3 轮质量反馈闭环、缓存控制）
    - CaseValidator: 校验与持久化（UI 可执行性、质量门禁、DB 入库）
    - BatchOrchestrator: 批量编排（并发控制、覆盖补全、失败归因注入）

继承深度 ≤ 1（仅 object），通过构造函数注入组件，避免 Mixin 多继承的调试栈深
与责任分散问题。对外保持公开方法签名兼容。
"""
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.test_case_generation.helpers import (
    ContentSanitizer,
    DEFAULT_TEST_POINT_PAGE_SIZE,
    MAX_TEST_POINT_PAGE_SIZE,
    TEST_CATEGORY_API_AUTO,
    TEST_CATEGORY_MANUAL,
    TEST_CATEGORY_UI_AUTO,
)
from app.services.test_case_generation.context_builder import ContextBuilder
from app.services.test_case_generation.ai_generator import AiGenerator
from app.services.test_case_generation.validator import CaseValidator
from app.services.test_case_generation.batch_orchestrator import BatchOrchestrator


class TestCaseGenerationService:
    """测试用例生成服务（组合模式）。

    通过构造函数注入 4 个组件，对外保持公开方法签名兼容：
        - get_context_for_generation: 委托 ContextBuilder
        - enrich_context_with_trust_and_scoring: 委托 ContextBuilder
        - generate_test_case_for_point: 委托 AiGenerator
        - generate_test_cases_batch: 委托 BatchOrchestrator
        - _save_test_case: 委托 CaseValidator
    """

    __test__ = False

    def __init__(self, db: Session) -> None:
        self.db = db
        # 构造函数注入 4 个组件，组件间通过 BatchOrchestrator 持有相互引用
        self._context_builder = ContextBuilder(db)
        self._ai_generator = AiGenerator(db)
        self._validator = CaseValidator(db)
        self._batch_orchestrator = BatchOrchestrator(
            db=db,
            context_builder=self._context_builder,
            ai_generator=self._ai_generator,
            validator=self._validator,
        )

    # ── 公开方法委托 ──
    async def get_context_for_generation(
        self,
        project_id: int,
        user_id: int,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_ids: Optional[List[int]] = None,
        force_refresh: bool = False,
        test_point_page: int = 1,
        test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE,
    ) -> Dict[str, Any]:
        """获取测试用例生成的上下文信息（委托 ContextBuilder）。"""
        return await self._context_builder.get_context_for_generation(
            project_id=project_id,
            user_id=user_id,
            requirement_file_ids=requirement_file_ids,
            ui_file_ids=ui_file_ids,
            ui_screen_ids=ui_screen_ids,
            test_point_ids=test_point_ids,
            force_refresh=force_refresh,
            test_point_page=test_point_page,
            test_point_page_size=test_point_page_size,
        )

    def enrich_context_with_trust_and_scoring(
        self,
        context: Dict[str, Any],
        project_id: int,
        history_case_ids: Optional[List[int]] = None,
    ) -> None:
        """历史用例信任度过滤与完整性评分（委托 ContextBuilder）。"""
        return self._context_builder.enrich_context_with_trust_and_scoring(
            context, project_id, history_case_ids=history_case_ids
        )

    async def generate_test_case_for_point(
        self,
        context: Dict[str, Any],
        test_point: Dict[str, Any],
        project_id: int,
        case_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """为单个测试点生成测试用例（委托 AiGenerator）。"""
        return await self._ai_generator.generate_test_case_for_point(
            context=context,
            test_point=test_point,
            project_id=project_id,
            case_type=case_type,
        )

    async def generate_test_cases_batch(
        self,
        project_id: int,
        user_id: int,
        test_point_ids: Optional[List[int]] = None,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_page: int = 1,
        test_point_page_size: int = 100,
        case_type: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """批量生成测试用例（委托 BatchOrchestrator）。"""
        async for frame in self._batch_orchestrator.generate_test_cases_batch(
            project_id=project_id,
            user_id=user_id,
            test_point_ids=test_point_ids,
            requirement_file_ids=requirement_file_ids,
            ui_file_ids=ui_file_ids,
            ui_screen_ids=ui_screen_ids,
            test_point_page=test_point_page,
            test_point_page_size=test_point_page_size,
            case_type=case_type,
        ):
            yield frame

    async def _save_test_case(
        self,
        project_id: int,
        generated_case: Dict[str, Any],
        test_point: Dict[str, Any],
        requirement_file_id: Optional[int] = None,
    ):
        """保存测试用例到数据库（委托 CaseValidator）。"""
        return await self._validator._save_test_case(
            project_id=project_id,
            generated_case=generated_case,
            test_point=test_point,
            requirement_file_id=requirement_file_id,
        )

    # ── 类方法委托（兼容旧 Mixin 时代直接通过 Service 类名调用的用例） ──
    @classmethod
    def _normalize_case_type(cls, *values: Optional[str]) -> str:
        """用例执行类型归一化（委托 CaseValidator）。"""
        return CaseValidator._normalize_case_type(*values)

    @classmethod
    def _quality_gate_issues(
        cls,
        generated_case: Dict[str, Any],
        quality_score: Optional[float],
        ui_specs: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[int] = None,
        db: Any = None,
    ):
        """质量门禁校验（委托 CaseValidator）。"""
        return CaseValidator._quality_gate_issues(
            generated_case,
            quality_score,
            ui_specs=ui_specs,
            project_id=project_id,
            db=db,
        )

    @classmethod
    def _resolve_generated_priority(
        cls,
        generated_case: Dict[str, Any],
        test_point: Dict[str, Any],
    ) -> int:
        """生成用例优先级解析（委托 CaseValidator）。"""
        return CaseValidator._resolve_generated_priority(generated_case, test_point)


async def get_test_case_context(
    db: Session,
    project_id: int,
    user_id: int,
    requirement_file_ids: Optional[List[int]] = None,
    ui_file_ids: Optional[List[int]] = None,
    ui_screen_ids: Optional[List[int]] = None,
    test_point_ids: Optional[List[int]] = None,
    test_point_page: int = 1,
    test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
) -> Dict[str, Any]:
    """获取测试用例生成的上下文"""
    service = TestCaseGenerationService(db)
    return await service.get_context_for_generation(
        project_id=project_id,
        user_id=user_id,
        requirement_file_ids=requirement_file_ids,
        ui_file_ids=ui_file_ids,
        ui_screen_ids=ui_screen_ids,
        test_point_ids=test_point_ids,
        test_point_page=test_point_page,
        test_point_page_size=test_point_page_size
    )


__all__ = [
    "TestCaseGenerationService",
    "ContentSanitizer",
    "get_test_case_context",
    "DEFAULT_TEST_POINT_PAGE_SIZE",
    "MAX_TEST_POINT_PAGE_SIZE",
    "TEST_CATEGORY_UI_AUTO",
    "TEST_CATEGORY_MANUAL",
    "TEST_CATEGORY_API_AUTO",
]
