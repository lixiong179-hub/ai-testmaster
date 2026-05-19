from app.utils.ai_client_stream._analyze import _AnalyzeStreamMixin
from app.utils.ai_client_stream._generate import _GenerateStreamMixin


class AIStreamMixin(_AnalyzeStreamMixin, _GenerateStreamMixin):
    pass


__all__ = ["AIStreamMixin"]
