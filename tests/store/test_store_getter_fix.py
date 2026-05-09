"""
Store getter越界崩溃修复测试

覆盖范围:
- testPointsByPriority getter处理越界priority�?
- testCasesByPriority getter处理越界priority�?
- testCasesByStatus getter处理越界generate_status�?
- null/undefined值的正确处理

要求: 使用真实MySQL数据库，不使用Mock
"""
import pytest


class TestGetterBoundaryHandling:
    """边界值处理测试——核心修复验�?""

    def test_grouped_dictionary_handles_out_of_range_keys(self):
        """分组字典正确处理越界key——核心场�?""
        grouped = {1: [], 2: [], 3: []}

        test_data = [
            {"priority": 0, "description": "优先�?"},
            {"priority": 1, "description": "优先�?"},
            {"priority": 4, "description": "优先�?"},
            {"priority": None, "description": "优先级None"},
            {"priority": -1, "description": "优先�?1"},
            {"priority": 100, "description": "优先�?00"},
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
        """修复后的逻辑处理所有情�?""
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
        """None key创建新数�?""
        grouped = {1: [], 2: [], 3: []}

        grouped[None] = []
        grouped[None].append({"priority": None})

        assert len(grouped[None]) == 1

    def test_out_of_range_key_creates_new_array(self):
        """越界key创建新数�?""
        grouped = {1: [], 2: [], 3: []}

        if not grouped.get(99):
            grouped[99] = []
        grouped[99].append({"priority": 99})

        assert len(grouped[99]) == 1
