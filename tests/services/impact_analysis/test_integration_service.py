"""TIA 集成服务单元测试（Phase 1 Task 4）。

测试对象：app/services/impact_analysis/integration_service.py
依赖：DB fixture（sync）+ TIAIntegrationService

测试用例:
    - load_coverage_entries: 空项目 / 有数据 / 异常降级
    - upsert_coverage_entries: 新增 / 覆盖（幂等） / 空列表
    - build_schedule_plan: TIA_ENABLED=False / 无覆盖率 / 有效调度
    - filter_test_case_ids: 全量回退 / 部分筛选 / 无交集回退
"""
import uuid

import pytest
from unittest.mock import patch

from app.services.impact_analysis.integration_service import TIAIntegrationService
from app.services.impact_analysis.models import CoverageEntry
from app.services.impact_analysis.scheduler import ImpactSchedulePlan
from app.services.impact_analysis.change_analyzer import ChangeAnalyzer


@pytest.fixture
def test_case(db, test_project):
    """创建测试用例（sync session 内）。

    复用全局 db + test_project fixture，case_no 加随机后缀避免唯一约束冲突。
    """
    from app.models.test_case import TestCase

    suffix = uuid.uuid4().hex[:8]
    tc = TestCase(
        case_no=f"TC-TIA-{suffix}",
        project_id=test_project.id,
        module="TIA测试",
        title=f"TIA覆盖率用例-{suffix}",
        precondition="无",
        steps_json=[],
        expected_result="成功",
        priority=1,
        case_type="UI",
        generate_status=1,
    )
    db.add(tc)
    db.flush()
    return tc


class TestLoadCoverageEntries:
    """load_coverage_entries 方法测试。"""

    def test_load_empty_project(self, db, test_project):
        """空项目返回空列表。"""
        service = TIAIntegrationService(db=db, project_root=".")
        entries = service.load_coverage_entries(project_id=test_project.id)
        assert entries == []

    def test_load_with_data(self, db, test_project, test_case):
        """有数据时返回 CoverageEntry 列表。"""
        from app.models.test_coverage_map import TestCoverageMap

        db.add(TestCoverageMap(
            project_id=test_project.id,
            test_case_id=test_case.id,
            file_path="app/foo.py",
            line_start=1,
            line_end=10,
            test_name="test_foo",
        ))
        db.commit()

        service = TIAIntegrationService(db=db, project_root=".")
        entries = service.load_coverage_entries(project_id=test_project.id)
        assert len(entries) == 1
        assert entries[0].test_case_id == test_case.id
        assert entries[0].file_path == "app/foo.py"
        assert entries[0].line_start == 1
        assert entries[0].line_end == 10
        assert entries[0].test_name == "test_foo"

    def test_load_invalid_entry_filtered(self, db, test_project, test_case):
        """无效条目（line_start > line_end）被过滤。"""
        from app.models.test_coverage_map import TestCoverageMap

        db.add(TestCoverageMap(
            project_id=test_project.id,
            test_case_id=test_case.id,
            file_path="app/foo.py",
            line_start=10,
            line_end=1,  # 反序，无效
            test_name="",
        ))
        db.commit()

        service = TIAIntegrationService(db=db, project_root=".")
        entries = service.load_coverage_entries(project_id=test_project.id)
        assert entries == []


class TestUpsertCoverageEntries:
    """upsert_coverage_entries 方法测试。"""

    def test_upsert_new_entries(self, db, test_project, test_case):
        """新增覆盖率映射。"""
        service = TIAIntegrationService(db=db, project_root=".")
        entries = [
            CoverageEntry(
                test_case_id=test_case.id,
                file_path="app/a.py",
                line_start=1,
                line_end=10,
                test_name="test_a",
            ),
            CoverageEntry(
                test_case_id=test_case.id,
                file_path="app/b.py",
                line_start=20,
                line_end=30,
                test_name="test_b",
            ),
        ]

        rows = service.upsert_coverage_entries(
            project_id=test_project.id,
            test_case_id=test_case.id,
            entries=entries,
        )
        assert rows == 2

        # 验证写入
        loaded = service.load_coverage_entries(project_id=test_project.id)
        assert len(loaded) == 2

    def test_upsert_overwrite_existing(self, db, test_project, test_case):
        """重跑覆盖率时覆盖已有映射（幂等）。"""
        service = TIAIntegrationService(db=db, project_root=".")

        # 第一次写入
        entries_v1 = [
            CoverageEntry(
                test_case_id=test_case.id,
                file_path="app/old.py",
                line_start=1,
                line_end=10,
            ),
        ]
        service.upsert_coverage_entries(
            project_id=test_project.id,
            test_case_id=test_case.id,
            entries=entries_v1,
        )

        # 第二次写入（不同文件）
        entries_v2 = [
            CoverageEntry(
                test_case_id=test_case.id,
                file_path="app/new.py",
                line_start=1,
                line_end=5,
            ),
        ]
        rows = service.upsert_coverage_entries(
            project_id=test_project.id,
            test_case_id=test_case.id,
            entries=entries_v2,
        )
        assert rows == 1

        # 验证旧映射被删除
        loaded = service.load_coverage_entries(project_id=test_project.id)
        assert len(loaded) == 1
        assert loaded[0].file_path == "app/new.py"

    def test_upsert_empty_entries(self, db, test_project, test_case):
        """空列表不写入。"""
        service = TIAIntegrationService(db=db, project_root=".")
        rows = service.upsert_coverage_entries(
            project_id=test_project.id,
            test_case_id=test_case.id,
            entries=[],
        )
        assert rows == 0

    def test_upsert_invalid_entry_skipped(self, db, test_project, test_case):
        """无效条目被跳过。"""
        service = TIAIntegrationService(db=db, project_root=".")
        entries = [
            CoverageEntry(
                test_case_id=test_case.id,
                file_path="app/foo.py",
                line_start=10,
                line_end=1,  # 反序，无效
            ),
        ]
        rows = service.upsert_coverage_entries(
            project_id=test_project.id,
            test_case_id=test_case.id,
            entries=entries,
        )
        assert rows == 0


class TestBuildSchedulePlan:
    """build_schedule_plan 方法测试。"""

    def test_plan_tia_disabled(self, db, test_project, monkeypatch):
        """TIA_ENABLED=False 时返回全量执行计划。"""
        from app.core.config import settings

        monkeypatch.setattr(settings, "TIA_ENABLED", False)

        service = TIAIntegrationService(db=db, project_root=".")
        plan = service.build_schedule_plan(
            project_id=test_project.id,
            total_test_count=10,
        )
        assert plan.is_full_run is True
        assert "TIA_ENABLED=False" in plan.fallback_reason

    def test_plan_no_coverage_returns_full_run(
        self, db, test_project, monkeypatch
    ):
        """TIA_ENABLED=True 但无覆盖率数据时降级全量执行。"""
        from app.core.config import settings

        monkeypatch.setattr(settings, "TIA_ENABLED", True)

        service = TIAIntegrationService(db=db, project_root=".")
        # patch git diff 返回有变更。
        # 注意：必须 patch 类级方法而非实例——build_schedule_plan 内部会重建
        # self._scheduler（注入覆盖率数据），实例级 patch 会因重建而失效。
        with patch.object(
            ChangeAnalyzer, "analyze_git_diff",
            return_value=[type("C", (), {"file_path": "app/foo.py",
                                          "added_lines": frozenset({1}),
                                          "deleted_lines": frozenset(),
                                          "is_new_file": False,
                                          "is_deleted": False})],
        ):
            plan = service.build_schedule_plan(
                project_id=test_project.id,
                total_test_count=10,
            )
        assert plan.is_full_run is True
        assert "冷启动" in plan.fallback_reason


class TestFilterTestCaseIds:
    """filter_test_case_ids 方法测试。"""

    def test_filter_empty_input(self, db, test_project):
        """空输入返回空列表。"""
        service = TIAIntegrationService(db=db, project_root=".")
        case_ids, plan = service.filter_test_case_ids(
            project_id=test_project.id,
            all_case_ids=[],
        )
        assert case_ids == []
        assert plan.is_full_run is True

    def test_filter_tia_disabled_returns_all(self, db, test_project, monkeypatch):
        """TIA_ENABLED=False 时返回全量用例。"""
        from app.core.config import settings

        monkeypatch.setattr(settings, "TIA_ENABLED", False)

        service = TIAIntegrationService(db=db, project_root=".")
        all_ids = [1, 2, 3, 4, 5]
        case_ids, plan = service.filter_test_case_ids(
            project_id=test_project.id,
            all_case_ids=all_ids,
        )
        assert case_ids == all_ids
        assert plan.is_full_run is True

    def test_filter_no_intersection_returns_all(
        self, db, test_project, monkeypatch
    ):
        """TIA 调度结果与待执行用例无交集时回退全量。"""
        from app.core.config import settings

        monkeypatch.setattr(settings, "TIA_ENABLED", True)

        service = TIAIntegrationService(db=db, project_root=".")
        # mock build_schedule_plan 返回有效 plan，但 ID 不在 all_case_ids 中
        fake_plan = ImpactSchedulePlan(
            test_case_ids=[100, 200],  # 不在 all_ids 中
            is_full_run=False,
            reduction_ratio=0.5,
        )
        with patch.object(
            service, "build_schedule_plan", return_value=fake_plan
        ):
            all_ids = [1, 2, 3]
            case_ids, plan = service.filter_test_case_ids(
                project_id=test_project.id,
                all_case_ids=all_ids,
            )
        assert case_ids == all_ids
        assert plan.is_full_run is True
        assert "无交集" in plan.fallback_reason

    def test_filter_partial_selection(self, db, test_project, monkeypatch):
        """TIA 调度结果与待执行用例有部分交集时返回交集。"""
        from app.core.config import settings

        monkeypatch.setattr(settings, "TIA_ENABLED", True)

        service = TIAIntegrationService(db=db, project_root=".")
        # mock build_schedule_plan 返回有效 plan，ID 部分在 all_case_ids 中
        fake_plan = ImpactSchedulePlan(
            test_case_ids=[1, 2, 100],  # 1, 2 在 all_ids 中，100 不在
            is_full_run=False,
            reduction_ratio=0.6,
        )
        with patch.object(
            service, "build_schedule_plan", return_value=fake_plan
        ):
            all_ids = [1, 2, 3, 4, 5]
            case_ids, plan = service.filter_test_case_ids(
                project_id=test_project.id,
                all_case_ids=all_ids,
            )
        assert case_ids == [1, 2]
        assert plan is fake_plan
