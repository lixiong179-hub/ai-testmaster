from app.services.xmind_case_parser._classify import TopicNode, _ClassifyMixin
from app.services.xmind_case_parser._parse import _ParseMixin
from app.services.xmind_case_parser._util import _UtilMixin


class XmindCaseParser(_ParseMixin, _ClassifyMixin, _UtilMixin):
    pass


__all__ = ["XmindCaseParser", "TopicNode"]
