
"""执行器Mixin - 组合初始化、数据对象和浏览器管理能力。"""
from app.services.precondition.init_mixin import InitMixin
from app.services.precondition.test_object_mixin import TestObjectInfoMixin
from app.services.precondition.browser_mixin import BrowserMixin


class ExecutorMixin(InitMixin, TestObjectInfoMixin, BrowserMixin):
    """执行器Mixin - 组合所有执行相关能力。"""
    pass
