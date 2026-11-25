"""质量评分统一服务（Task 14 三合一）。

将三处评分逻辑统一为单一服务：grade_status（4 档）、
score_dimensions（7 维度）、prior_score（prior 评分）。三处共享底层
_classify_* 判定与 quality_scoring_constants 常量，消除同一字段在不同
评分函数中给出冲突分数的问题。常量与正则统一在 quality_scoring_constants
定义，本模块仅包含判定与评分逻辑。
"""

from typing import Any, Literal

from app.services.case_quality.quality_scoring_constants import (
    CLICK_ACTION_KEYWORDS,
    EXPECTED_VAGUE_PATTERNS,
    EXPECTED_VAGUE_WORDS,
    INPUT_ACTION_KEYWORDS,
    INPUT_VALUE_PLACEHOLDERS,
    LOGGED_IN_MARKERS,
    LOGGED_OUT_MARKERS,
    MANUAL_JUDGMENT_PATTERN,
    STEP_INFERENCE_ACTION_PATTERN,
    STEP_INFERENCE_EXPECTED_PATTERN,
    STEP_REFERENCE_PATTERN,
    STEP_UNCERTAINTY_PATTERN,
    TITLE_ATOMICITY_VIOLATION_PATTERN,
    TITLE_MAX_LENGTH,
    TITLE_MIN_LENGTH,
    TITLE_VAGUE_PATTERNS,
    TITLE_VAGUE_WORDS,
    UI_ACTION_TYPES,
    VALID_ACTION_TYPES,
    VALID_CASE_CATEGORIES,
    TitleVerdict,
)

CaseStatus = Literal["passed", "warning", "pending_review", "rejected"]
_STATUS_ORDER: dict[str, int] = {"passed": 0, "warning": 1, "pending_review": 2, "rejected": 3}
_STATUS_BY_SEVERITY = ("passed", "warning", "pending_review", "rejected")

_REJECTED = _STATUS_ORDER["rejected"]
_PENDING_REVIEW = _STATUS_ORDER["pending_review"]
_WARNING = _STATUS_ORDER["warning"]


def _title_severity(title: str) -> int:
    verdict = QualityScoringService._classify_title(title)
    return {"empty": _REJECTED, "vague": _PENDING_REVIEW, "length": _WARNING}.get(verdict, 0)


def _precondition_severity(precondition: str) -> int:
    verdict = QualityScoringService._classify_precondition(precondition)
    if verdict == "empty":
        return _REJECTED
    if verdict in ("missing_login", "contradictory", "short"):
        return _PENDING_REVIEW
    return 0


def _steps_severity(steps: list[dict[str, Any]], case_type: str) -> int:
    verdict = QualityScoringService._classify_steps(steps, case_type)
    if verdict in ("empty", "insufficient"):
        return _REJECTED
    if verdict == "content_issue":
        return _PENDING_REVIEW
    return 0


def _expected_severity(expected_result: str) -> int:
    verdict = QualityScoringService._classify_expected(expected_result)
    if verdict == "empty":
        return _REJECTED
    if verdict in ("vague", "short"):
        return _PENDING_REVIEW
    return 0


def _category_severity(case_category: str) -> int:
    verdict = QualityScoringService._classify_case_category(case_category)
    return _REJECTED if verdict in ("empty", "invalid") else 0


def _aux_severity(case: dict[str, Any], steps: list[dict[str, Any]]) -> int:
    """辅助规则：测试数据缺失仅 warning；原子性/边界/类型一致性为 pending_review。"""
    severity = 0
    if not QualityScoringService._check_test_data(steps):
        severity = max(severity, _WARNING)
    if not QualityScoringService._check_atomicity(steps):
        severity = max(severity, _PENDING_REVIEW)
    if QualityScoringService._boundary_issues(case):
        severity = max(severity, _PENDING_REVIEW)
    if QualityScoringService._type_consistency_issues(case):
        severity = max(severity, _PENDING_REVIEW)
    return severity


class QualityScoringService:
    """质量评分统一服务。

    三处评分入口（4 档 / 7 维度 / prior）共享底层 _classify_* 判定，
    保证同一用例在三处不再给出冲突分数。
    """

    # ── 核心判定：标题 ──
    @staticmethod
    def _classify_title(title: str) -> TitleVerdict:
        """判定标题质量等级（grade_status 与 score_dimensions 共用）。

        合并原 TITLE_VAGUE_WORDS 与 TITLE_VAGUE_PATTERNS 两套冲突规则。
        """
        if not title or not title.strip():
            return "empty"
        title = title.strip()
        if (
            any(word in title for word in TITLE_VAGUE_WORDS)
            or TITLE_VAGUE_PATTERNS.match(title)
            or TITLE_ATOMICITY_VIOLATION_PATTERN.search(title)
        ):
            return "vague"
        if len(title) < TITLE_MIN_LENGTH or len(title) > TITLE_MAX_LENGTH:
            return "length"
        return "ok"

    # ── 核心判定：前置条件 ──
    @staticmethod
    def _classify_precondition(precondition: str) -> str:
        """判定前置条件质量等级（含登录状态互斥校验）。"""
        if not precondition or not precondition.strip():
            return "empty"
        precondition = precondition.strip()
        has_logged_in = any(m in precondition for m in LOGGED_IN_MARKERS)
        has_logged_out = any(m in precondition for m in LOGGED_OUT_MARKERS)
        if has_logged_in and has_logged_out:
            return "contradictory"
        if not has_logged_in and not has_logged_out:
            return "missing_login"
        if len(precondition) < 15:
            return "short"
        return "ok"

    # ── 核心判定：步骤 ──
    @staticmethod
    def _classify_steps(steps: list[dict[str, Any]], case_type: str = "") -> str:
        """判定步骤质量等级（数量问题与内容问题区分）。"""
        if not steps or len(steps) == 0:
            return "empty"
        if len(steps) < 2 or len(steps) > 8:
            return "insufficient"
        if any(QualityScoringService._step_has_content_issue(step, case_type) for step in steps):
            return "content_issue"
        return "ok"

    @staticmethod
    def _step_fields_missing(step: dict[str, Any]) -> bool:
        """action（缺失时回退 description）与 expected_result 任一为空。"""
        action = step.get("action", "") or step.get("description", "")
        expected = step.get("expected_result", "")
        return not action or not action.strip() or not expected or not expected.strip()

    @staticmethod
    def _step_has_content_issue(step: dict[str, Any], case_type: str) -> bool:
        """单步骤内容判定：候选规则与生成侧 `validate_steps` 保持一致。"""
        if QualityScoringService._step_fields_missing(step):
            return True
        action = step.get("action", "") or step.get("description", "")
        description = step.get("description", "")
        expected = step.get("expected_result", "")
        if STEP_REFERENCE_PATTERN.search(f"{action} {description}"):
            return True
        if STEP_UNCERTAINTY_PATTERN.search(action):
            return True
        if STEP_INFERENCE_ACTION_PATTERN.search(action):
            return True
        if STEP_INFERENCE_EXPECTED_PATTERN.search(expected):
            return True
        return case_type == "ui_automation" and bool(MANUAL_JUDGMENT_PATTERN.search(action))

    # ── 核心判定：预期结果 ──
    @staticmethod
    def _classify_expected(expected_result: str) -> str:
        """判定预期结果质量等级（合并 EXPECTED_VAGUE_WORDS 与 PATTERNS）。"""
        if not expected_result or not expected_result.strip():
            return "empty"
        expected_result = expected_result.strip()
        if any(word in expected_result for word in EXPECTED_VAGUE_WORDS) or EXPECTED_VAGUE_PATTERNS.search(
            expected_result
        ):
            return "vague"
        if len(expected_result) < 10:
            return "short"
        return "ok"

    # ── 核心判定：case_category ──
    @staticmethod
    def _classify_case_category(case_category: str) -> str:
        if not case_category:
            return "empty"
        if case_category not in VALID_CASE_CATEGORIES:
            return "invalid"
        return "ok"

    # ── 4 档状态：grade_status ──
    @staticmethod
    def grade_status(case: dict[str, Any]) -> CaseStatus:
        """对单条用例执行全量质量校验，返回 4 档状态。

        与 score_dimensions 共享 _classify_* 判定。只 rejected 阻断入库，
        pending_review/warning 不阻断（历史避坑：质量门禁分级阻断）。

        实现：各维度各自算出严重度，最终取最大值——等价于原 `worse()` 的
        "只升不降"聚合，但不再需要 `nonlocal` 可变状态。
        """
        steps = case.get("steps", [])
        severities = [
            _title_severity(case.get("title", "")),
            _precondition_severity(case.get("precondition", "")),
            _steps_severity(steps, case.get("case_type", "")),
            _expected_severity(case.get("expected_result", "")),
            _category_severity(case.get("case_category", "")),
            _aux_severity(case, steps),
        ]
        return _STATUS_BY_SEVERITY[max(severities)]

    @staticmethod
    def _check_test_data(steps: list[dict[str, Any]]) -> bool:
        """校验 input/select 步骤有具体输入值（True=通过）。"""
        if not steps:
            return True
        for step in steps:
            if step.get("action_type", "") not in ("input", "select"):
                continue
            input_value = (step.get("input_value") or "").strip()
            if not input_value or input_value in INPUT_VALUE_PLACEHOLDERS:
                return False
        return True

    @staticmethod
    def _check_atomicity(steps: list[dict[str, Any]]) -> bool:
        """校验步骤原子性（无混合点击+输入，True=通过）。"""
        if not steps:
            return True
        for step in steps:
            action = step.get("action", "") or step.get("description", "")
            has_click = any(k in action for k in CLICK_ACTION_KEYWORDS)
            has_input = any(k in action for k in INPUT_ACTION_KEYWORDS)
            if has_click and has_input:
                return False
        return True

    @staticmethod
    def _boundary_issues(case: dict[str, Any]) -> bool:
        """边界用例是否使用占位符而非实际边界值（True=有问题）。"""
        if case.get("case_category") != "boundary":
            return False
        steps = case.get("steps", [])
        if not isinstance(steps, list):
            return False
        for step in steps:
            if not isinstance(step, dict):
                continue
            if step.get("action_type") not in ("input", "select"):
                continue
            value = str(step.get("input_value") or "").strip()
            if not value or value in INPUT_VALUE_PLACEHOLDERS:
                return True
        return False

    @staticmethod
    def _type_consistency_issues(case: dict[str, Any]) -> bool:
        """case_type 与 action_type 组合是否矛盾（True=有问题）。"""
        case_type = case.get("case_type", "")
        steps = case.get("steps", [])
        if not isinstance(steps, list):
            return False
        for step in steps:
            if not isinstance(step, dict):
                continue
            action_type = step.get("action_type", "")
            if not action_type:
                continue
            if case_type == "api_automation" and action_type in UI_ACTION_TYPES:
                return True
            if case_type == "manual" and action_type == "api_call":
                return True
        return False

    # ── 7 维度评分：score_dimensions ──
    @staticmethod
    def score_dimensions(case: dict[str, Any]) -> dict[str, float]:
        """计算单条用例的 7 维度连续评分（每维度 0-10）。

        与 grade_status 共享 _classify_* 判定，消除与 prior 评分的冲突。
        """
        case_type = case.get("case_type", "")

        title_v = QualityScoringService._classify_title(case.get("title", ""))
        title_score = {"empty": 0.0, "vague": 4.0, "length": 7.0, "ok": 10.0}[title_v]

        pre_v = QualityScoringService._classify_precondition(case.get("precondition", ""))
        precondition_score = {
            "empty": 0.0,
            "missing_login": 4.0,
            "contradictory": 4.0,
            "short": 7.0,
            "ok": 10.0,
        }[pre_v]

        steps_v = QualityScoringService._classify_steps(case.get("steps", []), case_type)
        steps_score = {
            "empty": 0.0,
            "insufficient": 7.0,
            "content_issue": 4.0,
            "ok": 10.0,
        }[steps_v]

        expected_v = QualityScoringService._classify_expected(case.get("expected_result", ""))
        expected_score = {
            "empty": 0.0,
            "vague": 4.0,
            "short": 7.0,
            "ok": 10.0,
        }[expected_v]

        cat_v = QualityScoringService._classify_case_category(case.get("case_category", ""))
        case_category_score = {"empty": 0.0, "invalid": 0.0, "ok": 10.0}[cat_v]

        action_type_score = QualityScoringService._score_action_type_dim(case.get("steps", []))
        atomicity_score = 10.0 if QualityScoringService._check_atomicity(case.get("steps", [])) else 4.0

        return {
            "title": title_score,
            "precondition": precondition_score,
            "steps": steps_score,
            "expected_result": expected_score,
            "case_category": case_category_score,
            "action_type": action_type_score,
            "atomicity": atomicity_score,
        }

    @staticmethod
    def _score_action_type_dim(steps: list[dict[str, Any]]) -> float:
        """action_type 维度评分：全部合法10/缺失7/非法0。"""
        if not steps:
            return 10.0
        has_missing = False
        for step in steps:
            action_type = step.get("action_type", "")
            if not action_type or not action_type.strip():
                has_missing = True
                continue
            if action_type.strip() not in VALID_ACTION_TYPES:
                return 0.0
        return 7.0 if has_missing else 10.0

    # ── prior 评分：prior_score ──
    @staticmethod
    def prior_score(case: dict[str, Any]) -> tuple[float, dict[str, float]]:
        """计算 prior content 质量分（0-100）与维度明细。

        prior 保留 0-25 分制精排序（长度细分/堆砌降分/步骤序号连续性），
        模糊判定与 grade_status/score_dimensions 共享统一常量与正则。

        Returns:
            (content 总分 0-100, 维度明细 breakdown)。
        """
        # 延迟导入避免循环依赖：_scoring 复用本模块常量
        from app.pipelines.steps._scoring import (
            _score_expected_result,
            _score_precondition,
            _score_steps,
            _score_title,
        )

        case_type = case.get("case_type", "")
        title_score = _score_title(case.get("title", ""))
        steps_score = _score_steps(case.get("steps", []), case_type=case_type)
        expected_score = _score_expected_result(case.get("expected_result", ""))
        precondition_score = _score_precondition(case.get("precondition", ""))

        content_score = max(0.0, min(100.0, title_score + steps_score + expected_score + precondition_score))
        breakdown: dict[str, float] = {
            "title_quality": round(title_score, 2),
            "steps_quality": round(steps_score, 2),
            "expected_result_quality": round(expected_score, 2),
            "precondition_quality": round(precondition_score, 2),
        }
        return round(content_score, 2), breakdown
