"""覆盖率采集器（Phase 1 Task 4：Test Impact Analysis）

业务用途：解析 coverage.py 输出的 JSON，建立测试用例 ↔ 代码行映射。
设计原则：
1. 输入为 coverage.json 路径或字典，纯函数无副作用；
2. 解析失败时返回空列表，不抛异常（监控告警由调用方处理）；
3. 支持增量采集：多次调用合并已有映射。

依赖：coverage.py（数据源，由 pytest --cov 生成）
"""
import json
import logging
import os
from typing import Dict, List, Optional

from app.services.impact_analysis.models import CoverageEntry

logger = logging.getLogger(__name__)


class CoverageCollector:
    """覆盖率数据采集器。

    用法：
        collector = CoverageCollector(project_root="/path/to/project")
        entries = collector.parse_coverage_json("/path/to/coverage.json", test_case_id=1)
    """

    def __init__(self, project_root: str) -> None:
        if not project_root:
            raise ValueError("project_root 不能为空")
        self._project_root = os.path.abspath(project_root)

    def parse_coverage_json(
        self,
        json_path: str,
        test_case_id: int,
        test_name: str = "",
    ) -> List[CoverageEntry]:
        """解析 coverage.py 生生的 JSON 文件。

        边界场景：
        1. 文件不存在 → 返回空列表 + 告警日志；
        2. JSON 格式错误 → 返回空列表 + 告警日志；
        3. file 字段为绝对路径 → 转换为相对路径。
        """
        if not os.path.exists(json_path):
            logger.warning(f"覆盖率文件不存在: {json_path}")
            return []

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"覆盖率文件解析失败: {json_path}, error={e}")
            return []

        return self.parse_coverage_data(data, test_case_id, test_name)

    def parse_coverage_data(
        self,
        data: Dict,
        test_case_id: int,
        test_name: str = "",
    ) -> List[CoverageEntry]:
        """解析 coverage.py 字典数据。

        coverage.py JSON 格式（file 章节）：
            {
              "files": {
                "app/services/foo.py": {
                  "executed_lines": [1, 2, 3, 10, 11],
                  "summary": {"covered_lines": 5, ...}
                }
              }
            }
        """
        if test_case_id <= 0:
            raise ValueError("test_case_id 必须为正整数")

        files = data.get("files", {})
        if not files:
            logger.warning("覆盖率数据无 files 字段")
            return []

        entries: List[CoverageEntry] = []
        for file_path, file_data in files.items():
            relative_path = self._to_relative_path(file_path)
            if not relative_path:
                continue  # 跳过项目外文件

            executed_lines = file_data.get("executed_lines", [])
            if not executed_lines:
                continue

            # 将连续行号合并为范围，减少条目数量
            for line_start, line_end in self._merge_consecutive_lines(executed_lines):
                entry = CoverageEntry(
                    test_case_id=test_case_id,
                    file_path=relative_path,
                    line_start=line_start,
                    line_end=line_end,
                    test_name=test_name,
                )
                if entry.is_valid():
                    entries.append(entry)

        logger.info(
            f"采集覆盖率条目: test_case_id={test_case_id}, "
            f"files={len(files)}, entries={len(entries)}"
        )
        return entries

    def _to_relative_path(self, file_path: str) -> Optional[str]:
        """将绝对路径转换为相对项目根目录的路径。

        边界场景：路径不在项目根目录下时返回 None。
        """
        if not file_path:
            return None
        abs_path = os.path.abspath(file_path)
        if not abs_path.startswith(self._project_root):
            return None
        return os.path.relpath(abs_path, self._project_root).replace(os.sep, "/")

    @staticmethod
    def _merge_consecutive_lines(lines: List[int]) -> List[tuple]:
        """将连续行号合并为 (start, end) 范围。

        示例：[1, 2, 3, 10, 11, 15] → [(1, 3), (10, 11), (15, 15)]
        """
        if not lines:
            return []
        sorted_lines = sorted(set(lines))
        ranges: List[tuple] = []
        start = prev = sorted_lines[0]
        for line in sorted_lines[1:]:
            if line == prev + 1:
                prev = line
            else:
                ranges.append((start, prev))
                start = prev = line
        ranges.append((start, prev))
        return ranges
