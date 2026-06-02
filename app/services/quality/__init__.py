"""QualityGate 统一校验体系。

提供用例入库前的多维度质量校验，所有校验器继承 BaseValidator，
输出统一的 ValidationResult（4档状态: passed/warning/pending_review/rejected）。
"""
