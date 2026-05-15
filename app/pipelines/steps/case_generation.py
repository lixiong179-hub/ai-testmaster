"""S11 CaseGeneration — 用例生成 Step

调用 AI 为每个测试点生成测试用例。
复用现有 TestCaseGenerationService 的 prompt 构建和解析逻辑，
但通过 Pipeline AIClient 抽象层调用模型。
"""
import hashlib
import json
import re
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


class CaseGeneration(PipelineStep):
    """用例生成 Step — 为每个测试点调用 AI 生成测试用例。"""

    name: ClassVar[str] = "case_generation"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["generation_tasks"]
    produces: ClassVar[List[str]] = ["generated_cases"]

    def should_run(self, ctx: PipelineContext) -> bool:
        tasks_artifact = ctx.get_artifact("generation_tasks")
        if tasks_artifact:
            tasks = tasks_artifact.get("generation_tasks", [])
            return len(tasks) > 0
        aligned = ctx.get_artifact("aligned_testpoints")
        if aligned:
            return aligned.get("total_testpoints", 0) > 0
        signals = ctx.get_artifact("raw_signals")
        if signals:
            return signals.get("has_testpoints", False)
        return False

    def cache_key(self, ctx: PipelineContext) -> str:
        tasks = ctx.get_artifact("generation_tasks")
        aligned = ctx.get_artifact("aligned_testpoints")
        signals = ctx.get_artifact("raw_signals")

        task_ids = []
        if tasks:
            task_ids = sorted(
                t.get("task_id", "") for t in tasks.get("generation_tasks", [])
            )

        tp_ids = []
        if aligned:
            tp_ids = sorted(
                a["test_point"].get("id", 0)
                for a in aligned.get("aligned_testpoints", [])
            )
        elif signals:
            tp_ids = sorted(
                tp.get("id", 0)
                for tp in signals.get("test_points", [])
                if tp is not None
            )

        raw = f"{self.name}:{self.version}:tasks={task_ids}:tp={tp_ids}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        signals = ctx.get_artifact("raw_signals")
        prd_content = signals.get("prd_content", "") if signals else ""
        ui_specs = signals.get("ui_specs", []) if signals else []
        ui_descriptions = signals.get("ui_descriptions", []) if signals else []
        has_ui = signals.get("has_ui", False) if signals else False

        tasks_artifact = ctx.get_artifact("generation_tasks")
        aligned = ctx.get_artifact("aligned_testpoints")

        # 构建 UI 描述文本
        ui_description = ""
        if ui_descriptions:
            ui_description = "\n".join(
                d.get("description", d.get("summary", ""))
                for d in ui_descriptions
                if d.get("description") or d.get("summary")
            )

        generated_cases = []
        failed_count = 0

        # 确定生成模式
        if tasks_artifact:
            generation_tasks = tasks_artifact.get("generation_tasks", [])
            deprecation_suggestions = tasks_artifact.get("deprecation_suggestions", [])
            # 筛选需要生成的任务
            actionable_tasks = [
                t for t in generation_tasks
                if t.get("task_type") in ("create", "modify", "locator_fix")
            ]
        else:
            generation_tasks = []
            deprecation_suggestions = []
            actionable_tasks = []

        # 从 history_fingerprints 提取已有用例详情供 create 任务查漏使用
        history_cases = []
        if actionable_tasks:
            hf_artifact = ctx.get_artifact("history_fingerprints")
            if hf_artifact:
                for fp in hf_artifact.get("fingerprints", [])[:50]:
                    history_cases.append({
                        "title": fp.get("title", fp.get("case_title", "")),
                        "module": fp.get("module", ""),
                        "summary": fp.get("summary", ""),
                        "priority": fp.get("priority", 3),
                    })

        if actionable_tasks:
            # 新架构：按 generation_tasks 生成
            for task in actionable_tasks:
                task_type = task.get("task_type")
                try:
                    if task_type == "create":
                        cases = _generate_create_case(
                            ctx, task, prd_content, ui_description, ui_specs, has_ui,
                            history_cases=history_cases,
                        )
                    elif task_type == "modify":
                        cases = _generate_modify_case(
                            ctx, task, prd_content, ui_description, ui_specs, has_ui,
                        )
                    elif task_type == "locator_fix":
                        cases = _generate_locator_fix(
                            ctx, task, prd_content, ui_description, ui_specs, has_ui,
                        )
                    else:
                        continue

                    if cases:
                        # 去重 + 类型覆盖检查
                        enriched = _enrich_case_data_with_task(cases, task, has_ui)
                        enriched = _dedup_cases_by_title(enriched)
                        coverage_gap = _check_type_coverage(enriched)
                        if coverage_gap:
                            tp_info = {
                                "id": task.get("task_id"),
                                "module": task.get("module", ""),
                                "function": task.get("function", ""),
                                "point": task.get("candidate_description", ""),
                                "priority": task.get("candidate_priority", 3),
                            }
                            supplemental = _generate_supplemental(
                                ctx=ctx, tp=tp_info, prd_content=prd_content,
                                ui_description=ui_description, ui_specs=ui_specs,
                                missing_types=coverage_gap,
                                existing_titles=[c.get("title", "") for c in enriched],
                                has_ui=has_ui,
                            )
                            if supplemental:
                                supplemental = _enrich_case_data_with_task(
                                    supplemental, task, has_ui,
                                )
                                supplemental = _dedup_cases_by_title(
                                    enriched + supplemental,
                                )[len(enriched):]
                                enriched.extend(supplemental)
                                coverage_gap = _check_type_coverage(enriched)

                        generated_cases.append({
                            "task": task,
                            "status": "success",
                            "case_data": enriched,
                            "coverage_gap": coverage_gap,
                        })
                    else:
                        failed_count += 1
                        generated_cases.append({
                            "task": task,
                            "status": "failed",
                            "error": "生成结果为空",
                        })
                except Exception as e:
                    failed_count += 1
                    logger.error(
                        "用例生成失败 task_id={}: {}",
                        task.get("task_id"), e,
                    )
                    generated_cases.append({
                        "task": task,
                        "status": "failed",
                        "error": str(e),
                    })
        else:
            # 回退到原有 aligned_testpoints 模式（保持向后兼容）
            if not aligned and not signals:
                return StepResult(
                    success=False,
                    error="缺少 generation_tasks、aligned_testpoints 和 raw_signals 产物",
                )

            if aligned:
                aligned_tps = aligned.get("aligned_testpoints", [])
            else:
                raw_tps = signals.get("test_points", []) if signals else []
                aligned_tps = [
                    {
                        "test_point": tp,
                        "ui_match": None,
                        "alignment_status": "no_ui_input",
                    }
                    for tp in raw_tps if tp is not None
                ]

            for entry in aligned_tps:
                tp = entry.get("test_point", {})
                try:
                    prompt = _build_full_prompt(
                        tp=tp,
                        prd_content=prd_content,
                        ui_description=ui_description,
                        ui_specs=ui_specs,
                    )

                    parsed = None
                    degraded = False
                    last_error = ""

                    for attempt in range(2):
                        response = ctx.get_ai_client().complete(
                            prompt=prompt,
                            temperature=0.3,
                            max_tokens=5000,
                            metadata={
                                "step_name": self.name,
                                "test_point_id": tp.get("id"),
                                "iteration_id": ctx.iteration_id,
                                "attempt": attempt + 1,
                            },
                        )
                        degraded = degraded or response.degraded

                        if not response.content:
                            last_error = "AI 返回空内容"
                            if attempt == 0:
                                logger.warning(
                                    "AI 返回空内容，tp_id={}，重试中",
                                    tp.get("id"),
                                )
                                continue
                            break

                        parsed = _parse_case_response(response.content)
                        if parsed:
                            break

                        last_error = "AI 响应解析失败"
                        if attempt == 0:
                            logger.warning(
                                "AI 响应解析失败，tp_id={}，重试中",
                                tp.get("id"),
                            )

                    if not parsed:
                        failed_count += 1
                        generated_cases.append({
                            "test_point": tp,
                            "status": "failed",
                            "error": (
                                f"{last_error}（重试后仍失败）"
                                if last_error else "生成失败"
                            ),
                        })
                        continue

                    case_data = _enrich_case_data(parsed, tp, has_ui)
                    case_data = _dedup_cases_by_title(case_data)
                    coverage_gap = _check_type_coverage(case_data)
                    if coverage_gap:
                        logger.info(
                            "测试点 tp_id={} 缺少覆盖类型: {}，追加生成中",
                            tp.get("id"), coverage_gap,
                        )
                        supplemental = _generate_supplemental(
                            ctx=ctx, tp=tp, prd_content=prd_content,
                            ui_description=ui_description, ui_specs=ui_specs,
                            missing_types=coverage_gap,
                            existing_titles=[c.get("title", "") for c in case_data],
                            has_ui=has_ui,
                        )
                        if supplemental:
                            supplemental = _enrich_case_data(supplemental, tp, has_ui)
                            supplemental = _dedup_cases_by_title(
                                case_data + supplemental,
                            )[len(case_data):]
                            case_data.extend(supplemental)
                            coverage_gap = _check_type_coverage(case_data)

                    generated_cases.append({
                        "test_point": tp,
                        "status": "success",
                        "case_data": case_data,
                        "degraded": degraded,
                        "coverage_gap": coverage_gap,
                    })
                except Exception as e:
                    failed_count += 1
                    logger.error(
                        "用例生成失败 tp_id={}: {}",
                        tp.get("id") if tp else "N/A", e,
                    )
                    generated_cases.append({
                        "test_point": tp,
                        "status": "failed",
                        "error": str(e),
                    })

        # 跨测试点/跨任务全局去重
        generated_cases = _dedup_cases_global(generated_cases)

        success_count = len([c for c in generated_cases if c["status"] == "success"])
        total = len(generated_cases)
        confidence = success_count / total if total > 0 else 0.0

        project_id = None
        if aligned:
            project_id = aligned.get("project_id")
        elif signals:
            project_id = signals.get("project_id")

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": project_id,
            "generated_cases": generated_cases,
            "total": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "has_ui": has_ui,
            "deprecation_suggestions": deprecation_suggestions,
        }

        return StepResult(
            success=success_count > 0,
            artifact_payload=payload,
            artifact_kind="generated_cases",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "success_rate": f"{success_count}/{total}",
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return "generated_cases" in payload and "total" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return StepResult(
            success=False,
            error=f"用例生成降级: {error}",
            artifact_payload={
                "iteration_id": ctx.iteration_id,
                "generated_cases": [],
                "total": 0,
                "success_count": 0,
                "failed_count": 0,
                "has_ui": False,
            },
            artifact_kind="generated_cases",
            artifact_confidence=0.0,
            degraded=True,
        )


def _build_full_prompt(
    tp: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    task_type: Optional[str] = None,
    task_context: Optional[Dict[str, Any]] = None,
    history_cases: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """复用 PromptBuilder.build_linear_prompt 构建完整版 Prompt。

    与旧版 TestCaseGenerationService 使用同一套 Prompt 模板，
    包含7组正反用例对比和14条生成规则，确保 Pipeline 路径生成质量一致。

    PRD 截断策略：按测试点关键词检索相关段落，而非硬截断前N字符。
    UI 规格策略：按测试点模块/功能筛选关联页面，而非取全部。

    Args:
        tp: 测试点字典。
        prd_content: PRD 文档内容。
        ui_description: UI 描述文本。
        ui_specs: UI 规格列表。
        task_type: 任务类型（create/modify/locator_fix）。
        task_context: 任务上下文（如 original_case、modification_hint 等）。
        history_cases: 项目已有用例摘要列表，用于 create 模式下去重提示。
    """
    from app.services.case_generation_prompt_builder import PromptBuilder

    # P2-1: PRD 按测试点关键词检索相关段落
    filtered_prd = _filter_prd_by_testpoint(prd_content, tp)

    # P2-2: UI 规格按测试点模块/功能筛选关联页面
    filtered_ui_specs = _filter_ui_specs_by_testpoint(ui_specs, tp)

    # 构建额外上下文，供 PromptBuilder 追加历史用例/变更指引段落
    extra_context: Dict[str, Any] = {}
    if task_type:
        extra_context["task_type"] = task_type
    if task_context:
        extra_context["task_context"] = task_context
    if history_cases and task_type == "create":
        extra_context["history_cases"] = history_cases[:20]  # 最多20条，控制Prompt长度

    return PromptBuilder.build_linear_prompt(
        requirement_content=filtered_prd,
        ui_description=ui_description,
        module=tp.get("module", "未知模块"),
        function=tp.get("function", "未知功能"),
        point=tp.get("point", ""),
        priority=tp.get("priority", 3),
        ui_specs=filtered_ui_specs,
        extra_context=extra_context,
    )


# PRD 相关段落检索的最大字符数
_PRD_MAX_CHARS = 6000


def _filter_prd_by_testpoint(prd_content: str, tp: Dict[str, Any]) -> str:
    """按测试点关键词从 PRD 中检索相关段落。

    策略:
        1. 提取测试点的 module + function + point 作为关键词
        2. 将 PRD 按段落拆分
        3. 优先选择包含关键词的段落
        4. 不够时补充相邻段落，直到达到 _PRD_MAX_CHARS
        5. 如果没有匹配段落，返回前 _PRD_MAX_CHARS 字符（兜底）
    """
    if not prd_content or not prd_content.strip():
        return prd_content

    # PRD 不太长时直接返回
    if len(prd_content) <= _PRD_MAX_CHARS:
        return prd_content

    # 提取关键词
    keywords = set()
    for field in ["module", "function", "point"]:
        val = tp.get(field, "")
        if val:
            # 拆分中文词组（简单按常见分隔符拆分）
            for part in re.split(r'[/、，,\s]+', val):
                if len(part) >= 2:
                    keywords.add(part.lower())

    if not keywords:
        return prd_content[:_PRD_MAX_CHARS]

    # 按段落拆分 PRD
    paragraphs = re.split(r'\n{2,}', prd_content)

    # 计算每个段落的相关度（匹配关键词数）
    scored_paragraphs = []
    for i, para in enumerate(paragraphs):
        para_lower = para.lower()
        match_count = sum(1 for kw in keywords if kw in para_lower)
        scored_paragraphs.append((match_count, i, para))

    # 按相关度排序，相关度相同则保持原文顺序
    scored_paragraphs.sort(key=lambda x: (-x[0], x[1]))

    # 选取段落直到达到最大字符数
    selected = []  # (idx, para_or_truncated)
    total_chars = 0

    for match_count, idx, para in scored_paragraphs:
        if total_chars + len(para) > _PRD_MAX_CHARS:
            # 尝试截断最后一段
            remaining = _PRD_MAX_CHARS - total_chars
            if remaining > 100:
                selected.append((idx, para[:remaining]))
                total_chars = _PRD_MAX_CHARS
            break

        selected.append((idx, para))
        total_chars += len(para)

        if total_chars >= _PRD_MAX_CHARS:
            break

    if not selected:
        return prd_content[:_PRD_MAX_CHARS]

    # 按原文顺序重排（保留截断版本）
    selected.sort(key=lambda x: x[0])
    ordered = [text for _, text in selected]

    return "\n\n".join(ordered)


def _filter_ui_specs_by_testpoint(
    ui_specs: List[Dict[str, Any]], tp: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """按测试点模块/功能筛选关联的 UI 页面规格。

    策略:
        1. 提取测试点的 module + function 作为关键词
        2. 优先选择 screen_name 或 ui_spec 中包含关键词的页面
        3. 不够时补充剩余页面，最多 10 个
        4. 如果没有匹配，返回前 10 个（兜底）
    """
    if not ui_specs or len(ui_specs) <= 10:
        return ui_specs

    keywords = set()
    for field in ["module", "function"]:
        val = tp.get(field, "")
        if val:
            for part in re.split(r'[/、，,\s]+', val):
                if len(part) >= 2:
                    keywords.add(part.lower())

    if not keywords:
        return ui_specs[:10]

    # 按相关度排序
    matched = []
    unmatched = []

    for spec in ui_specs:
        screen_name = spec.get("screen_name", "").lower()
        ui_spec = spec.get("ui_spec", {})
        # 搜索 screen_name 和 ui_spec 的 purpose/regions 文本
        spec_text = screen_name
        if isinstance(ui_spec, dict):
            spec_text += " " + (ui_spec.get("purpose", "") or "").lower()
            # 搜索 region 名称
            regions = ui_spec.get("regions", {})
            if isinstance(regions, dict):
                spec_text += " " + " ".join(k.lower() for k in regions.keys() if k)

        if any(kw in spec_text for kw in keywords):
            matched.append(spec)
        else:
            unmatched.append(spec)

    # 优先匹配页面，不够时补充不匹配的，最多 10 个
    result = matched[:10]
    if len(result) < 10:
        result.extend(unmatched[:10 - len(result)])

    return result


def _parse_case_response(content: str) -> Optional[List[Dict[str, Any]]]:
    from app.utils.ai_client_parser import fix_common_json_issues, clean_json_string

    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # 优先提取包装字段
            cases = result.get("cases") or result.get("test_cases") or []
            if isinstance(cases, list):
                return cases
            # 单条用例 dict（含 title/steps 等字段），包装为列表
            if result.get("title") or result.get("steps"):
                return [result]
    except json.JSONDecodeError:
        pass

    fixed = fix_common_json_issues(content)
    if fixed:
        try:
            result = json.loads(fixed)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                cases = result.get("cases") or result.get("test_cases") or []
                if isinstance(cases, list):
                    return cases
                if result.get("title") or result.get("steps"):
                    return [result]
        except json.JSONDecodeError:
            pass

    cleaned = clean_json_string(content)
    if cleaned:
        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                if result.get("title") or result.get("steps"):
                    return [result]
        except json.JSONDecodeError:
            pass

    json_match = re.search(r'\[[\s\S]*\]', content)
    if json_match:
        array_content = json_match.group()
        fixed_array = clean_json_string(array_content)
        if fixed_array:
            try:
                return json.loads(fixed_array)
            except json.JSONDecodeError:
                pass

    return None


def _validate_test_data(case: Dict[str, Any]) -> None:
    """R6: 校验用例的 test_data 字段结构合法性。

    校验规则：
        1. test_data 必须为 dict 类型，否则重置为 {}
        2. 非空时至少包含 normal/boundary/abnormal 中一个键
        3. 每个键的值必须为 dict 类型，否则重置为 {}
    """
    if "test_data" not in case:
        case["test_data"] = {}
        return

    td = case["test_data"]
    # 校验 test_data 是否为 dict 类型
    if not isinstance(td, dict):
        logger.warning(
            "test_data 类型非法 ({}), 使用空对象兜底, title={}",
            type(td).__name__, case.get("title", "")[:30],
        )
        case["test_data"] = {}
        return

    # 校验是否至少包含 normal/boundary/abnormal 中一个键
    valid_keys = {"normal", "boundary", "abnormal"}
    has_valid_key = any(k in valid_keys for k in td.keys())
    if not has_valid_key and len(td) > 0:
        logger.warning(
            "test_data 缺少 normal/boundary/abnormal 键, 保留原值, title={}",
            case.get("title", "")[:30],
        )

    # 校验每个键的值是否为 dict
    for key in list(td.keys()):
        if not isinstance(td[key], dict):
            logger.warning(
                "test_data['{}'] 非dict类型，已重置, title={}",
                key, case.get("title", "")[:30],
            )
            td[key] = {}


def _enrich_case_data(
    parsed: List[Dict[str, Any]], tp: Dict[str, Any], has_ui: bool
) -> List[Dict[str, Any]]:
    tp_module = tp.get("module", "")
    tp_point = tp.get("point", "")
    tp_id = tp.get("id")

    for case in parsed:
        if not case.get("module"):
            case["module"] = tp_module
        if not case.get("title"):
            case["title"] = f"{tp_point} - 测试用例"
        case["test_point_id"] = tp_id
        case["lifecycle_status"] = "draft"
        # P6: 仅在 AI 未输出 case_type 时 fallback，不覆盖 AI 判断
        if not case.get("case_type"):
            case["case_type"] = "API" if not has_ui else "ui_automation"
        # R6: test_data 结构校验 + 兜底
        _validate_test_data(case)

    return parsed


# P5: 标题去重相似度阈值
_TITLE_SIMILARITY_THRESHOLD = 0.6


def _jaccard_similarity(a: str, b: str) -> float:
    """计算两个字符串的 Jaccard 相似度（bigram 词粒度）。

    使用 2 字 bigram 而非字符级，避免"验证拍照裁剪提交完整流程"和
    "验证拍照裁剪提交异常流程"被误判为重复（字符级相似度0.71，
    但实际是不同类型用例；bigram 级为0.57，正确不去重）。
    """
    if not a or not b:
        return 0.0

    def _to_ngrams(text: str, n: int = 2) -> set:
        return {text[i:i+n] for i in range(len(text) - n + 1)} if len(text) >= n else {text}

    set_a = _to_ngrams(a)
    set_b = _to_ngrams(b)
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _dedup_cases_by_title(cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """同测试点内标题相似度去重。

    策略：
        Jaccard 相似度 > 0.6 的用例视为重复，保留先出现的（通常质量更高）。
    """
    if len(cases) <= 1:
        return cases

    kept: List[Dict[str, Any]] = []
    for case in cases:
        title = case.get("title", "")
        is_dup = False
        for existing in kept:
            existing_title = existing.get("title", "")
            if _jaccard_similarity(title, existing_title) > _TITLE_SIMILARITY_THRESHOLD:
                is_dup = True
                logger.info(
                    "去重：标题相似度过高，丢弃 \"{}\"（与 \"{}\" 相似）",
                    title[:30], existing_title[:30],
                )
                break
        if not is_dup:
            kept.append(case)

    return kept


def _dedup_cases_global(
    generated_cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """跨测试点全局标题去重。

    当所有测试点（或所有任务）的用例生成完毕后调用。
    对每条用例的标题与全局已有标题做 bigram Jaccard 去重。

    策略：
        遍历所有 generated_cases 中的 case_data 条目。
        构建全局已保留标题集合。
        Jaccard 相似度 > 0.6 的用例视为重复，保留先出现的。
        去重日志中标注被丢弃用例的来源（test_point 或 task_id）。
    """
    kept: List[Dict[str, Any]] = []
    kept_titles: List[str] = []

    for entry in generated_cases:
        if entry.get("status") != "success":
            kept.append(entry)
            continue

        case_data = entry.get("case_data", [])
        filtered_cases: List[Dict[str, Any]] = []

        for case in case_data:
            title = case.get("title", "")
            is_dup = False
            for existing_title in kept_titles:
                if _jaccard_similarity(title, existing_title) > _TITLE_SIMILARITY_THRESHOLD:
                    is_dup = True
                    # 获取来源标识
                    source = entry.get("test_point", {}).get("id") or \
                             entry.get("task", {}).get("task_id", "unknown")
                    logger.info(
                        "全局去重：丢弃 \"{}\"（来源: {}，与 \"{}\" 相似）",
                        title[:30], source, existing_title[:30],
                    )
                    break

            if not is_dup:
                filtered_cases.append(case)
                kept_titles.append(title)

        entry_copy = dict(entry)
        entry_copy["case_data"] = filtered_cases
        kept.append(entry_copy)

    return kept


# ── R3: 测试类型覆盖度验证 + 追加生成 ──

# 测试类型关键词映射
_TYPE_KEYWORDS = {
    "positive": ["正向", "正常", "主流程", "happy", "成功提交", "完整流程", "正确输入", "常规"],
    "boundary": ["边界", "上限", "下限", "最大", "最小", "临界", "超长", "超限", "空值", "极值",
                 "最多", "最少", "最长", "最短", "极限", "范围", "阈值"],
    "negative": ["异常", "错误", "失败", "缺失", "拒绝", "无权限", "断网", "超时", "容错", "拦截",
                 "非法", "无效", "不存在", "未授权", "冲突", "重复"],
}


def _classify_case_type(case: Dict[str, Any]) -> Optional[str]:
    """根据用例标题和内容推断测试类型（positive/boundary/negative）。"""
    title = (case.get("title") or "").lower()

    # 步骤1: 优先检查 case_category / case_type 字段的显式值
    cat = (case.get("case_category") or case.get("case_type") or "").lower()
    if "boundary" in cat or "边界" in cat:
        return "boundary"
    if "negative" in cat or "异常" in cat or "abnormal" in cat:
        return "negative"
    if "positive" in cat or "正向" in cat or "normal" in cat or "happy" in cat:
        return "positive"

    # 步骤2: fallback 标题关键词匹配
    text = title
    for type_name, keywords in _TYPE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return type_name

    # 步骤3: 增强 — 步骤内容级匹配
    steps = case.get("steps", [])
    if isinstance(steps, list):
        steps_text = ""
        for step in steps:
            if isinstance(step, dict):
                steps_text += (step.get("action", "") + " " + step.get("expected_result", "")).lower()
        if steps_text:
            for type_name, keywords in _TYPE_KEYWORDS.items():
                if any(kw in steps_text for kw in keywords):
                    return type_name

    # 步骤4: 默认视为正向
    return "positive"


def _check_type_coverage(cases: List[Dict[str, Any]]) -> List[str]:
    """检查用例集是否覆盖正向/边界/异常三种类型，返回缺失类型列表。"""
    covered = set()
    for case in cases:
        case_type = _classify_case_type(case)
        if case_type:
            covered.add(case_type)

    required = {"positive", "boundary", "negative"}
    return sorted(required - covered)


# ── 补充 Prompt 的正反对比示例数据（精简版，与 case_prompt.py 对齐）──

# 每种测试类型对应的对比示例：(组标题, [行列表])
_SUPPLEMENT_EXAMPLES: Dict[str, tuple] = {
    "positive": ("对比1-主流程", [
        "❌差劲：测试拍照提交作文功能 | 前置：账号已登录，APP运行正常 | 预期：页面正常→提交成功",
        "问题：描述笼统；前置缺网络/权限；预期模糊无判定标准",
        "✅优秀：联网+已授权验证拍照裁剪提交完整流程 | 前置：已登录、相机权限允许、设备网络正常 "
        "| 步骤：1.进入模块 2.拍摄裁剪 3.点击提交 "
        "| 预期：1.页面加载正常 2.相机唤起裁剪完成 3.提交成功跳转报告页",
        "优点：前置完整可复现；步骤原子化；预期与步骤一一对应",
    ]),
    "boundary": ("对比2-边界值", [
        "❌差劲：测试拍照数量限制 | 步骤：连续拍摄多张照片 | 预期：达到上限后禁止拍照",
        "问题：未量化上限；步骤模糊；预期缺弹窗文案校验",
        "✅优秀：验证最多3页拍摄限制 | 步骤：1.进拍摄页 2.依次拍3张 3.尝试拍第4张 "
        "| 预期：1.预览正常 2.3张保存成功 3.弹出上限提示无法触发第四次拍摄",
        "优点：精准覆盖边界值；操作量化复现性强；预期多重校验",
    ]),
    "negative": ("对比3-异常场景", [
        "❌差劲：无相机权限测试拍照 | 前置：相机权限禁止 | 预期：无法打开相机弹出提示",
        "问题：未区分临时/永久拒绝；预期过于简单未校验弹窗按钮",
        "✅优秀：相机权限永久拒绝 | 前置：已登录、系统关闭相机权限 "
        "| 步骤：1.点击拍照入口 "
        "| 预期：1.无法唤起相机弹出权限引导弹窗，弹窗含提示文案、取消、前往设置按钮",
        "优点：精准锁定异常场景；校验弹窗文案+按钮+跳转逻辑",
    ]),
}


def _append_supplement_examples(parts: List[str], missing_types: List[str]) -> None:
    """向 parts 追加补充 Prompt 的正反用例对比示例。

    按缺失类型选取对应对比组，最多2组。优先级：negative > boundary > positive。
    """
    priority_order = ["negative", "boundary", "positive"]
    selected = [t for t in priority_order if t in missing_types][:2]

    if not selected:
        return

    parts.append("## 正反用例对比（学习优秀写法，避免差劲写法）")
    parts.append("")
    for miss_type in selected:
        entry = _SUPPLEMENT_EXAMPLES.get(miss_type)
        if entry is None:
            continue
        title, lines = entry
        parts.append(f"【{title}】")
        parts.extend(lines)
        parts.append("")


def _generate_supplemental(
    ctx: PipelineContext,
    tp: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    missing_types: List[str],
    existing_titles: List[str],
    has_ui: bool,
) -> Optional[List[Dict[str, Any]]]:
    """R3: 对缺失测试类型追加生成用例。

    构建补充 Prompt，明确指定缺失类型，并排除已有标题避免重复。
    Prompt 质量对齐 case_prompt.py 的主 Prompt：
    含针对性规则、正反对比示例、完整 JSON 输出模板。
    """
    type_labels = {
        "positive": "正向用例（Happy Path）",
        "boundary": "边界值用例",
        "negative": "异常用例",
    }
    missing_labels = [type_labels.get(t, t) for t in missing_types]
    existing_titles_text = "、".join(f"「{t}」" for t in existing_titles[:10])

    parts: List[str] = []

    # ── 1. 角色声明 ──
    parts.append("你是一名资深测试工程师。")
    parts.append("")

    # ── 2. 任务说明 ──
    parts.append("## 任务")
    parts.append("以下测试点已生成部分用例，但缺少以下测试类型：")
    for label in missing_labels:
        parts.append(f"- {label}")
    parts.append("请为该测试点补充生成缺失类型的测试用例，每种缺失类型至少1条。")
    parts.append("")
    parts.append(f"已有用例标题（禁止重复）：{existing_titles_text or '无'}")
    parts.append("")

    # ── 3. 测试点信息 ──
    parts.append("## 测试点信息")
    parts.append(json.dumps(tp, ensure_ascii=False))
    parts.append("")

    # ── 4. 生成规则（精简版，与主 Prompt 规则对齐）─-─
    parts.append("## 生成规则")
    if "positive" in missing_types:
        parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
        parts.append("2. 分支流程需标注触发条件，作为独立场景生成用例")
    if "negative" in missing_types:
        parts.append("3. 异常流程需标注异常场景和预期错误提示")
    if "boundary" in missing_types:
        parts.append("4. 边界值用例需量化上下限，预期含界面+数据+弹窗多重校验")
    parts.append(
        "5. 标题格式：「场景/条件」+「操作」+「验证重点」，15-40字，"
        "禁用\"功能验证\"等模糊词"
    )
    parts.append(
        "6. 前置条件必须含\"账号已登录\"和网络环境，"
        "禁止依赖特定业务数据，禁止含操作步骤或页面导航状态"
    )
    parts.append(
        "7. 步骤原子化可执行，每步必须有 action 和 expected_result，禁止口语化"
    )
    parts.append(
        "8. 预期结果可量化判定，禁止\"页面正常\"\"功能正常\"等模糊描述"
    )
    parts.append("")

    # ── 5. 正反用例对比（按缺失类型选取，最多2组）─-─
    _append_supplement_examples(parts, missing_types)

    # ── 6. 输出格式 ──
    parts.append("## 输出格式要求：")
    parts.append("严格按以下JSON数组格式输出，不要添加任何其他文字：")
    parts.append("")
    parts.append("[")
    parts.append("  {")
    parts.append('    "title": "用例标题（15-40字，要素明确）",')
    parts.append('    "module": "所属模块",')
    parts.append('    "precondition": "前置条件（含登录状态、网络环境）",')
    parts.append('    "steps": [')
    parts.append('      {"action": "具体操作步骤", "expected_result": "每步预期结果"}')
    parts.append('    ],')
    parts.append('    "expected_result": "整体预期结果",')
    parts.append('    "case_type": "用例类型（功能测试/边界测试/异常测试）",')
    parts.append('    "priority": 数字1-5,')
    parts.append('    "case_category": "正向/边界/异常",')
    parts.append('    "test_data": {}')
    parts.append('  }')
    parts.append(']')

    supplement_prompt = "\n".join(parts)

    try:
        response = ctx.get_ai_client().complete(
            prompt=supplement_prompt,
            temperature=0.4,
            max_tokens=3000,
            metadata={
                "step_name": "case_generation_supplement",
                "test_point_id": tp.get("id"),
                "iteration_id": ctx.iteration_id,
                "supplement_for_types": ",".join(missing_types),
            },
        )
        if not response.content:
            return None
        return _parse_case_response(response.content)
    except Exception as e:
        logger.warning("追加生成失败 tp_id={}: {}", tp.get("id"), e)
        return None


# ── 新架构：按 generation_tasks 分发的生成函数 ──


def _generate_create_case(
    ctx: PipelineContext,
    task: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    has_ui: bool,
    history_cases: Optional[List[Dict[str, Any]]] = None,
) -> Optional[List[Dict[str, Any]]]:
    """为 create 任务生成新用例（含查漏补缺上下文）。"""
    tp = {
        "module": task.get("candidate_module", task.get("module", "")),
        "function": task.get("candidate_description", ""),
        "point": task.get("candidate_description", ""),
        "priority": task.get("candidate_priority", 3),
        "id": task.get("task_id"),
    }
    prompt = _build_full_prompt(
        tp=tp,
        prd_content=prd_content,
        ui_description=ui_description,
        ui_specs=ui_specs,
        task_type="create",
        task_context={
            "candidate_description": task.get("candidate_description", ""),
            "candidate_reason": task.get("candidate_reason", ""),
        },
        history_cases=history_cases,
    )
    parsed = None
    for attempt in range(2):
        response = ctx.get_ai_client().complete(
            prompt=prompt,
            temperature=0.3,
            max_tokens=5000,
            metadata={
                "step_name": "case_generation_create",
                "task_id": task.get("task_id"),
                "attempt": attempt + 1,
            },
        )
        if not response.content:
            if attempt == 0:
                logger.warning("AI 返回空内容，task_id={}，重试中", task.get("task_id"))
                continue
            break
        parsed = _parse_case_response(response.content)
        if parsed:
            break
        if attempt == 0:
            logger.warning("AI 响应解析失败，task_id={}，重试中", task.get("task_id"))

    return parsed


def _generate_modify_case(
    ctx: PipelineContext,
    task: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    has_ui: bool,
) -> Optional[List[Dict[str, Any]]]:
    """为 modify 任务生成修改版用例（基于原有用例内容）。"""
    original = task.get("original_case", {})
    tp = {
        "module": original.get("module", task.get("module", "")),
        "function": task.get("modification_hint", ""),
        "point": original.get("title", task.get("candidate_description", "")),
        "priority": task.get("candidate_priority", original.get("priority", 3)),
        "id": task.get("task_id"),
    }
    prompt = _build_full_prompt(
        tp=tp,
        prd_content=prd_content,
        ui_description=ui_description,
        ui_specs=ui_specs,
        task_type="modify",
        task_context={
            "original_case": original,
            "modification_hint": task.get("modification_hint", ""),
            "need_locator_fix": task.get("need_locator_fix", False),
        },
    )
    parsed = None
    for attempt in range(2):
        response = ctx.get_ai_client().complete(
            prompt=prompt,
            temperature=0.3,
            max_tokens=5000,
            metadata={
                "step_name": "case_generation_modify",
                "task_id": task.get("task_id"),
                "attempt": attempt + 1,
            },
        )
        if not response.content:
            if attempt == 0:
                logger.warning("AI 返回空内容，task_id={}，重试中", task.get("task_id"))
                continue
            break
        parsed = _parse_case_response(response.content)
        if parsed:
            break
        if attempt == 0:
            logger.warning("AI 响应解析失败，task_id={}，重试中", task.get("task_id"))

    return parsed


def _generate_locator_fix(
    ctx: PipelineContext,
    task: Dict[str, Any],
    prd_content: str,
    ui_description: str,
    ui_specs: List[Dict[str, Any]],
    has_ui: bool,
) -> Optional[List[Dict[str, Any]]]:
    """为 locator_fix 任务修复定位器信息（基于新UI元素描述）。"""
    original = task.get("original_case", {})
    tp = {
        "module": original.get("module", task.get("module", "")),
        "function": "定位器修复",
        "point": original.get("title", ""),
        "priority": original.get("priority", 3),
        "id": task.get("task_id"),
    }
    prompt = _build_full_prompt(
        tp=tp,
        prd_content=prd_content,
        ui_description=ui_description,
        ui_specs=ui_specs,
        task_type="locator_fix",
        task_context={
            "original_case": original,
            "locator_hint": task.get(
                "locator_hint",
                "UI元素定位器已变更，请使用新UI描述中的元素名称",
            ),
        },
    )
    parsed = None
    for attempt in range(2):
        response = ctx.get_ai_client().complete(
            prompt=prompt,
            temperature=0.2,
            max_tokens=4000,
            metadata={
                "step_name": "case_generation_locator",
                "task_id": task.get("task_id"),
                "attempt": attempt + 1,
            },
        )
        if not response.content:
            if attempt == 0:
                logger.warning("AI 返回空内容，task_id={}，重试中", task.get("task_id"))
                continue
            break
        parsed = _parse_case_response(response.content)
        if parsed:
            break
        if attempt == 0:
            logger.warning("AI 响应解析失败，task_id={}，重试中", task.get("task_id"))

    return parsed


def _enrich_case_data_with_task(
    parsed: List[Dict[str, Any]],
    task: Dict[str, Any],
    has_ui: bool,
) -> List[Dict[str, Any]]:
    """基于 task 信息充实用例数据（含 change_type + parent_case_id）。"""
    tp_module = task.get("candidate_module", task.get("module", ""))
    tp_point = (
        task.get("candidate_description", "")
        or task.get("modification_hint", "")
    )
    task_id = task.get("task_id")
    task_type = task.get("task_type", "")
    case_id = task.get("case_id")

    for case in parsed:
        if not case.get("module"):
            case["module"] = tp_module
        if not case.get("title"):
            case["title"] = f"{tp_point} - 测试用例"
        case["task_id"] = task_id
        case["lifecycle_status"] = "draft"
        if not case.get("case_type"):
            case["case_type"] = "API" if not has_ui else "ui_automation"
        # R6: test_data 结构校验 + 兜底
        _validate_test_data(case)
        # 设置变更类型
        if task_type == "modify":
            case["ai_change_type"] = "modified"
            case["parent_case_id"] = case_id
        elif task_type == "locator_fix":
            case["ai_change_type"] = "locator_fix"
            case["parent_case_id"] = case_id
        elif task_type == "create":
            case["ai_change_type"] = "added"
            # parent_case_id 不设置（保持 None）

    return parsed
