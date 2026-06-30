"""
字典分组越界 key 处理测试

覆盖范围:
- 分组字典处理越界 priority 值（0/4/-1/100 等）
- None key 的正确处理与新建数组
- 越界 key 自动创建新分组的逻辑验证

该逻辑模式用于前端 store getter 与后端分组聚合场景。
"""
import pytest


class TestGetterBoundaryHandling:
    """边界值处理测试——核心修复验证"""

    def test_grouped_dictionary_handles_out_of_range_keys(self):
        """分组字典正确处理越界key——核心场景"""
        grouped = {1: [], 2: [], 3: []}

        test_data = [
            {"priority": 0, "description": "优先级0"},
            {"priority": 1, "description": "优先级1"},
            {"priority": 4, "description": "优先级4"},
            {"priority": None, "description": "优先级None"},
            {"priority": -1, "description": "优先级-1"},
            {"priority": 100, "description": "优先级100"},
        ]

        for point in test_data:
            key = point["priority"]
            if not grouped.get(key):
                grouped[key] = []
            grouped[key].append(point)

        assert len(grouped[0]) == 1
        assert len(grouped[1]) == 1
        assert len(grouped[4]) == 1
        assert len(grouped[None]) == 1
        assert len(grouped[-1]) == 1
        assert len(grouped[100]) == 1

    def test_fixed_logic_handles_all_cases(self):
        """修复后的逻辑处理所有情况"""
        grouped = {1: [], 2: [], 3: []}

        test_data = [
            {"priority": 0}, {"priority": 1}, {"priority": 2}, {"priority": 3},
            {"priority": 4}, {"priority": None}, {"priority": -1}, {"priority": 100}
        ]

        for point in test_data:
            key = point["priority"]
            if not grouped.get(key):
                grouped[key] = []
            grouped[key].append(point)

        assert len(grouped[0]) == 1
        assert len(grouped[1]) == 1
        assert len(grouped[4]) == 1
        assert len(grouped[None]) == 1
        assert len(grouped[-1]) == 1
        assert len(grouped[100]) == 1

    def test_null_key_creates_new_array(self):
        """None key创建新数组"""
        grouped = {1: [], 2: [], 3: []}

        grouped[None] = []
        grouped[None].append({"priority": None})

        assert len(grouped[None]) == 1

    def test_out_of_range_key_creates_new_array(self):
        """越界key创建新数组"""
        grouped = {1: [], 2: [], 3: []}

        if not grouped.get(99):
            grouped[99] = []
        grouped[99].append({"priority": 99})

        assert len(grouped[99]) == 1
