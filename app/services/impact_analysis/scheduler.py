"""智能调度器（Phase 1 Task 4：Test Impact Analysis）

业务用途：基于 TIA 分析结果生成测试执行计划，仅运行受影响用例。
设计原则：
1. 与现有 Pipeline 执行解耦，通过 ImpactSchedulePlan 接入；
2. 支持降级：TIA 失败时回退至全量执行；
3. 调度计划包含执行用例 ID 列表与预估节省时间。

依赖：app.services.impact_analysis.{coverage_collector, change_analyzer, impact_mapper}
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.impact_analysis.change_analyzer import ChangeAnalyzer
from app.services.impact_analysis.coverage_collector import CoverageCollector
from app.services.impact_analysis.impact_mapper import ImpactMapper
from app.services.impact_analysis.models import CoverageEntry, ImpactResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImpactSchedulePlan:
    """TIA 调度计划：包含执行用例与降级标志。

    业务用途：Pipeline 执行器读取此计划决定执行范围。
    边界场景：fallback=True 时执行全量用例，TIA 分析失败兜底。
    """
    test_case_ids: List[int] = field(default_factory=list)
    is_full_run: bool = False  # 是否全量执行
    fallback_reason: str = ""  # 降级原因（is_full_run=True 时填写）
    reduction_ratio: float = 0.0  # 用例缩减比例
    estimated_saved_seconds: float = 0.0  # 预估节省时间（秒）

    @property
    def is_effective(self) -> bool:
        """调度计划是否有效（非全量执行且缩减比例 ≥10%）。"""
        return not self.is_full_run and self.reduction_ratio >= 0.1


class ImpactScheduler:
    """智能调度器：编排覆盖率采集、变更分析、影响映射。

    用法：
        scheduler = ImpactScheduler(
            project_root="/path/to/project",
            coverage_entries=loaded_entries,
        )
        plan = scheduler.schedule(
            base_ref="HEAD~1",
            target_ref="HEAD",
            total_test_count=100,
            avg_test_duration_seconds=5.0,
        )
        if plan.is_effective:
            run_only(plan.test_case_ids)
        else:
            run_all()
    """

    def __init__(
        self,
        project_root: str,
        coverage_entries: Optional[List[CoverageEntry]] = None,
    ) -> None:
        if not project_root:
            raise ValueError("project_root 不能为空")
        self._project_root = project_root
        self._coverage_entries: List[CoverageEntry] = coverage_entries or []
        self._collector = CoverageCollector(project_root=project_root)
        self._analyzer = ChangeAnalyzer(project_root=project_root)
        self._mapper = ImpactMapper()

    def update_coverage_entries(self, entries: List[CoverageEntry]) -> None:
        """更新覆盖率映射（增量采集后调用）。"""
        if not entries:
            return
        self._coverage_entries.extend(entries)
        logger.info(f"覆盖率映射更新: +{len(entries)}, total={len(self._coverage_entries)}")

    def schedule(
        self,
        base_ref: str = "HEAD~1",
        target_ref: str = "HEAD",
        total_test_count: int = 0,
        avg_test_duration_seconds: float = 5.0,
    ) -> ImpactSchedulePlan:
        """生成 TIA 调度计划。

        边界场景：
        1. git diff 失败 → 全量执行（降级）；
        2. 覆盖率映射为空 → 全量执行（冷启动）；
        3. 受影响用例为 0 → 跳过执行（无变更影响）；
        4. 受影响用例占总数 >80% → 全量执行（缩减比例过低）。
        """
        # 1. 分析代码变更
        changes = self._analyzer.analyze_git_diff(base_ref, target_ref)
        if not changes:
            return ImpactSchedulePlan(
                is_full_run=True,
                fallback_reason="git diff 无变更或分析失败",
            )

        # 2. 计算影响范围
        result: ImpactResult = self._mapper.map_impact(
            coverage_entries=self._coverage_entries,
            code_changes=changes,
            total_test_count=total_test_count,
        )

        # 3. 降级策略：覆盖率冷启动
        if not self._coverage_entries:
            return ImpactSchedulePlan(
                is_full_run=True,
                fallback_reason="覆盖率数据冷启动，全量执行",
            )

        # 4. 降级策略：缩减比例过低
        if result.reduction_ratio < 0.2 and total_test_count > 0:
            logger.info(
                f"TIA 缩减比例过低 ({result.reduction_ratio:.2%})，回退全量执行"
            )
            return ImpactSchedulePlan(
                is_full_run=True,
                fallback_reason=f"缩减比例过低 ({result.reduction_ratio:.2%})",
            )

        # 5. 生成调度计划
        saved_count = max(0, total_test_count - len(result.impacted_test_ids))
        estimated_saved = saved_count * avg_test_duration_seconds

        logger.info(
            f"TIA 调度计划: 执行 {len(result.impacted_test_ids)}/{total_test_count}, "
            f"节省 {saved_count} 用例 (~{estimated_saved:.1f}s)"
        )

        return ImpactSchedulePlan(
            test_case_ids=result.impacted_test_ids,
            is_full_run=False,
            reduction_ratio=result.reduction_ratio,
            estimated_saved_seconds=estimated_saved,
        )
