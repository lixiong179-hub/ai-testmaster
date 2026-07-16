"""test_case_generation - AI 生成器（组合模式组件）。

合并自 ai_mixin.py，提供 AiGenerator 类负责调用 AI 生成测试用例，
含缓存控制、Prompt 构建（委托 PromptBuilder）、3 轮质量反馈闭环与响应解析。

ai_response_parser.py 因被外部测试引用保留独立文件，本模块 re-export parse_ai_response。
ai_prompt_builder.py 中 build_generation_prompt/build_ui_spec_prompt 历史上未被引用
（实际使用 app.services.prompt_builder.PromptBuilder），已作为废弃代码删除。

构造函数 db 可选（兼容无参实例化的单元测试），对外保持 generate_test_case_for_point
公开方法签名兼容。
"""
import asyncio
import copy
import hashlib
import json
import threading
import time
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.prompt_builder import PromptBuilder
from app.services.test_case_generation.ai_response_parser import parse_ai_response
from app.services.test_case_generation.helpers import (
    ContentSanitizer,
    TEST_CATEGORY_MANUAL,
    TEST_CATEGORY_UI_AUTO,
)
from app.services.test_case_generation.quality_validator import validate_single_case_status


def _get_openai_client() -> "AsyncOpenAIClient":
    """延迟导入并创建 AsyncOpenAIClient 单例（线程安全）。

    性能优化：从同步 OpenAIClient 切换到 AsyncOpenAIClient，避免
    asyncio.to_thread 包装开销，并启用单次调用硬超时。
    """
    from app.ai.openai_client import AsyncOpenAIClient
    if not hasattr(_get_openai_client, "_instance"):
        with _get_openai_client._lock:
            if not hasattr(_get_openai_client, "_instance"):
                _get_openai_client._instance = AsyncOpenAIClient()
    return _get_openai_client._instance


_get_openai_client._lock = threading.Lock()


class AiGenerator:
    """测试用例 AI 生成器。

    职责：
        1. 为单个测试点调用 AI 生成测试用例
        2. 3 轮质量反馈闭环（委托 quality_feedback_loop）
        3. AI 响应解析与缓存控制
    """

    _AI_CACHE_MAX_SIZE = 200
    _AI_CACHE_TTL_SECONDS = 3600

    def __init__(self, db: Optional[Session] = None) -> None:
        self.db = db

    # ── 缓存控制 ──
    def _get_generation_cache(self) -> Dict[str, Any]:
        cache = getattr(self, "_generation_cache", None)
        if cache is None:
            cache = {}
            self._generation_cache = cache
        return cache

    def _build_generation_cache_key(self, context: Dict[str, Any]) -> str:
        cache_payload = {
            "requirement_content": context.get("requirement_content", ""),
            "ui_description": context.get("ui_description", ""),
            "ui_specs": context.get("ui_specs", []),
            "test_point": context.get("test_point", {}),
            "case_type": context.get("case_type"),
            "case_category": context.get("case_category"),
            # 缓存键必须包含 history_cases 和 execution_feedback，
            # 否则同测试点跨批次重试时缓存命中会抵消上下文增强效果
            "history_cases": context.get("history_cases", []),
            "execution_feedback": context.get("execution_feedback"),
            "model": settings.DEEPSEEK_MODEL,
        }
        raw = json.dumps(cache_payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _get_cached_generation(self, cache_key: str) -> Dict[str, Any] | None:
        cache = self._get_generation_cache()
        entry = cache.get(cache_key)
        if not entry:
            return None
        value, created_at = entry
        if time.monotonic() - created_at > self._AI_CACHE_TTL_SECONDS:
            cache.pop(cache_key, None)
            return None
        return dict(value)

    def _set_cached_generation(self, cache_key: str, value: Dict[str, Any]) -> None:
        cache = self._get_generation_cache()
        if len(cache) >= self._AI_CACHE_MAX_SIZE:
            oldest_key = min(cache, key=lambda key: cache[key][1])
            cache.pop(oldest_key, None)
        cache[cache_key] = (dict(value), time.monotonic())

    def _get_case_generation_max_tokens(self, *, retry_full: bool = False) -> int:
        if retry_full:
            return int(getattr(settings, "AI_CASE_GENERATION_MAX_TOKENS_FULL", 8192))
        return int(getattr(settings, "AI_CASE_GENERATION_MAX_TOKENS", 4096))

    # ── 公开入口 ──
    async def generate_test_case_for_point(
        self,
        context: Dict[str, Any],
        test_point: Dict[str, Any],
        project_id: int,
        case_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """为单个测试点生成测试用例。"""
        ui_description = self._build_ui_description(context.get("ui_descriptions", []))
        requirement_content = ContentSanitizer.sanitize(context.get("requirement_content", ""))
        ui_description = ContentSanitizer.sanitize(ui_description)

        has_ui = bool(ui_description and ui_description.strip()) or bool(context.get("ui_specs", []))

        # case_type 描述执行方式，case_category 描述测试场景（positive/boundary/exception）。
        # 历史实现把 case_type 值赋给 case_category 局部变量导致字段污染，R1 修复后分离语义。
        if not has_ui:
            derived_case_type = TEST_CATEGORY_MANUAL
        else:
            ui_keywords = ['按钮', '表单', '输入框', '下拉框', '复选框', '单选框', '链接', '导航',
                           'button', 'input', 'form', 'dropdown', 'checkbox', 'radio', 'link', 'menu']
            ui_has_interactive = any(k in ui_description.lower() for k in ui_keywords)
            derived_case_type = TEST_CATEGORY_UI_AUTO if ui_has_interactive else TEST_CATEGORY_MANUAL

        generation_context = {
            "requirement_content": requirement_content,
            "ui_description": ui_description,
            # 并发安全：ui_specs/history_cases 是 base_context 的嵌套可变对象，
            # 在 3 路并发生成下若按引用共享，下游修改会污染其他测试点。深拷贝切断共享引用。
            "ui_specs": copy.deepcopy(context.get("ui_specs", [])),
            "test_point": test_point,
            # 多测试点场景下需让 AI 一次生成 ≥3 条用例，上游 batch_orchestrator
            # 会把整个 test_points 列表放入 context，透传到 _generate_case_with_ai 计算 min_case_count
            "test_points": context.get("test_points", []),
            "case_type": case_type or derived_case_type,
            # case_category 由 AI 按测试场景生成，仅在显式传入时透传，不用 case_type 值兜底
            "case_category": context.get("case_category"),
            "history_cases": copy.deepcopy(context.get("history_cases", [])),
            "project_id": project_id,
            "execution_feedback": context.get("execution_feedback"),
        }

        generated_case = await self._generate_case_with_ai(generation_context)
        generated_case["_context_ui_specs"] = copy.deepcopy(context.get("ui_specs", []))
        return generated_case

    async def _generate_case_with_ai(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用 AI 生成测试用例，含 3 轮质量反馈闭环。

        业务原因：首轮 AI 输出可能不达标，通过 run_quality_feedback_loop 注入质量反馈，
        让 AI 在第 2/3 轮修复问题，提升一次通过率。流式与非流式端点共用此闭环。
        """
        from app.services.case_quality.quality_feedback_loop import (
            build_quality_feedback_text, run_quality_feedback_loop,
        )

        test_point = context.get("test_point", {})
        test_points = context.get("test_points", [])
        min_case_count = 3 if (len(test_points) >= 2 if test_points else False) else 1

        cache_key = self._build_generation_cache_key(context)
        cached = self._get_cached_generation(cache_key)
        if cached is not None:
            logger.info("AI生成测试用例缓存命中")
            return cached

        prompt_kwargs: Dict[str, Any] = {
            "requirement_content": context.get("requirement_content", ""),
            "ui_description": context.get("ui_description", ""),
            "module": test_point.get("module", "未知模块"),
            "function": test_point.get("function", "未知功能"),
            "point": test_point.get("point", ""),
            "priority": test_point.get("priority", 2),
            "ui_specs": context.get("ui_specs", []),
            "case_type": context.get("case_type"),
            "min_case_count": min_case_count,
            "history_cases": context.get("history_cases", []),
            "project_id": context.get("project_id"),
            "db": getattr(self, "db", None),
            "execution_feedback": context.get("execution_feedback"),
        }

        async def _regen_with_feedback(
            extra_context: Dict[str, Any],
        ) -> Optional[Dict[str, Any]]:
            """重生成函数：注入 extra_context 到 PromptBuilder，调用 AI 并校验额外用例。"""
            kwargs = dict(prompt_kwargs)
            if extra_context:
                kwargs["extra_context"] = extra_context
            prompt = PromptBuilder.build_linear_prompt(**kwargs)
            new_case = await self._call_ai_and_parse(prompt, min_case_count=min_case_count)
            if new_case is None:
                return None
            self._validate_extra_cases(new_case)
            return new_case

        # 首轮生成（无 extra_context）
        first_case = await _regen_with_feedback({})
        if first_case is None:
            raise ValueError("AI生成失败: 所有轮次均未返回有效用例")

        # 调用共享 3 轮反馈闭环（含 quality_signals 注入）
        final_case, status, _ = await run_quality_feedback_loop(
            first_case, _regen_with_feedback, build_quality_feedback_text,
        )

        # 只缓存 passed 用例，避免低质量用例污染缓存
        if status == "passed":
            self._set_cached_generation(cache_key, final_case)
        return final_case

    def _validate_extra_cases(self, case: Dict[str, Any]) -> None:
        """校验并剔除 rejected 的额外用例。只剔除 rejected，pending_review/warning 保留。"""
        extra_cases = case.get("_extra_cases", [])
        if not extra_cases:
            return
        validated_extras: List[Dict[str, Any]] = []
        for extra in extra_cases:
            extra_status, _ = validate_single_case_status(extra)
            if extra_status != "rejected":
                validated_extras.append(extra)
            else:
                logger.warning(f"额外用例校验不通过已剔除: {extra.get('title', '')}")
        case["_extra_cases"] = validated_extras

    async def _call_ai_and_parse(
        self, prompt: str, min_case_count: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """调用 AI 并解析响应，含收紧的重试策略。

        性能优化：
        1. 重试次数从 3 轮收到 2 轮（首次 + 1 次重试），避免 75s+ 长尾
        2. 仅解析失败/截断（ValueError/JSONDecodeError）才升级 max_tokens 重试
        3. ConnectionError / asyncio.TimeoutError 立即抛出（SDK 已有 max_retries）
        4. 退避时间从指数（1s, 2s）改为固定 0.5s，避免雪崩
        5. 直接 await async client，移除 asyncio.to_thread 包装
        """
        max_retries = 2
        last_error: Optional[str] = None
        use_full_tokens = False

        for attempt in range(max_retries):
            try:
                client = _get_openai_client()
                max_tokens = self._get_case_generation_max_tokens(retry_full=use_full_tokens)
                # AsyncOpenAIClient.complete_async 直接 await，单次调用受
                # settings.AI_CALL_TIMEOUT_SECONDS 硬超时保护
                response = await client.complete_async(prompt, max_tokens=max_tokens)
                content = response.content or ""
                if not content:
                    raise ValueError("AI响应内容为空")

                parsed = parse_ai_response(content)

                if "cases" in parsed and isinstance(parsed["cases"], list):
                    cases_list = parsed["cases"]
                    if not cases_list:
                        raise ValueError("AI返回的用例数组为空")
                    if len(cases_list) < min_case_count:
                        logger.warning(
                            f"AI返回用例数 {len(cases_list)} 少于期望 {min_case_count}"
                        )
                    primary_case = cases_list[0]
                    primary_case["_extra_cases"] = cases_list[1:]
                    return primary_case

                return parsed

            except (ValueError, json.JSONDecodeError) as e:
                # 仅解析失败/截断才重试，并升级 max_tokens
                last_error = str(e)
                use_full_tokens = True
                logger.warning(f"AI响应解析失败(尝试{attempt + 1}/{max_retries}): {e}")
            except (ConnectionError, asyncio.TimeoutError) as e:
                # 网络错误与超时立即抛出，不再重试（SDK 内部已 max_retries=3）
                logger.error(f"AI调用网络/超时错误，不再重试: {e}")
                raise ValueError(f"AI生成失败: {e}") from e
            except Exception as e:
                last_error = str(e)
                logger.error(f"AI调用异常(尝试{attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(0.5)

        raise ValueError(f"AI生成失败: {last_error}")

    def _build_ui_description(self, ui_descriptions: List[Dict[str, Any]]) -> str:
        """构建 UI 描述文本（简化版：description 优先，summary 兜底）。"""
        parts = []
        for desc in ui_descriptions:
            if desc.get("description"):
                parts.append(desc["description"])
            elif desc.get("summary"):
                parts.append(desc["summary"])
        return "\n".join(parts)


# 向后兼容别名：历史代码以 TestCaseGenerationAiMixin 名称实例化
TestCaseGenerationAiMixin = AiGenerator
