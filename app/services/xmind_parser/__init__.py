from app.services.xmind_parser._parse import XmindParseError, _ParseMixin
from app.services.xmind_parser._util import _UtilMixin


class XmindParser(_ParseMixin, _UtilMixin):
    pass


__all__ = ["XmindParser", "XmindParseError"]
