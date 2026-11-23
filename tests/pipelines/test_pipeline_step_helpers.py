"""Pipeline 纯函数辅助行为护栏（G-8 B5d 拆分前置测试）。

覆盖三处高分支密度纯函数：
    - `_run_consistency_check`：预期数量统计、比率阈值与置信度降级、
      deprecation 旧用例批量校验（限 20 条、单次 in_ 查询）
    - `_classify_case_type_local`：category → title → steps 三级判定与默认正向
    - `_extract_inferred`：变更说明 / 反推摘要 / 变更摘要 / 能力清单四段拼装
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.pipelines.context import PipelineContext
from app.pipelines.steps._persist_consistency import _run_consistency_check
from app.pipelines.steps._qg_coverage import _classify_case_type_local
from app.pipelines.steps._scenario_candidates_helpers import _extract_inferred


def _ctx(artifacts: dict[str, dict] | None = None, db=None) -> PipelineContext:
    ctx = PipelineContext(db=db, ai_client=None, run=SimpleNamespace(id=1), iteration_id=1)
    for kind, payload in (artifacts or {}).items():
        ctx.set_artifact(kind, SimpleNamespace(payload=payload))
    return ctx


def _tasks(*task_types: str, deprecations: list | None = None) -> dict:
    return {
        "generation_tasks": [{"task_type": t} for t in task_types],
        "deprecation_suggestions": deprecations or [],
    }


class TestRunConsistencyCheck:
    def test_no_tasks_artifact_is_consistent(self):
        check, confidence = _run_consistency_check(_ctx(), [])

        assert check == {
            "expected_count": 0,
            "persisted_count": 0,
            "deprecation_suggestions_count": 0,
            "is_consistent": True,
            "warning": None,
        }
        assert confidence == 1.0

    def test_only_counting_task_types(self):
        ctx = _ctx({"generation_tasks": _tasks("create", "modify", "locator_fix", "skip", "obsolete")})

        check, _ = _run_consistency_check(ctx, [1, 2, 3])

        assert check["expected_count"] == 3
        assert check["is_consistent"] is True

    def test_ratio_within_range_keeps_confidence(self):
        ctx = _ctx({"generation_tasks": _tasks("create", "create")})

        check, confidence = _run_consistency_check(ctx, [1, 2])

        assert check["is_consistent"] is True
        assert check["warning"] is None
        assert confidence == 1.0

    def test_ratio_too_low_warns_and_downgrades(self):
        ctx = _ctx({"generation_tasks": _tasks("create", "create", "create", "create")})

        check, confidence = _run_consistency_check(ctx, [1])

        assert check["is_consistent"] is False
        assert "比率: 0.25" in check["warning"]
        assert confidence == 0.7

    def test_ratio_too_high_warns_and_downgrades(self):
        ctx = _ctx({"generation_tasks": _tasks("create")})

        check, confidence = _run_consistency_check(ctx, [1, 2])

        assert check["is_consistent"] is False
        assert "比率: 2.00" in check["warning"]
        assert confidence == 0.7

    def test_deprecation_suggestions_verified(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [
            SimpleNamespace(id=11, lifecycle_status="deprecated"),
            SimpleNamespace(id=12, lifecycle_status="active"),
        ]
        ctx = _ctx(
            {
                "generation_tasks": _tasks(
                    "create",
                    deprecations=[{"case_id": 11}, {"case_id": 12}, {"case_id": 13}],
                )
            },
            db=db,
        )

        check, _ = _run_consistency_check(ctx, [1])

        verification = check["deprecation_verification"]
        assert verification == {"total": 3, "verified": 3, "not_found": 1, "already_deprecated": 1}
        db.query.return_value.filter.assert_called_once()

    def test_deprecation_items_without_case_id_skipped(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        ctx = _ctx({"generation_tasks": _tasks("create", deprecations=[{"reason": "无 id"}])}, db=db)

        check, _ = _run_consistency_check(ctx, [1])

        assert check["deprecation_verification"]["verified"] == 0
        db.query.assert_not_called()

    def test_deprecation_check_limited_to_twenty(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        deprecations = [{"case_id": i} for i in range(1, 31)]
        ctx = _ctx({"generation_tasks": _tasks("create", deprecations=deprecations)}, db=db)

        check, _ = _run_consistency_check(ctx, [])

        assert check["deprecation_suggestions_count"] == 30
        assert check["deprecation_verification"]["total"] == 30
        assert check["deprecation_verification"]["verified"] == 20


class TestClassifyCaseTypeLocal:
    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            ("boundary_test", "boundary"),
            ("NEGATIVE", "negative"),
            ("异常场景", "negative"),
            ("正向流程", "positive"),
        ],
    )
    def test_category_keywords(self, category, expected):
        assert _classify_case_type_local({"case_category": category}) == expected

    def test_case_type_field_used_when_category_missing(self):
        assert _classify_case_type_local({"case_type": "boundary"}) == "boundary"

    def test_title_keywords_fallback(self):
        assert _classify_case_type_local({"title": "手机号超长输入"}) == "boundary"
        assert _classify_case_type_local({"title": "无权限访问订单"}) == "negative"
        assert _classify_case_type_local({"title": "主流程下单"}) == "positive"

    def test_steps_keywords_fallback(self):
        case = {"steps": [{"action": "输入非法字符", "expected_result": "提示错误"}]}
        assert _classify_case_type_local(case) == "negative"

    def test_steps_non_list_ignored(self):
        assert _classify_case_type_local({"steps": "点击按钮"}) == "positive"

    def test_non_dict_steps_ignored(self):
        assert _classify_case_type_local({"steps": ["点击按钮", 42]}) == "positive"

    def test_default_positive(self):
        assert _classify_case_type_local({}) == "positive"


class TestExtractInferred:
    def test_empty_inputs_returns_placeholder(self):
        assert _extract_inferred(None) == "（无反推摘要/变更线索）"
        assert _extract_inferred("非字典结构") == "（无反推摘要/变更线索）"

    def test_change_notes_included_and_truncated(self):
        text = _extract_inferred(None, {"change_notes": "改" * 1200})

        assert text.startswith("变更说明: ")
        assert len(text) < 1200

    def test_summary_prefers_analysis_summary(self):
        inferred = {"parsed": {"analysis_summary": "分析摘要", "summary": "旧摘要"}}
        assert "反推摘要: 分析摘要" in _extract_inferred(inferred)

    def test_summary_falls_back_to_summary(self):
        inferred = {"parsed": {"summary": "旧摘要"}}
        assert "反推摘要: 旧摘要" in _extract_inferred(inferred)

    def test_change_summary_serialized(self):
        inferred = {"parsed": {"change_summary": {"新增": ["下单"]}}}
        text = _extract_inferred(inferred)

        assert "变更摘要:" in text
        assert '"新增"' in text

    def test_capabilities_low_confidence_marked(self):
        inferred = {
            "parsed": {
                "inferred_capabilities": [
                    {"name": "下单", "confidence": 0.4},
                    {"name": "退款", "confidence": 0.9},
                    {"key": "无置信度"},
                ]
            }
        }
        text = _extract_inferred(inferred)

        assert "⚠️下单(置信度0.4,待确认)" in text
        assert "- 退款(置信度0.9)" in text
        assert "- 无置信度" in text

    def test_capabilities_non_dict_skipped_and_capped(self):
        caps = [{"name": f"能力{i}"} for i in range(15)] + ["非法项"]
        text = _extract_inferred({"parsed": {"capabilities": caps}})

        assert text.count("- 能力") == 10

    def test_unserializable_change_summary_falls_back_to_str(self):
        inferred = {"parsed": {"change_summary": {1, 2, 3}}}
        text = _extract_inferred(inferred)

        assert "变更摘要: {" in text
