from app.services.decision_application_service._core import (
    ApplyDecision,
    ApplyResult,
    apply_decisions,
    apply_single,
    _ACTION_HANDLERS,
    _ensure_target_exists,
    _build_result,
    _handle_keep,
    _handle_needs_modify,
    _handle_locator_broken,
)
from app.services.decision_application_service._handlers import (
    _handle_locator_and_modify,
    _handle_deprecate,
    _handle_add_new,
    _handle_conflict,
    _handle_pending_review,
    _load_decisions_from_review,
    _verdict_to_action,
)

_ACTION_HANDLERS.update({
    "locator_and_modify": _handle_locator_and_modify,
    "deprecate": _handle_deprecate,
    "add_new": _handle_add_new,
    "conflict": _handle_conflict,
    "pending_review": _handle_pending_review,
})

__all__ = [
    "ApplyDecision", "ApplyResult", "apply_decisions", "apply_single",
]
