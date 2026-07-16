"""test_case_generation - 上下文构建器（thin wrapper）。

实际实现拆分至：
- _context_loaders_mixin.py: 测试点加载、上下文骨架编排与收尾、需求质量评估
- _requirement_ui_loaders_mixin.py: 需求文档与 UI 描述加载器
- _history_scoring_mixin.py: 历史用例信任度与完整性评分

本文件保持向后兼容，原有 `from ... import ContextBuilder` 路径无需修改。
"""
from sqlalchemy.orm import Session

from app.services.test_case_generation._context_loaders_mixin import _ContextLoadersMixin
from app.services.test_case_generation._history_scoring_mixin import _HistoryScoringMixin
from app.services.test_case_generation._requirement_ui_loaders_mixin import _RequirementUiLoadersMixin


class ContextBuilder(_ContextLoadersMixin, _RequirementUiLoadersMixin, _HistoryScoringMixin):
    """测试用例生成上下文构建器（组合自多个 mixin）。

    职责：
        1. 加载测试点（指定 ID 或分页+未覆盖优先）
        2. 加载需求文档内容（按文件 ID 或测试点关联/关键词匹配）
        3. 加载 UI 描述（按屏幕 ID/文件 ID/关键词匹配）
        4. 历史用例信任度过滤与完整性评分
    """

    __test__ = False

    def __init__(self, db: Session) -> None:
        self.db = db


# 向后兼容别名：历史代码以 TestCaseGenerationBaseMixin 名称实例化
TestCaseGenerationBaseMixin = ContextBuilder
