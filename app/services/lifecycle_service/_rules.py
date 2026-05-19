from app.models.enums import TestCaseLifecycleStatus


TRANSITION_RULES: dict[tuple[str, str], dict] = {
    (TestCaseLifecycleStatus.DRAFT.value, TestCaseLifecycleStatus.PENDING_REVIEW.value): {
        "requires": [],
        "description": "AI 生成完成，提交审核",
    },
    (TestCaseLifecycleStatus.PENDING_REVIEW.value, TestCaseLifecycleStatus.ACTIVE.value): {
        "requires": [],
        "description": "人工评审通过（或先验分自动通过）",
    },
    (TestCaseLifecycleStatus.PENDING_REVIEW.value, TestCaseLifecycleStatus.NEEDS_MODIFY.value): {
        "requires": [],
        "description": "人工评审否决，需修改",
    },
    (TestCaseLifecycleStatus.PENDING_REVIEW.value, TestCaseLifecycleStatus.DEPRECATED.value): {
        "requires": ["deprecate_reason"],
        "description": "人工判定无价值，废弃",
    },
    (TestCaseLifecycleStatus.ACTIVE.value, TestCaseLifecycleStatus.NEEDS_MODIFY.value): {
        "requires": ["review_id"],
        "description": "评审决定需修改",
    },
    (TestCaseLifecycleStatus.ACTIVE.value, TestCaseLifecycleStatus.LOCATOR_BROKEN.value): {
        "requires": [],
        "description": "UI 变更导致 locator 失效",
    },
    (TestCaseLifecycleStatus.ACTIVE.value, TestCaseLifecycleStatus.DEPRECATED.value): {
        "requires": ["deprecate_reason"],
        "description": "废弃，需原因",
    },
    (TestCaseLifecycleStatus.NEEDS_MODIFY.value, TestCaseLifecycleStatus.ACTIVE.value): {
        "requires": [],
        "description": "撤销需修改，恢复为活跃",
    },
    (TestCaseLifecycleStatus.NEEDS_MODIFY.value, TestCaseLifecycleStatus.PENDING_REVIEW.value): {
        "requires": [],
        "description": "创建新版本提交审核",
        "side_effect": "archive_old_version",
    },
    (TestCaseLifecycleStatus.DEPRECATED.value, TestCaseLifecycleStatus.ACTIVE.value): {
        "requires": [],
        "description": "撤销废弃，恢复为活跃",
    },
    (TestCaseLifecycleStatus.DRAFT.value, TestCaseLifecycleStatus.DEPRECATED.value): {
        "requires": ["deprecate_reason"],
        "description": "草稿用例废弃",
    },
    (TestCaseLifecycleStatus.NEEDS_MODIFY.value, TestCaseLifecycleStatus.DEPRECATED.value): {
        "requires": ["deprecate_reason"],
        "description": "需修改用例废弃",
    },
    (TestCaseLifecycleStatus.LOCATOR_BROKEN.value, TestCaseLifecycleStatus.ACTIVE.value): {
        "requires": [],
        "description": "重录验证通过",
    },
    (TestCaseLifecycleStatus.LOCATOR_BROKEN.value, TestCaseLifecycleStatus.DEPRECATED.value): {
        "requires": ["deprecate_reason"],
        "description": "定位失效后废弃",
    },
    (TestCaseLifecycleStatus.DEPRECATED.value, TestCaseLifecycleStatus.ARCHIVED.value): {
        "requires": [],
        "description": "冷却期满，归档",
        "cooldown_hours": True,
    },
}

_VALID_TRANSITIONS: dict[str, set[str]] = {}
for (_from, _to), _rule in TRANSITION_RULES.items():
    _VALID_TRANSITIONS.setdefault(_from, set()).add(_to)


class IllegalStateTransition(ValueError):
    def __init__(self, from_status: str, to_status: str, detail: str = ""):
        self.from_status = from_status
        self.to_status = to_status
        msg = f"Illegal transition: {from_status} → {to_status}"
        if detail:
            msg += f" — {detail}"
        super().__init__(msg)


class MissingReviewError(ValueError):
    def __init__(self, transition: str):
        super().__init__(f"Transition '{transition}' requires review_id")


class CooldownNotElapsedError(ValueError):
    def __init__(self, remaining_hours: float):
        self.remaining_hours = remaining_hours
        super().__init__(
            f"Cooldown not elapsed, {remaining_hours:.1f} hours remaining"
        )


class MissingDeprecateReasonError(ValueError):
    def __init__(self, transition: str):
        super().__init__(f"Transition '{transition}' requires deprecate_reason")
