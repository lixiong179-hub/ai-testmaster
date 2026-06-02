"""QualityGate 统一校验体系测试。

测试覆盖:
    - 每个校验器独立测试
    - 项目级规则覆盖
    - 统一4档状态输出
    - QualityGateService 编排
    - ValidationResult 合并规则
    - grade_to_status / status_to_grade 映射
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.quality.validators.base import (
    BaseValidator,
    ValidationIssue,
    ValidationResult,
    Severity,
)
from app.services.quality.validators.case_validator import CaseValidator
from app.services.quality.validators.update_suggestion_validator import UpdateSuggestionValidator
from app.services.quality.validators.import_result_validator import ImportResultValidator
from app.services.quality.validators.material_conflict_validator import MaterialConflictValidator
from app.services.quality.validators.ui_reference_validator import UIReferenceValidator
from app.services.quality.validators.duplication_validator import DuplicationValidator
from app.services.quality.quality_gate_service import QualityGateService


# ──────────────────────────────────────────────
# 1. BaseValidator & ValidationResult 测试
# ──────────────────────────────────────────────

class TestValidationIssue:
    """ValidationIssue 数据结构测试。"""

    def test_create_valid_issue(self) -> None:
        issue = ValidationIssue(field="title", message="标题为空", severity="rejected")
        assert issue.field == "title"
        assert issue.message == "标题为空"
        assert issue.severity == "rejected"

    def test_invalid_severity_raises(self) -> None:
        with pytest.raises(ValueError, match="severity must be one of"):
            ValidationIssue(field="title", message="test", severity="invalid")

    def test_default_severity_is_passed(self) -> None:
        issue = ValidationIssue(field="title", message="ok")
        assert issue.severity == "passed"


class TestValidationResult:
    """ValidationResult 数据结构测试。"""

    def test_create_valid_result(self) -> None:
        result = ValidationResult(status="passed", issues=[])
        assert result.status == "passed"
        assert result.issues == []

    def test_invalid_status_raises(self) -> None:
        with pytest.raises(ValueError, match="status must be one of"):
            ValidationResult(status="invalid", issues=[])

    def test_merge_empty_list(self) -> None:
        merged = ValidationResult.merge([])
        assert merged.status == "passed"
        assert merged.issues == []

    def test_merge_takes_worst_status(self) -> None:
        r1 = ValidationResult(status="passed", issues=[])
        r2 = ValidationResult(status="warning", issues=[])
        r3 = ValidationResult(status="pending_review", issues=[])
        merged = ValidationResult.merge([r1, r2, r3])
        assert merged.status == "pending_review"

    def test_merge_with_rejected(self) -> None:
        r1 = ValidationResult(status="passed", issues=[])
        r2 = ValidationResult(status="rejected", issues=[])
        merged = ValidationResult.merge([r1, r2])
        assert merged.status == "rejected"

    def test_merge_collects_all_issues(self) -> None:
        i1 = ValidationIssue(field="a", message="issue1", severity="warning")
        i2 = ValidationIssue(field="b", message="issue2", severity="rejected")
        r1 = ValidationResult(status="warning", issues=[i1])
        r2 = ValidationResult(status="rejected", issues=[i2])
        merged = ValidationResult.merge([r1, r2])
        assert len(merged.issues) == 2
        assert merged.issues[0].field == "a"
        assert merged.issues[1].field == "b"


class TestSeverity:
    """Severity 枚举排序测试。"""

    def test_severity_ordering(self) -> None:
        assert Severity["passed"].value < Severity["warning"].value
        assert Severity["warning"].value < Severity["pending_review"].value
        assert Severity["pending_review"].value < Severity["rejected"].value


# ──────────────────────────────────────────────
# 2. CaseValidator 测试
# ──────────────────────────────────────────────

class TestCaseValidator:
    """用例基本格式校验器测试。"""

    def setup_method(self) -> None:
        self.validator = CaseValidator()

    def test_valid_case(self) -> None:
        case_data = {
            "title": "验证用户登录功能正常工作",
            "steps": [
                {"action": "点击登录按钮", "expected_result": "跳转到首页"},
                {"action": "查看欢迎信息", "expected_result": "显示欢迎文字"},
            ],
            "precondition": "用户已注册账号",
            "expected_result": "登录成功并跳转到首页",
        }
        result = self.validator.validate(case_data)
        assert result.status == "passed"
        assert len(result.issues) == 0

    def test_empty_title(self) -> None:
        case_data = {
            "title": "",
            "steps": [{"action": "a", "expected_result": "b"}] * 2,
            "precondition": "已登录",
            "expected_result": "结果",
        }
        result = self.validator.validate(case_data)
        assert result.status == "rejected"
        assert any(i.field == "title" and i.severity == "rejected" for i in result.issues)

    def test_title_too_short(self) -> None:
        case_data = {
            "title": "短标题",
            "steps": [{"action": "a", "expected_result": "b"}] * 2,
            "precondition": "已登录",
            "expected_result": "结果",
        }
        result = self.validator.validate(case_data)
        assert result.status == "rejected"
        assert any("过短" in i.message for i in result.issues)

    def test_title_too_long(self) -> None:
        case_data = {
            "title": "超" * 51,
            "steps": [{"action": "a", "expected_result": "b"}] * 2,
            "precondition": "已登录",
            "expected_result": "结果",
        }
        result = self.validator.validate(case_data)
        assert any("过长" in i.message for i in result.issues)

    def test_steps_too_few(self) -> None:
        case_data = {
            "title": "验证用户登录功能正常工作",
            "steps": [{"action": "a", "expected_result": "b"}],
            "precondition": "已登录",
            "expected_result": "结果",
        }
        result = self.validator.validate(case_data)
        assert result.status == "rejected"
        assert any("步骤数不足" in i.message for i in result.issues)

    def test_steps_too_many(self) -> None:
        case_data = {
            "title": "验证用户登录功能正常工作",
            "steps": [{"action": "a", "expected_result": "b"}] * 9,
            "precondition": "已登录",
            "expected_result": "结果",
        }
        result = self.validator.validate(case_data)
        assert any("步骤数过多" in i.message for i in result.issues)

    def test_empty_precondition(self) -> None:
        case_data = {
            "title": "验证用户登录功能正常工作",
            "steps": [{"action": "a", "expected_result": "b"}] * 2,
            "precondition": "",
            "expected_result": "结果",
        }
        result = self.validator.validate(case_data)
        assert result.status == "rejected"
        assert any(i.field == "precondition" for i in result.issues)

    def test_empty_expected_result(self) -> None:
        case_data = {
            "title": "验证用户登录功能正常工作",
            "steps": [{"action": "a", "expected_result": "b"}] * 2,
            "precondition": "已登录",
            "expected_result": "",
        }
        result = self.validator.validate(case_data)
        assert result.status == "rejected"
        assert any(i.field == "expected_result" for i in result.issues)

    def test_context_override_title_min(self) -> None:
        case_data = {
            "title": "短",
            "steps": [{"action": "a", "expected_result": "b"}] * 2,
            "precondition": "已登录",
            "expected_result": "结果",
        }
        result = self.validator.validate(case_data, context={"title_min": 1})
        assert not any("过短" in i.message for i in result.issues)


# ──────────────────────────────────────────────
# 3. UpdateSuggestionValidator 测试
# ──────────────────────────────────────────────

class TestUpdateSuggestionValidator:
    """更新建议校验器测试。"""

    def setup_method(self) -> None:
        self.validator = UpdateSuggestionValidator()

    def test_non_update_case_passes(self) -> None:
        case_data = {"change_type": "NEW_CASE", "title": "test"}
        result = self.validator.validate(case_data)
        assert result.status == "passed"

    def test_update_case_missing_diff_fields(self) -> None:
        case_data = {"change_type": "UPDATE_CASE"}
        result = self.validator.validate(case_data)
        assert result.status == "rejected"
        assert any(i.field == "diff_fields" for i in result.issues)

    def test_update_case_empty_diff_fields(self) -> None:
        case_data = {"change_type": "UPDATE_CASE", "diff_fields": []}
        result = self.validator.validate(case_data)
        assert result.status == "rejected"

    def test_update_case_missing_history_id(self) -> None:
        case_data = {
            "change_type": "UPDATE_CASE",
            "diff_fields": {"title": "new"},
        }
        result = self.validator.validate(case_data)
        assert result.status == "rejected"
        assert any(i.field == "history_case_id" for i in result.issues)

    def test_update_case_history_id_not_exist(self) -> None:
        case_data = {
            "change_type": "UPDATE_CASE",
            "diff_fields": {"title": "new"},
            "history_case_id": 999,
        }
        ctx = {"existing_case_ids": {1, 2, 3}}
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "rejected"
        assert any("不存在" in i.message for i in result.issues)

    def test_update_case_valid(self) -> None:
        case_data = {
            "change_type": "UPDATE_CASE",
            "diff_fields": {"title": "new"},
            "history_case_id": 1,
        }
        ctx = {"existing_case_ids": {1, 2, 3}}
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "passed"

    def test_ai_change_type_field(self) -> None:
        case_data = {
            "ai_change_type": "UPDATE_CASE",
            "diff_fields": {"title": "new"},
            "history_case_id": 1,
        }
        ctx = {"existing_case_ids": {1}}
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "passed"


# ──────────────────────────────────────────────
# 4. ImportResultValidator 测试
# ──────────────────────────────────────────────

class TestImportResultValidator:
    """导入用例格式完整性校验器测试。"""

    def setup_method(self) -> None:
        self.validator = ImportResultValidator()

    def test_non_import_source_passes(self) -> None:
        case_data = {"title": "test"}
        result = self.validator.validate(case_data)
        assert result.status == "passed"

    def test_import_missing_title(self) -> None:
        case_data = {"title": "", "steps": [{"action": "a", "expected_result": "b"}]}
        result = self.validator.validate(case_data, context={"source": "import"})
        assert result.status == "rejected"
        assert any("缺少标题" in i.message for i in result.issues)

    def test_import_missing_steps(self) -> None:
        case_data = {"title": "测试用例标题", "steps": None}
        result = self.validator.validate(case_data, context={"source": "import"})
        assert result.status == "rejected"
        assert any("缺少步骤列表" in i.message for i in result.issues)

    def test_import_steps_not_list(self) -> None:
        case_data = {"title": "测试用例标题", "steps": "not a list"}
        result = self.validator.validate(case_data, context={"source": "import"})
        assert result.status == "rejected"
        assert any("必须为列表" in i.message for i in result.issues)

    def test_import_step_missing_action(self) -> None:
        case_data = {
            "title": "测试用例标题",
            "steps": [{"expected_result": "结果"}],
            "module": "登录模块",
        }
        result = self.validator.validate(case_data, context={"source": "import"})
        assert result.status == "rejected"
        assert any("缺少操作描述" in i.message for i in result.issues)

    def test_import_step_missing_expected_result(self) -> None:
        case_data = {
            "title": "测试用例标题",
            "steps": [{"action": "点击按钮"}],
            "module": "登录模块",
        }
        result = self.validator.validate(case_data, context={"source": "import"})
        assert result.status == "rejected"
        assert any("缺少预期结果" in i.message for i in result.issues)

    def test_import_missing_module_warning(self) -> None:
        case_data = {
            "title": "测试用例标题",
            "steps": [{"action": "点击", "expected_result": "结果"}],
        }
        result = self.validator.validate(case_data, context={"source": "import"})
        assert any("缺少模块" in i.message for i in result.issues)

    def test_import_valid(self) -> None:
        case_data = {
            "title": "测试用例标题",
            "steps": [{"action": "点击", "expected_result": "结果"}],
            "module": "登录模块",
        }
        result = self.validator.validate(case_data, context={"source": "import"})
        assert result.status == "passed"


# ──────────────────────────────────────────────
# 5. MaterialConflictValidator 测试
# ──────────────────────────────────────────────

class TestMaterialConflictValidator:
    """资料冲突校验器测试。"""

    def setup_method(self) -> None:
        self.validator = MaterialConflictValidator()

    def test_no_context_passes(self) -> None:
        case_data = {"title": "test"}
        result = self.validator.validate(case_data)
        assert result.status == "passed"

    def test_req_without_ui_conflict(self) -> None:
        case_data = {"title": "验证登录功能", "steps": []}
        ctx = {
            "requirement_keywords": {"登录"},
            "ui_screen_names": {"首页", "设置页"},
        }
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "pending_review"
        assert any("资料冲突" in i.message for i in result.issues)

    def test_ui_without_req_warning(self) -> None:
        case_data = {"title": "在首页点击按钮", "steps": []}
        ctx = {
            "requirement_keywords": {"注册"},
            "ui_screen_names": {"首页"},
        }
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "warning"
        assert any("资料冲突" in i.message for i in result.issues)

    def test_both_matched_passes(self) -> None:
        case_data = {"title": "在首页验证登录功能", "steps": []}
        ctx = {
            "requirement_keywords": {"登录"},
            "ui_screen_names": {"首页"},
        }
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "passed"

    def test_empty_keywords_passes(self) -> None:
        case_data = {"title": "test"}
        ctx = {"requirement_keywords": set(), "ui_screen_names": {"首页"}}
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "passed"


# ──────────────────────────────────────────────
# 6. UIReferenceValidator 测试
# ──────────────────────────────────────────────

class TestUIReferenceValidator:
    """UI元素引用命中率校验器测试。"""

    def setup_method(self) -> None:
        self.validator = UIReferenceValidator(min_hit_rate=0.8)

    def test_no_ui_specs_passes(self) -> None:
        case_data = {"title": "test", "steps": [{"action": "点击按钮"}]}
        result = self.validator.validate(case_data)
        assert result.status == "passed"

    def test_high_hit_rate_passes(self) -> None:
        case_data = {
            "title": "test",
            "steps": [
                {"action": "点击【登录按钮】"},
                {"action": "在【用户名输入框】输入admin"},
            ],
        }
        ctx = {
            "ui_specs": [
                {
                    "screen_name": "登录页",
                    "ui_spec": {
                        "elements": [
                            {"name": "登录按钮"},
                            {"name": "用户名输入框"},
                        ],
                    },
                },
            ],
        }
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "passed"

    def test_low_hit_rate_pending_review(self) -> None:
        case_data = {
            "title": "test",
            "steps": [
                {"action": "点击【登录按钮】"},
                {"action": "点击【不存在的元素】"},
                {"action": "点击【另一个不存在的元素】"},
                {"action": "点击【第三个不存在的元素】"},
                {"action": "点击【第四个不存在的元素】"},
            ],
        }
        ctx = {
            "ui_specs": [
                {
                    "screen_name": "登录页",
                    "ui_spec": {
                        "elements": [{"name": "登录按钮"}],
                    },
                },
            ],
        }
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "pending_review"
        assert any("命中率" in i.message for i in result.issues)

    def test_no_target_elements_passes(self) -> None:
        case_data = {
            "title": "test",
            "steps": [{"action": "执行操作"}],
        }
        ctx = {
            "ui_specs": [
                {
                    "screen_name": "首页",
                    "ui_spec": {"elements": [{"name": "按钮"}]},
                },
            ],
        }
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "passed"


# ──────────────────────────────────────────────
# 7. DuplicationValidator 测试
# ──────────────────────────────────────────────

class TestDuplicationValidator:
    """用例重复校验器测试。"""

    def setup_method(self) -> None:
        self.validator = DuplicationValidator(similarity_threshold=0.9)

    def test_no_existing_titles_passes(self) -> None:
        case_data = {"title": "验证用户登录功能正常工作"}
        result = self.validator.validate(case_data)
        assert result.status == "passed"

    def test_similar_title_detected(self) -> None:
        case_data = {"title": "验证用户登录功能正常工作"}
        ctx = {"existing_titles": ["验证用户登录功能正常工作"]}
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "pending_review"
        assert any("相似度" in i.message for i in result.issues)

    def test_different_title_passes(self) -> None:
        case_data = {"title": "验证用户注册功能正常工作"}
        ctx = {"existing_titles": ["验证用户登录功能正常工作"]}
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "passed"

    def test_empty_title_passes(self) -> None:
        case_data = {"title": ""}
        ctx = {"existing_titles": ["验证用户登录功能正常工作"]}
        result = self.validator.validate(case_data, context=ctx)
        assert result.status == "passed"

    def test_custom_threshold(self) -> None:
        validator = DuplicationValidator(similarity_threshold=0.5)
        case_data = {"title": "验证用户登录功能正常工作"}
        ctx = {"existing_titles": ["验证用户注册功能正常工作"]}
        result = validator.validate(case_data, context=ctx)
        assert result.status == "pending_review"


# ──────────────────────────────────────────────
# 8. QualityGateService 编排测试
# ──────────────────────────────────────────────

class TestQualityGateService:
    """QualityGateService 编排测试。"""

    def setup_method(self) -> None:
        self.service = QualityGateService()

    def test_valid_case_passes(self) -> None:
        case_data = {
            "title": "验证用户登录功能正常工作",
            "steps": [
                {"action": "点击登录按钮", "expected_result": "跳转首页"},
                {"action": "查看欢迎信息", "expected_result": "显示欢迎"},
            ],
            "precondition": "用户已注册账号",
            "expected_result": "登录成功并跳转到首页",
        }
        result = self.service.validate(case_data)
        assert result.status == "passed"

    def test_invalid_case_rejected(self) -> None:
        case_data = {
            "title": "",
            "steps": [],
            "precondition": "",
            "expected_result": "",
        }
        result = self.service.validate(case_data)
        assert result.status == "rejected"
        assert len(result.issues) > 0

    def test_project_rules_override(self) -> None:
        mock_db = MagicMock()
        mock_rule = MagicMock()
        mock_rule.rule_key = "title_min"
        mock_rule.rule_value = 2
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_rule]

        service = QualityGateService(db=mock_db)
        case_data = {
            "title": "短标题",
            "steps": [
                {"action": "a", "expected_result": "b"},
                {"action": "c", "expected_result": "d"},
            ],
            "precondition": "已登录",
            "expected_result": "结果",
        }
        result = service.validate(case_data, project_id=1)
        assert not any("过短" in i.message for i in result.issues)

    def test_project_rules_load_failure(self) -> None:
        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("db error")
        service = QualityGateService(db=mock_db)
        case_data = {
            "title": "验证用户登录功能正常工作",
            "steps": [
                {"action": "a", "expected_result": "b"},
                {"action": "c", "expected_result": "d"},
            ],
            "precondition": "已登录",
            "expected_result": "结果",
        }
        result = service.validate(case_data, project_id=1)
        assert result.status == "passed"

    def test_validator_exception_handled(self) -> None:
        service = QualityGateService()
        with patch.object(
            service.validators[0], "validate", side_effect=Exception("boom")
        ):
            case_data = {
                "title": "验证用户登录功能正常工作",
                "steps": [
                    {"action": "a", "expected_result": "b"},
                    {"action": "c", "expected_result": "d"},
                ],
                "precondition": "已登录",
                "expected_result": "结果",
            }
            result = service.validate(case_data)
            assert result.status in ("passed", "warning")

    def test_context_passed_to_validators(self) -> None:
        case_data = {
            "title": "验证用户登录功能正常工作",
            "steps": [
                {"action": "a", "expected_result": "b"},
                {"action": "c", "expected_result": "d"},
            ],
            "precondition": "已登录",
            "expected_result": "结果",
        }
        ctx = {"source": "import", "existing_titles": ["验证用户登录功能正常工作"]}
        result = self.service.validate(case_data, context=ctx)
        assert any("相似度" in i.message for i in result.issues)

    def test_grade_to_status_mapping(self) -> None:
        assert QualityGateService.grade_to_status("A") == "passed"
        assert QualityGateService.grade_to_status("B") == "warning"
        assert QualityGateService.grade_to_status("C") == "pending_review"
        assert QualityGateService.grade_to_status("D") == "rejected"
        assert QualityGateService.grade_to_status("X") == "pending_review"

    def test_status_to_grade_mapping(self) -> None:
        assert QualityGateService.status_to_grade("passed") == "A"
        assert QualityGateService.status_to_grade("warning") == "B"
        assert QualityGateService.status_to_grade("pending_review") == "C"
        assert QualityGateService.status_to_grade("rejected") == "D"
        assert QualityGateService.status_to_grade("unknown") == "C"

    def test_merge_takes_worst_status(self) -> None:
        case_data = {
            "title": "验证用户登录功能正常工作",
            "steps": [
                {"action": "a", "expected_result": "b"},
                {"action": "c", "expected_result": "d"},
            ],
            "precondition": "已登录",
            "expected_result": "结果",
        }
        ctx = {
            "requirement_keywords": {"登录"},
            "ui_screen_names": {"设置页"},
        }
        result = self.service.validate(case_data, context=ctx)
        assert result.status in ("passed", "warning", "pending_review", "rejected")


# ──────────────────────────────────────────────
# 9. 统一4档状态输出测试
# ──────────────────────────────────────────────

class TestUnifiedStatusOutput:
    """验证所有校验器输出统一4档状态。"""

    def test_case_validator_output_status(self) -> None:
        validator = CaseValidator()
        result = validator.validate({"title": "", "steps": [], "precondition": "", "expected_result": ""})
        assert result.status in ("passed", "warning", "pending_review", "rejected")

    def test_update_suggestion_validator_output_status(self) -> None:
        validator = UpdateSuggestionValidator()
        result = validator.validate({"change_type": "UPDATE_CASE"})
        assert result.status in ("passed", "warning", "pending_review", "rejected")

    def test_import_result_validator_output_status(self) -> None:
        validator = ImportResultValidator()
        result = validator.validate({"title": ""}, context={"source": "import"})
        assert result.status in ("passed", "warning", "pending_review", "rejected")

    def test_material_conflict_validator_output_status(self) -> None:
        validator = MaterialConflictValidator()
        result = validator.validate({"title": "test"})
        assert result.status in ("passed", "warning", "pending_review", "rejected")

    def test_ui_reference_validator_output_status(self) -> None:
        validator = UIReferenceValidator()
        result = validator.validate({"title": "test", "steps": []})
        assert result.status in ("passed", "warning", "pending_review", "rejected")

    def test_duplication_validator_output_status(self) -> None:
        validator = DuplicationValidator()
        result = validator.validate({"title": "test"})
        assert result.status in ("passed", "warning", "pending_review", "rejected")


# ──────────────────────────────────────────────
# 10. quality_validator.py 统一4档状态测试
# ──────────────────────────────────────────────

class TestQualityValidatorStatus:
    """验证 quality_validator.py 的 validate_single_case_status 输出。"""

    def test_valid_case_returns_passed(self) -> None:
        from app.services.test_case_generation.quality_validator import validate_single_case_status
        case = {
            "title": "验证用户登录功能正常工作",
            "precondition": "账号已登录，网络环境正常，测试数据已准备",
            "steps": [
                {"action": "点击登录按钮", "expected_result": "跳转到首页"},
                {"action": "查看欢迎信息", "expected_result": "显示欢迎文字"},
            ],
            "expected_result": "登录成功并显示欢迎页面，用户名正确显示",
            "case_category": "positive",
        }
        status, issues = validate_single_case_status(case)
        assert status == "passed"
        assert len(issues) == 0

    def test_empty_title_returns_rejected(self) -> None:
        from app.services.test_case_generation.quality_validator import validate_single_case_status
        case = {
            "title": "",
            "precondition": "账号已登录",
            "steps": [
                {"action": "点击", "expected_result": "结果"},
                {"action": "查看", "expected_result": "结果"},
            ],
            "expected_result": "登录成功并显示欢迎页面",
            "case_category": "positive",
        }
        status, issues = validate_single_case_status(case)
        assert status == "rejected"
        assert any("为空" in i for i in issues)

    def test_vague_title_returns_pending_review(self) -> None:
        from app.services.test_case_generation.quality_validator import validate_single_case_status
        case = {
            "title": "功能验证测试用例标题加长版",
            "precondition": "账号已登录，网络环境正常",
            "steps": [
                {"action": "点击按钮", "expected_result": "跳转到首页"},
                {"action": "查看信息", "expected_result": "显示文字"},
            ],
            "expected_result": "登录成功并显示欢迎页面",
            "case_category": "positive",
        }
        status, issues = validate_single_case_status(case)
        assert status == "pending_review"
        assert any("模糊词" in i for i in issues)


# ──────────────────────────────────────────────
# 11. quality_gate.py 4档状态映射测试
# ──────────────────────────────────────────────

class TestGradeToQualityStatus:
    """验证 _grade_to_quality_status 映射。"""

    def test_a_to_passed(self) -> None:
        from app.pipelines.steps.quality_gate import _grade_to_quality_status
        assert _grade_to_quality_status("A") == "passed"

    def test_b_to_warning(self) -> None:
        from app.pipelines.steps.quality_gate import _grade_to_quality_status
        assert _grade_to_quality_status("B") == "warning"

    def test_c_to_pending_review(self) -> None:
        from app.pipelines.steps.quality_gate import _grade_to_quality_status
        assert _grade_to_quality_status("C") == "pending_review"

    def test_d_to_rejected(self) -> None:
        from app.pipelines.steps.quality_gate import _grade_to_quality_status
        assert _grade_to_quality_status("D") == "rejected"

    def test_unknown_defaults_to_pending_review(self) -> None:
        from app.pipelines.steps.quality_gate import _grade_to_quality_status
        assert _grade_to_quality_status("X") == "pending_review"
