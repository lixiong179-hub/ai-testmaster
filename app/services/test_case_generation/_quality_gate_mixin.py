"""
Test Case Generation Service - 质量门禁与动作修正子Mixin
从 validate_mixin.py 拆分：action_type 自动修正、前置条件清洗、case_type 归一化、
质量门禁校验（QualityGateService + 本地硬性校验）、生成优先级解析。
"""
import re
from typing import Any, Dict, List, Optional, Tuple
from loguru import logger

from app.core.constants import DEFAULT_AI_FALLBACK_CASE_TYPE, normalize_priority
from app.services.quality.quality_gate_service import QualityGateService


class TestCaseGenerationQualityGateMixin:
    """质量门禁与动作修正：action_type/precondition/case_type 规整 + 质量门禁判定。"""

    _CLICK_KEYWORDS = frozenset({"点击", "勾选", "切换", "按下", "长按"})
    _INPUT_KEYWORDS = frozenset({"输入", "填写", "键入", "录入"})
    _ASSERT_KEYWORDS = frozenset({"查看", "检查", "验证", "确认", "核对", "观察", "获取"})
    _NAVIGATE_KEYWORDS = frozenset({"等待", "静置", "等待加载"})
    _ASSERT_CLICK_PATTERNS = re.compile(
        r'(检查.*(?:点击|可点击|是否可)|查看.*(?:点击|可点击|是否可)|'
        r'验证.*(?:点击|可点击|是否可)|确认.*(?:点击|可点击|是否可))'
    )

    _VALID_CASE_TYPES = frozenset({
        "ui_automation",
        "manual",
        "api_automation",
        "performance",
        "security",
    })
    _MIN_PERSIST_QUALITY_SCORE = 80.0
    _MIN_PRECONDITION_LENGTH = 15
    _PRIORITY_ONE_KEYWORDS = frozenset({
        "\u4e3b\u6d41\u7a0b",
        "\u5168\u6d41\u7a0b",
        "\u6838\u5fc3",
        "\u63d0\u4ea4\u6279\u6539",
        "\u6279\u6539",
        "\u65ad\u7f51",
        "\u65e0\u7f51\u7edc",
        "\u7f51\u7edc\u5f02\u5e38",
        "\u6570\u636e\u4e22\u5931",
        "\u5d29\u6e83",
        "\u767d\u5c4f",
        "\u672a\u767b\u5f55",
        "\u6743\u9650",
        "\u8d8a\u6743",
        "\u5b89\u5168",
        "\u91cd\u590d\u63d0\u4ea4",
        "\u8fde\u7eed\u5feb\u901f\u70b9\u51fb",
        "\u6b63\u786e\u7387100%",
        "\u542c\u5199\u7ed3\u679c",
        "\u7ed3\u679c\u9875",
    })

    @staticmethod
    def _correct_action_type(action: str, action_type: str) -> str:
        if not action:
            return action_type
        cls = TestCaseGenerationQualityGateMixin
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
        # R5 修复：QualityGate 编排异常时降级为 warning 不阻断入库，仅记录告警。
        # 业务原因：QualityGateService.validate 内部虽对每个 validator 有 try/except，
        # 但 _build_context / ValidationResult.merge / db session 失效等环节仍可能抛
        # 异常。无兜底时异常会冒泡到 _save_test_case → batch_mixin._generate_one，
        # 导致本应通过本地硬性校验的用例被误判为失败。本地硬性校验（quality_score /
        # precondition / UI 可执行性）仍正常执行，由 local_blocking 决定是否阻断。
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

        # 本地硬性校验：任一失败则提升为 rejected
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

        # 仅 rejected 返回非空 issues，其他状态返回空列表（不阻断）
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
