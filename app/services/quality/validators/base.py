"""校验器基类与数据结构定义。

所有校验器必须继承 BaseValidator 并实现 validate 方法，
返回统一的 ValidationResult（4档状态）。

状态严重度排序: rejected > pending_review > warning > passed
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional


class Severity(IntEnum):
    """校验结果严重度枚举，值越大越严重。"""
    passed = 0
    warning = 1
    pending_review = 2
    rejected = 3


@dataclass
class ValidationIssue:
    """单条校验问题。

    Attributes:
        field: 出问题的字段名
        message: 问题描述
        severity: 严重度（passed/warning/pending_review/rejected）
    """
    field: str
    message: str
    severity: str = "passed"

    def __post_init__(self) -> None:
        valid = {s.name for s in Severity}
        if self.severity not in valid:
            raise ValueError(
                f"severity must be one of {sorted(valid)}, got '{self.severity}'"
            )


@dataclass
class ValidationResult:
    """校验结果，包含4档状态和问题列表。

    Attributes:
        status: 整体状态（passed/warning/pending_review/rejected）
        issues: 所有校验问题列表
    """
    status: str = "passed"
    issues: List[ValidationIssue] = field(default_factory=list)

    def __post_init__(self) -> None:
        valid = {s.name for s in Severity}
        if self.status not in valid:
            raise ValueError(
                f"status must be one of {sorted(valid)}, got '{self.status}'"
            )

    @staticmethod
    def merge(results: List["ValidationResult"]) -> "ValidationResult":
        """合并多个校验结果，取最严重状态，汇总所有问题。"""
        if not results:
            return ValidationResult(status="passed", issues=[])
        worst = max(
            results,
            key=lambda r: Severity[r.status].value,
        )
        all_issues: List[ValidationIssue] = []
        for r in results:
            all_issues.extend(r.issues)
        return ValidationResult(status=worst.status, issues=all_issues)


class BaseValidator(ABC):
    """校验器抽象基类。

    所有校验器必须实现 validate 方法，接收用例数据和上下文，
    返回 ValidationResult。
    """

    @abstractmethod
    def validate(
        self,
        case_data: Dict,
        context: Optional[Dict] = None,
    ) -> ValidationResult:
        """执行校验并返回结果。

        Args:
            case_data: 用例数据字典
            context: 上下文信息（如项目级规则覆盖、UI规格等）

        Returns:
            ValidationResult: 校验结果
        """
        ...
