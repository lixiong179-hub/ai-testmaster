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
from typing import Any
from loguru import logger

from app.models.element_locator import ElementLocator
from app.services.self_healing.failure_analyzer import FailureAnalyzer
from app.services.self_healing.metrics import (
    record_attempt,
    record_failure,
    record_success,
)
from app.services.test_execution_engine.models import (
    ActionType, StepExecutionError,
)
from app.services.test_execution_engine.self_healing_policy_mixin import (
    SelfHealingPolicyMixin,
)
from app.services.test_execution_engine.self_healing_strategy_helpers import (
    estimate_token_cost,
)

# 视觉/语义定位相关错误关键词：命中才进入自愈判定，其余异常直接抛出
_LOCATOR_ERROR_KEYWORDS = (
    "timeout", "waiting", "not found", "no element",
    "selector", "等待", "超时", "未找到", "不存在",
    "stale", "detached", "not attached",
)


class SelfHealingExecuteMixin(SelfHealingPolicyMixin):

    async def _execute_with_self_healing(
        self,
        step,
        locator_record: ElementLocator | None,
        action_type: ActionType,
        action_info: dict[str, Any],
        step_test_data: dict[str, str] | None = None
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

        old_selector = None
        if locator_record:
            best = locator_record.get_best_locator()
            if best:
                old_selector = best.get("value")

        try:
            await self._execute_action_directly(
                action_type, action_info, locator_record, step_test_data
            )
            if locator_record and old_selector:
                ElementLocator.atomic_record_success(
                    self.db, locator_record.id, locator_record.version
                )
            return
        except Exception as primary_error:
            error_str = str(primary_error).lower()
            if not any(kw in error_str for kw in _LOCATOR_ERROR_KEYWORDS):
                raise

            if not self._is_self_healing_enabled(step, locator_record):
                logger.info(
                    f"定位器失效但自愈未启用（全局或项目级） | 旧选择器: {old_selector}"
                )
                raise

            analysis = FailureAnalyzer().analyze(
                primary_error,
                await self._capture_dom_snapshot(),
                old_selector,
            )
            failure_type = analysis.failure_type.value
            strategy = analysis.suggested_strategy
            heal_started = asyncio.get_running_loop().time()
            self._self_healing_attempts += 1
            record_attempt()
            logger.info(
                f"定位器失效，失败分类={failure_type} 建议策略={strategy} | "
                f"旧选择器: {old_selector} | 步骤ID: {getattr(step, 'id', None)}"
            )

            if strategy == "retry":
                if await self._retry_after_locator_failure(
                    action_type, action_info, locator_record, step_test_data, old_selector
                ):
                    duration = asyncio.get_running_loop().time() - heal_started
                    self._self_healing_successes += 1
                    self._self_healing_total_duration += duration
                    record_success(0, duration)
                    logger.info("load_delay 重试成功，跳过 AI 自愈")
                    return
                logger.info("load_delay 重试仍失败，升级为 AI 自愈")

            if strategy == "skip":
                duration = asyncio.get_running_loop().time() - heal_started
                self._self_healing_total_duration += duration
                self._audit_healing_decision(
                    step=step, locator_record=locator_record,
                    old_selector=old_selector, new_selector=None,
                    failure_type=failure_type, strategy="skip",
                    confidence=None, token_cost=0,
                )
                record_failure(failure_type, duration)
                logger.warning(
                    f"环境噪声类失败，跳过自愈 | 失败类型: {failure_type} | "
                    f"错误: {primary_error}"
                )
                raise primary_error

            nl_description = await self._get_nl_description(getattr(step, "id", None))
            if not nl_description:
                nl_description = action_info.get("text", "")

            token_estimate = estimate_token_cost(nl_description)
            guard = self._get_token_guard()
            if guard.check_single_call(token_estimate) or guard.is_daily_budget_exhausted():
                duration = asyncio.get_running_loop().time() - heal_started
                self._self_healing_total_duration += duration
                self._audit_healing_decision(
                    step=step, locator_record=locator_record,
                    old_selector=old_selector, new_selector=None,
                    failure_type=failure_type, strategy="ai_heal",
                    confidence=None, token_cost=0,
                )
                record_failure(failure_type, duration)
                logger.warning(
                    f"Token 预算熔断，跳过 AI 自愈 | 预估: {token_estimate} | "
                    f"失败类型: {failure_type}"
                )
                raise primary_error

            logger.info(
                f"启动AI自愈 | 步骤描述: {nl_description} | 失败类型: {failure_type}"
            )
            try:
                heal_output = await self._ai_self_heal_action(
                    nl_description, action_type, action_info, step_test_data
                )
            except Exception as heal_error:
                duration = asyncio.get_running_loop().time() - heal_started
                self._self_healing_total_duration += duration
                self._audit_healing_decision(
                    step=step, locator_record=locator_record,
                    old_selector=old_selector, new_selector=None,
                    failure_type=failure_type, strategy="ai_heal",
                    confidence=None, token_cost=0,
                )
                record_failure(failure_type, duration)
                logger.error(
                    f"自愈失败，AI无法解析步骤 | 步骤描述: {nl_description} | "
                    f"自愈错误: {heal_error}"
                )
                raise primary_error

            selector, confidence, token_cost, heal_strategy = self._normalize_heal_result(
                heal_output
            )
            low_confidence = (
                confidence is not None
                and confidence < self._healing_confidence_threshold()
            )

            if selector and locator_record and not low_confidence:
                await self._update_locator_after_healing(
                    locator_record.id, selector, old_selector
                )
            elif low_confidence:
                logger.warning(
                    f"自愈置信度 {confidence} 低于阈值，跳过定位器回写 | "
                    f"新选择器: {selector}"
                )

            duration = asyncio.get_running_loop().time() - heal_started
            self._self_healing_total_duration += duration
            self._audit_healing_decision(
                step=step, locator_record=locator_record,
                old_selector=old_selector, new_selector=selector,
                failure_type=failure_type, strategy=heal_strategy,
                confidence=confidence, token_cost=token_cost,
                low_confidence=low_confidence,
            )

            if not selector:
                record_failure(failure_type, duration)
                logger.error(f"AI 自愈未产出可用选择器 | 步骤描述: {nl_description}")
                raise primary_error

            self._self_healing_successes += 1
            if token_cost:
                try:
                    guard.consume(token_cost)
                except Exception:
                    logger.debug("自愈 Token 消耗累计失败", exc_info=True)
            record_success(token_cost, duration)
            logger.info(
                f"自愈成功 | 策略: {heal_strategy} | 新选择器: {selector} | "
                f"置信度: {confidence} | Token: {token_cost}"
            )
            return
