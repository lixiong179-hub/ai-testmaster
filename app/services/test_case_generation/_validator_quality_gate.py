"""test_case_generation - 质量门禁与动作修正 mixin。

从 validator.py 拆分，负责：
    1. 步骤动作类型修正（_correct_action_type）
    2. 前置条件清洗（_clean_precondition）
    3. 用例类型归一化（_normalize_case_type）
    4. 质量门禁判定（_quality_gate_issues，调用 QualityGateService + 本地硬性校验）
    5. 生成用例优先级解析（_resolve_generated_priority）

被 validator.py 的 CaseValidator 通过多继承组合，不单独对外暴露。
_quality_gate_issues 内部调用 cls._ui_executability_issues，由
UIElementValidationMixin 提供，运行时通过 CaseValidator MRO 解析。
"""
import re
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.core.constants import DEFAULT_AI_FALLBACK_CASE_TYPE, normalize_priority
from app.services.quality.quality_gate_service import QualityGateService


class QualityGateMixin:
    """质量门禁与动作修正 mixin。

    职责：
        动作类型修正、前置条件清洗、用例类型归一化、质量门禁判定与
        优先级解析。常量与方法由 CaseValidator 通过多继承组合。

    注意：
        _quality_gate_issues 调用 cls._ui_executability_issues，该方法由
        UIElementValidationMixin 提供，需与 CaseValidator 组合后使用。
    """

    # ── 质量门禁与动作修正常量（合并自 _quality_gate_mixin） ──
    _CLICK_KEYWORDS = frozenset({"点击", "勾选", "切换", "按下", "长按"})
    _INPUT_KEYWORDS = frozenset({"输入", "填写", "键入", "录入"})
    _ASSERT_KEYWORDS = frozenset({"查看", "检查", "验证", "确认", "核对", "观察", "获取"})
    _NAVIGATE_KEYWORDS = frozenset({"等待", "静置", "等待加载"})
    _ASSERT_CLICK_PATTERNS = re.compile(
        r'(检查.*(?:点击|可点击|是否可)|查看.*(?:点击|可点击|是否可)|'
        r'验证.*(?:点击|可点击|是否可)|确认.*(?:点击|可点击|是否可))'
    )
    _VALID_CASE_TYPES = frozenset({
        "ui_automation", "manual", "api_automation", "performance", "security",
    })
    _MIN_PERSIST_QUALITY_SCORE = 80.0
    _MIN_PRECONDITION_LENGTH = 15
    _PRIORITY_ONE_KEYWORDS = frozenset({
        "主流程", "全流程", "核心", "提交批改", "批改", "断网", "无网络",
        "网络异常", "数据丢失", "崩溃", "白屏", "未登录", "权限", "越权",
        "安全", "重复提交", "连续快速点击", "正确率100%", "听写结果", "结果页",
    })

    @classmethod
    def _correct_action_type(cls, action: str, action_type: str) -> str:
        if not action:
            return action_type
        has_assert = any(kw in action for kw in cls._ASSERT_KEYWORDS)
        has_click = any(kw in action for kw in cls._CLICK_KEYWORDS)
        if has_assert and has_click:
            if cls._ASSERT_CLICK_PATTERNS.search(action):
                return "verify"
            return "click"
        if has_click:
            return "click"
        if any(kw in action for kw in cls._INPUT_KEYWORDS):
            return "input"
        if has_assert:
            return "verify"
        if any(kw in action for kw in cls._NAVIGATE_KEYWORDS):
            return "navigate"
        return action_type

    @staticmethod
    def _clean_precondition(precondition: str) -> str:
        if not precondition:
            return precondition
        patterns = [
            r'[、，,]?\s*通过(?:Mock|cy\.intercept|ADB|devtools)[^、，,]*',
            r'[、，,]?\s*Mock[^、，,]*',
            r'[、，,]?\s*cy\.intercept\([^)]*\)[^、，,]*',
            r'[、，,]?\s*ADB[^、，,]*',
            r'[、，,]?\s*devtools[^、，,]*',
            r'[、，,]?\s*（?清除(?:token|cookie|session|缓存|localStorage|sessionStorage)[^）、，,]*）?',
            r'[、，,]?\s*清除(?:token|cookie|session|缓存|localStorage|sessionStorage)[^、，,]*',
            r'[、，,]?\s*（?(?:token|cookie|session)[^）、，,]*）?',
        ]
        cleaned = precondition
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'[、，,]\s*$', '', cleaned.strip())
        cleaned = re.sub(r'^[、，,]\s*', '', cleaned)
        cleaned = re.sub(r'（\s*）', '', cleaned)
        cleaned = re.sub(r'\(\s*\)', '', cleaned)
        return cleaned

    @classmethod
    def _normalize_case_type(cls, *values: Optional[str]) -> str:
        for value in values:
            if not value:
                continue
            for part in str(value).split(","):
                normalized = part.strip()
                if normalized in cls._VALID_CASE_TYPES:
                    return normalized
        return DEFAULT_AI_FALLBACK_CASE_TYPE

    @classmethod
    def _quality_gate_issues(
        cls,
        generated_case: Dict[str, Any],
        quality_score: Optional[float],
        ui_specs: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[int] = None,
        db: Any = None,
    ) -> Tuple[List[str], str]:
        """使用 QualityGateService 执行统一校验，返回 (issues, status) 元组。

        分级阻断规则:
            - rejected: 返回非空 issues，调用方应阻断入库
            - pending_review/warning/passed: 返回空 issues 列表，调用方不阻断

        本地硬性校验（quality_score/precondition/UI可执行性）失败时，
        状态提升为 rejected，确保硬性质量门槛始终阻断。
        """
        context: Dict[str, Any] = {
            "ui_specs": ui_specs or generated_case.get("_context_ui_specs"),
        }
        gate_service = QualityGateService(db=db)
        try:
            result = gate_service.validate(
                generated_case,
                context=context,
                project_id=project_id,
            )
            gate_status: str = result.status
            issues: List[str] = [issue.message for issue in result.issues]
        except Exception as e:
            logger.warning(f"QualityGate 编排异常，降级为 warning: {e}")
            gate_status = "warning"
            issues = []

        local_blocking = False
        if quality_score is None:
            issues.append("quality score is missing")
            local_blocking = True
        elif quality_score < cls._MIN_PERSIST_QUALITY_SCORE:
            issues.append(
                f"quality score {quality_score:.0f} is below "
                f"{cls._MIN_PERSIST_QUALITY_SCORE:.0f}"
            )
            local_blocking = True
        precondition = (generated_case.get("precondition") or "").strip()
        if len(precondition) < cls._MIN_PRECONDITION_LENGTH:
            issues.append(
                f"precondition is too short ({len(precondition)} chars)"
            )
            local_blocking = True
        ui_issues = cls._ui_executability_issues(
            generated_case.get("steps", []),
            ui_specs or generated_case.get("_context_ui_specs"),
        )
        if ui_issues:
            issues.extend(ui_issues)
            local_blocking = True

        if local_blocking:
            gate_status = "rejected"

        if gate_status == "rejected":
            return issues, gate_status
        return [], gate_status

    @classmethod
    def _resolve_generated_priority(
        cls,
        generated_case: Dict[str, Any],
        test_point: Dict[str, Any],
    ) -> int:
        priority = normalize_priority(
            generated_case.get("priority", test_point.get("priority", 2))
        )
        point_priority = normalize_priority(test_point.get("priority", priority))
        if priority == 1 or point_priority == 1:
            return 1

        text = " ".join(
            str(value or "")
            for value in (
                generated_case.get("title"),
                generated_case.get("expected_result"),
                generated_case.get("case_category"),
                test_point.get("point"),
                test_point.get("function"),
            )
        )
        if any(keyword in text for keyword in cls._PRIORITY_ONE_KEYWORDS):
            return 1
        return priority
