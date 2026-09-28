"""Test Impact Analysis 单元测试（Phase 1 Task 4）

测试对象：app/services/impact_analysis/{models,coverage_collector,change_analyzer,impact_mapper,scheduler}.py
依赖：纯函数测试，无 DB/Redis 调用
运行：python -m pytest tests/services/impact_analysis/ -v --tb=short
"""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from app.services.impact_analysis.models import (
    CoverageEntry, CodeChange, ImpactResult, ImpactRange,
)
from app.services.impact_analysis.coverage_collector import CoverageCollector
from app.services.impact_analysis.change_analyzer import ChangeAnalyzer
from app.services.impact_analysis.impact_mapper import ImpactMapper
from app.services.impact_analysis.scheduler import ImpactScheduler, ImpactSchedulePlan


class TestCoverageEntry:
    """覆盖率条目数据结构测试。"""

    def test_valid_entry(self):
        entry = CoverageEntry(test_case_id=1, file_path="app/foo.py", line_start=1, line_end=10)
        assert entry.is_valid() is True

    def test_invalid_entry_zero_test_id(self):
        entry = CoverageEntry(test_case_id=0, file_path="app/foo.py", line_start=1, line_end=10)
        assert entry.is_valid() is False

    def test_invalid_entry_reverse_lines(self):
        entry = CoverageEntry(test_case_id=1, file_path="app/foo.py", line_start=10, line_end=1)
        assert entry.is_valid() is False

    def test_covers_line_inside_range(self):
        entry = CoverageEntry(test_case_id=1, file_path="app/foo.py", line_start=5, line_end=10)
        assert entry.covers_line(7) is True

    def test_covers_line_outside_range(self):
        entry = CoverageEntry(test_case_id=1, file_path="app/foo.py", line_start=5, line_end=10)
        assert entry.covers_line(11) is False

    def test_overlaps(self):
        entry = CoverageEntry(test_case_id=1, file_path="app/foo.py", line_start=5, line_end=10)
        assert entry.overlaps(8, 15) is True
        assert entry.overlaps(11, 20) is False


class TestCodeChange:
    """代码变更数据结构测试。"""

    def test_change_size(self):
        change = CodeChange(
            file_path="app/foo.py",
            added_lines=frozenset({1, 2, 3}),
            deleted_lines=frozenset({10, 11}),
        )
        assert change.change_size == 5

    def test_is_significant_above_threshold(self):
        change = CodeChange(
            file_path="app/foo.py",
            added_lines=frozenset({1, 2, 3, 4, 5}),
        )
        assert change.is_significant(threshold=5) is True

    def test_is_significant_below_threshold(self):
        change = CodeChange(
            file_path="app/foo.py",
            added_lines=frozenset({1, 2}),
        )
        assert change.is_significant(threshold=5) is False

    def test_is_significant_new_file(self):
        change = CodeChange(file_path="app/new.py", is_new_file=True)
        assert change.is_significant() is True


class TestCoverageCollector:
    """覆盖率采集器测试。"""

    def test_parse_coverage_data_basic(self, tmp_path):
        collector = CoverageCollector(project_root=str(tmp_path))
        data = {
            "files": {
                str(tmp_path / "app" / "foo.py"): {
                    "executed_lines": [1, 2, 3, 10, 11, 15],
                }
            }
        }
        entries = collector.parse_coverage_data(data, test_case_id=1, test_name="test_foo")
        assert len(entries) == 3  # [(1,3), (10,11), (15,15)]
        assert entries[0].line_start == 1
        assert entries[0].line_end == 3
        assert entries[1].line_start == 10
        assert entries[1].line_end == 11
        assert entries[2].line_start == 15
        assert entries[2].line_end == 15

    def test_parse_coverage_data_empty_files(self, tmp_path):
        collector = CoverageCollector(project_root=str(tmp_path))
        entries = collector.parse_coverage_data({"files": {}}, test_case_id=1)
        assert entries == []

    def test_parse_coverage_data_invalid_test_id(self, tmp_path):
        collector = CoverageCollector(project_root=str(tmp_path))
        with pytest.raises(ValueError, match="test_case_id"):
            collector.parse_coverage_data({"files": {}}, test_case_id=0)

    def test_parse_coverage_data_skips_external_files(self, tmp_path):
        collector = CoverageCollector(project_root=str(tmp_path))
        external_path = "/external/foo.py"
        data = {
            "files": {
                external_path: {"executed_lines": [1, 2, 3]},
            }
        }
        entries = collector.parse_coverage_data(data, test_case_id=1)
        assert entries == []

    def test_parse_coverage_json_file_not_found(self, tmp_path):
        collector = CoverageCollector(project_root=str(tmp_path))
        entries = collector.parse_coverage_json("/nonexistent/coverage.json", test_case_id=1)
        assert entries == []

    def test_parse_coverage_json_invalid_json(self, tmp_path):
        collector = CoverageCollector(project_root=str(tmp_path))
        json_path = tmp_path / "bad.json"
        json_path.write_text("{invalid json", encoding="utf-8")
        entries = collector.parse_coverage_json(str(json_path), test_case_id=1)
        assert entries == []

    def test_merge_consecutive_lines(self):
        # 测试私有静态方法
        result = CoverageCollector._merge_consecutive_lines([1, 2, 3, 10, 11, 15])
        assert result == [(1, 3), (10, 11), (15, 15)]

    def test_merge_consecutive_lines_empty(self):
        result = CoverageCollector._merge_consecutive_lines([])
        assert result == []

    def test_merge_consecutive_lines_unsorted(self):
        result = CoverageCollector._merge_consecutive_lines([10, 1, 2, 11, 3])
        assert result == [(1, 3), (10, 11)]


class TestChangeAnalyzer:
    """代码变更分析器测试。"""

    def test_parse_diff_text_empty(self, tmp_path):
        analyzer = ChangeAnalyzer(project_root=str(tmp_path))
        assert analyzer.parse_diff_text("") == []
        assert analyzer.parse_diff_text("   ") == []

    def test_parse_diff_text_single_file_added(self, tmp_path):
        analyzer = ChangeAnalyzer(project_root=str(tmp_path))
        diff_text = """diff --git a/app/foo.py b/app/foo.py
new file mode 100644
--- /dev/null
+++ b/app/foo.py
@@ -0,0 +1,3 @@
+def new_func():
+    return 1
+    return 2
"""
        changes = analyzer.parse_diff_text(diff_text)
        assert len(changes) == 1
        assert changes[0].file_path == "app/foo.py"
        assert changes[0].is_new_file is True
        assert 1 in changes[0].added_lines
        assert 2 in changes[0].added_lines
        assert 3 in changes[0].added_lines

    def test_parse_diff_text_modified_file(self, tmp_path):
        analyzer = ChangeAnalyzer(project_root=str(tmp_path))
        diff_text = """diff --git a/app/bar.py b/app/bar.py
--- a/app/bar.py
+++ b/app/bar.py
@@ -5,3 +5,4 @@
 def existing():
-    return None
+    return 1
+    pass
"""
        changes = analyzer.parse_diff_text(diff_text)
        assert len(changes) == 1
        assert changes[0].file_path == "app/bar.py"
        assert changes[0].is_new_file is False
        # @@ -5,3 +5,4 @@：old/new 起始行均为 5
        # context "def existing():" 占用 old=5 / new=5，各自行号推进到 6
        # deleted "-return None" → old 行号 6
        # added "+return 1" → new 行号 6
        # added "+pass" → new 行号 7
        assert 6 in changes[0].deleted_lines  # -return None
        assert 6 in changes[0].added_lines  # +return 1
        assert 7 in changes[0].added_lines  # +pass

    def test_parse_diff_text_deleted_file(self, tmp_path):
        analyzer = ChangeAnalyzer(project_root=str(tmp_path))
        diff_text = """diff --git a/app/dead.py b/app/dead.py
deleted file mode 100644
--- a/app/dead.py
+++ /dev/null
@@ -1,2 +0,0 @@
-def dead():
-    return None
"""
        changes = analyzer.parse_diff_text(diff_text)
        assert len(changes) == 1
        assert changes[0].is_deleted is True

    def test_parse_diff_text_multiple_files(self, tmp_path):
        analyzer = ChangeAnalyzer(project_root=str(tmp_path))
        diff_text = """diff --git a/app/a.py b/app/a.py
--- a/app/a.py
+++ b/app/a.py
@@ -1,1 +1,2 @@
+new line
diff --git a/app/b.py b/app/b.py
--- a/app/b.py
+++ b/app/b.py
@@ -1,1 +1,2 @@
+another line
"""
        changes = analyzer.parse_diff_text(diff_text)
        assert len(changes) == 2
        assert changes[0].file_path == "app/a.py"
        assert changes[1].file_path == "app/b.py"

    def test_analyze_git_diff_failure(self, tmp_path):
        """git 命令失败时返回空列表。"""
        analyzer = ChangeAnalyzer(project_root=str(tmp_path))
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
            changes = analyzer.analyze_git_diff("HEAD~1", "HEAD")
            assert changes == []

    def test_analyze_git_diff_timeout(self, tmp_path):
        """git 命令超时时返回空列表。"""
        import subprocess
        analyzer = ChangeAnalyzer(project_root=str(tmp_path))
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=1)):
            changes = analyzer.analyze_git_diff("HEAD~1", "HEAD", timeout=1)
            assert changes == []

    def test_analyze_git_diff_git_not_found(self, tmp_path):
        """git 命令不存在时返回空列表。"""
        analyzer = ChangeAnalyzer(project_root=str(tmp_path))
        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            changes = analyzer.analyze_git_diff("HEAD~1", "HEAD")
            assert changes == []


class TestImpactMapper:
    """影响映射器测试。"""

    def test_map_impact_no_changes(self):
        """无代码变更时返回空影响范围。"""
        mapper = ImpactMapper()
        result = mapper.map_impact(
            coverage_entries=[CoverageEntry(1, "app/foo.py", 1, 10)],
            code_changes=[],
            total_test_count=100,
        )
        assert result.impacted_test_ids == []
        assert "无代码变更" in result.analysis_basis

    def test_map_impact_no_coverage_returns_empty(self):
        """覆盖率冷启动时返回空（保守策略需全量执行）。"""
        mapper = ImpactMapper()
        result = mapper.map_impact(
            coverage_entries=[],
            code_changes=[CodeChange(file_path="app/foo.py", added_lines=frozenset({1, 2}))],
            total_test_count=100,
        )
        assert result.impacted_test_ids == []
        assert "冷启动" in result.analysis_basis

    def test_map_impact_direct_match(self):
        """变更行被覆盖率映射时返回对应测试用例。"""
        mapper = ImpactMapper()
        entries = [
            CoverageEntry(test_case_id=1, file_path="app/foo.py", line_start=1, line_end=10),
            CoverageEntry(test_case_id=2, file_path="app/foo.py", line_start=20, line_end=30),
        ]
        changes = [CodeChange(file_path="app/foo.py", added_lines=frozenset({5}))]
        result = mapper.map_impact(entries, changes, total_test_count=10)
        assert result.impacted_test_ids == [1]
        assert result.reduction_ratio == 0.9  # 1 - 1/10

    def test_map_impact_multiple_files(self):
        """多文件变更时聚合受影响用例。"""
        mapper = ImpactMapper()
        entries = [
            CoverageEntry(test_case_id=1, file_path="app/a.py", line_start=1, line_end=10),
            CoverageEntry(test_case_id=2, file_path="app/b.py", line_start=1, line_end=10),
        ]
        changes = [
            CodeChange(file_path="app/a.py", added_lines=frozenset({5})),
            CodeChange(file_path="app/b.py", added_lines=frozenset({5})),
        ]
        result = mapper.map_impact(entries, changes, total_test_count=10)
        assert sorted(result.impacted_test_ids) == [1, 2]

    def test_map_impact_deleted_file(self):
        """文件删除时覆盖该文件的所有用例受影响。"""
        mapper = ImpactMapper()
        entries = [
            CoverageEntry(test_case_id=1, file_path="app/dead.py", line_start=1, line_end=10),
            CoverageEntry(test_case_id=2, file_path="app/dead.py", line_start=20, line_end=30),
        ]
        changes = [CodeChange(file_path="app/dead.py", is_deleted=True)]
        result = mapper.map_impact(entries, changes, total_test_count=10)
        assert sorted(result.impacted_test_ids) == [1, 2]

    def test_filter_high_confidence(self):
        """筛选高置信度用例。"""
        mapper = ImpactMapper()
        ranges = [
            ImpactRange(test_case_id=1, confidence=0.9),
            ImpactRange(test_case_id=2, confidence=0.5),
            ImpactRange(test_case_id=3, confidence=0.8),
        ]
        high_conf = mapper.filter_high_confidence(ranges, threshold=0.7)
        assert high_conf == [1, 3]


class TestImpactScheduler:
    """智能调度器测试。"""

    def test_schedule_no_changes_returns_full_run(self, tmp_path):
        """无代码变更时全量执行。"""
        scheduler = ImpactScheduler(project_root=str(tmp_path))
        with patch.object(scheduler._analyzer, "analyze_git_diff", return_value=[]):
            plan = scheduler.schedule(total_test_count=100)
            assert plan.is_full_run is True
            assert "无变更" in plan.fallback_reason or "失败" in plan.fallback_reason

    def test_schedule_no_coverage_returns_full_run(self, tmp_path):
        """覆盖率冷启动时全量执行。"""
        scheduler = ImpactScheduler(project_root=str(tmp_path))
        changes = [CodeChange(file_path="app/foo.py", added_lines=frozenset({1}))]
        with patch.object(scheduler._analyzer, "analyze_git_diff", return_value=changes):
            plan = scheduler.schedule(total_test_count=100)
            assert plan.is_full_run is True
            assert "冷启动" in plan.fallback_reason

    def test_schedule_low_reduction_returns_full_run(self, tmp_path):
        """缩减比例过低时全量执行。"""
        entries = [
            CoverageEntry(test_case_id=i, file_path="app/foo.py", line_start=1, line_end=100)
            for i in range(1, 91)  # 90/100 受影响，缩减 10%
        ]
        scheduler = ImpactScheduler(project_root=str(tmp_path), coverage_entries=entries)
        changes = [CodeChange(file_path="app/foo.py", added_lines=frozenset({50}))]
        with patch.object(scheduler._analyzer, "analyze_git_diff", return_value=changes):
            plan = scheduler.schedule(total_test_count=100)
            # 缩减 10% < 20% 阈值，应全量执行
            assert plan.is_full_run is True
            assert "缩减比例过低" in plan.fallback_reason

    def test_schedule_effective_plan(self, tmp_path):
        """有效缩减时返回部分执行计划。"""
        entries = [
            CoverageEntry(test_case_id=1, file_path="app/foo.py", line_start=1, line_end=10),
        ]
        scheduler = ImpactScheduler(project_root=str(tmp_path), coverage_entries=entries)
        changes = [CodeChange(file_path="app/foo.py", added_lines=frozenset({5}))]
        with patch.object(scheduler._analyzer, "analyze_git_diff", return_value=changes):
            plan = scheduler.schedule(total_test_count=100, avg_test_duration_seconds=5.0)
            assert plan.is_full_run is False
            assert plan.test_case_ids == [1]
            assert plan.reduction_ratio == 0.99
            assert plan.estimated_saved_seconds == 99 * 5.0
            assert plan.is_effective is True

    def test_update_coverage_entries(self, tmp_path):
        scheduler = ImpactScheduler(project_root=str(tmp_path))
        entries = [CoverageEntry(test_case_id=1, file_path="app/foo.py", line_start=1, line_end=10)]
        scheduler.update_coverage_entries(entries)
        assert len(scheduler._coverage_entries) == 1


class TestImpactSchedulePlan:
    """调度计划数据结构测试。"""

    def test_is_effective_partial_run(self):
        plan = ImpactSchedulePlan(
            test_case_ids=[1, 2, 3],
            is_full_run=False,
            reduction_ratio=0.7,
        )
        assert plan.is_effective is True

    def test_is_effective_full_run(self):
        plan = ImpactSchedulePlan(is_full_run=True)
        assert plan.is_effective is False

    def test_is_effective_low_reduction(self):
        plan = ImpactSchedulePlan(
            test_case_ids=[1],
            is_full_run=False,
            reduction_ratio=0.05,  # 低于 10%
        )
        assert plan.is_effective is False


class TestImpactResult:
    """TIA 分析结果数据结构测试。"""

    def test_saved_execution_count(self):
        result = ImpactResult(
            impacted_test_ids=[1, 2, 3],
            total_test_count=10,
        )
        assert result.saved_execution_count == 7

    def test_is_effective_above_threshold(self):
        result = ImpactResult(
            impacted_test_ids=[1, 2],
            total_test_count=10,
            reduction_ratio=0.8,
        )
        assert result.is_effective is True

    def test_is_effective_below_threshold(self):
        result = ImpactResult(
            impacted_test_ids=list(range(1, 10)),
            total_test_count=10,
            reduction_ratio=0.05,
        )
        assert result.is_effective is False
