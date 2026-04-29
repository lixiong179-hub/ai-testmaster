"""数据模型定义 - 定义本子包所需的数据结构、枚举和结果模型。
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ComplexityScore:
    step_count: int = 0
    action_variety: int = 0
    precondition_count: int = 0
    has_verification: bool = False
    has_captcha: bool = False
    score: float = 0.0
    level: str = "simple"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_count": self.step_count,
            "action_variety": self.action_variety,
            "precondition_count": self.precondition_count,
            "has_verification": self.has_verification,
            "has_captcha": self.has_captcha,
            "score": round(self.score, 2),
            "level": self.level,
        }


@dataclass
class RedundancyScore:
    similar_case_count: int = 0
    similar_cases: List[Dict[str, Any]] = field(default_factory=list)
    duplicate_step_count: int = 0
    score: float = 0.0
    level: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "similar_case_count": self.similar_case_count,
            "similar_cases": self.similar_cases,
            "duplicate_step_count": self.duplicate_step_count,
            "score": round(self.score, 2),
            "level": self.level,
        }


@dataclass
class CoverageScore:
    total_elements: int = 0
    covered_elements: int = 0
    uncovered_elements: int = 0
    coverage_rate: float = 0.0
    score: float = 0.0
    level: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_elements": self.total_elements,
            "covered_elements": self.covered_elements,
            "uncovered_elements": self.uncovered_elements,
            "coverage_rate": round(self.coverage_rate, 2),
            "score": round(self.score, 2),
            "level": self.level,
        }


@dataclass
class QualityReport:
    case_id: int
    case_name: str
    overall_score: float = 0.0
    overall_level: str = "unrated"
    complexity: Optional[ComplexityScore] = None
    redundancy: Optional[RedundancyScore] = None
    coverage: Optional[CoverageScore] = None
    suggestions: List[str] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "overall_score": round(self.overall_score, 2),
            "overall_level": self.overall_level,
            "complexity": self.complexity.to_dict() if self.complexity else None,
            "redundancy": self.redundancy.to_dict() if self.redundancy else None,
            "coverage": self.coverage.to_dict() if self.coverage else None,
            "suggestions": self.suggestions,
            "analyzed_at": self.analyzed_at.isoformat(),
        }
