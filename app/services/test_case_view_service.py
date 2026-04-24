"""测试用例视图服务 - 兼容性入口模块。

本模块仅作为向后兼容的导入入口，所有实现已迁移至
app.services.test_case_view 子包的各Mixin模块中。

迁移映射:
    - 数据类 -> models.py
    - 业务视图方法 -> business_view_mixin.py
    - 技术视图方法 -> technical_view_mixin.py
    - 视图配置方法 -> view_config_mixin.py
    - Excel导入导出 -> excel_mixin.py
"""
from app.services.test_case_view import (
    TestCaseViewService,
    BusinessStepView,
    TechnicalStepView,
    BusinessTestCaseView,
    TechnicalTestCaseView,
)

__all__ = [
    'TestCaseViewService',
    'BusinessStepView',
    'TechnicalStepView',
    'BusinessTestCaseView',
    'TechnicalTestCaseView',
]
