"""Excel导入导出Mixin - 组合导出、导入、验证三个子Mixin。

标准格式: 双Sheet（用例信息+测试步骤），包含定位信息
功能用例格式: 单Sheet，纯功能描述，面向第三方公司
"""
from app.services.test_case_view.excel_export_mixin import ExcelExportMixin
from app.services.test_case_view.excel_import_mixin import ExcelImportMixin
from app.services.test_case_view.excel_validate_mixin import ExcelValidateMixin


class ExcelMixin(ExcelExportMixin, ExcelImportMixin, ExcelValidateMixin):
    """Excel导入导出 - 组合导出、导入、验证能力。"""
    pass
