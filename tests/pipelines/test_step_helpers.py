"""
M1-T11 Pipeline Steps 辅助函数单元测试

覆盖各 Step 的辅助函数、分支逻辑和边界场景，
确保核心分支覆盖率 ≥ 95%。
"""
import json
import pytest
from typing import Dict, Any

from app.pipelines.steps.signal_gatherer import (
    _load_file_content,
    _load_ui_from_input,
    _load_test_points_from_input,
    _parse_xmind_to_testpoints,
    _format_test_point,
    _compute_signal_confidence,
)
from app.pipelines.steps.testpoint_alignment._helpers import (
    _find_matching_screens,
    _is_significant_match,
    _is_cjk,
    _compute_alignment_confidence,
)
from app.pipelines.steps._parsing import (
    _parse_case_response,
    _enrich_case_data,
)
from app.pipelines.steps._signal_scoring import (
    _compute_prior_score,
    _score_to_grade,
)
from app.pipelines.steps.persist import _build_score_map
from app.pipelines.scenarios import get_scenario, get_scenario_by_version, list_scenarios


class TestLoadFileContent:
    def test_none_file_id_returns_empty(self, db, testProject):
        result = _load_file_content(
            ctx=_make_ctx(db, testProject), file_id=None, project_id=testProject.id
        )
        assert result == ""

    def test_zero_file_id_returns_empty(self, db, testProject):
        result = _load_file_content(
            ctx=_make_ctx(db, testProject), file_id=0, project_id=testProject.id
        )
        assert result == ""

    def test_nonexistent_file_id_returns_empty(self, db, testProject):
        result = _load_file_content(
            ctx=_make_ctx(db, testProject), file_id=99999, project_id=testProject.id
        )
        assert result == ""


class TestLoadUiFromInput:
    def test_with_payload_screen_ids(self, db, testProject):
        from app.models.ui_prototype import UIPrototypeScreen

        screen = UIPrototypeScreen(
            project_id=testProject.id,
            prototype_name="test_proto",
            screen_name="登录页",
            screen_order=1,
            parse_status="completed",
            summary="登录页面",
            ui_spec={"elements": [{"type": "button", "text": "登录"}]},
        )
        db.add(screen)
        db.flush()

        inp = _make_input(payload={"screen_ids": [screen.id]})
        ui_desc, ui_spec, fids = _load_ui_from_input(
            _make_ctx(db, testProject), inp, testProject.id
        )
        assert len(ui_desc) == 1
        assert ui_desc[0]["screen_name"] == "登录页"
        assert len(ui_spec) == 1

    def test_without_payload_falls_back_to_all_screens(self, db, testProject):
        from app.models.ui_prototype import UIPrototypeScreen

        for i in range(2):
            db.add(UIPrototypeScreen(
                project_id=testProject.id,
                prototype_name="proto",
                screen_name=f"页面{i}",
                screen_order=i,
                parse_status="completed",
                summary=f"页面{i}摘要",
                ui_spec={"elements": []},
            ))
        db.flush()

        inp = _make_input(payload=None)
        ui_desc, ui_spec, fids = _load_ui_from_input(
            _make_ctx(db, testProject), inp, testProject.id
        )
        assert len(ui_desc) >= 2

    def test_empty_payload_screen_ids_falls_back(self, db, testProject):
        from app.models.ui_prototype import UIPrototypeScreen

        db.add(UIPrototypeScreen(
            project_id=testProject.id,
            prototype_name="proto",
            screen_name="回退页面",
            screen_order=0,
            parse_status="completed",
            summary="摘要",
            ui_spec={"elements": []},
        ))
        db.flush()

        inp = _make_input(payload={"screen_ids": []})
        ui_desc, ui_spec, fids = _load_ui_from_input(
            _make_ctx(db, testProject), inp, testProject.id
        )
        assert len(ui_desc) >= 1

    def test_screen_without_ui_spec(self, db, testProject):
        from app.models.ui_prototype import UIPrototypeScreen

        screen = UIPrototypeScreen(
            project_id=testProject.id,
            prototype_name="proto",
            screen_name="无规格页面",
            screen_order=0,
            parse_status="completed",
            summary="摘要",
            ui_spec=None,
        )
        db.add(screen)
        db.flush()

        inp = _make_input(payload={"screen_ids": [screen.id]})
        ui_desc, ui_spec, fids = _load_ui_from_input(
            _make_ctx(db, testProject), inp, testProject.id
        )
        assert len(ui_desc) == 1
        assert len(ui_spec) == 0

    def test_with_file_id_fallback(self, db, testProject):
        from app.models.ui_prototype import UIPrototypeScreen
        from app.models.project import ProjectFile

        file_record = ProjectFile(
            project_id=testProject.id,
            file_name="ui_proto",
            file_url="/tmp/ui_proto.png",
            file_type="png",
            size=1024,
            resource_type="ui_mockup",
            extract_status="completed",
            content="",
        )
        db.add(file_record)
        db.flush()

        screen = UIPrototypeScreen(
            project_id=testProject.id,
            prototype_name="ui_proto",
            screen_name="UI页面",
            screen_order=0,
            parse_status="completed",
            summary="UI摘要",
            ui_spec={"elements": [{"type": "button", "text": "提交"}]},
        )
        db.add(screen)
        db.flush()

        inp = _make_input(payload=None, file_id=file_record.id)
        ui_desc, ui_spec, fids = _load_ui_from_input(
            _make_ctx(db, testProject), inp, testProject.id
        )
        assert len(ui_desc) >= 1
        assert file_record.id in fids


class TestLoadTestPointsFromInput:
    def test_with_payload_point_ids(self, db, testProject):
        from app.models.test_point import TestPoint

        tp = TestPoint(
            project_id=testProject.id,
            module="测试模块",
            point="测试点1",
            priority=1,
        )
        db.add(tp)
        db.flush()

        inp = _make_input(payload={"test_point_ids": [tp.id]})
        results = _load_test_points_from_input(_make_ctx(db, testProject), inp, testProject.id)
        assert len(results) == 1
        assert results[0]["id"] == tp.id
        assert results[0]["module"] == "测试模块"

    def test_without_payload_loads_all(self, db, testProject):
        from app.models.test_point import TestPoint

        for i in range(3):
            db.add(TestPoint(
                project_id=testProject.id,
                module=f"模块{i}",
                point=f"测试点{i}",
                priority=i + 1,
            ))
        db.flush()

        inp = _make_input(payload=None)
        results = _load_test_points_from_input(_make_ctx(db, testProject), inp, testProject.id)
        assert len(results) >= 3

    def test_empty_payload_point_ids(self, db, testProject):
        inp = _make_input(payload={"test_point_ids": []})
        from app.models.test_point import TestPoint
        for i in range(2):
            db.add(TestPoint(
                project_id=testProject.id,
                module=f"模块{i}",
                point=f"测试点{i}",
                priority=i + 1,
            ))
        db.flush()
        results = _load_test_points_from_input(_make_ctx(db, testProject), inp, testProject.id)
        assert len(results) >= 2


class TestParseXmindToTestpoints:
    def test_valid_json_array(self):
        payload = {
            "xmind_content": json.dumps([
                {"module": "登录", "point": "用户名验证", "priority": 1},
                {"module": "注册", "point": "邮箱格式", "priority": 2},
            ])
        }
        results = _parse_xmind_to_testpoints(payload, 1)
        assert len(results) == 2
        assert results[0]["module"] == "登录"
        assert results[1]["id"] == -2

    def test_valid_json_object(self):
        payload = {
            "xmind_content": json.dumps({"module": "登录", "point": "密码验证"})
        }
        results = _parse_xmind_to_testpoints(payload, 1)
        assert len(results) == 1

    def test_empty_content(self):
        assert _parse_xmind_to_testpoints({"xmind_content": ""}, 1) == []

    def test_no_xmind_content_key(self):
        assert _parse_xmind_to_testpoints({}, 1) == []

    def test_invalid_json(self):
        results = _parse_xmind_to_testpoints({"xmind_content": "not json"}, 1)
        assert results == []

    def test_non_dict_items_skipped(self):
        payload = {"xmind_content": json.dumps(["string_item", 123])}
        results = _parse_xmind_to_testpoints(payload, 1)
        assert len(results) == 0

    def test_missing_fields_use_defaults(self):
        payload = {"xmind_content": json.dumps([{"title": "仅标题"}])}
        results = _parse_xmind_to_testpoints(payload, 1)
        assert len(results) == 1
        assert results[0]["module"] == "xmind"
        assert results[0]["point"] == "仅标题"

    def test_xmind_content_as_list(self):
        payload = {"xmind_content": json.dumps([{"module": "登录", "point": "验证"}])}
        results = _parse_xmind_to_testpoints(payload, 1)
        assert len(results) == 1

    def test_xmind_content_already_parsed(self):
        payload = {"xmind_content": [{"module": "登录", "point": "验证"}]}
        results = _parse_xmind_to_testpoints(payload, 1)
        assert len(results) == 1


class TestFormatTestPoint:
    def test_with_ai_prompt_json(self):
        tp = _make_test_point_obj(
            ai_prompt=json.dumps({"function": "登录功能"})
        )
        result = _format_test_point(tp)
        assert result["function"] == "登录功能"

    def test_with_invalid_ai_prompt(self):
        tp = _make_test_point_obj(ai_prompt="not json")
        result = _format_test_point(tp)
        assert result["function"] == ""

    def test_with_none_ai_prompt(self):
        tp = _make_test_point_obj(ai_prompt=None)
        result = _format_test_point(tp)
        assert result["function"] == ""


class TestComputeSignalConfidence:
    def test_all_signals(self):
        assert _compute_signal_confidence({
            "has_prd": True, "has_ui": True, "has_testpoints": True
        }) == 1.0

    def test_only_prd(self):
        assert _compute_signal_confidence({
            "has_prd": True, "has_ui": False, "has_testpoints": False
        }) == 0.4

    def test_no_signals(self):
        assert _compute_signal_confidence({
            "has_prd": False, "has_ui": False, "has_testpoints": False
        }) == 0.0


class TestIsCjk:
    def test_chinese_char(self):
        assert _is_cjk("中") is True

    def test_ascii_char(self):
        assert _is_cjk("a") is False

    def test_digit(self):
        assert _is_cjk("1") is False


class TestIsSignificantMatch:
    def test_exact_match(self):
        assert _is_significant_match("登录", "登录") is True

    def test_cjk_substring_match(self):
        assert _is_significant_match("登录", "用户登录页面") is True

    def test_short_query_rejected(self):
        assert _is_significant_match("a", "abc") is False

    def test_empty_query(self):
        assert _is_significant_match("", "target") is False

    def test_empty_target(self):
        assert _is_significant_match("query", "") is False

    def test_not_found(self):
        assert _is_significant_match("注册", "登录页面") is False

    def test_long_query_always_matches(self):
        assert _is_significant_match("用户管理", "系统用户管理模块") is True

    def test_ascii_word_boundary(self):
        assert _is_significant_match("login", "user_login_page") is True


class TestFindMatchingScreens:
    def test_module_match(self):
        tp = {"module": "用户管理", "point": "", "function": ""}
        ui_specs = [
            {"screen_id": 1, "screen_name": "用户管理页面", "ui_spec": {}},
        ]
        result = _find_matching_screens(tp, ui_specs)
        assert len(result) == 1
        assert result[0]["screen_id"] == 1

    def test_element_text_match(self):
        tp = {"module": "", "point": "登录", "function": ""}
        ui_specs = [
            {
                "screen_id": 1,
                "screen_name": "首页",
                "ui_spec": {"elements": [{"type": "button", "text": "登录按钮"}]},
            },
        ]
        result = _find_matching_screens(tp, ui_specs)
        assert len(result) == 1

    def test_no_match(self):
        tp = {"module": "设置", "point": "修改密码", "function": ""}
        ui_specs = [
            {"screen_id": 1, "screen_name": "用户管理", "ui_spec": {}},
        ]
        result = _find_matching_screens(tp, ui_specs)
        assert len(result) == 0

    def test_dedup_screen_ids(self):
        tp = {"module": "用户", "point": "", "function": ""}
        ui_specs = [
            {"screen_id": 1, "screen_name": "用户管理", "ui_spec": {"elements": [{"type": "button", "text": "用户登录"}]}},
        ]
        result = _find_matching_screens(tp, ui_specs)
        assert len(result) == 1

    def test_multi_word_module(self):
        tp = {"module": "用户 管理", "point": "", "function": ""}
        ui_specs = [
            {"screen_id": 1, "screen_name": "用户管理页面", "ui_spec": {}},
        ]
        result = _find_matching_screens(tp, ui_specs)
        assert len(result) == 1

    def test_function_field_match(self):
        tp = {"module": "", "point": "", "function": "登录"}
        ui_specs = [
            {
                "screen_id": 1,
                "screen_name": "首页",
                "ui_spec": {"elements": [{"type": "button", "text": "登录"}]},
            },
        ]
        result = _find_matching_screens(tp, ui_specs)
        assert len(result) == 1

    def test_empty_ui_specs(self):
        tp = {"module": "测试", "point": "测试", "function": ""}
        result = _find_matching_screens(tp, [])
        assert len(result) == 0


class TestComputeAlignmentConfidence:
    def test_all_aligned(self):
        aligned = [
            {"alignment_status": "aligned"},
            {"alignment_status": "aligned"},
        ]
        assert _compute_alignment_confidence(aligned, []) == 1.0

    def test_no_aligned(self):
        aligned = [
            {"alignment_status": "no_ui_match"},
        ]
        assert _compute_alignment_confidence(aligned, []) == 0.0

    def test_empty_list(self):
        assert _compute_alignment_confidence([], []) == 0.0


# TestBuildCasePrompt 和 TestFormatUiSpecsForPrompt 类已删除:
# _build_case_prompt 和 _format_ui_specs_for_prompt 函数已从生产代码移除,
# 对应测试不再可恢复, 故直接删除测试类 (而非保留 skip 标记)


class TestParseCaseResponse:
    def test_valid_json_array(self):
        content = json.dumps([{"title": "用例1"}])
        result = _parse_case_response(content)
        assert len(result) == 1

    def test_dict_with_cases_key(self):
        content = json.dumps({"cases": [{"title": "用例1"}]})
        result = _parse_case_response(content)
        assert len(result) == 1

    def test_dict_with_test_cases_key(self):
        content = json.dumps({"test_cases": [{"title": "用例1"}]})
        result = _parse_case_response(content)
        assert len(result) == 1

    def test_markdown_code_block(self):
        content = "```json\n" + json.dumps([{"title": "用例1"}]) + "\n```"
        result = _parse_case_response(content)
        assert len(result) == 1

    def test_invalid_json_returns_none(self):
        result = _parse_case_response("not json at all no brackets")
        assert result is None

    def test_dict_without_cases_key_returns_empty_list(self):
        content = json.dumps({"other_key": "value"})
        result = _parse_case_response(content)
        assert result == []

    def test_json_with_comments(self):
        content = '[\n  {"title": "用例1"} // 注释\n]'
        result = _parse_case_response(content)
        assert result is not None
        assert len(result) == 1

    def test_json_with_trailing_comma(self):
        content = '[\n  {"title": "用例1"},\n]'
        result = _parse_case_response(content)
        assert result is not None


class TestEnrichCaseData:
    def test_fills_missing_fields(self):
        parsed = [{"title": ""}]
        tp = {"id": 42, "module": "用户管理", "point": "登录"}
        result = _enrich_case_data(parsed, tp, has_ui=True)
        assert result[0]["module"] == "用户管理"
        assert result[0]["title"] == "登录 - 测试用例"
        assert result[0]["test_point_id"] == 42
        assert result[0]["lifecycle_status"] == "draft"

    def test_no_ui_sets_case_type_api(self):
        parsed = [{"title": "测试"}]
        tp = {"id": 1, "module": "模块", "point": "测试点"}
        result = _enrich_case_data(parsed, tp, has_ui=False)
        assert result[0]["case_type"] == "api_automation"

    def test_with_ui_keeps_original_case_type(self):
        parsed = [{"title": "测试", "case_type": "UI"}]
        tp = {"id": 1, "module": "模块", "point": "测试点"}
        result = _enrich_case_data(parsed, tp, has_ui=True)
        assert result[0]["case_type"] == "UI"


class TestComputePriorScore:
    def test_perfect_score(self, db):
        case_data = {
            "title": "登录验证",
            "steps": [{"action": "输入", "expected": "成功"}] * 5,
            "expected_result": "成功登录",
            "precondition": "用户已注册",
            "module": "用户管理",
            "priority": 1,
        }
        tp = {"point": "登录功能"}
        signals = {"has_prd": True, "has_testpoints": True, "has_ui": True, "is_old_project": True}
        inferred = {"confidence": 0.9}
        aligned = {"conflict_count": 0}
        score, grade, breakdown = _compute_prior_score(
            case_data, tp, signals, inferred, aligned, 0, db,
        )
        assert score == 64.0
        assert grade == "C"

    def test_minimal_score(self, db):
        case_data = {}
        tp = {}
        signals = {}
        inferred = {}
        aligned = {}
        score, grade, breakdown = _compute_prior_score(
            case_data, tp, signals, inferred, aligned, 0, db,
        )
        assert score == 2.0
        assert grade == "D"

    def test_partial_score(self, db):
        case_data = {"title": "测试", "priority": 3}
        tp = {}
        signals = {"has_ui": True}
        inferred = {"confidence": 0.5}
        aligned = {"conflict_count": 0}
        score, grade, breakdown = _compute_prior_score(
            case_data, tp, signals, inferred, aligned, 0, db,
        )
        assert breakdown["ui_prototype"] == 25.0
        assert breakdown["inferred_capability_confidence"] == 7.5
        assert breakdown["history"] == 5.0


class TestScoreToGrade:
    def test_grade_a(self):
        assert _score_to_grade(85) == "A"
        assert _score_to_grade(100) == "A"

    def test_grade_b(self):
        assert _score_to_grade(65) == "B"
        assert _score_to_grade(84) == "B"

    def test_grade_c(self):
        assert _score_to_grade(45) == "C"
        assert _score_to_grade(64) == "C"

    def test_grade_d(self):
        assert _score_to_grade(44) == "D"

    def test_grade_d_lower_bound(self):
        assert _score_to_grade(0) == "D"


class TestBuildScoreMap:
    def test_with_scores(self):
        scores_artifact = {
            "scores": [
                {"case_title": "登录验证", "grade": "A"},
                {"case_title": "注册验证", "grade": "D"},
            ]
        }
        result = _build_score_map(scores_artifact)
        assert "登录验证" in result
        assert result["登录验证"]["grade"] == "A"

    def test_none_artifact(self):
        assert _build_score_map(None) == {}

    def test_empty_scores(self):
        assert _build_score_map({"scores": []}) == {}

    def test_none_case_title(self):
        scores_artifact = {"scores": [{"case_title": None, "grade": "A"}]}
        result = _build_score_map(scores_artifact)
        assert len(result) == 0


class TestScenariosRegistry:
    def test_get_scenario_1(self):
        scenario = get_scenario(1)
        assert scenario is not None
        assert scenario["name"] == "scenario_1_full"
        assert len(scenario["steps"]) == 5

    def test_get_nonexistent_scenario(self):
        assert get_scenario(99) is None

    def test_get_scenario_by_version(self):
        scenario = get_scenario_by_version("1.0")
        assert scenario is not None
        assert scenario["name"] == "scenario_1_full"

    def test_get_scenario_by_unknown_version(self):
        assert get_scenario_by_version("99.0") is None

    def test_list_scenarios(self):
        scenarios = list_scenarios()
        assert 1 in scenarios
        assert len(scenarios) >= 1


def _make_ctx(db, testProject):
    from app.pipelines.context import PipelineContext
    from app.ai.mock_client import MockAIClient
    from app.models.iteration import Iteration
    from app.services import pipeline_service

    iteration = db.query(Iteration).filter_by(project_id=testProject.id).first()
    if not iteration:
        iteration = Iteration(
            project_id=testProject.id,
            name="helper_test_iteration",
            status="draft",
        )
        db.add(iteration)
        db.flush()

    run = pipeline_service.create_run(
        db=db,
        iteration_id=iteration.id,
        input_hash="coverage_test_hash",
        pipeline_version="1.0",
    )
    db.flush()

    return PipelineContext(
        db=db,
        ai_client=MockAIClient(),
        run=run,
        iteration_id=iteration.id,
        user_id=1,
    )


def _make_input(payload=None, file_id=None):
    class FakeInput:
        def __init__(self, p, fid):
            self.payload = p
            self.file_id = fid
    return FakeInput(payload, file_id)


def _make_test_point_obj(ai_prompt=None):
    class FakeTestPoint:
        def __init__(self, ap):
            self.id = 1
            self.module = "测试模块"
            self.point = "测试点"
            self.priority = 2
            self.ai_prompt = ap
    return FakeTestPoint(ai_prompt)
