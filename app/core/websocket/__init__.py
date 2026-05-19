import threading
from typing import Dict, List
from fastapi import WebSocket

from app.core.websocket._core import _CoreMixin
from app.core.websocket._messages import _MessageMixin


class ConnectionManager(_CoreMixin, _MessageMixin):

    MAX_CONNECTIONS_PER_EXECUTION = 10

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self._lock = threading.Lock()


manager = ConnectionManager()

__all__ = ["ConnectionManager", "manager"]
