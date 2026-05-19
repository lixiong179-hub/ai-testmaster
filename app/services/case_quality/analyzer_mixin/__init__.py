from app.services.case_quality.analyzer_mixin._case_analyzer import _CaseAnalyzerMixin
from app.services.case_quality.analyzer_mixin._project_analyzer import _ProjectAnalyzerMixin


class AnalyzerMixin(_CaseAnalyzerMixin, _ProjectAnalyzerMixin):
    pass


CaseQualityAnalyzerMixin = AnalyzerMixin

__all__ = ["AnalyzerMixin", "CaseQualityAnalyzerMixin"]
