import json
import re
import time
from typing import Dict, Any, Optional, List
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
    AI_GENERATE_MAX_TOKENS,
    AI_GENERATE_MAX_TOKENS_FULL,
    _resolve_max_tokens,
)
from app.utils.ai_client_enhanced._enhanced_prompt import (
    _build_priority_rules,
    _build_generation_prompt,
)
from app.utils.ai_client_enhanced._enhanced_logging import _record_enhanced_call


def generate_test_case_enhanced(
    context: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    graph_prompt = context.get('graph_prompt')
    min_case_count = 3
    test_points = context.get('test_points', [])
    if test_points and len(test_points) < 2:
        min_case_count = 1
    if graph_prompt:
        prompt = graph_prompt
    else:
        prompt, min_case_count = _build_generation_prompt(context)

    # Task 15/16: 注入质量反馈与质量信号（重生成轮次）。
    # graph 与线性模式统一在此注入，避免散落到各 Prompt 构建分支。
    # 禁止盲重试：quality_signals 携带具体问题与低分维度（历史避坑要点 4）。
    quality_feedback = context.get('quality_feedback')
    if quality_feedback:
        prompt += f"\n\n## 质量反馈\n{quality_feedback}\n"
    quality_signals = context.get('quality_signals')
    if quality_signals:
        from app.services.case_quality.quality_signals import format_quality_signals
        signals_text = format_quality_signals(quality_signals)
        if signals_text:
            prompt += f"\n\n{signals_text}\n"

    client = get_ai_client()
    max_retries = 3
    messages = [{"role": "user", "content": prompt}]
    is_graph_mode = bool(graph_prompt)
    if is_graph_mode and min_case_count < 3:
        min_case_count = 3
    max_tokens = _resolve_max_tokens(context, graph_mode=is_graph_mode)
    for attempt in range(max_retries):
        try:
            started_at = time.monotonic()
            logger.debug(f"增强版AI生成测试用例 - 尝试 {attempt + 1}/{max_retries}")
            response = client.chat.completions.create(
                model=client.model_name,
                messages=messages,
                temperature=0.3,
                max_tokens=max_tokens
            )
            latency_ms = int((time.monotonic() - started_at) * 1000)
            finish_reason = response.choices[0].finish_reason if response.choices else None
            logger.debug(
                "增强版AI生成调用完成: "
                f"latency_ms={latency_ms}, max_tokens={max_tokens}, "
                f"finish_reason={finish_reason}, attempt={attempt + 1}/{max_retries}"
            )
            # 记录 AI 调用日志（审计增强）
            _record_enhanced_call(
                metadata=metadata,
                model_name=client.model_name,
                response=response,
                latency_ms=latency_ms,
            )
            if finish_reason == "length" and max_tokens < AI_GENERATE_MAX_TOKENS_FULL:
                max_tokens = AI_GENERATE_MAX_TOKENS_FULL
                logger.warning("增强版AI响应被截断，提升max_tokens后重试")
                continue
            resp_content = response.choices[0].message.content
            if not resp_content:
                raise AIResponseParseError("AI返回内容为空")
            resp_content = resp_content.strip()
            code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', resp_content)
            if code_block_match:
                resp_content = code_block_match.group(1).strip()
            elif resp_content.startswith("```"):
                resp_content = re.sub(r'^```(?:json)?\s*\n?', '', resp_content)
                resp_content = re.sub(r'\n?```\s*$', '', resp_content)
                resp_content = resp_content.strip()
            generated_case = None
            try:
                generated_case = json.loads(resp_content)
            except json.JSONDecodeError:
                json_match = re.search(r'\[[\s\S]*\]\s*$', resp_content)
                if not json_match:
                    json_match = re.search(r'\{[\s\S]*\}', resp_content)
                if json_match:
                    matched_str = json_match.group(0)
                    try:
                        generated_case = json.loads(matched_str)
                    except json.JSONDecodeError:
                        fixed = fix_common_json_issues(matched_str)
                        if fixed:
                            try:
                                generated_case = json.loads(fixed)
                            except json.JSONDecodeError:
                                pass
                        if generated_case is None:
                            cleaned = clean_json_string(matched_str)
                            if cleaned:
                                try:
                                    generated_case = json.loads(cleaned)
                                except json.JSONDecodeError:
                                    pass
                        if generated_case is None:
                            repaired = _repair_truncated_json(matched_str)
                            if repaired:
                                try:
                                    generated_case = json.loads(repaired)
                                except json.JSONDecodeError:
                                    pass
            if generated_case is not None:
                normalized_cases: list = []
                if isinstance(generated_case, list):
                    for case_item in generated_case:
                        if isinstance(case_item, dict):
                            if 'expected_results' in case_item and isinstance(case_item.get('expected_results'), list):
                                normalized_cases.append(normalize_new_format(case_item))
                            else:
                                normalized_cases.append(normalize_old_format(case_item))
                elif isinstance(generated_case, dict):
                    if 'expected_results' in generated_case and isinstance(generated_case.get('expected_results'), list):
                        normalized_cases.append(normalize_new_format(generated_case))
                    else:
                        normalized_cases.append(normalize_old_format(generated_case))
                if not normalized_cases:
                    logger.warning(f"AI返回内容格式化后为空 (尝试 {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    raise AIResponseParseError("AI返回内容格式化后为空")
                passed, issues = validate_cases_quality(normalized_cases, min_count=min_case_count)
                quality_score = compute_quality_score(normalized_cases)
                if passed:
                    logger.info(
                        f"增强版AI生成测试用例成功，共{len(normalized_cases)}条，质量分{quality_score:.0f}"
                    )
                    return normalized_cases
                if quality_score >= QUALITY_MIN_SCORE:
                    logger.warning(
                        f"用例质量分{quality_score:.0f}≥阈值{QUALITY_MIN_SCORE}，"
                        f"存在次要问题: {issues}"
                    )
                    return normalized_cases
                if attempt < max_retries - 1:
                    feedback = (
                        "上一次生成的用例存在以下质量问题，请逐一修正后重新生成：\n"
                        + "\n".join(f"- {issue}" for issue in issues)
                    )
                    messages.append({"role": "assistant", "content": resp_content[:3000]})
                    messages.append({"role": "user", "content": feedback})
                    logger.warning(
                        f"用例质量分{quality_score:.0f}<阈值{QUALITY_MIN_SCORE}，"
                        f"触发质量反馈重试 (尝试 {attempt + 1}/{max_retries})，"
                        f"问题数: {len(issues)}"
                    )
                    time.sleep(2)
                    continue
                logger.error(
                    f"用例质量分{quality_score:.0f}<阈值{QUALITY_MIN_SCORE}，"
                    f"已达最大重试次数，降级返回，问题数: {len(issues)}"
                )
                return normalized_cases
            logger.warning(f"AI返回内容无法解析 (尝试 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            raise AIResponseParseError("AI返回内容无法解析为有效的测试用例")
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
