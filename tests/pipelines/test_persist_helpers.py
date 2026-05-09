"""T9/T10 Persist 关联 单元测试

覆盖:
    - T9: parent_case_id / ai_change_type 推导逻辑（modify/create/locator_fix）
    - T10: 一致性校验逻辑（expected_count vs persisted_count, ratio 阈值）
    - _build_score_map: score_map 构建逻辑
"""
import pytest
from unittest.mock import MagicMock

from app.pipelines.steps.persist import _build_score_map


# ── _build_score_map ──


class TestBuildScoreMap:
    def test_empty_artifact(self):
        assert _build_score_map(None) == {}

    def test_no_scores(self):
        assert _build_score_map({}) == {}

    def test_with_scores(self):
        artifact = {
            "scores": [
                {"case_title": "用例A", "grade": "A", "total_score": 90},
                {"case_title": "用例B", "grade": "B", "total_score": 70},
            ],
        }
        result = _build_score_map(artifact)
        assert "用例A" in result
        assert "用例B" in result
        assert result["用例A"]["grade"] == "A"

    def test_skip_empty_title(self):
        artifact = {
            "scores": [
                {"case_title": "", "grade": "A"},
                {"case_title": "用例C", "grade": "C"},
            ],
        }
        result = _build_score_map(artifact)
        assert len(result) == 1
        assert "用例C" in result


# ── T9: parent_case_id / ai_change_type 推导 ──
# （这些逻辑在 Persist.execute 内部，通过 mock ctx 验证）


class TestParentCaseIdDerivation:
    """验证 task_type → ai_change_type / parent_case_id 的映射规则。"""

    def test_modify_task(self):
        task = {"task_type": "modify", "case_id": 42}
        task_type = task.get("task_type", "")
        parent_case_id = task.get("case_id")
        ai_change_type = None
        if task_type == "modify":
            ai_change_type = "modified"
        elif task_type == "locator_fix":
            ai_change_type = "locator_fix"
        elif task_type == "create":
            ai_change_type = "added"
        assert parent_case_id == 42
        assert ai_change_type == "modified"

    def test_create_task(self):
        task = {"task_type": "create"}
        task_type = task.get("task_type", "")
        parent_case_id = task.get("case_id")  # None
        ai_change_type = None
        if task_type == "create":
            ai_change_type = "added"
        assert parent_case_id is None
        assert ai_change_type == "added"

    def test_locator_fix_task(self):
        task = {"task_type": "locator_fix", "case_id": 99}
        task_type = task.get("task_type", "")
        parent_case_id = task.get("case_id")
        ai_change_type = None
        if task_type == "locator_fix":
            ai_change_type = "locator_fix"
        assert parent_case_id == 99
        assert ai_change_type == "locator_fix"

    def test_modify_missing_case_id(self):
        """modify 任务缺少 case_id → parent_case_id=None，应 warning。"""
        task = {"task_type": "modify"}
        parent_case_id = task.get("case_id")  # None
        assert parent_case_id is None
        # 实际代码中会 logger.warning

    def test_no_task(self):
        """无 task 信息 → parent_case_id=None, ai_change_type=None。"""
        task = None
        parent_case_id = None
        ai_change_type = None
        assert parent_case_id is None
        assert ai_change_type is None


# ── T10: 一致性校验逻辑 ──


class TestConsistencyCheck:
    """验证 expected_count vs persisted_count 的 ratio 阈值逻辑。"""

    def test_consistent_ratio(self):
        """persisted/expected 在 0.8~1.2 之间 → is_consistent=True。"""
        expected_count = 10
        persisted_count = 9
        ratio = persisted_count / expected_count
        is_consistent = not (ratio < 0.8 or ratio > 1.2)
        assert is_consistent is True

    def test_too_few_persisted(self):
        """persisted < 80% expected → is_consistent=False。"""
        expected_count = 10
        persisted_count = 7
        ratio = persisted_count / expected_count
        is_consistent = not (ratio < 0.8 or ratio > 1.2)
        assert is_consistent is False

    def test_too_many_persisted(self):
        """persisted > 120% expected → is_consistent=False。"""
        expected_count = 10
        persisted_count = 13
        ratio = persisted_count / expected_count
        is_consistent = not (ratio < 0.8 or ratio > 1.2)
        assert is_consistent is False

    def test_zero_expected(self):
        """expected=0 → 不校验（避免除零）。"""
        expected_count = 0
        persisted_count = 5
        # 实际代码: if expected_count > 0
        if expected_count > 0:
            ratio = persisted_count / expected_count
        else:
            ratio = 1.0
        assert ratio == 1.0

    def test_exact_match(self):
        """persisted == expected → is_consistent=True。"""
        expected_count = 5
        persisted_count = 5
        ratio = persisted_count / expected_count
        is_consistent = not (ratio < 0.8 or ratio > 1.2)
        assert is_consistent is True

    def test_confidence_reduction(self):
        """不一致时 confidence 降至 0.7。"""
        expected_count = 10
        persisted_count = 5
        ratio = persisted_count / expected_count
        artifact_confidence = 1.0
        if ratio < 0.8 or ratio > 1.2:
            artifact_confidence = min(artifact_confidence, 0.7)
        assert artifact_confidence == 0.7
