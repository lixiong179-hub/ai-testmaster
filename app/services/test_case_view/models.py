"""测试用例视图数据模型 - 定义双视图体系的数据类。

包含:
    - BusinessStepView: 业务视图步骤
    - TechnicalStepView: 技术视图步骤
    - BusinessTestCaseView: 业务视图用例
    - TechnicalTestCaseView: 技术视图用例
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class BusinessStepView:
    """业务视图步骤 - 面向非技术人员的步骤展示。"""
    step_number: int
    action: str
    expected_result: str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应序列化。"""
        return {
            "step_number": self.step_number,
            "action": self.action,
            "expected_result": self.expected_result
        }


@dataclass
class TechnicalStepView:
    """技术视图步骤 - 面向测试工程师的步骤展示。"""
    step_number: int
    action: str
    expected_result: str
    has_locator: bool
    locator_status: str
    css_selector: Optional[str] = None
    xpath: Optional[str] = None
    ai_coordinate: Optional[Dict[str, float]] = None
    element_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，仅包含非空的技术字段。"""
        result = {
            "step_number": self.step_number,
            "action": self.action,
            "expected_result": self.expected_result,
            "has_locator": self.has_locator,
            "locator_status": self.locator_status
        }
        if self.css_selector:
            result["css_selector"] = self.css_selector
        if self.xpath:
            result["xpath"] = self.xpath
        if self.ai_coordinate:
            result["ai_coordinate"] = self.ai_coordinate
        if self.element_type:
            result["element_type"] = self.element_type
        return result


@dataclass
class BusinessTestCaseView:
    """业务视图测试用例 - 面向非技术人员的用例展示。"""
    case_id: int
    case_no: str
    title: str
    description: Optional[str]
    precondition: Optional[str]
    steps: List[BusinessStepView] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，包含步骤总数统计。"""
        return {
            "case_id": self.case_id,
            "case_no": self.case_no,
            "title": self.title,
            "description": self.description,
            "precondition": self.precondition,
            "steps": [s.to_dict() for s in self.steps],
            "total_steps": len(self.steps)
        }


@dataclass
class TechnicalTestCaseView:
    """技术视图测试用例 - 面向测试工程师的用例展示。"""
    case_id: int
    case_no: str
    title: str
    steps: List[TechnicalStepView] = field(default_factory=list)
    locator_coverage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，覆盖率保留一位小数。"""
        return {
            "case_id": self.case_id,
            "case_no": self.case_no,
            "title": self.title,
            "steps": [s.to_dict() for s in self.steps],
            "total_steps": len(self.steps),
            "locator_coverage": f"{self.locator_coverage:.1f}%"
        }
