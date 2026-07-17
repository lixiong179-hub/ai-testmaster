"""测试用例视图子包 - 支持业务视图和技术视图的双视图管理。

通过Mixin组合模式实现视图服务，各功能模块独立维护。

核心类:
    - TestCaseViewService: 视图服务主类

Mixin组合:
    - BusinessViewMixin: 业务视图查询与导出
    - TechnicalViewMixin: 技术视图查询与导出
    - ViewConfigMixin: 视图配置管理
    - ExcelMixin: Excel导入导出
    - TestCaseViewAsyncMixin: 异步版本方法（供 async 端点直接调用）
"""
from typing import Union
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.test_case_view.business_view_mixin import BusinessViewMixin
from app.services.test_case_view.technical_view_mixin import TechnicalViewMixin
from app.services.test_case_view.view_config_mixin import ViewConfigMixin
from app.services.test_case_view.excel_mixin import ExcelMixin
from app.services.test_case_view.async_mixin import TestCaseViewAsyncMixin
from app.services.test_case_view.models import (
    BusinessStepView,
    TechnicalStepView,
    BusinessTestCaseView,
    TechnicalTestCaseView,
)


class TestCaseViewService(
    BusinessViewMixin,
    TechnicalViewMixin,
    ViewConfigMixin,
    ExcelMixin,
    TestCaseViewAsyncMixin,
):
    """测试用例视图服务 - 提供业务视图和技术视图的查询、导出与导入功能。

    职责:
        - 业务视图查询与导出（Markdown/HTML）
        - 技术视图查询与导出（JSON/Python脚本）
        - 视图配置管理（步骤可见性控制）
        - Excel导入导出（标准格式/功能用例格式）
        - 定位覆盖率统计

    hybrid 模式：sync 端点用 sync 方法（BusinessViewMixin 等），
    async 端点用 async 方法（TestCaseViewAsyncMixin，方法名带 _async 后缀）。
    """

    __test__ = False

    def __init__(self, db: Union[Session, AsyncSession]) -> None:
        """初始化视图服务。

        Args:
            db: 数据库会话，sync 端点传 Session，async 端点传 AsyncSession。
        """
        self.db = db


__all__ = [
    'TestCaseViewService',
    'BusinessStepView',
    'TechnicalStepView',
    'BusinessTestCaseView',
    'TechnicalTestCaseView',
    'BusinessViewMixin',
    'TechnicalViewMixin',
    'ViewConfigMixin',
    'ExcelMixin',
    'TestCaseViewAsyncMixin',
]
