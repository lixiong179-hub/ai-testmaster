import json
import re
import time
from typing import Any
from loguru import logger

from app.utils.ai_client_core import (
    AIServiceError,
    AIResponseParseError,
    AIResponseFormatError,
    get_ai_client,
)
from app.utils.ai_client_parser import (
    fix_common_json_issues,
    clean_json_string,
)
from app.utils.ai_client_formatter import (
    normalize_new_format,
    normalize_old_format,
)
from app.services.test_case_generation.quality_validator import (
    validate_cases_quality,
    compute_quality_score,
    QUALITY_MIN_SCORE,
)
from app.utils.ai_client_enhanced._repair import _repair_truncated_json
from app.utils.ai_client_enhanced._enhanced_context import (
    # 转发符号：app/utils/ai_client_enhanced/__init__.py 与测试从此模块导入
    AI_GENERATE_MAX_TOKENS,  # noqa: F401
    AI_GENERATE_MAX_TOKENS_FULL,
    _resolve_max_tokens,
)
from app.utils.ai_client_enhanced._enhanced_prompt import (
    # 转发符号：tests/test_context_precision_features.py 从此模块导入
    _build_priority_rules,  # noqa: F401
    _build_generation_prompt,
)
from app.utils.ai_client_enhanced._enhanced_logging import _record_enhanced_call
import contextlib


def _prepare_enhanced_prompt(context: dict[str, Any]) -> tuple[str, int, bool]:
    """构造 prompt，并推断最小用例数与 graph 模式。"""
    graph_prompt = context.get("graph_prompt")
    min_case_count = 3
    test_points = context.get("test_points", [])
    if test_points and len(test_points) < 2:
        min_case_count = 1
    if graph_prompt:
        prompt = graph_prompt
    else:
        prompt, min_case_count = _build_generation_prompt(context)

    # Task 15/16: 注入质量反馈与质量信号（重生成轮次）。
    # graph 与线性模式统一在此注入，避免散落到各 Prompt 构建分支。
    # 禁止盲重试：quality_signals 携带具体问题与低分维度（历史避坑要点 4）。
    quality_feedback = context.get("quality_feedback")
    if quality_feedback:
        prompt += f"\n\n## 质量反馈\n{quality_feedback}\n"
    quality_signals = context.get("quality_signals")
    if quality_signals:
        from app.services.case_quality.quality_signals import format_quality_signals

        signals_text = format_quality_signals(quality_signals)
        if signals_text:
            prompt += f"\n\n{signals_text}\n"
    return prompt, min_case_count, bool(graph_prompt)


def _request_enhanced_completion(
    client: Any,
    messages: list[dict[str, str]],
    max_tokens: int,
    metadata: dict[str, Any] | None,
    attempt: int,
    max_retries: int,
) -> tuple[Any, str | None]:
    """发起一次生成请求，并记录 AI 调用日志（审计增强）。"""
    started_at = time.monotonic()
    logger.debug(f"增强版AI生成测试用例 - 尝试 {attempt + 1}/{max_retries}")
    response = client.chat.completions.create(
        model=client.model_name, messages=messages, temperature=0.3, max_tokens=max_tokens
    )
    latency_ms = int((time.monotonic() - started_at) * 1000)
    finish_reason = response.choices[0].finish_reason if response.choices else None
    logger.debug(
        "增强版AI生成调用完成: "
        f"latency_ms={latency_ms}, max_tokens={max_tokens}, "
        f"finish_reason={finish_reason}, attempt={attempt + 1}/{max_retries}"
    )
    _record_enhanced_call(
        metadata=metadata,
        model_name=client.model_name,
        response=response,
        latency_ms=latency_ms,
    )
    return response, finish_reason


def _should_extend_tokens(finish_reason: str | None, max_tokens: int) -> bool:
    """响应被截断且尚未用满 token 上限时，提升上限再试。"""
    return finish_reason == "length" and max_tokens < AI_GENERATE_MAX_TOKENS_FULL


def _extract_resp_content(response: Any) -> str:
    """取响应正文；空内容视为解析错误。"""
    resp_content = response.choices[0].message.content
    if not resp_content:
        raise AIResponseParseError("AI返回内容为空")
    return resp_content.strip()


def _strip_code_fence(text: str) -> str:
    """剥离 Markdown 代码块围栏。"""
    code_block_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```", text)
    if code_block_match:
        return code_block_match.group(1).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
        return text.strip()
    return text


def _try_json_loads(text: str) -> Any | None:
    """尽力解析 JSON，失败返回 None。"""
    with contextlib.suppress(json.JSONDecodeError):
        return json.loads(text)
    return None


def _locate_json_fragment(text: str) -> str | None:
    """从混杂文本中定位 JSON 片段（优先以数组结尾者）。"""
    json_match = re.search(r"\[[\s\S]*\]\s*$", text)
    if not json_match:
        json_match = re.search(r"\{[\s\S]*\}", text)
    return json_match.group(0) if json_match else None


def _parse_json_fragment(fragment: str) -> Any | None:
    """按「直接 → 修常见问题 → 清洗 → 截断修复」顺序解析片段。"""
    direct = _try_json_loads(fragment)
    if direct is not None:
        return direct
    for fixer in (fix_common_json_issues, clean_json_string, _repair_truncated_json):
        candidate = fixer(fragment)
        if candidate:
            parsed = _try_json_loads(candidate)
            if parsed is not None:
                return parsed
    return None


def _parse_generated_case(resp_content: str) -> Any | None:
    """解析响应正文中的 JSON；无法解析返回 None。"""
    try:
        return json.loads(resp_content)
    except json.JSONDecodeError:
        fragment = _locate_json_fragment(resp_content)
        if fragment is None:
            return None
        return _parse_json_fragment(fragment)


def _normalize_single_case(case_item: dict[str, Any]) -> dict[str, Any]:
    """按是否含 expected_results 选择新/旧格式归一化。"""
    if "expected_results" in case_item and isinstance(case_item.get("expected_results"), list):
        return normalize_new_format(case_item)
    return normalize_old_format(case_item)


def _normalize_generated_cases(generated_case: Any) -> list[dict[str, Any]]:
    """把解析结果统一为归一化用例列表（非 dict 元素跳过）。"""
    if isinstance(generated_case, list):
        return [_normalize_single_case(item) for item in generated_case if isinstance(item, dict)]
    if isinstance(generated_case, dict):
        return [_normalize_single_case(generated_case)]
    return []


def _retry_after_delay(attempt: int, max_retries: int, error: Exception) -> None:
    """未到上限则 sleep 后返回（由调用方重试），否则抛出该错误。"""
    if attempt < max_retries - 1:
        time.sleep(2)
        return
    raise error


def _parse_and_normalize(resp_content: str, attempt: int, max_retries: int) -> list[dict[str, Any]] | None:
    """解析并归一化；不可用时返回 None（已 sleep 或已抛出异常）。"""
    generated_case = _parse_generated_case(resp_content)
    if generated_case is None:
        logger.warning(f"AI返回内容无法解析 (尝试 {attempt + 1}/{max_retries})")
        _retry_after_delay(attempt, max_retries, AIResponseParseError("AI返回内容无法解析为有效的测试用例"))
        return None
    normalized_cases = _normalize_generated_cases(generated_case)
    if not normalized_cases:
        logger.warning(f"AI返回内容格式化后为空 (尝试 {attempt + 1}/{max_retries})")
        _retry_after_delay(attempt, max_retries, AIResponseParseError("AI返回内容格式化后为空"))
        return None
    return normalized_cases


def _decide_quality_outcome(
    normalized_cases: list[dict[str, Any]],
    min_case_count: int,
    messages: list[dict[str, str]],
    resp_content: str,
    attempt: int,
    max_retries: int,
) -> list[dict[str, Any]] | None:
    """质量门：通过或降级返回用例；未通过则追加反馈并返回 None 触发重试。"""
    passed, issues = validate_cases_quality(normalized_cases, min_count=min_case_count)
    quality_score = compute_quality_score(normalized_cases)
    if passed:
        logger.info(f"增强版AI生成测试用例成功，共{len(normalized_cases)}条，质量分{quality_score:.0f}")
        return normalized_cases
    if quality_score >= QUALITY_MIN_SCORE:
        logger.warning(f"用例质量分{quality_score:.0f}≥阈值{QUALITY_MIN_SCORE}，存在次要问题: {issues}")
        return normalized_cases
    if attempt < max_retries - 1:
        feedback = "上一次生成的用例存在以下质量问题，请逐一修正后重新生成：\n" + "\n".join(
            f"- {issue}" for issue in issues
        )
        messages.append({"role": "assistant", "content": resp_content[:3000]})
        messages.append({"role": "user", "content": feedback})
        logger.warning(
            f"用例质量分{quality_score:.0f}<阈值{QUALITY_MIN_SCORE}，"
            f"触发质量反馈重试 (尝试 {attempt + 1}/{max_retries})，"
            f"问题数: {len(issues)}"
        )
        time.sleep(2)
        return None
    logger.error(
        f"用例质量分{quality_score:.0f}<阈值{QUALITY_MIN_SCORE}，已达最大重试次数，降级返回，问题数: {len(issues)}"
    )
    return normalized_cases


def _run_enhanced_attempt(
    client: Any,
    messages: list[dict[str, str]],
    max_tokens: int,
    metadata: dict[str, Any] | None,
    min_case_count: int,
    attempt: int,
    max_retries: int,
) -> tuple[list[dict[str, Any]] | None, int]:
    """执行单次尝试；返回（用例或 None=需重试，本次使用的 max_tokens）。"""
    response, finish_reason = _request_enhanced_completion(client, messages, max_tokens, metadata, attempt, max_retries)
    if _should_extend_tokens(finish_reason, max_tokens):
        logger.warning("增强版AI响应被截断，提升max_tokens后重试")
        return None, AI_GENERATE_MAX_TOKENS_FULL
    resp_content = _strip_code_fence(_extract_resp_content(response))
    normalized_cases = _parse_and_normalize(resp_content, attempt, max_retries)
    if normalized_cases is None:
        return None, max_tokens
    quality_cases = _decide_quality_outcome(
        normalized_cases, min_case_count, messages, resp_content, attempt, max_retries
    )
    return quality_cases, max_tokens


def generate_test_case_enhanced(
    context: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """增强版用例生成：提示词组装 → 请求 → 解析归一化 → 质量门 → 重试。"""
    prompt, min_case_count, is_graph_mode = _prepare_enhanced_prompt(context)
    client = get_ai_client()
    max_retries = 3
    messages = [{"role": "user", "content": prompt}]
    if is_graph_mode and min_case_count < 3:
        min_case_count = 3
    max_tokens = _resolve_max_tokens(context, graph_mode=is_graph_mode)

    for attempt in range(max_retries):
        try:
            normalized_cases, max_tokens = _run_enhanced_attempt(
                client, messages, max_tokens, metadata, min_case_count, attempt, max_retries
            )
            if normalized_cases is not None:
                return normalized_cases
        except (AIResponseParseError, AIResponseFormatError):
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise
        except Exception as e:
            logger.error(f"增强版AI生成测试用例失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise AIServiceError(f"增强版AI生成测试用例失败: {str(e)}")
    raise AIServiceError("增强版AI生成测试用例失败: 超过最大重试次数")
