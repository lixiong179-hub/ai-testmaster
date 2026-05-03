"""BackwardScan Pydantic 输出 Schema

定义反向扫描 AI 输出的结构化 Schema，用于校验和解析。

5 种 verdict：
    - VALID: 用例仍然有效
    - LOCATOR_ONLY: 仅定位器失效
    - NEEDS_MODIFY: 业务逻辑需更新
    - DEPRECATED: 用例已过时
    - UNCERTAIN: 需人工评审
"""
import json
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, validator


class BackwardVerdict(str, Enum):
    """反向扫描判定结果枚举。"""

    VALID = "VALID"
    LOCATOR_ONLY = "LOCATOR_ONLY"
    NEEDS_MODIFY = "NEEDS_MODIFY"
    DEPRECATED = "DEPRECATED"
    UNCERTAIN = "UNCERTAIN"


class BackwardCaseVerdict(BaseModel):
    """单条用例的反向扫描判定。"""

    case_id: int = Field(..., description="用例 ID")
    verdict: BackwardVerdict = Field(..., description="判定结果")
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="置信度 0.0-1.0",
    )
    hint: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="判定理由",
    )

    @validator("verdict", pre=True)
    def normalize_verdict(cls, v: Any) -> Any:
        if isinstance(v, str):
            upper = v.upper()
            if upper in {e.value for e in BackwardVerdict}:
                return upper
        return v

    @validator("confidence", pre=True)
    def coerce_confidence(cls, v: Any) -> float:
        return float(v)


class BackwardScanOutput(BaseModel):
    """反向扫描 AI 输出的完整结构。"""

    verdicts: List[BackwardCaseVerdict] = Field(
        ...,
        description="每条用例的判定结果列表",
    )

    @validator("verdicts")
    def check_no_duplicate_case_ids(cls, v: List[BackwardCaseVerdict]) -> List[BackwardCaseVerdict]:
        seen = set()
        for item in v:
            if item.case_id in seen:
                raise ValueError(f"Duplicate case_id: {item.case_id}")
            seen.add(item.case_id)
        return v


class ValidationResult(BaseModel):
    """校验结果。"""

    valid: bool = Field(description="是否校验通过")
    errors: List[str] = Field(default_factory=list, description="校验错误列表")
    auto_corrected: List[str] = Field(
        default_factory=list,
        description="自动修正的项目列表",
    )
    output: Optional[BackwardScanOutput] = Field(
        default=None,
        description="修正后的输出（校验通过时）",
    )
    retries: int = Field(default=0, description="重试次数")


def validate_backward_output(
    raw: Any,
    expected_case_ids: Optional[List[int]] = None,
) -> ValidationResult:
    """校验反向扫描 AI 输出。

    校验规则：
        1. raw 必须可解析为 BackwardScanOutput
        2. 每条 verdict 的 case_id 必须在 expected_case_ids 中（如果提供）
        3. confidence < 0.7 时自动改 verdict=UNCERTAIN
        4. hint 不能为空
        5. verdict 必须是合法枚举值
        6. confidence 必须在 0.0-1.0 范围内（超出范围报错，不静默截断）

    Args:
        raw: AI 返回的原始数据（dict 或 JSON 字符串）。
        expected_case_ids: 期望的 case_id 列表，用于检测缺失/多余。

    Returns:
        ValidationResult 包含校验结果、错误列表、自动修正项和修正后的输出。
    """
    errors: List[str] = []
    auto_corrected: List[str] = []

    if raw is None:
        return ValidationResult(
            valid=False,
            errors=["AI 输出为空"],
        )

    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            return ValidationResult(
                valid=False,
                errors=[f"JSON 解析失败: {e}"],
            )

    if isinstance(data, dict) and "verdicts" not in data:
        return ValidationResult(
            valid=False,
            errors=["AI 输出缺少 verdicts 字段且不是列表"],
        )
    elif isinstance(data, list):
        data = {"verdicts": data}

    try:
        output = BackwardScanOutput(**data)
    except Exception as e:
        return ValidationResult(
            valid=False,
            errors=[f"Schema 校验失败: {e}"],
        )

    corrected_verdicts = []
    for item in output.verdicts:
        verdict = item.verdict
        if item.confidence < 0.7 and verdict != BackwardVerdict.UNCERTAIN:
            auto_corrected.append(
                f"case_id={item.case_id}: confidence={item.confidence:.2f} < 0.7, "
                f"verdict {verdict.value} → UNCERTAIN"
            )
            verdict = BackwardVerdict.UNCERTAIN

        corrected_verdicts.append(
            BackwardCaseVerdict(
                case_id=item.case_id,
                verdict=verdict,
                confidence=item.confidence,
                hint=item.hint,
            )
        )

    output = BackwardScanOutput(verdicts=corrected_verdicts)

    if expected_case_ids is not None:
        expected_set = set(expected_case_ids)
        actual_set = {v.case_id for v in output.verdicts}

        missing = expected_set - actual_set
        if missing:
            errors.append(f"缺少 case_id: {sorted(missing)}")

        extra = actual_set - expected_set
        if extra:
            errors.append(f"多余 case_id: {sorted(extra)}")

    is_valid = len(errors) == 0
    return ValidationResult(
        valid=is_valid,
        errors=errors,
        auto_corrected=auto_corrected,
        output=output if is_valid else None,
    )
