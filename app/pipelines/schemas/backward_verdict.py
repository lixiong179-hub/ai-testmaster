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
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, validator


class BackwardVerdict(StrEnum):
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

    verdicts: list[BackwardCaseVerdict] = Field(
        ...,
        description="每条用例的判定结果列表",
    )

    @validator("verdicts")
    def check_no_duplicate_case_ids(cls, v: list[BackwardCaseVerdict]) -> list[BackwardCaseVerdict]:
        seen = set()
        for item in v:
            if item.case_id in seen:
                raise ValueError(f"Duplicate case_id: {item.case_id}")
            seen.add(item.case_id)
        return v


class ValidationResult(BaseModel):
    """校验结果。"""

    valid: bool = Field(description="是否校验通过")
    errors: list[str] = Field(default_factory=list, description="校验错误列表")
    auto_corrected: list[str] = Field(
        default_factory=list,
        description="自动修正的项目列表",
    )
    output: BackwardScanOutput | None = Field(
        default=None,
        description="修正后的输出（校验通过时）",
    )
    retries: int = Field(default=0, description="重试次数")


def validate_backward_output(
    raw: Any,
    expected_case_ids: list[int] | None = None,
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
    if raw is None:
        return ValidationResult(
            valid=False,
            errors=["AI 输出为空"],
        )

    data, parse_error = _coerce_payload(raw)
    if parse_error:
        return ValidationResult(valid=False, errors=[parse_error])

    output, schema_error = _build_scanned_output(data)
    if schema_error or output is None:
        return ValidationResult(valid=False, errors=[schema_error or "Schema 校验失败"])

    output, auto_corrected = _downgrade_low_confidence(output)
    errors = _check_case_ids(output, expected_case_ids)

    is_valid = len(errors) == 0
    return ValidationResult(
        valid=is_valid,
        errors=errors,
        auto_corrected=auto_corrected,
        output=output if is_valid else None,
    )


def _coerce_payload(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """str → JSON；裸列表 → {"verdicts": [...]}；缺 verdicts 的 dict 直接判错。"""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as e:
            return None, f"JSON 解析失败: {e}"

    if isinstance(data, dict) and "verdicts" not in data:
        return None, "AI 输出缺少 verdicts 字段且不是列表"
    if isinstance(data, list):
        data = {"verdicts": data}
    return data, None


def _build_scanned_output(data: Any) -> tuple[BackwardScanOutput | None, str | None]:
    try:
        return BackwardScanOutput(**data), None
    except Exception as e:
        return None, f"Schema 校验失败: {e}"


def _downgrade_low_confidence(output: BackwardScanOutput) -> tuple[BackwardScanOutput, list[str]]:
    """confidence < 0.7 的非 UNCERTAIN 判定自动降级，并记录修正说明。"""
    corrected_verdicts: list[BackwardCaseVerdict] = []
    auto_corrected: list[str] = []
    for item in output.verdicts:
        verdict = item.verdict
        if item.confidence < 0.7 and verdict != BackwardVerdict.UNCERTAIN:
            auto_corrected.append(
                f"case_id={item.case_id}: confidence={item.confidence:.2f} < 0.7, verdict {verdict.value} → UNCERTAIN"
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
    return BackwardScanOutput(verdicts=corrected_verdicts), auto_corrected


def _check_case_ids(output: BackwardScanOutput, expected_case_ids: list[int] | None) -> list[str]:
    """期望 case_id 集合与实际集合的差集告警（未提供期望值时跳过）。"""
    if expected_case_ids is None:
        return []

    expected_set = set(expected_case_ids)
    actual_set = {v.case_id for v in output.verdicts}
    errors: list[str] = []

    missing = expected_set - actual_set
    if missing:
        errors.append(f"缺少 case_id: {sorted(missing)}")

    extra = actual_set - expected_set
    if extra:
        errors.append(f"多余 case_id: {sorted(extra)}")
    return errors
