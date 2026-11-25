"""B6b 前置护栏：`quality/validators` 三处拆分前后的行为锁定。

覆盖导入格式完整性、资料冲突判定与 UI 元素名收集（含嵌套 dict/list 递归、
通用词/短名过滤），保证「提取而不重排」的拆分不改变判定结果。
"""

import pytest

from app.services.quality.validators.base import Severity, ValidationIssue
from app.services.quality.validators.import_result_validator import ImportResultValidator
from app.services.quality.validators.material_conflict_validator import MaterialConflictValidator
from app.services.quality.validators.ui_reference_validator import UIReferenceValidator


class TestWorstSeverity:
    @pytest.mark.parametrize(
        ("severities", "expected"),
        [
            ([], "passed"),
            (["warning"], "warning"),
            (["warning", "rejected"], "rejected"),
            (["pending_review", "warning"], "pending_review"),
            (["passed", "warning"], "warning"),
        ],
    )
    def test_picks_max(self, severities, expected):
        from app.services.quality.validators.base import worst_severity

        issues = [ValidationIssue(field="f", message="m", severity=s) for s in severities]
        assert worst_severity(issues) == expected

    def test_severity_order_is_monotonic(self):
        assert Severity.rejected > Severity.pending_review > Severity.warning > Severity.passed


class TestImportResultValidator:
    def setup_method(self):
        self.validator = ImportResultValidator()

    def _valid_case(self):
        return {
            "title": "登录成功",
            "module": "登录",
            "steps": [{"action": "点击登录", "expected_result": "进入首页"}],
        }

    def test_non_import_source_skips(self):
        result = self.validator.validate(self._valid_case(), {"source": "ai"})
        assert result.status == "passed"
        assert result.issues == []

    def test_valid_case_passes(self):
        result = self.validator.validate(self._valid_case(), {"source": "import"})
        assert result.status == "passed"

    def test_missing_title_rejected(self):
        case = {**self._valid_case(), "title": "   "}
        result = self.validator.validate(case, {"source": "import"})
        assert result.status == "rejected"
        assert [i.field for i in result.issues] == ["title"]

    def test_missing_steps_rejected(self):
        case = {**self._valid_case(), "steps": None}
        result = self.validator.validate(case, {"source": "import"})
        assert result.status == "rejected"
        assert [i.field for i in result.issues] == ["steps"]
        assert "缺少步骤列表" in result.issues[0].message

    def test_steps_not_list_rejected(self):
        case = {**self._valid_case(), "steps": {"action": "x"}}
        result = self.validator.validate(case, {"source": "import"})
        assert result.status == "rejected"
        assert "必须为列表" in result.issues[0].message

    def test_step_not_dict_rejected(self):
        case = {**self._valid_case(), "steps": ["点击登录"]}
        result = self.validator.validate(case, {"source": "import"})
        assert result.status == "rejected"
        assert result.issues[0].field == "steps[0]"
        assert "不是有效的字典" in result.issues[0].message

    def test_step_missing_action_and_expected(self):
        case = {**self._valid_case(), "steps": [{"action": " ", "expected_result": ""}]}
        result = self.validator.validate(case, {"source": "import"})
        assert [i.field for i in result.issues] == ["steps[0].action", "steps[0].expected_result"]

    def test_step_description_counts_as_action(self):
        case = {**self._valid_case(), "steps": [{"description": "描述式动作", "expected_result": "OK"}]}
        assert self.validator.validate(case, {"source": "import"}).status == "passed"

    def test_missing_module_is_warning(self):
        case = {**self._valid_case(), "module": ""}
        result = self.validator.validate(case, {"source": "import"})
        assert result.status == "warning"
        assert result.issues[0].severity == "warning"

    def test_worst_issue_wins(self):
        case = {"title": "", "module": "", "steps": [{"action": "a", "expected_result": "b"}]}
        result = self.validator.validate(case, {"source": "import"})
        assert result.status == "rejected"
        assert len(result.issues) == 2


class TestMaterialConflictValidator:
    def setup_method(self):
        self.validator = MaterialConflictValidator()

    def _context(self, **overrides):
        ctx = {"requirement_keywords": {"登录", "下单"}, "ui_screen_names": {"登录页", "订单页"}}
        ctx.update(overrides)
        return ctx

    def test_missing_context_passes(self):
        assert self.validator.validate({"title": "登录"}, {}).status == "passed"
        assert self.validator.validate({"title": "登录"}, {"requirement_keywords": {"登录"}}).status == "passed"

    def test_requirement_without_ui_is_pending_review(self):
        result = self.validator.validate({"title": "登录流程验证"}, self._context())
        assert result.status == "pending_review"
        assert "未匹配到任何UI界面名称" in result.issues[0].message

    def test_ui_without_requirement_is_warning(self):
        result = self.validator.validate({"title": "订单页截图"}, self._context())
        assert result.status == "warning"
        assert "未匹配到任何需求关键词" in result.issues[0].message

    def test_both_matched_passes(self):
        assert self.validator.validate({"title": "登录页与登录"}, self._context()).status == "passed"

    def test_matching_is_case_insensitive(self):
        ctx = {"requirement_keywords": {"Login"}, "ui_screen_names": {"login page"}}
        assert self.validator.validate({"title": "login page check"}, ctx).status == "passed"

    def test_steps_description_fallback(self):
        case = {"title": "", "steps": [{"description": "进入订单页并完成下单"}]}
        assert self.validator.validate(case, self._context()).status == "passed"

    def test_non_string_keywords_ignored(self):
        ctx = {"requirement_keywords": {123}, "ui_screen_names": {None}}
        result = self.validator.validate({"title": "登录"}, ctx)
        assert result.status == "passed"

    def test_conflict_message_truncates_to_three(self):
        ctx = {"requirement_keywords": {"登录", "下单", "支付", "退款"}, "ui_screen_names": {"无关页"}}
        result = self.validator.validate({"title": "登录下单支付退款"}, ctx)
        assert result.issues[0].message.count("'") == 6  # 三个关键词各一对引号


class TestUIReferenceCollectNames:
    def setup_method(self):
        self.validator = UIReferenceValidator()

    def test_nested_dict_and_list(self):
        specs = [
            {
                "screen_name": "登录页",
                "ui_spec": {
                    "elements": [
                        {"name": "账号输入框", "meta": {"label": "深度标签"}},
                        {"children": [{"text": "子节点按钮"}]},
                    ]
                },
            }
        ]
        names = self.validator._collect_ui_element_names(specs)
        assert "登录页" in names
        assert "账号输入框" in names
        assert "深度标签" in names
        assert "子节点按钮" in names

    def test_scalar_under_ui_key_via_list(self):
        # 元素键的值为列表时：dict 分支先 add(list) 无效，随后 list 分支把 key_hint 下传，
        # 标量再由 `elif key_hint in keys` 分支收集
        specs = [{"ui_spec": {"name": ["纯文本标签"]}}]
        assert "纯文本标签" in self.validator._collect_ui_element_names(specs)

    def test_generic_words_and_short_names_filtered(self):
        specs = [{"screen_name": "页面", "ui_spec": {"name": "按", "text": "登录"}}]
        names = self.validator._collect_ui_element_names(specs)
        assert "页面" not in names
        assert "按" not in names
        assert "登录" in names

    def test_non_dict_spec_item_skipped(self):
        assert self.validator._collect_ui_element_names([None, "x", 1]) == set()

    def test_none_specs(self):
        assert self.validator._collect_ui_element_names(None) == set()

    def test_unknown_keys_ignored(self):
        specs = [{"ui_spec": {"unknown_key": "不该被收集"}}]
        assert "不该被收集" not in self.validator._collect_ui_element_names(specs)

    def test_validate_uses_context_min_hit_rate(self):
        ctx = {
            "ui_specs": [{"ui_spec": {"name": "账号输入框"}}],
            "ui_min_hit_rate": 0.5,
        }
        case = {"steps": [{"action": "点击【账号输入框】"}, {"action": "点击【未知元素】"}]}
        result = self.validator.validate(case, ctx)
        assert result.status == "passed"  # 命中 1/2 ≥ 0.5
