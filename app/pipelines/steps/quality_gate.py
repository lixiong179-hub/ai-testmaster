"""S12 QualityGate — 先验质量门 Step

对生成的用例做先验质量评估，计算质量分和等级。
双维度加权融合：score = 0.4 * signal_score + 0.6 * content_score
- signal_score: 信号完整性（PRD/UI/测试点/历史/确认）
- content_score: 用例内容质量（title/steps/expected_result/precondition）
"""
import hashlib
import re
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


class QualityGate(PipelineStep):
    """先验质量门 Step — 评估生成用例的先验质量分。"""

    name: ClassVar[str] = "quality_gate"
    version: ClassVar[str] = "2.0"
    requires: ClassVar[List[str]] = ["generated_cases"]
    produces: ClassVar[List[str]] = ["quality_scores"]

    def should_run(self, ctx: PipelineContext) -> bool:
        cases = ctx.get_artifact("generated_cases")
        if not cases:
            return False
        return cases.get("success_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        cases = ctx.get_artifact("generated_cases")
        if not cases:
            return ""
        case_titles = []
        for entry in cases.get("generated_cases", []):
            if entry.get("status") == "success":
                for cd in entry.get("case_data", []):
                    case_titles.append(cd.get("title", ""))
        raw = f"{self.name}:{self.version}:titles={sorted(case_titles)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        cases_artifact = ctx.get_artifact("generated_cases")
        if not cases_artifact:
            return StepResult(success=False, error="缺少 generated_cases 产物")

        signals = ctx.get_artifact("raw_signals") or {}
        inferred = ctx.get_artifact("inferred_business_summary") or {}
        aligned = ctx.get_artifact("aligned_testpoints") or {}

        analyzer = None
        try:
            from app.services.case_quality import CaseQualityAnalyzer
            if ctx.db is not None:
                analyzer = CaseQualityAnalyzer(ctx.db)
        except Exception as e:
            logger.warning("CaseQualityAnalyzer 初始化失败，降级到自研评分: {}", e)

        generated_cases = cases_artifact.get("generated_cases", [])
        scores = []
        total_score = 0.0
        graded_count = 0
        _score_idx = 0  # Fix1: scores 唯一索引，替代 title 匹配去重

        # R4: 按测试点聚合，计算跨用例覆盖度加减分
        tp_coverage_adj: Dict[Any, float] = {}  # tp_id -> 覆盖度加减分
        for entry in generated_cases:
            if entry.get("status") != "success":
                continue
            # 兼容新架构(task)和回退模式(test_point)
            tp = entry.get("test_point") or _build_tp_from_task(entry.get("task"))
            tp_id = tp.get("id") if tp else None
            coverage_gap = entry.get("coverage_gap", [])
            if coverage_gap:
                # 缺失每种类型 -8分
                tp_coverage_adj[tp_id] = -8.0 * len(coverage_gap)
            else:
                # 全覆盖 +5分
                tp_coverage_adj[tp_id] = 5.0

        for entry in generated_cases:
            if entry.get("status") != "success":
                continue

            case_data_list = entry.get("case_data", [])
            # 兼容新架构(task)和回退模式(test_point)
            tp = entry.get("test_point") or _build_tp_from_task(entry.get("task"))
            tp_id = tp.get("id") if tp else None
            coverage_adj = tp_coverage_adj.get(tp_id, 0.0)

            for case_data in case_data_list:
                if analyzer is not None:
                    try:
                        score, grade, breakdown = _compute_analyzer_score(analyzer, case_data)
                    except Exception as e:
                        logger.warning("CaseQualityAnalyzer 分析失败，降级到自研评分: {}", e)
                        score, grade, breakdown = _compute_prior_score(
                            case_data, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db,
                        )
                else:
                    score, grade, breakdown = _compute_prior_score(
                        case_data, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db,
                    )

                # R4: 应用覆盖度加减分（均摊到同测试点每条用例）
                if coverage_adj != 0.0 and case_data_list:
                    per_case_adj = round(coverage_adj / len(case_data_list), 2)
                    score = max(0.0, min(100.0, round(score + per_case_adj, 2)))
                    breakdown["coverage_adjustment"] = per_case_adj
                    grade = _score_to_grade(score)

                scores.append({
                    "_score_idx": _score_idx,  # Fix1: 唯一索引
                    "test_point_id": tp_id,
                    "case_title": case_data.get("title", ""),
                    "score": score,
                    "grade": grade,
                    "breakdown": breakdown,
                    "lifecycle_status": case_data.get("lifecycle_status", "draft"),
                })
                total_score += score
                graded_count += 1

                # 直接写入 case_data，避免 Persist 按 tp_id 覆盖问题
                case_data["prior_quality_score"] = score
                case_data["prior_quality_grade"] = grade
                # Fix1: 记录 D 级用例的 score_idx，供 R5 精确移除
                if grade == "D":
                    case_data["lifecycle_status"] = "pending_review"
                    case_data["_d_score_idx"] = _score_idx

                _score_idx += 1

        # R5: D级用例自动重生成闭环（最多1次）
        d_grade_entries = _collect_d_grade_cases(generated_cases)
        if d_grade_entries:
            logger.info("R5: 发现 {} 条D级用例，尝试重生成", len(d_grade_entries))
            _regenerate_d_cases(ctx, d_grade_entries, signals, inferred, aligned, scores, analyzer)

        # BUG-2 fix: 统一清理所有 case_data 中的内部字段 _d_score_idx
        for entry in generated_cases:
            for c in entry.get("case_data", []):
                c.pop("_d_score_idx", None)

        # 重新计算平均分（重生成后分数可能变化）
        total_score = sum(s["score"] for s in scores)
        graded_count = len(scores)
        avg_score = total_score / graded_count if graded_count > 0 else 0.0
        avg_grade = _score_to_grade(avg_score)

        # BUG-1 fix: 清理 scores 中的内部字段，不暴露到 payload
        clean_scores = []
        for s in scores:
            clean_scores.append({k: v for k, v in s.items() if not k.startswith("_")})

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": cases_artifact.get("project_id"),
            "scores": clean_scores,
            "total_graded": graded_count,
            "average_score": round(avg_score, 2),
            "average_grade": avg_grade,
            "needs_review_count": len([s for s in scores if s["grade"] == "D"]),
        }

        # 跨模块覆盖度汇总
        module_coverage: Dict[str, Any] = {}
        for entry in generated_cases:
            if entry.get("status") != "success":
                continue
            for case_data in entry.get("case_data", []):
                case_module = case_data.get("module", "未分类")
                case_type = _classify_case_type_local(case_data)
                final_score = case_data.get("prior_quality_score", 0)

                if case_module not in module_coverage:
                    module_coverage[case_module] = {
                        "case_count": 0,
                        "type_distribution": {"positive": 0, "boundary": 0, "negative": 0},
                        "total_score": 0.0,
                    }

                mc = module_coverage[case_module]
                mc["case_count"] += 1
                mc["type_distribution"][case_type] = mc["type_distribution"].get(case_type, 0) + 1
                mc["total_score"] += final_score

        # 计算每个模块的平均分
        for module_name, mc in module_coverage.items():
            mc["average_score"] = round(mc["total_score"] / mc["case_count"], 1) if mc["case_count"] > 0 else 0.0
            del mc["total_score"]

        # UI 元素覆盖统计
        total_ui_elements = 0
        covered_ui_elements = 0

        if signals:
            ui_specs = signals.get("ui_specs", [])
            for spec in ui_specs:
                regions = spec.get("ui_spec", {}).get("regions", {})
                if isinstance(regions, dict):
                    total_ui_elements += len(regions)

        if cases_artifact:
            covered_element_names: set = set()
            for gc_entry in cases_artifact.get("generated_cases", []):
                if gc_entry.get("status") != "success":
                    continue
                for case in gc_entry.get("case_data", []):
                    for step in case.get("steps", []):
                        target = step.get("target_element", "")
                        if target:
                            covered_element_names.add(target.lower())
            covered_ui_elements = len(covered_element_names)

        ui_element_coverage = {
            "total": total_ui_elements,
            "covered": covered_ui_elements,
            "coverage_rate": round(covered_ui_elements / total_ui_elements, 2) if total_ui_elements > 0 else 0.0,
        }

        # 添加到 payload
        payload["module_coverage"] = module_coverage
        payload["ui_element_coverage"] = ui_element_coverage

        confidence = min(avg_score / 100.0, 1.0)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="quality_scores",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "avg_score": avg_score,
                "avg_grade": avg_grade,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        return "scores" in payload and "average_score" in payload

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        cases_artifact = ctx.get_artifact("generated_cases")
        generated_cases = cases_artifact.get("generated_cases", []) if cases_artifact else []
        scores = []
        for entry in generated_cases:
            if entry.get("status") != "success":
                continue
            for case_data in entry.get("case_data", []):
                scores.append({
                    "test_point_id": (entry.get("test_point") or {}).get("id"),
                    "case_title": case_data.get("title", ""),
                    "score": 50.0,
                    "grade": "C",
                    "breakdown": {"fallback": True},
                    "lifecycle_status": "pending_review",
                })

        return StepResult(
            success=True,
            artifact_payload={
                "iteration_id": ctx.iteration_id,
                "scores": scores,
                "total_graded": len(scores),
                "average_score": 50.0,
                "average_grade": "C",
                "needs_review_count": len(scores),
            },
            artifact_kind="quality_scores",
            artifact_confidence=0.3,
            degraded=True,
        )


def _compute_analyzer_score(
    analyzer: Any,
    case_data: Dict[str, Any],
) -> tuple[float, str, Dict[str, float]]:
    result = analyzer.analyze_case(case_data)

    complexity_score = result["complexity_score"]
    coverage_score = result["coverage_score"]
    redundancy_score = result["redundancy_score"]
    suggestion_count = result["suggestion_count"]

    complexity_norm = (10 - complexity_score) / 10 * 100
    coverage_norm = coverage_score / 10 * 100
    redundancy_norm = (10 - redundancy_score) / 10 * 100
    suggestion_norm = max(0, 100 - suggestion_count * 10)

    score = complexity_norm * 0.3 + coverage_norm * 0.3 + redundancy_norm * 0.2 + suggestion_norm * 0.2
    score = max(0.0, min(100.0, round(score, 2)))

    breakdown: Dict[str, float] = {
        "analyzer_complexity": round(complexity_score, 2),
        "analyzer_coverage": round(coverage_score, 2),
        "analyzer_redundancy": round(redundancy_score, 2),
        "analyzer_suggestion_count": float(suggestion_count),
        "complexity_norm": round(complexity_norm, 2),
        "coverage_norm": round(coverage_norm, 2),
        "redundancy_norm": round(redundancy_norm, 2),
        "suggestion_norm": round(suggestion_norm, 2),
    }

    grade = _score_to_grade(score)
    return score, grade, breakdown


def _compute_prior_score(
    case_data: Dict[str, Any],
    tp: Dict[str, Any],
    signals: Dict[str, Any],
    inferred: Dict[str, Any],
    aligned: Dict[str, Any],
    iteration_id: int,
    db: Any,
) -> tuple[float, str, Dict[str, float]]:
    # ── 维度1: 信号完整性（满分100） ──
    signal_score = 0.0
    signal_breakdown: Dict[str, float] = {}

    signals = signals or {}
    inferred = inferred or {}
    aligned = aligned or {}

    has_prd = signals.get("has_prd", False)
    has_testpoints = signals.get("has_testpoints", False)
    has_ui = signals.get("has_ui", False)
    has_history = signals.get("is_old_project", False)

    if has_prd:
        prd_score = 25.0
        signal_breakdown["prd"] = prd_score
        signal_score += prd_score
    else:
        inferred_confidence = inferred.get("confidence", 0.0)
        caps_score = round(inferred_confidence * 15, 2)
        signal_breakdown["inferred_capability_confidence"] = caps_score
        signal_score += caps_score

    tp_score = 20.0 if has_testpoints else 0.0
    signal_breakdown["testpoints"] = tp_score
    signal_score += tp_score

    ui_score = 25.0 if has_ui else 0.0
    signal_breakdown["ui_prototype"] = ui_score
    signal_score += ui_score

    history_score = 15.0 if has_history else 5.0
    signal_breakdown["history"] = history_score
    signal_score += history_score

    confirmed = _check_user_confirmed(db, iteration_id)
    confirmed_score = 15.0 if confirmed else 0.0
    signal_breakdown["user_confirmed"] = confirmed_score
    signal_score += confirmed_score

    conflict_count = aligned.get("conflict_count", 0)
    conflict_penalty = min(15.0, conflict_count * 3.0)
    signal_breakdown["conflict_penalty"] = -conflict_penalty
    signal_score -= conflict_penalty

    signal_score = max(0.0, min(100.0, signal_score))

    # ── 维度2: 用例内容质量（满分100） ──
    content_score = 0.0
    content_breakdown: Dict[str, float] = {}

    # title 规范性（25分）
    title_score = _score_title(case_data.get("title", ""))
    content_breakdown["title_quality"] = title_score
    content_score += title_score

    # steps 充分性（25分）
    case_type = case_data.get("case_type", "")
    steps_score = _score_steps(case_data.get("steps", []), case_type=case_type)
    content_breakdown["steps_quality"] = steps_score
    content_score += steps_score

    # expected_result 具体性（25分）
    expected_score = _score_expected_result(case_data.get("expected_result", ""))
    content_breakdown["expected_result_quality"] = expected_score
    content_score += expected_score

    # precondition 完整性（25分）
    precondition_score = _score_precondition(case_data.get("precondition", ""))
    content_breakdown["precondition_quality"] = precondition_score
    content_score += precondition_score

    content_score = max(0.0, min(100.0, content_score))

    # ── 双维度加权融合 ──
    # R1: 权重反转 0.4/0.6，内容质量为主、信号为辅，防止信号完备时低质量用例过关
    final_score = round(0.4 * signal_score + 0.6 * content_score, 2)
    final_score = max(0.0, min(100.0, final_score))

    breakdown: Dict[str, float] = {}
    breakdown["signal_score"] = round(signal_score, 2)
    breakdown["content_score"] = round(content_score, 2)
    breakdown.update(signal_breakdown)
    breakdown.update(content_breakdown)

    grade = _score_to_grade(final_score)
    return round(final_score, 2), grade, breakdown


# ── 内容维度评分函数 ──

# 模糊标题黑名单
_VAGUE_TITLE_PATTERNS = re.compile(
    r'^(功能验证|界面测试|UI测试|接口测试|性能测试|安全测试|'
    r'异常测试|边界测试|兼容性测试|回归测试|'
    r'.{1,6}测试$|.{1,6}验证$|.{1,6}功能$)',
    re.IGNORECASE,
)

# 模糊预期结果黑名单
_VAGUE_EXPECTED_PATTERNS = re.compile(
    r'(正常显示|提交成功|功能正常|页面正常|操作成功|'
    r'显示正常|运行正常|没问题|交互跳转正确|无崩溃白屏|'
    r'UI元素完整|无崩溃|无白屏|流程正常|'
    r'无异常|无报错|正常工作)',
    re.IGNORECASE,
)

# 可量化判定标记（具体值的标志，含交互结果动词）
_QUANTIFIABLE_PATTERNS = re.compile(
    r'(为["\u201c]|等于|显示.*[：:]|文案.*[：:]|'
    r'不可|无法|禁止|锁定|超时|状态码|错误码|'
    r'\d+次|\d+秒|\d+条|\d+个|\d+%|'
    r'\d+页|\d+张|\d+行|\d+字段|\d+记录|'
    r'置灰|隐藏|消失|变红|变灰|高亮|'
    r'跳转|弹出|返回|关闭|刷新|重定向|'
    r'提示|弹窗|Toast|对话框|Snackbar|'
    r'\d+[~\-～至到]\d+|'
    r'(最多|不超过|不大于|上限为|≤|<=)\s*\d+\s*(个|条|次|秒|字|页|张|行|字段|记录|字符|位|MB|KB|GB|%)|'
    r'(最少|不少于|不小于|至少|下限为|≥|>=)\s*\d+\s*(个|条|次|秒|字|页|张|行|字段|记录|字符|位|MB|KB|GB|%))',
    re.IGNORECASE,
)


# 动词堆砌检测：标题中连续出现3个及以上动词短语
_VERB_STACKING_PATTERN = re.compile(
    r'(点击|验证|检查|查看|测试|校验|弹出|关闭|跳转|返回)'
    r'.*?(点击|验证|检查|查看|测试|校验|弹出|关闭|跳转|返回)'
    r'.*?(点击|验证|检查|查看|测试|校验|弹出|关闭|跳转|返回)',
    re.IGNORECASE,
)

# 从 quality_validator 导入共享正则模式，避免重复定义导致维护不一致
from app.services.test_case_generation.quality_validator import (
    _STEP_UNCERTAINTY_PATTERN,
    _MANUAL_JUDGMENT_PATTERN,
    _TITLE_ATOMICITY_VIOLATION,
)


def _score_title(title: str) -> float:
    """评估用例标题规范性（0-25分）。

    规则:
        - 空标题: 0分
        - 模糊标题（"功能验证"/"XX测试"等）: 5分
        - 原子性违规（标题混合主流程+分支/旁路逻辑）: 5分
        - 长度 < 15字: 10分（不够具体）
        - 长度 > 40字: 15分（过于冗长）
        - 长度 15-40字且非模糊: 25分
        - 堆砌词检测: 标题含连续3个及以上动词短语且长度>30字、原评分>=15时，降为15分
    """
    if not title or not title.strip():
        return 0.0

    title = title.strip()
    base_score: float

    if _VAGUE_TITLE_PATTERNS.match(title):
        base_score = 5.0
    elif _TITLE_ATOMICITY_VIOLATION.search(title):
        base_score = 5.0
    else:
        length = len(title)
        if length < 15:
            base_score = 10.0
        elif length > 40:
            base_score = 15.0
        else:
            base_score = 25.0

    # 堆砌词检测：连续3个及以上动词短语模式的标题，限制最高15分
    if _VERB_STACKING_PATTERN.search(title) and len(title) > 30 and base_score >= 15.0:
        return 15.0

    return base_score


def _extract_step_number(step: dict) -> int | None:
    """从步骤字典中提取序号。

    优先读取 step 字段，支持 "1"、"步骤1"、"step1" 等格式。
    返回 int 类型的序号，无法提取时返回 None。
    """
    step_val = step.get("step")
    if step_val is None:
        return None
    if isinstance(step_val, int):
        return step_val
    if isinstance(step_val, str):
        match = re.search(r'\d+', step_val)
        if match:
            return int(match.group())
    return None


def _score_steps(steps: Any, case_type: str = "") -> float:
    """评估测试步骤充分性（0-25分）。

    规则:
        - 无步骤: 0分
        - 1步: 5分
        - 2步: 10-20分（按完整比例）
        - 3步及以上: 15-25分（按完整比例）
        - 完整性: 每步同时包含 action 和 expected_result 视为完整
        - 步骤序号连续性: 序号不连续时扣减，最多扣5分，不低于0分
        - 步骤不确定性: 步骤含"或"字措辞时扣减，每处扣3分
        - 自动化可执行性: ui_automation类型含人工判断时扣减，每处扣5分
    """
    if not steps:
        return 0.0

    if isinstance(steps, list):
        count = len(steps)
    elif isinstance(steps, str):
        return 5.0  # 字符串格式的步骤，无法准确计数
    else:
        return 5.0

    if count <= 0:
        return 0.0
    if count == 1:
        return 5.0

    # 检查步骤结构完整性：每步是否同时有 action 和 expected_result
    complete_count = 0
    step_numbers: list[int] = []
    uncertainty_deduction = 0.0
    manual_judgment_deduction = 0.0

    for s in steps:
        if isinstance(s, dict):
            has_action = bool(s.get("action") or s.get("description"))
            has_expected = bool(s.get("expected_result") or s.get("expected"))
            if has_action and has_expected:
                complete_count += 1
            # 提取步骤序号
            num = _extract_step_number(s)
            if num is not None:
                step_numbers.append(num)
            # 步骤不确定性检测
            action_text = (s.get("action") or s.get("description") or "")
            if _STEP_UNCERTAINTY_PATTERN.search(action_text):
                uncertainty_deduction += 3.0
            # 自动化可执行性检测
            if case_type == "ui_automation" and _MANUAL_JUDGMENT_PATTERN.search(action_text):
                manual_judgment_deduction += 5.0

    completeness_ratio = complete_count / count if count > 0 else 0.0

    if count == 2:
        score = round(10.0 + 10.0 * completeness_ratio, 1)
    else:
        # count >= 3：15(全不完整) ~ 25(全完整)，按比例
        score = round(15.0 + 10.0 * completeness_ratio, 1)

    # 步骤序号连续性检查：从1开始连续递增，缺失时扣减
    if step_numbers and len(step_numbers) >= 2:
        sorted_nums = sorted(set(step_numbers))
        max_num = sorted_nums[-1]
        # 从1到max_num应该有的步骤总数
        expected_total = max_num
        actual_total = len(sorted_nums)
        missing_count = expected_total - actual_total
        if missing_count > 0:
            deduction = min(missing_count, 5)
            score = max(0.0, score - deduction)

    # 步骤不确定性扣减（上限6分）
    uncertainty_deduction = min(uncertainty_deduction, 6.0)
    score = max(0.0, score - uncertainty_deduction)

    # 自动化可执行性扣减（上限10分）
    manual_judgment_deduction = min(manual_judgment_deduction, 10.0)
    score = max(0.0, score - manual_judgment_deduction)

    return score


def _score_expected_result(expected: str) -> float:
    """评估预期结果具体性（0-25分）。

    规则（R2: 量化优先）:
        - 空预期结果: 0分
        - 含量化标记（具体值/状态/数值）: 25分（量化优先，即使同时含模糊词）
        - 含模糊词（"正常"/"成功"等）且无量化标记: 5分
        - 其余（有交互动词但缺量化标准）: 15分
    """
    if not expected or not expected.strip():
        return 0.0

    # R2: 量化优先——先检测量化标记，有则直接25分
    if _QUANTIFIABLE_PATTERNS.search(expected):
        return 25.0

    if _VAGUE_EXPECTED_PATTERNS.search(expected):
        return 5.0

    return 15.0


def _score_precondition(precondition: str) -> float:
    """评估前置条件完整性（0-25分）。

    规则:
        - 空前置条件: 0分
        - 有内容但无登录和网络声明: 5分
        - 仅有网络声明(无登录): 10分
        - 仅有登录声明(无网络): 15分
        - 包含网络+登录: 20分
        - 包含网络+登录+权限/角色: 25分
        - 环境声明加分: 声明浏览器/设备/操作系统类型时 +2分（上限25分）
    """
    if not precondition or not precondition.strip():
        return 0.0

    pc_lower = precondition.lower()

    has_network = bool(re.search(r'(网络|network|浏览器网络|设备网络|wifi|联网)', pc_lower))
    has_login = bool(re.search(r'(登录|login|已登录|账号已登录|token|auth|鉴权|bearer|已授权)', pc_lower))
    has_permission = bool(re.search(r'(权限|permission|授权|已授权|角色|role)', pc_lower))

    if has_network and has_login and has_permission:
        score = 25.0
    elif has_network and has_login:
        score = 20.0
    elif has_login:
        score = 15.0
    elif has_network:
        score = 10.0
    else:
        # 有内容但缺少登录和网络声明
        score = 5.0

    # 环境声明检测：声明了浏览器类型、设备型号或操作系统版本时 +2分
    has_env = bool(re.search(
        r'(chrome|firefox|safari|edge|iPhone|iPad|Android|Windows|Mac|iOS|浏览器|设备|操作系统|系统版本)',
        pc_lower,
    ))
    if has_env and score < 25.0:
        score = min(25.0, score + 2.0)

    return score


def _check_user_confirmed(db: Any, iteration_id: int) -> bool:
    if db is None:
        return False
    from app.models.iteration import IterationInput

    supplement = db.query(IterationInput).filter(
        IterationInput.iteration_id == iteration_id,
        IterationInput.kind == "supplement",
    ).first()
    return supplement is not None


def _build_tp_from_task(task: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """从新架构 task 字段构建兼容的 test_point 字典。"""
    if not task:
        return None
    task_type = task.get("task_type", "")
    if task_type == "modify" or task_type == "locator_fix":
        original = task.get("original_case", {})
        return {
            "id": task.get("task_id"),
            "module": original.get("module", task.get("module", "")),
            "function": task.get("modification_hint", ""),
            "point": original.get("title", ""),
            "priority": task.get("candidate_priority", original.get("priority", 3)),
        }
    if task_type == "create":
        return {
            "id": task.get("task_id"),
            "module": task.get("candidate_module", task.get("module", "")),
            "function": task.get("candidate_description", ""),
            "point": task.get("candidate_description", ""),
            "priority": task.get("candidate_priority", 3),
        }
    return None


def _score_to_grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 65:
        return "B"
    if score >= 45:
        return "C"
    return "D"


# 本地版类型分类（与 case_generation._classify_case_type 逻辑一致）
_TYPE_KEYWORDS_LOCAL: Dict[str, List[str]] = {
    "positive": ["正向", "正常", "主流程", "happy", "成功提交", "完整流程", "正确输入", "常规"],
    "boundary": ["边界", "上限", "下限", "最大", "最小", "临界", "超长", "超限", "空值", "极值",
                 "最多", "最少", "最长", "最短", "极限", "范围", "阈值"],
    "negative": ["异常", "错误", "失败", "缺失", "拒绝", "无权限", "断网", "超时", "容错", "拦截",
                 "非法", "无效", "不存在", "未授权", "冲突", "重复"],
}


def _classify_case_type_local(case: Dict[str, Any]) -> str:
    """推断测试类型。

    优先通过 case_category/case_type 字段判断，
    其次通过标题关键词匹配。
    """
    cat = (case.get("case_category") or case.get("case_type") or "").lower()
    for type_name in ("boundary", "negative", "positive"):
        kw_map = {
            "boundary": ["boundary", "边界"],
            "negative": ["negative", "异常", "abnormal"],
            "positive": ["positive", "正向", "normal", "happy"],
        }
        if any(k in cat for k in kw_map[type_name]):
            return type_name
    title = (case.get("title") or "").lower()
    for type_name, keywords in _TYPE_KEYWORDS_LOCAL.items():
        if any(kw in title for kw in keywords):
            return type_name

    # 步骤3: 步骤内容级匹配
    steps = case.get("steps", [])
    if isinstance(steps, list):
        steps_text = ""
        for step in steps:
            if isinstance(step, dict):
                steps_text += (step.get("action", "") + " " + step.get("expected_result", "")).lower()
        if steps_text:
            for type_name, keywords in _TYPE_KEYWORDS_LOCAL.items():
                if any(kw in steps_text for kw in keywords):
                    return type_name

    return "positive"


# ── R5: D级用例自动重生成闭环 ──

def _collect_d_grade_cases(
    generated_cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """收集所有D级用例及其所属的测试点信息，供重生成使用。"""
    d_entries = []
    for entry in generated_cases:
        if entry.get("status") != "success":
            continue
        tp = entry.get("test_point", {})
        case_data_list = entry.get("case_data", [])
        d_cases = [c for c in case_data_list if c.get("prior_quality_grade") == "D"]
        if d_cases:
            # Fix1: 收集 D 级用例的 score_idx 列表，供精确移除
            d_score_idxs = [c.get("_d_score_idx") for c in d_cases if c.get("_d_score_idx") is not None]
            # 同测试点已合格用例的标题（作为上下文避免重复）
            good_titles = [
                c.get("title", "") for c in case_data_list
                if c.get("prior_quality_grade") != "D"
            ]
            d_entries.append({
                "test_point": tp,
                "d_cases": d_cases,
                "d_score_idxs": d_score_idxs,
                "good_titles": good_titles,
                "parent_entry": entry,
            })
    return d_entries


def _regenerate_d_cases(
    ctx: PipelineContext,
    d_entries: List[Dict[str, Any]],
    signals: Dict[str, Any],
    inferred: Dict[str, Any],
    aligned: Dict[str, Any],
    scores: List[Dict[str, Any]],
    analyzer: Any = None,
) -> None:
    """R5: 对D级用例重生成（含上下文补充），替换原D级用例。

    策略：
        - 仅重生成D级用例，保留已合格用例
        - 补充同测试点已合格用例标题作为上下文（避免重复）
        - 最多重生成1次，仍D级则保持 pending_review
    """
    import json as _json
    from app.pipelines.steps.case_generation import (
        _parse_case_response, _enrich_case_data, _check_type_coverage,
    )

    for d_entry in d_entries:
        tp = d_entry["test_point"]
        d_cases = d_entry["d_cases"]
        d_score_idxs = set(d_entry["d_score_idxs"])  # Fix1: 用 idx 精确移除
        good_titles = d_entry["good_titles"]
        parent_entry = d_entry["parent_entry"]

        good_titles_text = "、".join(f"「{t}」" for t in good_titles[:10]) if good_titles else "无"
        d_titles = [c.get("title", "未知") for c in d_cases]

        regen_parts: List[str] = []
        regen_parts.append("你是一名资深测试工程师。")
        regen_parts.append("")
        regen_parts.append("## 任务")
        regen_parts.append("以下测试点的部分用例质量不达标（预期结果模糊、步骤不完整等），请重新生成这些用例。")
        regen_parts.append("")
        regen_parts.append("## 测试点信息：")
        regen_parts.append(_json.dumps(tp, ensure_ascii=False))
        regen_parts.append("")
        regen_parts.append("## 需要重新生成的用例标题：")
        for t in d_titles:
            regen_parts.append(f"- {t}")
        regen_parts.append("")
        regen_parts.append("## 同测试点已合格用例标题（禁止重复）：")
        regen_parts.append(good_titles_text)
        regen_parts.append("")
        regen_parts.append("## 生成规则")
        regen_parts.append("1. 主干流程必须完整覆盖，步骤不可颠倒、不可遗漏")
        regen_parts.append("2. 分支流程需标注触发条件，作为独立场景生成用例")
        regen_parts.append("3. 异常流程需标注异常场景和预期错误提示")
        regen_parts.append("4. 标题格式：「场景/条件」+「操作」+「验证重点」，15-40字，禁用模糊词")
        regen_parts.append("5. 前置条件必须含\"账号已登录\"和网络环境，禁止依赖特定业务数据")
        regen_parts.append("6. 步骤原子化可执行，每步必须有 action 和 expected_result")
        regen_parts.append("7. 预期结果可量化判定，禁止\"页面正常\"\"功能正常\"等模糊描述，必须含量化标记（具体文案、状态变化、数值）")
        regen_parts.append("")
        regen_parts.append("## 输出格式要求：")
        regen_parts.append("严格按以下JSON数组格式输出，不要添加任何其他文字：")
        regen_parts.append("")
        regen_parts.append("[")
        regen_parts.append("  {")
        regen_parts.append('    "title": "用例标题（15-40字，要素明确）",')
        regen_parts.append('    "module": "所属模块",')
        regen_parts.append('    "precondition": "前置条件（含登录状态、网络环境）",')
        regen_parts.append('    "steps": [')
        regen_parts.append('      {"action": "具体操作步骤", "expected_result": "每步预期结果"}')
        regen_parts.append('    ],')
        regen_parts.append('    "expected_result": "整体预期结果",')
        regen_parts.append('    "case_type": "用例类型（功能测试/边界测试/异常测试）",')
        regen_parts.append('    "priority": 数字1-5,')
        regen_parts.append('    "case_category": "正向/边界/异常",')
        regen_parts.append('    "test_data": {}')
        regen_parts.append('  }')
        regen_parts.append(']')

        regen_prompt = "\n".join(regen_parts)

        try:
            response = ctx.ai_client.complete(
                prompt=regen_prompt,
                temperature=0.4,
                max_tokens=3000,
                metadata={
                    "step_name": "quality_gate_regen",
                    "test_point_id": tp.get("id"),
                    "iteration_id": ctx.iteration_id,
                    "regen_count": len(d_cases),
                },
            )
            if not response.content:
                logger.warning("R5: D级用例重生成返回空，tp_id={}", tp.get("id"))
                continue

            # 解析重生成结果
            has_ui = signals.get("has_ui", False)
            parsed = _parse_case_response(response.content)
            if not parsed:
                logger.warning("R5: D级用例重生成解析失败，tp_id={}", tp.get("id"))
                continue

            regen_cases = _enrich_case_data(parsed, tp, has_ui)

            # 替换原D级用例
            old_case_data = parent_entry.get("case_data", [])
            new_case_data = [c for c in old_case_data if c.get("prior_quality_grade") != "D"]
            new_case_data.extend(regen_cases)
            # BUG-2 fix: 清理内部字段 _d_score_idx，不传递到 Persist
            for c in new_case_data:
                c.pop("_d_score_idx", None)
            parent_entry["case_data"] = new_case_data

            # Fix2: 重新计算覆盖度加减分（基于替换后的完整用例集）
            regen_coverage_gap = _check_type_coverage(new_case_data)
            if regen_coverage_gap:
                regen_coverage_adj = -8.0 * len(regen_coverage_gap)
            else:
                regen_coverage_adj = 5.0
            per_regen_case_adj = round(regen_coverage_adj / len(new_case_data), 2) if new_case_data else 0.0

            # 重新评分重生成的用例
            for regen_case in regen_cases:
                if analyzer is not None:
                    try:
                        score, grade, breakdown = _compute_analyzer_score(analyzer, regen_case)
                    except Exception:
                        score, grade, breakdown = _compute_prior_score(
                            regen_case, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db,
                        )
                else:
                    score, grade, breakdown = _compute_prior_score(
                        regen_case, tp, signals, inferred, aligned, ctx.iteration_id, ctx.db,
                    )

                # Fix2: 应用覆盖度加减分
                if per_regen_case_adj != 0.0:
                    score = max(0.0, min(100.0, round(score + per_regen_case_adj, 2)))
                    breakdown["coverage_adjustment"] = per_regen_case_adj
                    grade = _score_to_grade(score)

                regen_case["prior_quality_score"] = score
                regen_case["prior_quality_grade"] = grade
                regen_case["lifecycle_status"] = "draft"
                if grade == "D":
                    regen_case["lifecycle_status"] = "pending_review"
                    logger.info("R5: 重生成后仍D级，保持 pending_review: {}", regen_case.get("title", "")[:30])
                else:
                    logger.info("R5: 重生成成功，{}级: {}", grade, regen_case.get("title", "")[:30])

                scores.append({
                    "test_point_id": tp.get("id"),
                    "case_title": regen_case.get("title", ""),
                    "score": score,
                    "grade": grade,
                    "breakdown": breakdown,
                    "lifecycle_status": regen_case.get("lifecycle_status", "draft"),
                    "regenerated": True,
                })

            # Fix1: 用 _score_idx 精确移除原D级用例的 scores 记录
            if d_score_idxs:
                scores[:] = [
                    s for s in scores
                    if s.get("_score_idx") not in d_score_idxs
                ]

        except Exception as e:
            logger.warning("R5: D级用例重生成异常，tp_id={}: {}", tp.get("id"), e)
