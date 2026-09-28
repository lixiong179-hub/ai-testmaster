"""TIA 数据模型（Phase 1 Task 4）

定义覆盖率条目、代码变更、影响范围等核心数据结构。
所有数据结构为 dataclass，纯数据无副作用，便于序列化与测试。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set


@dataclass(frozen=True)
class CoverageEntry:
    """覆盖率条目：测试用例覆盖的代码文件与行范围。

    业务用途：建立"测试用例 ↔ 代码"映射，供影响分析查询。
    边界场景：line_start > line_end 时视为无效条目，采集器应过滤。
    """
    test_case_id: int
    file_path: str  # 相对项目根目录的路径，如 app/services/foo.py
    line_start: int  # 起始行号（1-based）
    line_end: int  # 结束行号（1-based，包含）
    test_name: str = ""  # 测试函数名，便于调试

    def is_valid(self) -> bool:
        """校验条目有效性。"""
        return (
            self.test_case_id > 0
            and bool(self.file_path)
            and self.line_start > 0
            and self.line_end >= self.line_start
        )

    def covers_line(self, line: int) -> bool:
        """判断该条目是否覆盖指定行号。"""
        return self.line_start <= line <= self.line_end

    def overlaps(self, other_start: int, other_end: int) -> bool:
        """判断该条目行范围是否与指定区间重叠。"""
        return not (self.line_end < other_start or self.line_start > other_end)


@dataclass(frozen=True)
class CodeChange:
    """代码变更条目：git diff 解析出的单文件变更。

    业务用途：标识哪些文件哪些行范围发生了变更，供影响映射查询。
    """
    file_path: str
    added_lines: Set[int] = field(default_factory=set)  # 新增行号集合
    deleted_lines: Set[int] = field(default_factory=set)  # 删除行号集合
    is_new_file: bool = False  # 是否新增文件
    is_deleted: bool = False  # 是否删除文件

    @property
    def change_size(self) -> int:
        """变更行数（新增+删除）。"""
        return len(self.added_lines) + len(self.deleted_lines)

    def is_significant(self, threshold: int = 5) -> bool:
        """判断变更是否显著（避免空格/注释等微小变更触发分析）。"""
        return self.change_size >= threshold or self.is_new_file or self.is_deleted


@dataclass(frozen=True)
class ImpactRange:
    """影响范围：单个测试用例受影响的代码区域。"""
    test_case_id: int
    impacted_files: List[str] = field(default_factory=list)
    impacted_line_count: int = 0
    confidence: float = 0.0  # 置信度 0.0-1.0，基于覆盖率匹配度计算

    def is_high_confidence(self, threshold: float = 0.7) -> bool:
        """判断影响范围是否高置信度。"""
        return self.confidence >= threshold


@dataclass(frozen=True)
class ImpactResult:
    """TIA 分析结果：受影响的测试用例集合与调度建议。"""
    impacted_test_ids: List[int] = field(default_factory=list)
    total_test_count: int = 0  # 全量测试用例数
    impacted_files: List[str] = field(default_factory=list)
    reduction_ratio: float = 0.0  # 用例缩减比例（0.0-1.0）
    analysis_basis: str = ""  # 分析依据描述，如 "git diff vs coverage map"

    @property
    def saved_execution_count(self) -> int:
        """节省的执行用例数。"""
        return max(0, self.total_test_count - len(self.impacted_test_ids))

    @property
    def is_effective(self) -> bool:
        """分析是否有效（缩减比例 ≥10% 才值得启用 TIA 调度）。"""
        return self.reduction_ratio >= 0.1
