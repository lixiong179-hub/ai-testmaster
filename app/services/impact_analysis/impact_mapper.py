"""影响映射器（Phase 1 Task 4：Test Impact Analysis）

业务用途：基于覆盖率映射与代码变更，识别受影响的测试用例。
设计原则：
1. 输入为覆盖率条目列表与代码变更列表，纯函数无副作用；
2. 增量计算：仅查询变更文件，避免全量扫描；
3. 置信度量化：基于覆盖率匹配度计算，低置信度用例标记人工复核。

依赖：app.services.impact_analysis.models
"""
import logging
from typing import Dict, Iterable, List, Set

from app.services.impact_analysis.models import (
    CodeChange,
    CoverageEntry,
    ImpactRange,
    ImpactResult,
)

logger = logging.getLogger(__name__)


class ImpactMapper:
    """影响映射器：根据代码变更查询受影响测试用例。

    用法：
        mapper = ImpactMapper()
        result = mapper.map_impact(coverage_entries, code_changes, total_tests=100)
        # result.impacted_test_ids 即为应执行的测试用例 ID 列表
    """

    def map_impact(
        self,
        coverage_entries: Iterable[CoverageEntry],
        code_changes: Iterable[CodeChange],
        total_test_count: int = 0,
    ) -> ImpactResult:
        """计算受影响的测试用例集合。

        边界场景：
        1. 覆盖率数据为空 → 返回全量测试（无依据缩减）；
        2. 代码变更为空 → 返回空影响范围（无变更无需执行）；
        3. 变更文件无覆盖率映射 → 返回全量测试（保守策略）。
        """
        entries_list = list(coverage_entries)
        changes_list = list(code_changes)

        if not changes_list:
            return ImpactResult(
                impacted_test_ids=[],
                total_test_count=total_test_count,
                impacted_files=[],
                reduction_ratio=0.0,
                analysis_basis="无代码变更，跳过测试执行",
            )

        if not entries_list:
            # 覆盖率数据冷启动：返回全量测试
            logger.info("覆盖率数据为空，采用保守策略返回全量测试")
            return ImpactResult(
                impacted_test_ids=[],  # 空表示需全量执行
                total_test_count=total_test_count,
                impacted_files=[c.file_path for c in changes_list],
                reduction_ratio=0.0,
                analysis_basis="覆盖率数据冷启动，全量执行",
            )

        # 按文件分组覆盖率条目，加速查询
        coverage_by_file: Dict[str, List[CoverageEntry]] = {}
        for entry in entries_list:
            coverage_by_file.setdefault(entry.file_path, []).append(entry)

        impacted_test_ids: Set[int] = set()
        impacted_files: Set[str] = set()
        impacted_ranges: Dict[int, ImpactRange] = {}

        for change in changes_list:
            if change.is_deleted:
                # 文件被删除：覆盖该文件的所有测试受影响
                file_entries = coverage_by_file.get(change.file_path, [])
                for entry in file_entries:
                    impacted_test_ids.add(entry.test_case_id)
                    impacted_files.add(change.file_path)
                continue

            file_entries = coverage_by_file.get(change.file_path, [])
            if not file_entries:
                # 变更文件无覆盖率映射：保守策略，标记为低置信度
                impacted_files.add(change.file_path)
                continue

            # 查询覆盖变更行的测试用例
            change_lines = change.added_lines | change.deleted_lines
            matched_count_for_file: Dict[int, int] = {}
            for entry in file_entries:
                for line in change_lines:
                    if entry.covers_line(line):
                        impacted_test_ids.add(entry.test_case_id)
                        impacted_files.add(change.file_path)
                        matched_count_for_file[entry.test_case_id] = (
                            matched_count_for_file.get(entry.test_case_id, 0) + 1
                        )
                        break  # 单行匹配即可，避免重复计数

            # 计算置信度：匹配行数 / 变更行数
            for test_id, matched in matched_count_for_file.items():
                confidence = min(1.0, matched / max(1, len(change_lines)))
                impacted_ranges[test_id] = ImpactRange(
                    test_case_id=test_id,
                    impacted_files=[change.file_path],
                    impacted_line_count=matched,
                    confidence=confidence,
                )

        # 计算缩减比例
        if total_test_count > 0:
            reduction_ratio = 1.0 - (len(impacted_test_ids) / total_test_count)
        else:
            reduction_ratio = 0.0

        result = ImpactResult(
            impacted_test_ids=sorted(impacted_test_ids),
            total_test_count=total_test_count,
            impacted_files=sorted(impacted_files),
            reduction_ratio=reduction_ratio,
            analysis_basis=f"git diff vs coverage map, entries={len(entries_list)}, changes={len(changes_list)}",
        )

        logger.info(
            f"TIA 分析完成: impacted={len(result.impacted_test_ids)}, "
            f"total={total_test_count}, reduction={reduction_ratio:.2%}"
        )
        return result

    def filter_high_confidence(
        self,
        ranges: Iterable[ImpactRange],
        threshold: float = 0.7,
    ) -> List[int]:
        """筛选高置信度测试用例 ID。

        业务用途：低置信度用例标记人工复核，高置信度用例自动执行。
        """
        return sorted({
            r.test_case_id for r in ranges if r.is_high_confidence(threshold)
        })
