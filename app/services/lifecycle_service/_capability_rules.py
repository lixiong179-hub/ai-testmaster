"""
Capability 生命周期状态流转规则

定义 TestCapability 的合法状态转换与异常类。
状态流转方向：active → deprecated → archived（终态不可逆）。
允许 active → archived（直接归档）。
"""
from app.models.enums import CapabilityStatus


CAPABILITY_TRANSITION_RULES: dict[tuple[str, str], dict] = {
    (CapabilityStatus.ACTIVE.value, CapabilityStatus.DEPRECATED.value): {
        "description": "活跃能力标记为废弃",
    },
    (CapabilityStatus.ACTIVE.value, CapabilityStatus.ARCHIVED.value): {
        "description": "活跃能力直接归档",
    },
    (CapabilityStatus.DEPRECATED.value, CapabilityStatus.ARCHIVED.value): {
        "description": "废弃能力归档",
    },
}

_CAPABILITY_VALID_TRANSITIONS: dict[str, set[str]] = {}
for (_from, _to), _rule in CAPABILITY_TRANSITION_RULES.items():
    _CAPABILITY_VALID_TRANSITIONS.setdefault(_from, set()).add(_to)


class IllegalCapabilityTransition(ValueError):
    """Capability 非法状态流转异常"""

    def __init__(self, fromStatus: str, toStatus: str, detail: str = ""):
        self.fromStatus = fromStatus
        self.toStatus = toStatus
        msg = f"Illegal capability transition: {fromStatus} -> {toStatus}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)
