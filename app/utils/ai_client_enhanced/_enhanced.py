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
from app.services.prompt_builder.comparison_examples import (
    get_comparison_examples,
    get_title_spec_rules,
    get_precondition_spec_rules,
    get_automation_friendly_rules,
)
from app.services.test_case_generation.quality_validator import (
    validate_cases_quality,
    compute_quality_score,
    QUALITY_MIN_SCORE,
)
from app.utils.ai_client_enhanced._repair import _repair_truncated_json

AI_GENERATE_MAX_TOKENS = 8192
AI_GENERATE_MAX_TOKENS_FULL = 16384


def _record_enhanced_call(
    metadata: Optional[Dict[str, Any]],
    model_name: str,
    response: Any,
    latency_ms: int,
) -> None:
    """记录增强版 AI 调用日志

    从 metadata 提取审计增强字段，从 response 提取 Token 用量，
    统一写入 AICallLog。

    Args:
        metadata: 元数据字典（含 db, generation_batch_id, scenario_type 等）
        model_name: 模型名称
        response: OpenAI API 响应对象
        latency_ms: 调用耗时（毫秒）
    """
    try:
        from app.ai.call_log import record_call
        db = metadata.get("db") if metadata else None
        usage_data = response.usage
        prompt_tokens = usage_data.prompt_tokens if usage_data else 0
        completion_tokens = usage_data.completion_tokens if usage_data else 0
        cost_usd = (
            prompt_tokens / 1000 * 0.0014
            + completion_tokens / 1000 * 0.0028
        )
        record_call(
            db,
            model=response.model or model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=round(cost_usd, 6),
            latency_ms=latency_ms,
            step_name=metadata.get("step_name") if metadata else None,
            run_id=metadata.get("run_id") if metadata else None,
            generation_batch_id=metadata.get("generation_batch_id") if metadata else None,
            scenario_type=metadata.get("scenario_type") if metadata else None,
            generation_strategy=metadata.get("generation_strategy") if metadata else None,
            prompt_key=metadata.get("prompt_key") if metadata else None,
            prompt_version=metadata.get("prompt_version") if metadata else None,
            prompt_hash=metadata.get("prompt_hash") if metadata else None,
        )
    except Exception as log_err:
        logger.warning(f"Failed to record enhanced AI call log: {log_err}")


def _resolve_max_tokens(context: Dict[str, Any], *, graph_mode: bool) -> int:
    test_points = _normalize_test_points(context)
    if graph_mode or len(test_points) > 1 or context.get("history_cases"):
        return AI_GENERATE_MAX_TOKENS_FULL
    return AI_GENERATE_MAX_TOKENS


def _as_dict_list(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_test_points(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    points_by_id: Dict[str, Dict[str, Any]] = {}
    anonymous_points: List[Dict[str, Any]] = []

    for key in ("test_points", "test_points_data", "test_point", "current_test_point"):
        for point in _as_dict_list(context.get(key)):
            point_id = point.get("id")
            if point_id is None:
                anonymous_points.append(point)
                continue
            point_key = str(point_id)
            merged = dict(points_by_id.get(point_key, {}))
            for field, value in point.items():
                if value not in (None, "", []):
                    merged[field] = value
            points_by_id[point_key] = merged

    return list(points_by_id.values()) + anonymous_points


def _normalize_ui_specs(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _stringify_ui_description(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, dict):
                name = item.get("screen_name") or item.get("file_name") or item.get("name") or "未命名"
                desc = item.get("description") or item.get("summary") or json.dumps(item, ensure_ascii=False)
                parts.append(f"【{name}】\n{desc}")
            elif item:
                parts.append(str(item))
        return "\n\n".join(parts)
    return ""


def _build_priority_rules(has_ui: bool, has_requirement: bool, has_test_point: bool) -> str:
    rules = """## 信息优先级与冲突规则（必须遵守）
1. 信息优先级：当前测试点 > 关联需求文档 > 当前UI元素(ui_spec) > UI流程/navigation_flow > 历史用例摘要
2. UI元素存在性仅依据当前UI解析结果(ui_spec)。不得使用未在当前UI上下文中出现的按钮、输入框、链接或页面元素
3. 需求与UI不一致时，以需求为准，但涉及UI交互的步骤必须标记【待确认UI】
4. ui_spec缺失或解析失败时，不得臆造元素；需要交互时必须标记【待确认UI】
5. 历史用例仅用于避免重复，不代表当前测试点必须覆盖同类场景；不得照搬、改写或合并历史用例步骤
6. 缺少信息时输出【待补充】或【待确认UI】，禁止编造页面、按钮、字段、接口或业务规则

## 硬约束
- 禁止使用需求中未提及的规则或UI中不存在的元素
- 缺失信息必须标记【待补充】或【待确认UI】
- 权重规则仅为可信上下文内的二级提示策略，不能覆盖上述来源优先级"""

    if not has_requirement:
        rules += "\n\n⚠️ **缺少需求文档**：可能导致生成的测试用例偏离实际业务功能。请基于现有信息生成合理的测试用例，但需注意可能无法完全贴合实际需求。UI或历史用例不得升级为业务事实来源。"
    if not has_ui:
        rules += "\n\n⚠️ **缺少UI原型图**：不得编造按钮、输入框、页面区域、弹窗或跳转入口。如测试点必须涉及UI操作，请使用【待确认UI】标记。优先生成基于需求、业务规则、接口或人工验证视角的测试用例。"
    if not has_test_point:
        rules += "\n\n⚠️ **缺少测试点**：请从需求文档的每个功能点自动推断需要生成的测试用例，但不得超出需求文档定义的功能边界。"

    return rules


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
        from app.utils.ai_client_prompt import (
            sanitize_input,
            build_ui_specs_description, build_project_env_info
        )
        raw_requirement = (
            context.get('requirement_content')
            or context.get('requirement')
            or context.get('requirement_text')
            or ''
        )
        requirement = sanitize_input(str(raw_requirement))
        test_points = _normalize_test_points(context)
        ui_specs = _normalize_ui_specs(context.get('ui_specs'))
        raw_ui_description = _stringify_ui_description(
            context.get('ui_description') or context.get('ui_descriptions')
        )
        project_config = context.get('project_config')
        if not isinstance(project_config, dict):
            project_config = {}
        extra_requirements = sanitize_input(str(context.get('extra_requirements') or ''), max_length=10000)
        has_requirement = bool(requirement and requirement.strip())
        ui_desc = (
            build_ui_specs_description(ui_specs)
            if ui_specs
            else sanitize_input(raw_ui_description)
        )
        has_ui = bool(ui_specs)
        has_ui_reference = has_ui or bool(ui_desc and ui_desc.strip() and ui_desc.strip() not in ("[]", "{}", ""))
        has_test_point = bool(test_points)
        min_case_count = 3 if (len(test_points) >= 2 if test_points else False) else 1
        priority_rules = _build_priority_rules(has_ui, has_requirement, has_test_point)
        if not has_ui:
            ui_desc = "无UI原型图解析结果"
        env_desc = build_project_env_info(project_config)
        history_cases = context.get('history_cases', [])
        history_cases_text = ""
        if history_cases:
            history_cases_text = "## 项目已有测试用例（覆盖摘要，仅供避重参考）\n\n"
            history_cases_text += "以下为项目已有的测试用例摘要，仅供避免重复生成使用：\n"
            history_cases_text += "- 这些用例已覆盖的场景无需重复生成\n"
            history_cases_text += "- 请仅生成新场景的用例，不要改写或废弃已有用例\n"
            history_cases_text += "- 已有用例的维护由保鲜建议流程单独处理\n\n"
            for i, case in enumerate(history_cases, 1):
                desc = case.get("summary", "") or case.get("expected_result", "") or "无摘要"
                history_cases_text += f"  {i}. [{case.get('module', '')}] {case.get('title', '')} (ID:{case.get('id', '')}) — {desc}\n"
        test_points_text = ""
        if test_points:
            test_points_text = "## 测试点列表\n"
            for i, tp in enumerate(test_points):
                module = tp.get('module', '')
                function = tp.get('function', '')
                point = tp.get('point', '')
                priority = tp.get('priority', 2)
                test_points_text += f"{i+1}. [{module} - {function}] {point} (优先级:{priority})\n"
        extra_requirements_text = ""
        if extra_requirements:
            extra_requirements_text = f"""## 补充生成要求
{extra_requirements}

---
"""
        prompt = f"""你是一名高级测试工程师，请根据以下信息生成一个高质量的测试用例。

{priority_rules}

---

## 需求文档
{requirement if has_requirement else "（未提供需求文档）"}

---

## UI原型图解析结果
{ui_desc}

---

{test_points_text}

---

{env_desc}

---

{history_cases_text}

---

{extra_requirements_text}

## 输出格式要求
0. {'必须返回测试用例，覆盖正向（case_category=positive）、边界（case_category=boundary）、异常（case_category=exception）三种测试类型。如果需求或UI涉及多个功能点或页面，请为每个功能点分别生成用例，总数不少于3条' if min_case_count >= 3 else '必须返回至少1条正向用例（case_category=positive）。仅在条件允许时补充边界（case_category=boundary）或异常（case_category=exception）用例，不要为了凑数而生成低质量用例'}
请严格按照以下JSON数组格式输出（不要添加markdown代码块标记）：
[
  {{
    "title": "正向场景+操作+验证重点",
    "module": "所属模块",
    "precondition": "系统已通过配置自动登录至目标页面",
    "case_type": "ui_automation/manual/api_automation/performance/security",
    "priority": "P0/P2/P3",
    "test_data": {{"normal": {{}}, "boundary": {{}}, "abnormal": {{}}}},
    "steps": [
      {{
        "step": "1",
        "description": "步骤1描述",
        "action": "具体的业务操作描述",
        "action_type": "click/input/navigate/verify/wait/scroll/hover/select/captcha/refresh/keypress",
        "input_value": "输入值（仅input类型有值，其他为空字符串）",
        "target_element": "目标元素描述",
        "expected_result": "该步骤的预期验证条件"
      }}
    ],
    "expected_result": "所有步骤预期结果的汇总描述",
    "case_category": "positive",
    "change_type": "added"
  }}
]
{get_title_spec_rules()}
{get_precondition_spec_rules()}
{get_comparison_examples()}
## 生成规则
1. **步骤要求**：每个步骤必须是原子操作；action_type必须是枚举值之一；input_value仅input/select填写；expected_result必须是可验证条件
2. **用例类型**：ui_automation(UI交互)/manual(人工判断)/api_automation(接口验证)/performance(性能)/security(安全)
3. **优先级**：P0(核心功能)/P2(一般验证)/P3(边界异常)
4. **覆盖要求**：必须覆盖需求文档所有功能点；每个测试点至少一个用例；有UI原型图时操作对象须与UI元素对应
5. **格式统一**：step字段为字符串类型；必须包含test_data字段（normal/boundary/abnormal三个空对象）
"""

        case_type = context.get('case_type')
        if case_type:
            prompt += f"\n## 用例类型约束\n"
            if case_type == "ui_automation" and not has_ui:
                prompt += (
                    "当前项目未提供UI原型图，ui_automation降级为草稿模式。\n"
                    "所有用例的 case_type 字段填写 \"manual\"，不得填写 \"ui_automation\"。\n"
                    "涉及UI交互的步骤必须标记【待确认UI】，不得编造按钮、输入框等页面元素。\n"
                    "优先生成基于需求、业务规则或人工验证视角的测试用例。\n"
                )
                case_type = "manual"
            else:
                prompt += f"所有用例的 case_type 字段必须统一为 \"{case_type}\"，不允许生成其他类型的用例。\n"
                type_guidance = {
                    "ui_automation": "步骤必须包含UI元素交互，action_type使用click/input/scroll等UI操作，预期结果可自动化验证",
                    "manual": "允许包含需要人工判断的步骤，预期结果允许主观描述，不要求完全可自动化",
                    "api_automation": "用例聚焦接口层面验证，步骤以API请求/响应断言为主，无需UI元素引用",
                    "performance": "关注响应时间、并发数、吞吐量等性能指标，预期结果包含数值阈值",
                    "security": "关注XSS注入、SQL注入、权限绕过、敏感数据泄露等安全验证点",
                }
                extra = type_guidance.get(case_type, "")
                if extra:
                    prompt += f"{extra}\n"

        prompt += f"\n{get_automation_friendly_rules()}\n"

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
            logger.info(f"增强版AI生成测试用例 - 尝试 {attempt + 1}/{max_retries}")
            response = client.chat.completions.create(
                model=client.model_name,
                messages=messages,
                temperature=0.3,
                max_tokens=max_tokens
            )
            latency_ms = int((time.monotonic() - started_at) * 1000)
            finish_reason = response.choices[0].finish_reason if response.choices else None
            logger.info(
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
