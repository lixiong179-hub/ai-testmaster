"""自愈策略辅助Mixin - 灰度闸门、失败重试、Token 预算与审计落库。

从 `SelfHealingExecuteMixin` 拆出（G-2），保持单文件 ≤400 行的服务层约束。
本 Mixin 只承载「策略决策的周边能力」，主控制流仍在
`self_healing_execute_mixin._execute_with_self_healing`。

职责:
    - 灰度闸门：全局开关 AND 项目级 `self_healing_config.enabled`
    - load_delay 重试：等待 `AI_SELF_HEALING_RETRY_WAIT_SECONDS` 后重执行一次
    - DOM 快照采集：供失败分类校正，失败时降级为空串
    - Token 预算：惰性构造 `TokenBudgetGuard`（Redis 不可用降级内存计数）
    - 自愈结果归一化：兼容 `HealResult` 与选择器字符串两种契约
    - 审计写入：`self_healing_audits` 仅追加落库
"""
import asyncio
from typing import Any
from loguru import logger

from app.models.element_locator import ElementLocator
from app.services.self_healing.models import HealResult
from app.services.test_execution_engine.models import ActionType


class SelfHealingPolicyMixin:

    async def _retry_after_locator_failure(
        self,
        action_type: ActionType,
        action_info: dict[str, Any],
        locator_record: ElementLocator | None,
        step_test_data: dict[str, str] | None,
        old_selector: str | None,
    ) -> bool:
        """load_delay 策略：等待后重执行一次，成功返回 True。"""
        from app.core.config import settings

        wait_seconds = float(
            getattr(settings, "AI_SELF_HEALING_RETRY_WAIT_SECONDS", 0) or 0
        )
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        try:
            await self._execute_action_directly(
                action_type, action_info, locator_record, step_test_data
            )
        except Exception as retry_error:
            logger.info(f"定位重试失败，准备降级 AI 自愈 | 错误: {retry_error}")
            return False

        if locator_record and old_selector:
            ElementLocator.atomic_record_success(
                self.db, locator_record.id, locator_record.version
            )
        return True

    async def _capture_dom_snapshot(self) -> str:
        """采集当前 DOM 快照用于失败分类校正；失败时降级为空串（仅关键词分类）。"""
        if not self.browser:
            return ""
        try:
            snapshot = await self.browser.execute_javascript(
                "document.documentElement.outerHTML"
            )
        except Exception:
            logger.debug("DOM 快照采集失败，降级为仅按错误信息分类", exc_info=True)
            return ""
        return snapshot if isinstance(snapshot, str) else ""

    def _is_self_healing_enabled(
        self, step, locator_record: ElementLocator | None
    ) -> bool:
        """灰度闸门：全局开关 AND 项目级 `self_healing_config.enabled`。

        项目无法解析（引擎未注入 db 或步骤缺少用例关联）时按全局开关执行，
        与项目缺省配置 `enabled=True` 的语义保持一致。
        """
        from app.core.config import settings

        if not settings.AI_SELF_HEALING_ENABLED:
            return False

        project_id = self._resolve_project_id(step, locator_record)
        if project_id is None or self.db is None:
            return True
        try:
            from app.services.self_healing.config_service import (
                SelfHealingConfigService,
            )

            return SelfHealingConfigService(self.db).is_self_healing_enabled(project_id)
        except Exception:
            logger.warning("读取项目级自愈配置失败，回退全局开关", exc_info=True)
            return True

    def _resolve_project_id(
        self, step, locator_record: ElementLocator | None
    ) -> int | None:
        """从步骤（或定位器）反查所属项目 ID，失败返回 None。"""
        if self.db is None:
            return None
        case_id = getattr(step, "test_case_id", None)
        try:
            if case_id is None and locator_record is not None:
                from app.models.test_case import TestStep

                step_id = getattr(locator_record, "step_id", None)
                if step_id is not None:
                    case_id = (
                        self.db.query(TestStep.test_case_id)
                        .filter(TestStep.id == step_id)
                        .scalar()
                    )
            if case_id is None:
                return None
            from app.models.test_case import TestCase

            return (
                self.db.query(TestCase.project_id)
                .filter(TestCase.id == case_id)
                .scalar()
            )
        except Exception:
            logger.debug("解析步骤所属项目失败，回退全局开关", exc_info=True)
            return None

    def _get_token_guard(self):
        """获取自愈 Token 预算守卫（首次访问时惰性构造并缓存）。"""
        guard = getattr(self, "_token_guard", None)
        if guard is not None:
            return guard

        redis_client = None
        try:
            import redis

            from app.core.config import settings

            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            logger.debug("Redis 不可用，自愈 Token 预算降级为进程内计数", exc_info=True)

        from app.services.self_healing.token_budget import TokenBudgetGuard

        guard = TokenBudgetGuard(redis_client=redis_client)
        self._token_guard = guard
        return guard

    @staticmethod
    def _healing_confidence_threshold() -> float:
        """读取自愈置信度阈值（运行时读取，支持配置热更新与测试替身）。"""
        from app.core.config import settings

        return float(getattr(settings, "AI_SELF_HEALING_CONFIDENCE_THRESHOLD", 0.7))

    @staticmethod
    def _normalize_heal_result(
        heal_output: Any,
    ) -> tuple[str | None, float | None, int, str]:
        """归一化自愈返回值。

        兼容两种契约：生产链路 `_ai_self_heal_action` 返回选择器字符串，
        策略层升级后返回 `HealResult`（含置信度/Token/策略）。
        """
        if isinstance(heal_output, HealResult):
            return (
                heal_output.selector,
                heal_output.confidence,
                int(heal_output.token_cost or 0),
                heal_output.strategy or "ai_heal",
            )
        if isinstance(heal_output, str):
            return heal_output, None, 0, "ai_heal"
        if isinstance(heal_output, dict):
            return (
                heal_output.get("selector"),
                heal_output.get("confidence"),
                int(heal_output.get("token_cost") or 0),
                heal_output.get("strategy") or "ai_heal",
            )
        return None, None, 0, "ai_heal"

    def _audit_healing_decision(
        self,
        *,
        step,
        locator_record: ElementLocator | None,
        old_selector: str | None,
        new_selector: str | None,
        failure_type: str,
        strategy: str,
        confidence: float | None,
        token_cost: int,
        low_confidence: bool = False,
    ) -> None:
        """写入自愈决策审计（仅追加）；审计失败不阻断执行主链路。"""
        case_id = getattr(step, "test_case_id", None)
        if case_id is None or self.db is None:
            logger.debug("步骤缺少用例关联，跳过自愈审计写入")
            return

        step_number = getattr(step, "step_number", None)
        step_index = max(int(step_number) - 1, 0) if step_number is not None else 0
        try:
            from app.services.self_healing.audit_service import (
                SelfHealingAuditService,
            )

            SelfHealingAuditService(self.db).record_audit(
                test_case_id=case_id,
                step_index=step_index,
                locator_id=getattr(locator_record, "id", None),
                old_selector=old_selector,
                new_selector=new_selector,
                failure_type=failure_type,
                strategy=strategy,
                confidence=confidence,
                token_cost=token_cost,
                low_confidence=low_confidence,
            )
        except Exception:
            logger.error("自愈审计写入失败（不影响执行结果）", exc_info=True)


__all__ = ["SelfHealingPolicyMixin"]
