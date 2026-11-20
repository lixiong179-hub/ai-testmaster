"""自愈执行Mixin - 在步骤执行中集成自愈修复逻辑。

当元素定位失败时，先做失败分类，再按分类选择策略（retry / skip / ai_heal），
只有 ai_heal 策略才会进入 AI 自愈；全程写审计并埋点。

自愈流程（R3-1 / G-2 三段式）:
    1. 使用已有定位器尝试执行操作
    2. 捕获定位相关异常（超时、元素不存在等）→ 非定位错误直接抛出
    3. 灰度闸门：全局开关 AND 项目级 `self_healing_config.enabled`
    4. 失败分类 `FailureAnalyzer`（error 关键词 + DOM 快照校正）
    5. 策略路由：
       - `retry`（load_delay）：等待 `AI_SELF_HEALING_RETRY_WAIT_SECONDS` 后重执行一次
       - `skip`（env_noise）：写审计（strategy=skip）后抛原始异常，不进 AI
       - `ai_heal`（element_gone / dom_changed）：Token 预算双控 → AI 自愈
    6. AI 自愈结果拆包（`HealResult`）→ 置信度门控 → 回写定位器（含乐观锁）
    7. 全路径埋点：attempts / success / failure(type)
"""

import asyncio
from dataclasses import dataclass
from typing import Any, NoReturn
from loguru import logger

from app.models.element_locator import ElementLocator
from app.services.self_healing.failure_analyzer import FailureAnalyzer
from app.services.self_healing.metrics import (
    record_attempt,
    record_failure,
    record_success,
)
from app.services.test_execution_engine.models import (
    ActionType,
    StepExecutionError,
)
from app.services.test_execution_engine.self_healing_policy_mixin import (
    SelfHealingPolicyMixin,
)
from app.services.test_execution_engine.self_healing_strategy_helpers import (
    estimate_token_cost,
)

# 视觉/语义定位相关错误关键词：命中才进入自愈判定，其余异常直接抛出
_LOCATOR_ERROR_KEYWORDS = (
    "timeout",
    "waiting",
    "not found",
    "no element",
    "selector",
    "等待",
    "超时",
    "未找到",
    "不存在",
    "stale",
    "detached",
    "not attached",
)


def _is_locator_error(error: Exception) -> bool:
    """错误信息是否命中定位类关键词（未命中直接原样抛出）。"""
    error_str = str(error).lower()
    return any(kw in error_str for kw in _LOCATOR_ERROR_KEYWORDS)


@dataclass(slots=True)
class _HealAttempt:
    """一次自愈处置的上下文，避免阶段方法间长参数透传。"""

    step: Any
    locator_record: ElementLocator | None
    old_selector: str | None
    failure_type: str
    strategy: str
    primary_error: Exception
    started_at: float


class SelfHealingExecuteMixin(SelfHealingPolicyMixin):
    async def _execute_with_self_healing(
        self,
        step,
        locator_record: ElementLocator | None,
        action_type: ActionType,
        action_info: dict[str, Any],
        step_test_data: dict[str, str] | None = None,
    ) -> None:
        """带自愈兜底的步骤执行包装器（失败分类 → 策略路由 → 自愈）。

        Args:
            step: 测试步骤对象
            locator_record: 元素定位记录（可为None）
            action_type: 操作类型
            action_info: 操作信息字典
            step_test_data: 测试数据
        """
        if not self.browser:
            raise StepExecutionError("浏览器未初始化")

        old_selector = self._resolve_old_selector(locator_record)
        try:
            await self._execute_action_directly(action_type, action_info, locator_record, step_test_data)
            self._record_locator_success(locator_record, old_selector)
        except Exception as primary_error:
            await self._handle_locator_failure(
                step,
                locator_record,
                action_type,
                action_info,
                step_test_data,
                old_selector,
                primary_error,
            )

    async def _handle_locator_failure(
        self,
        step,
        locator_record: ElementLocator | None,
        action_type: ActionType,
        action_info: dict[str, Any],
        step_test_data: dict[str, str] | None,
        old_selector: str | None,
        primary_error: Exception,
    ) -> None:
        """定位类失败处置：分类 → 灰度闸门 → 策略路由（retry / skip）→ AI 自愈。"""
        if not _is_locator_error(primary_error):
            raise primary_error

        if not self._is_self_healing_enabled(step, locator_record):
            logger.info(f"定位器失效但自愈未启用（全局或项目级） | 旧选择器: {old_selector}")
            raise primary_error

        analysis = FailureAnalyzer().analyze(
            primary_error,
            await self._capture_dom_snapshot(),
            old_selector,
        )
        attempt = _HealAttempt(
            step=step,
            locator_record=locator_record,
            old_selector=old_selector,
            failure_type=analysis.failure_type.value,
            strategy=analysis.suggested_strategy,
            primary_error=primary_error,
            started_at=asyncio.get_running_loop().time(),
        )
        self._self_healing_attempts += 1
        record_attempt()
        logger.info(
            f"定位器失效，失败分类={attempt.failure_type} 建议策略={attempt.strategy} | "
            f"旧选择器: {old_selector} | 步骤ID: {getattr(step, 'id', None)}"
        )

        if attempt.strategy == "retry":
            retried = await self._retry_after_locator_failure(
                action_type, action_info, locator_record, step_test_data, old_selector
            )
            if retried:
                self._finish_retry_success(attempt)
                return
            logger.info("load_delay 重试仍失败，升级为 AI 自愈")

        if attempt.strategy == "skip":
            self._audit_and_raise(
                attempt,
                strategy="skip",
                log_message=f"环境噪声类失败，跳过自愈 | 失败类型: {attempt.failure_type} | 错误: {primary_error}",
            )

        await self._run_ai_heal(attempt, action_type, action_info, step_test_data)

    async def _run_ai_heal(
        self,
        attempt: _HealAttempt,
        action_type: ActionType,
        action_info: dict[str, Any],
        step_test_data: dict[str, str] | None,
    ) -> None:
        """AI 自愈：Token 预算双控 → 调用 → 置信度门控回写 → 审计与埋点。"""
        nl_description = await self._get_nl_description(getattr(attempt.step, "id", None))
        if not nl_description:
            nl_description = action_info.get("text", "")

        token_estimate = estimate_token_cost(nl_description)
        guard = self._get_token_guard()
        if guard.check_single_call(token_estimate) or guard.is_daily_budget_exhausted():
            self._audit_and_raise(
                attempt,
                strategy="ai_heal",
                log_message=f"Token 预算熔断，跳过 AI 自愈 | 预估: {token_estimate} | 失败类型: {attempt.failure_type}",
            )

        logger.info(f"启动AI自愈 | 步骤描述: {nl_description} | 失败类型: {attempt.failure_type}")
        heal_output = await self._invoke_ai_heal(attempt, nl_description, action_type, action_info, step_test_data)

        selector, confidence, token_cost, heal_strategy = self._normalize_heal_result(heal_output)
        low_confidence = confidence is not None and confidence < self._healing_confidence_threshold()
        await self._apply_heal_result(attempt, selector, confidence, low_confidence)

        duration = self._elapsed(attempt.started_at)
        self._self_healing_total_duration += duration
        self._audit_healing_decision(
            step=attempt.step,
            locator_record=attempt.locator_record,
            old_selector=attempt.old_selector,
            new_selector=selector,
            failure_type=attempt.failure_type,
            strategy=heal_strategy,
            confidence=confidence,
            token_cost=token_cost,
            low_confidence=low_confidence,
        )

        if not selector:
            record_failure(attempt.failure_type, duration)
            logger.error(f"AI 自愈未产出可用选择器 | 步骤描述: {nl_description}")
            raise attempt.primary_error

        self._self_healing_successes += 1
        self._consume_heal_tokens(guard, token_cost)
        record_success(token_cost, duration)
        logger.info(
            f"自愈成功 | 策略: {heal_strategy} | 新选择器: {selector} | 置信度: {confidence} | Token: {token_cost}"
        )

    async def _invoke_ai_heal(
        self,
        attempt: _HealAttempt,
        nl_description: str,
        action_type: ActionType,
        action_info: dict[str, Any],
        step_test_data: dict[str, str] | None,
    ) -> Any:
        """调用 AI 自愈；异常时按 ai_heal 策略审计后抛原始异常。"""
        try:
            return await self._ai_self_heal_action(nl_description, action_type, action_info, step_test_data)
        except Exception as heal_error:
            self._audit_and_raise(
                attempt,
                strategy="ai_heal",
                log_message=f"自愈失败，AI无法解析步骤 | 步骤描述: {nl_description} | 自愈错误: {heal_error}",
                level="error",
            )

    async def _apply_heal_result(
        self,
        attempt: _HealAttempt,
        selector: str | None,
        confidence: float | None,
        low_confidence: bool,
    ) -> None:
        """置信度门控：达标且命中定位器才回写（含乐观锁）。"""
        if selector and attempt.locator_record and not low_confidence:
            await self._update_locator_after_healing(attempt.locator_record.id, selector, attempt.old_selector)
        elif low_confidence:
            logger.warning(f"自愈置信度 {confidence} 低于阈值，跳过定位器回写 | 新选择器: {selector}")

    def _audit_and_raise(
        self,
        attempt: _HealAttempt,
        *,
        strategy: str,
        log_message: str,
        token_cost: int = 0,
        level: str = "warning",
    ) -> NoReturn:
        """写审计 + 埋点后抛出原始异常，保证调用方语义与原实现一致。"""
        duration = self._elapsed(attempt.started_at)
        self._self_healing_total_duration += duration
        self._audit_healing_decision(
            step=attempt.step,
            locator_record=attempt.locator_record,
            old_selector=attempt.old_selector,
            new_selector=None,
            failure_type=attempt.failure_type,
            strategy=strategy,
            confidence=None,
            token_cost=token_cost,
        )
        record_failure(attempt.failure_type, duration)
        if level == "error":
            logger.error(log_message)
        else:
            logger.warning(log_message)
        raise attempt.primary_error

    def _finish_retry_success(self, attempt: _HealAttempt) -> None:
        """load_delay 重试成功：累计指标后返回，不再进入 AI 自愈。"""
        duration = self._elapsed(attempt.started_at)
        self._self_healing_successes += 1
        self._self_healing_total_duration += duration
        record_success(0, duration)
        logger.info("load_delay 重试成功，跳过 AI 自愈")

    @staticmethod
    def _elapsed(started_at: float) -> float:
        return asyncio.get_running_loop().time() - started_at

    @staticmethod
    def _resolve_old_selector(locator_record: ElementLocator | None) -> str | None:
        """取定位器当前最优选择器值，作为自愈前后的对照基准。"""
        if not locator_record:
            return None
        best = locator_record.get_best_locator()
        return best.get("value") if best else None

    def _record_locator_success(self, locator_record: ElementLocator | None, old_selector: str | None) -> None:
        """直接执行成功即累加定位器命中次数（仅原选择器可用时）。"""
        if locator_record and old_selector:
            ElementLocator.atomic_record_success(self.db, locator_record.id, locator_record.version)

    @staticmethod
    def _consume_heal_tokens(guard, token_cost: int) -> None:
        """回写 Token 消耗；失败只降级为 debug，不影响执行结果。"""
        if not token_cost:
            return
        try:
            guard.consume(token_cost)
        except Exception:
            logger.debug("自愈 Token 消耗累计失败", exc_info=True)
