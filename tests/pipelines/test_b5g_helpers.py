"""B5g 拆分件护栏：CaseGeneration 输入归一 / Runner 循环控制 / BackwardScan 校验分段。

这三处原先都长在单一函数体内（execute / run / validate_backward_output），分支只能靠
Step 级与端到端用例间接覆盖。拆分后对纯函数部分直接加锁，保证口径不漂移。
"""

from app.pipelines._runner_control import _progress_pct, _resume_filter
from app.pipelines.schemas.backward_verdict import (
    BackwardScanOutput,
    BackwardVerdict,
    _build_scanned_output,
    _check_case_ids,
    _coerce_payload,
    _downgrade_low_confidence,
    validate_backward_output,
)
from app.pipelines.steps._case_generation_inputs import (
    _build_ui_description,
    _early_exit_result,
    _empty_cases_payload,
    _load_history_cases,
    _signal_inputs,
    _split_tasks,
)


class _FakeCtx:
    iteration_id = 11

    def __init__(self, scenario=None, artifacts=None):
        self.config = {} if scenario is None else {"scenario": scenario}
        self._artifacts = artifacts or {}

    def get_artifact(self, kind):
        return self._artifacts.get(kind)


class TestSignalInputs:
    def test_none_signals_give_defaults(self):
        assert _signal_inputs(None) == {
            "prd_content": "",
            "ui_specs": [],
            "ui_descriptions": [],
            "has_ui": False,
            "project_id": None,
        }

    def test_signals_passthrough(self):
        inputs = _signal_inputs(
            {
                "prd_content": "需求",
                "ui_specs": [{"screen_id": 1}],
                "ui_descriptions": [],
                "has_ui": True,
                "project_id": 3,
            }
        )
        assert inputs["prd_content"] == "需求"
        assert inputs["has_ui"] is True
        assert inputs["project_id"] == 3


class TestBuildUiDescription:
    def test_empty(self):
        assert _build_ui_description([]) == ""

    def test_skips_blank_items(self):
        assert _build_ui_description([{"description": ""}, {"description": "甲"}, {"summary": "乙"}]) == "甲\n乙"


class TestSplitTasks:
    def test_none_artifact(self):
        assert _split_tasks(None) == ([], [], [])

    def test_splits_actionable(self):
        tasks, deprecations, actionable = _split_tasks(
            {
                "generation_tasks": [
                    {"task_type": "create"},
                    {"task_type": "keep"},
                    {"task_type": "locator_fix"},
                ],
                "deprecation_suggestions": [{"case_id": 1}],
            }
        )
        assert len(tasks) == 3
        assert [t["task_type"] for t in actionable] == ["create", "locator_fix"]
        assert deprecations == [{"case_id": 1}]


class TestLoadHistoryCases:
    def test_no_actionable_tasks_is_lazy(self):
        ctx = _FakeCtx(artifacts={"history_fingerprints": {"fingerprints": [{"title": "t"}]}})
        assert _load_history_cases(ctx, []) == []

    def test_maps_fingerprints(self):
        fps = [{"case_title": "标题", "module": "模块", "summary": "摘要"}] + [{"title": f"t{i}"} for i in range(60)]
        ctx = _FakeCtx(artifacts={"history_fingerprints": {"fingerprints": fps}})
        cases = _load_history_cases(ctx, [{"task_type": "create"}])
        assert len(cases) == 50  # 上限 50 条
        assert cases[0] == {"title": "标题", "module": "模块", "summary": "摘要", "priority": 3}

    def test_missing_artifact(self):
        assert _load_history_cases(_FakeCtx(), [{"task_type": "create"}]) == []


class TestEarlyExitResult:
    def _inputs(self, **overrides):
        base = {"prd_content": "", "ui_specs": [], "ui_descriptions": [], "has_ui": False, "project_id": 5}
        base.update(overrides)
        return base

    def test_actionable_continues(self):
        result = _early_exit_result(
            _FakeCtx(), {"generation_tasks": []}, [{"task_type": "create"}], None, None, self._inputs(), []
        )
        assert result is None

    def test_tasks_without_actionable_fails(self):
        result = _early_exit_result(
            _FakeCtx(), {"generation_tasks": []}, [], None, None, self._inputs(), [{"case_id": 1}]
        )
        assert result is not None
        assert result.success is False
        assert "没有可执行的" in result.error
        assert result.artifact_payload["deprecation_suggestions"] == [{"case_id": 1}]

    def test_scenario_4_returns_success_empty(self):
        result = _early_exit_result(_FakeCtx(scenario=4), None, [], None, None, self._inputs(), [{"case_id": 1}])
        assert result is not None
        assert result.success is True
        assert result.artifact_payload["total"] == 0
        assert result.artifact_payload["deprecation_suggestions"] == []

    def test_missing_all_artifacts_fails(self):
        result = _early_exit_result(_FakeCtx(), None, [], None, None, self._inputs(), [])
        assert result is not None
        assert result.success is False
        assert "缺少 generation_tasks" in result.error

    def test_signals_present_continues_legacy(self):
        result = _early_exit_result(_FakeCtx(), None, [], None, {"project_id": 5}, self._inputs(), [])
        assert result is None


class TestEmptyCasesPayload:
    def test_shape(self):
        payload = _empty_cases_payload(_FakeCtx(), {"project_id": 5, "has_ui": True}, [])
        assert payload["iteration_id"] == 11
        assert payload["project_id"] == 5
        assert payload["has_ui"] is True
        assert payload["generated_cases"] == []
        assert payload["total"] == 0


class TestRunnerProgressPct:
    def test_started(self):
        assert _progress_pct(0, 4) == 0.0
        assert _progress_pct(1, 4) == 25.0

    def test_finished(self):
        assert _progress_pct(0, 4, finished=True) == 25.0
        assert _progress_pct(3, 4, finished=True) == 100.0


class TestResumeFilter:
    def test_no_resume_point_never_skips(self):
        should_skip = _resume_filter(None)
        assert should_skip("a") is False
        assert should_skip("b") is False

    def test_skips_until_resume_point_inclusive(self):
        should_skip = _resume_filter("b")
        assert should_skip("a") is True
        assert should_skip("b") is False
        assert should_skip("c") is False


class TestBackwardPayloadCoercion:
    def test_invalid_json(self):
        data, error = _coerce_payload("not json")
        assert data is None and "JSON 解析失败" in error

    def test_dict_without_verdicts(self):
        data, error = _coerce_payload({"other": 1})
        assert data is None and "verdicts" in error

    def test_list_wrapped(self):
        data, error = _coerce_payload([{"case_id": 1}])
        assert error is None
        assert data == {"verdicts": [{"case_id": 1}]}

    def test_invalid_schema(self):
        output, error = _build_scanned_output({"verdicts": [{"case_id": 1}]})
        assert output is None and "Schema 校验失败" in error


class TestBackwardDownGrade:
    def test_low_confidence_downgraded(self):
        output = BackwardScanOutput(
            verdicts=[
                {"case_id": 1, "verdict": "VALID", "confidence": 0.5, "hint": "低置信"},
                {"case_id": 2, "verdict": "VALID", "confidence": 0.9, "hint": "高置信"},
            ]
        )
        corrected, notes = _downgrade_low_confidence(output)
        assert corrected.verdicts[0].verdict == BackwardVerdict.UNCERTAIN
        assert corrected.verdicts[1].verdict == BackwardVerdict.VALID
        assert len(notes) == 1

    def test_already_uncertain_not_renotified(self):
        output = BackwardScanOutput(
            verdicts=[{"case_id": 1, "verdict": "UNCERTAIN", "confidence": 0.5, "hint": "待评审"}]
        )
        _, notes = _downgrade_low_confidence(output)
        assert notes == []


class TestBackwardCaseIdCheck:
    def _output(self, ids):
        return BackwardScanOutput(
            verdicts=[{"case_id": i, "verdict": "VALID", "confidence": 0.9, "hint": "ok"} for i in ids]
        )

    def test_no_expectation(self):
        assert _check_case_ids(self._output([1]), None) == []

    def test_missing_and_extra(self):
        errors = _check_case_ids(self._output([1, 9]), [1, 2])
        assert any("缺少 case_id" in e for e in errors)
        assert any("多余 case_id" in e for e in errors)

    def test_exact_match(self):
        assert _check_case_ids(self._output([1, 2]), [1, 2]) == []


class TestValidateBackwardOutputWrapper:
    def test_none_raw(self):
        result = validate_backward_output(None)
        assert result.valid is False
        assert result.errors == ["AI 输出为空"]

    def test_valid_payload_outputs_object(self):
        result = validate_backward_output(
            {"verdicts": [{"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": "ok"}]},
            expected_case_ids=[1],
        )
        assert result.valid is True
        assert result.output is not None
        assert result.output.verdicts[0].case_id == 1

    def test_missing_case_id_invalidates_and_drops_output(self):
        result = validate_backward_output(
            {"verdicts": [{"case_id": 1, "verdict": "VALID", "confidence": 0.9, "hint": "ok"}]},
            expected_case_ids=[1, 2],
        )
        assert result.valid is False
        assert result.output is None
