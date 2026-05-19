"""M2-T03 BackwardScan Prompt + Schema 单元测试

覆盖：
    - BackwardVerdict 枚举值
    - BackwardCaseVerdict Schema 校验
    - BackwardScanOutput 去重校验
    - validate_backward_output 正常/异常/边界场景
    - confidence < 0.7 自动改 UNCERTAIN
    - 缺少/多余 case_id 检测
    - build_backward_scan_prompt 模板构建
    - _format_cases_for_prompt 格式化

使用纯 Pydantic 校验，无需数据库。
"""
import json
import pytest
from pydantic import ValidationError

from app.pipelines.prompts.backward_scan import (
    BACKWARD_SCAN_SYSTEM_PROMPT,
    BACKWARD_SCAN_USER_TEMPLATE,
    build_backward_scan_prompt,
    _format_cases_for_prompt,
    _format_steps_json,
)
from app.pipelines.schemas.backward_verdict import (
    BackwardVerdict,
    BackwardCaseVerdict,
    BackwardScanOutput,
    ValidationResult,
    validate_backward_output,
)


class TestBackwardVerdict:
    def test_five_verdict_values(self):
        assert len(BackwardVerdict) == 5
        assert BackwardVerdict.VALID.value == "VALID"
        assert BackwardVerdict.LOCATOR_ONLY.value == "LOCATOR_ONLY"
        assert BackwardVerdict.NEEDS_MODIFY.value == "NEEDS_MODIFY"
        assert BackwardVerdict.DEPRECATED.value == "DEPRECATED"
        assert BackwardVerdict.UNCERTAIN.value == "UNCERTAIN"


class TestBackwardCaseVerdict:
    def test_valid_verdict(self):
        v = BackwardCaseVerdict(
            case_id=1, verdict="VALID", confidence=0.9, hint="用例有效"
        )
        assert v.verdict == BackwardVerdict.VALID

    def test_normalize_lowercase_verdict(self):
        v = BackwardCaseVerdict(
            case_id=2, verdict="valid", confidence=0.8, hint="小写verdict"
        )
        assert v.verdict == BackwardVerdict.VALID

    def test_invalid_verdict_raises(self):
        with pytest.raises(ValidationError):
            BackwardCaseVerdict(
                case_id=3, verdict="INVALID", confidence=0.5, hint="非法"
            )

    def test_confidence_boundary_zero(self):
        v = BackwardCaseVerdict(
            case_id=4, verdict="VALID", confidence=0.0, hint="边界"
        )
        assert v.confidence == 0.0

    def test_confidence_boundary_one(self):
        v = BackwardCaseVerdict(
            case_id=5, verdict="VALID", confidence=1.0, hint="边界"
        )
        assert v.confidence == 1.0

    def test_empty_hint_raises(self):
        with pytest.raises(ValidationError):
            BackwardCaseVerdict(
                case_id=8, verdict="VALID", confidence=0.9, hint=""
            )

    def test_all_five_verdicts(self):
        for verdict_str in ["VALID", "LOCATOR_ONLY", "NEEDS_MODIFY", "DEPRECATED", "UNCERTAIN"]:
            v = BackwardCaseVerdict(
                case_id=10, verdict=verdict_str, confidence=0.8, hint=f"{verdict_str}测试"
            )
            assert v.verdict == BackwardVerdict(verdict_str)

    def test_confidence_above_one_raises(self):
        with pytest.raises(ValidationError):
            BackwardCaseVerdict(
                case_id=11, verdict="VALID", confidence=1.5, hint="超限"
            )

    def test_confidence_below_zero_raises(self):
        with pytest.raises(ValidationError):
            BackwardCaseVerdict(
                case_id=12, verdict="VALID", confidence=-0.1, hint="超限"
            )


class TestBackwardScanOutput:
    def test_valid_output(self):
        output = BackwardScanOutput(verdicts=[
            BackwardCaseVerdict(case_id=1, verdict="VALID", confidence=0.9, hint="有效"),
            BackwardCaseVerdict(case_id=2, verdict="NEEDS_MODIFY", confidence=0.8, hint="需修改"),
        ])
        assert len(output.verdicts) == 2

    def test_duplicate_case_id_raises(self):
        with pytest.raises(ValidationError, match="Duplicate"):
            BackwardScanOutput(verdicts=[
                BackwardCaseVerdict(case_id=1, verdict="VALID", confidence=0.9, hint="有效"),
                BackwardCaseVerdict(case_id=1, verdict="DEPRECATED", confidence=0.7, hint="重复"),
            ])

    def test_empty_verdicts_list(self):
        output = BackwardScanOutput(verdicts=[])
        assert len(output.verdicts) == 0


class TestValidateBackwardOutput:
    def test_valid_output(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
                {"case_id": 2, "verdict": "NEEDS_MODIFY", "confidence": 0.8, "hint": "需修改"},
            ]
        }
        result = validate_backward_output(raw)
        assert result.valid is True
        assert result.output is not None
        assert len(result.output.verdicts) == 2

    def test_none_input(self):
        result = validate_backward_output(None)
        assert result.valid is False
        assert "为空" in result.errors[0]

    def test_invalid_json_string(self):
        result = validate_backward_output("not json{{{")
        assert result.valid is False
        assert "JSON" in result.errors[0]

    def test_valid_json_string(self):
        raw = json.dumps({
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
            ]
        })
        result = validate_backward_output(raw)
        assert result.valid is True

    def test_list_instead_of_dict(self):
        raw = [
            {"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
        ]
        result = validate_backward_output(raw)
        assert result.valid is True

    def test_missing_verdicts_key(self):
        raw = {"data": []}
        result = validate_backward_output(raw)
        assert result.valid is False

    def test_low_confidence_auto_corrected(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.5, "hint": "低置信度"},
            ]
        }
        result = validate_backward_output(raw)
        assert result.valid is True
        assert len(result.auto_corrected) == 1
        assert "UNCERTAIN" in result.auto_corrected[0]
        assert result.output.verdicts[0].verdict == BackwardVerdict.UNCERTAIN

    def test_confidence_0_7_not_auto_corrected(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.7, "hint": "刚好0.7"},
            ]
        }
        result = validate_backward_output(raw)
        assert result.valid is True
        assert len(result.auto_corrected) == 0
        assert result.output.verdicts[0].verdict == BackwardVerdict.VALID

    def test_uncertain_verdict_not_double_corrected(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "UNCERTAIN", "confidence": 0.3, "hint": "已是不确定"},
            ]
        }
        result = validate_backward_output(raw)
        assert result.valid is True
        assert len(result.auto_corrected) == 0

    def test_missing_case_ids(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
            ]
        }
        result = validate_backward_output(raw, expected_case_ids=[1, 2, 3])
        assert result.valid is False
        assert any("缺少" in e for e in result.errors)

    def test_extra_case_ids(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
                {"case_id": 99, "verdict": "VALID", "confidence": 0.9, "hint": "多余"},
            ]
        }
        result = validate_backward_output(raw, expected_case_ids=[1])
        assert result.valid is False
        assert any("多余" in e for e in result.errors)

    def test_all_case_ids_match(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": "有效"},
                {"case_id": 2, "verdict": "NEEDS_MODIFY", "confidence": 0.8, "hint": "需修改"},
            ]
        }
        result = validate_backward_output(raw, expected_case_ids=[1, 2])
        assert result.valid is True

    def test_schema_validation_failure(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "INVALID_VERDICT", "confidence": 0.9, "hint": "非法"},
            ]
        }
        result = validate_backward_output(raw)
        assert result.valid is False
        assert "Schema" in result.errors[0]

    def test_empty_hint_fails_schema(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": ""},
            ]
        }
        result = validate_backward_output(raw)
        assert result.valid is False

    def test_multiple_auto_corrections(self):
        raw = {
            "verdicts": [
                {"case_id": 1, "verdict": "VALID", "confidence": 0.3, "hint": "低"},
                {"case_id": 2, "verdict": "NEEDS_MODIFY", "confidence": 0.5, "hint": "也低"},
                {"case_id": 3, "verdict": "DEPRECATED", "confidence": 0.9, "hint": "高"},
            ]
        }
        result = validate_backward_output(raw, expected_case_ids=[1, 2, 3])
        assert result.valid is True
        assert len(result.auto_corrected) == 2
        assert result.output.verdicts[0].verdict == BackwardVerdict.UNCERTAIN
        assert result.output.verdicts[1].verdict == BackwardVerdict.UNCERTAIN
        assert result.output.verdicts[2].verdict == BackwardVerdict.DEPRECATED


class TestBuildBackwardScanPrompt:
    def test_basic_prompt(self):
        cases = [
            {"case_id": 1, "title": "登录测试", "module": "用户", "summary": "验证登录", "priority": 1, "lifecycle_status": "active"},
        ]
        prompt = build_backward_scan_prompt(
            change_signals="接口 /api/login 新增 captcha 字段",
            cases=cases,
            module_label="用户管理",
        )
        assert "captcha" in prompt
        assert "登录测试" in prompt
        assert "用户管理" in prompt

    def test_no_module_label(self):
        cases = [
            {"case_id": 2, "title": "查询测试", "module": "订单", "summary": "验证查询", "priority": 2, "lifecycle_status": "active"},
        ]
        prompt = build_backward_scan_prompt(
            change_signals="订单查询接口变更",
            cases=cases,
        )
        assert "全部" in prompt

    def test_empty_cases(self):
        prompt = build_backward_scan_prompt(
            change_signals="无变更",
            cases=[],
        )
        assert "无现有用例" in prompt

    def test_system_prompt_contains_verdicts(self):
        assert "VALID" in BACKWARD_SCAN_SYSTEM_PROMPT
        assert "LOCATOR_ONLY" in BACKWARD_SCAN_SYSTEM_PROMPT
        assert "NEEDS_MODIFY" in BACKWARD_SCAN_SYSTEM_PROMPT
        assert "DEPRECATED" in BACKWARD_SCAN_SYSTEM_PROMPT
        assert "UNCERTAIN" in BACKWARD_SCAN_SYSTEM_PROMPT


class TestFormatCasesForPrompt:
    def test_format_single_case(self):
        cases = [
            {"case_id": 1, "title": "测试", "module": "模块A", "summary": "摘要", "priority": 1, "lifecycle_status": "active"},
        ]
        text = _format_cases_for_prompt(cases)
        assert "用例 #1" in text
        assert "测试" in text

    def test_format_empty_list(self):
        text = _format_cases_for_prompt([])
        assert "无现有用例" in text

    def test_format_multiple_cases(self):
        cases = [
            {"case_id": 1, "title": "用例1", "module": "模块A", "summary": "摘要1", "priority": 1, "lifecycle_status": "active"},
            {"case_id": 2, "title": "用例2", "module": "模块B", "summary": "摘要2", "priority": 2, "lifecycle_status": "active"},
        ]
        text = _format_cases_for_prompt(cases)
        assert "用例 #1" in text
        assert "用例 #2" in text

    def test_format_cases_with_steps_json(self):
        cases = [
            {
                "case_id": 1,
                "title": "步骤测试",
                "module": "模块A",
                "summary": "摘要",
                "priority": 1,
                "lifecycle_status": "active",
                "precondition": "用户已登录",
                "steps_json": [{"step": "点击提交", "expected": "提交成功"}],
            },
        ]
        text = _format_cases_for_prompt(cases)
        assert "前置条件: 用户已登录" in text
        assert "点击提交" in text


class TestFormatStepsJson:
    def test_none_steps(self):
        assert _format_steps_json(None) == "无"

    def test_empty_list(self):
        assert _format_steps_json([]) == "无"

    def test_valid_steps(self):
        steps = [{"step": "点击登录", "expected": "登录成功"}]
        result = _format_steps_json(steps)
        assert "点击登录" in result

    def test_non_serializable_steps(self):
        class BadObj:
            def __str__(self):
                return "bad-obj-str"

        result = _format_steps_json(BadObj())
        assert "bad-obj-str" in result


class TestNormalizeVerdictNonString:
    def test_int_verdict_passes_through(self):
        with pytest.raises(ValidationError):
            BackwardCaseVerdict(
                case_id=20, verdict=123, confidence=0.9, hint="整数verdict"
            )

    def test_non_string_non_matching_upper(self):
        with pytest.raises(ValidationError):
            BackwardCaseVerdict(
                case_id=21, verdict="UNKNOWN_VERDICT", confidence=0.9, hint="非法字符串"
            )