"""TIA 集成服务（Phase 1 Task 4：Test Impact Analysis）

业务用途：将 TIA 模块接入测试执行链路与 API 层，提供：
1. 从 DB 加载 CoverageEntry 列表（避免每次重新解析 coverage.json）；
2. 测试执行后采集覆盖率并 upsert 到 test_coverage_maps 表；
3. 调用 ImpactScheduler 生成 ImpactSchedulePlan；
4. 将 plan 应用于待执行用例 ID 列表，返回筛选后的执行范围。

设计原则：
1. 依赖注入 db: Session，禁止内部新建 Session；
2. 所有 IO 异常捕获并降级（返回全量执行计划），不阻断主流程；
3. TIA_ENABLED=False 时直接返回全量执行，灰度回退；
4. upsert 使用 MySQL INSERT ... ON DUPLICATE KEY UPDATE，
   通过 (test_case_id, file_path) 唯一键去重。

依赖：
- app.services.impact_analysis.scheduler.ImpactScheduler
- app.services.impact_analysis.coverage_collector.CoverageCollector
- app.models.test_coverage_map.TestCoverageMap
"""
import logging
from typing import List, Optional, Tuple

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import BASE_DIR, settings
from app.models.test_coverage_map import TestCoverageMap
from app.services.impact_analysis.coverage_collector import CoverageCollector
from app.services.impact_analysis.models import CoverageEntry
from app.services.impact_analysis.scheduler import (
    ImpactSchedulePlan,
    ImpactScheduler,
)

logger = logging.getLogger(__name__)


class TIAIntegrationService:
    """TIA 集成服务：DB 加载/写入覆盖率、生成调度计划、筛选执行用例。

    用法：
        service = TIAIntegrationService(db=db, project_root="/path/to/project")
        plan = service.build_schedule_plan(
            project_id=1,
            total_test_count=100,
            base_ref="HEAD~1",
            target_ref="HEAD",
        )
        if plan.is_effective:
            run_only(plan.test_case_ids)
        else:
            run_all()
    """

    def __init__(self, db: Session, project_root: Optional[str] = None) -> None:
        """初始化集成服务。

        Args:
            db: 同步数据库会话。
            project_root: 项目根目录，None 时使用 config.BASE_DIR。
        """
        self._db = db
        self._project_root = project_root or str(BASE_DIR)
        self._scheduler = ImpactScheduler(project_root=self._project_root)
        self._collector = CoverageCollector(project_root=self._project_root)

    # ── 覆盖率加载 ────────────────────────────────────────────────

    def load_coverage_entries(self, project_id: int) -> List[CoverageEntry]:
        """从 DB 按 project_id 加载覆盖率映射，构造 CoverageEntry 列表。

        边界场景：
        1. 项目无覆盖率数据 → 返回空列表（调用方走全量执行降级）；
        2. DB 查询异常 → 返回空列表 + 告警日志。
        """
        try:
            rows = (
                self._db.execute(
                    select(TestCoverageMap).where(
                        TestCoverageMap.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
            entries: List[CoverageEntry] = []
            for row in rows:
                entry = CoverageEntry(
                    test_case_id=row.test_case_id,
                    file_path=row.file_path,
                    line_start=row.line_start,
                    line_end=row.line_end,
                    test_name=row.test_name or "",
                )
                if entry.is_valid():
                    entries.append(entry)
            logger.info(
                f"加载覆盖率映射: project_id={project_id}, entries={len(entries)}"
            )
            return entries
        except Exception as e:
            logger.warning(
                f"加载覆盖率映射失败 project_id={project_id}: {e}"
            )
            return []

    # ── 覆盖率写入 ────────────────────────────────────────────────

    def upsert_coverage_entries(
        self,
        project_id: int,
        test_case_id: int,
        entries: List[CoverageEntry],
    ) -> int:
        """将覆盖率条目 upsert 到 test_coverage_maps 表。

        业务用途：测试执行完成后采集覆盖率，调用本方法持久化映射。
        实现采用 MySQL INSERT ... ON DUPLICATE KEY UPDATE，
        通过 (test_case_id, file_path) 唯一键去重。

        Args:
            project_id: 项目 ID。
            test_case_id: 测试用例 ID（与 entries 中的 test_case_id 一致）。
            entries: 覆盖率条目列表。

        Returns:
            实际写入/更新的行数。
        """
        if not entries:
            return 0

        # 先删除该用例的所有旧映射（保证幂等：重跑覆盖率时不会残留过期行）
        self._db.execute(
            text(
                "DELETE FROM test_coverage_maps WHERE test_case_id = :case_id"
            ),
            {"case_id": test_case_id},
        )

        # 批量插入新映射
        rows_to_insert = []
        for entry in entries:
            if not entry.is_valid():
                continue
            if entry.test_case_id != test_case_id:
                logger.warning(
                    f"覆盖率条目 test_case_id 不一致: expected={test_case_id}, "
                    f"actual={entry.test_case_id}, skip"
                )
                continue
            rows_to_insert.append(
                {
                    "project_id": project_id,
                    "test_case_id": test_case_id,
                    "file_path": entry.file_path,
                    "line_start": entry.line_start,
                    "line_end": entry.line_end,
                    "test_name": entry.test_name or "",
                }
            )

        if not rows_to_insert:
            self._db.commit()
            return 0

        # 使用 INSERT ... ON DUPLICATE KEY UPDATE 处理同一 (test_case_id, file_path)
        # 多个连续行范围的情况（CoverageCollector 会将非连续行拆分为多条 entry）
        self._db.execute(
            text(
                "INSERT INTO test_coverage_maps "
                "(project_id, test_case_id, file_path, line_start, line_end, test_name, created_at, updated_at) "
                "VALUES (:project_id, :test_case_id, :file_path, :line_start, :line_end, :test_name, UTC_TIMESTAMP(), UTC_TIMESTAMP()) "
                "ON DUPLICATE KEY UPDATE "
                "line_start = VALUES(line_start), "
                "line_end = VALUES(line_end), "
                "test_name = VALUES(test_name), "
                "updated_at = UTC_TIMESTAMP()"
            ),
            rows_to_insert,
        )
        self._db.commit()
        logger.info(
            f"覆盖率映射写入: project_id={project_id}, case_id={test_case_id}, "
            f"rows={len(rows_to_insert)}"
        )
        return len(rows_to_insert)

    def ingest_coverage_json(
        self,
        project_id: int,
        test_case_id: int,
        json_path: str,
        test_name: str = "",
    ) -> int:
        """解析 coverage.json 并写入 DB。

        业务用途：测试执行后采集 coverage.py 输出，调用本方法持久化。
        边界场景：文件不存在/解析失败 → 返回 0 + 告警日志。
        """
        entries = self._collector.parse_coverage_json(
            json_path=json_path,
            test_case_id=test_case_id,
            test_name=test_name,
        )
        if not entries:
            logger.info(
                f"覆盖率采集为空: project_id={project_id}, case_id={test_case_id}"
            )
            return 0
        return self.upsert_coverage_entries(
            project_id=project_id,
            test_case_id=test_case_id,
            entries=entries,
        )

    # ── 调度计划生成 ──────────────────────────────────────────────

    def build_schedule_plan(
        self,
        project_id: int,
        total_test_count: int = 0,
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
        avg_test_duration_seconds: Optional[float] = None,
    ) -> ImpactSchedulePlan:
        """生成 TIA 调度计划。

        业务用途：测试执行前调用，根据代码变更与覆盖率映射生成执行计划。
        边界场景：
        1. TIA_ENABLED=False → 直接返回全量执行计划；
        2. 加载覆盖率失败 → 返回全量执行（降级）；
        3. ImpactScheduler 内部异常 → 返回全量执行（降级）。
        """
        if not settings.TIA_ENABLED:
            return ImpactSchedulePlan(
                is_full_run=True,
                fallback_reason="TIA_ENABLED=False，全量执行",
            )

        try:
            entries = self.load_coverage_entries(project_id=project_id)
            # 重建 scheduler 注入加载到的覆盖率数据
            self._scheduler = ImpactScheduler(
                project_root=self._project_root,
                coverage_entries=entries,
            )
            plan = self._scheduler.schedule(
                base_ref=base_ref or settings.TIA_GIT_BASE_REF,
                target_ref=target_ref or settings.TIA_GIT_TARGET_REF,
                total_test_count=total_test_count,
                avg_test_duration_seconds=(
                    avg_test_duration_seconds
                    if avg_test_duration_seconds is not None
                    else settings.TIA_AVG_TEST_DURATION_SECONDS
                ),
            )
            logger.info(
                f"TIA 调度计划生成: project_id={project_id}, "
                f"is_full_run={plan.is_full_run}, "
                f"reduction_ratio={plan.reduction_ratio:.2%}, "
                f"test_count={len(plan.test_case_ids)}"
            )
            return plan
        except Exception as e:
            logger.warning(
                f"TIA 调度计划生成失败，降级全量执行: project_id={project_id}, "
                f"error={e}"
            )
            return ImpactSchedulePlan(
                is_full_run=True,
                fallback_reason=f"TIA 调度失败: {e}",
            )

    # ── 执行用例筛选 ──────────────────────────────────────────────

    def filter_test_case_ids(
        self,
        project_id: int,
        all_case_ids: List[int],
        base_ref: Optional[str] = None,
        target_ref: Optional[str] = None,
    ) -> Tuple[List[int], ImpactSchedulePlan]:
        """根据 TIA 调度计划筛选待执行用例 ID。

        业务用途：测试执行链路调用本方法获取最终执行范围。
        返回 (实际执行用例 ID 列表, 调度计划)，调度计划供日志/审计使用。

        边界场景：
        1. plan.is_full_run=True → 返回 all_case_ids（全量执行）；
        2. plan.test_case_ids 为空但 plan.is_effective=False → 返回 all_case_ids；
        3. plan.test_case_ids 中的 ID 不在 all_case_ids 中 → 自动过滤。
        """
        if not all_case_ids:
            return [], ImpactSchedulePlan(
                is_full_run=True,
                fallback_reason="无待执行用例",
            )

        plan = self.build_schedule_plan(
            project_id=project_id,
            total_test_count=len(all_case_ids),
            base_ref=base_ref,
            target_ref=target_ref,
        )

        if plan.is_full_run or not plan.test_case_ids:
            return all_case_ids, plan

        # 过滤：仅保留同时存在于 all_case_ids 与 plan.test_case_ids 的 ID
        all_set = set(all_case_ids)
        filtered = [tid for tid in plan.test_case_ids if tid in all_set]
        if not filtered:
            logger.warning(
                f"TIA 调度结果与待执行用例无交集，回退全量执行: "
                f"project_id={project_id}"
            )
            return all_case_ids, ImpactSchedulePlan(
                is_full_run=True,
                fallback_reason="TIA 调度结果与待执行用例无交集",
            )

        logger.info(
            f"TIA 筛选用例: project_id={project_id}, "
            f"all={len(all_case_ids)}, filtered={len(filtered)}, "
            f"saved={len(all_case_ids) - len(filtered)}"
        )
        return filtered, plan


__all__ = ["TIAIntegrationService"]
