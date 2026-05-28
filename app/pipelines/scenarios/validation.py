"""Scenario input validation helpers."""
from dataclasses import dataclass
from typing import Any, List

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class ScenarioSignalSnapshot:
    project_id: int
    input_count: int
    has_prd: bool
    has_ui: bool
    has_testpoints: bool
    has_change_notes: bool
    history_count: int
    active_history_count: int

    @property
    def has_history(self) -> bool:
        return self.history_count > 0

    @property
    def has_change_signal(self) -> bool:
        return self.has_prd or self.has_ui or self.has_testpoints or self.has_change_notes


def inspect_iteration_signals(db: Session, iteration: Any) -> ScenarioSignalSnapshot:
    """Resolve the iteration inputs that the pipeline can actually consume."""
    project_id = int(iteration.project_id)
    has_prd = False
    has_ui = False
    has_testpoints = False
    has_change_notes = False

    for inp in list(iteration.inputs or []):
        kind = getattr(inp, "kind", "")
        payload = _payload(inp)

        if kind == "prd":
            has_prd = has_prd or _has_file_content(db, project_id, getattr(inp, "file_id", None))
        elif kind == "prototype":
            has_ui = has_ui or _has_resolved_ui(db, project_id, inp)
        elif kind == "testpoint":
            has_testpoints = has_testpoints or _has_resolved_testpoints(db, project_id, inp)
        elif kind == "xmind":
            has_testpoints = has_testpoints or _has_file_content(db, project_id, getattr(inp, "file_id", None))
        elif kind == "change_notes":
            has_change_notes = has_change_notes or _payload_has_text(
                payload, ("notes", "change_notes", "description", "summary")
            )

    history_count, active_history_count = _history_counts(db, project_id)
    return ScenarioSignalSnapshot(
        project_id=project_id,
        input_count=len(iteration.inputs or []),
        has_prd=has_prd,
        has_ui=has_ui,
        has_testpoints=has_testpoints,
        has_change_notes=has_change_notes,
        history_count=history_count,
        active_history_count=active_history_count,
    )


def validate_scenario_inputs(db: Session, iteration: Any, scenario_id: int) -> List[str]:
    snapshot = inspect_iteration_signals(db, iteration)
    errors: List[str] = []

    if scenario_id == 1:
        _require(errors, snapshot.has_prd, "场景 1 需要有效 PRD 输入")
        _require(errors, snapshot.has_ui, "场景 1 需要有效 UI 原型输入")
        _require(errors, snapshot.has_testpoints, "场景 1 需要有效测试点输入")
        _require(
            errors,
            not snapshot.has_history,
            "场景 1 适用于新项目；当前项目已有历史用例，请使用场景 4/5",
        )

    elif scenario_id == 2:
        _require(errors, snapshot.has_prd, "场景 2 需要有效 PRD 输入")
        _require(errors, snapshot.has_testpoints, "场景 2 需要有效测试点输入")
        _require(errors, not snapshot.has_ui, "场景 2 是无 UI 场景；有 UI 输入请使用场景 1/4")
        _require(
            errors,
            not snapshot.has_history,
            "场景 2 适用于新项目；当前项目已有历史用例，请使用场景 4/5",
        )

    elif scenario_id == 3:
        _require(errors, snapshot.has_ui, "场景 3 需要有效 UI 原型输入")
        _require(errors, not snapshot.has_prd, "场景 3 是仅 UI 场景；有 PRD 输入请使用场景 1/4")
        _require(errors, not snapshot.has_testpoints, "场景 3 是仅 UI 场景；有测试点输入请使用场景 1/4")
        _require(errors, not snapshot.has_history, "场景 3 适用于新项目；有历史用例请使用场景 5")

    elif scenario_id == 4:
        _require(errors, snapshot.has_history, "场景 4 需要项目已有历史用例")
        _require(
            errors,
            snapshot.has_change_signal,
            "场景 4 需要至少一种变更信号：PRD/UI/测试点/变更说明",
        )

    elif scenario_id == 5:
        _require(errors, snapshot.has_history, "场景 5 需要项目已有历史用例")
        _require(errors, not snapshot.has_prd, "场景 5 是无新 PRD 场景；有 PRD 输入请使用场景 4")
        _require(
            errors,
            snapshot.has_change_signal,
            "场景 5 需要至少一种变更信号（UI/测试点/变更说明）；无任何变更信号时无法触发有意义的用例生成",
        )

    else:
        errors.append(f"场景 {scenario_id} 不存在")

    return errors


def _require(errors: List[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def _payload(inp: Any) -> dict:
    payload = getattr(inp, "payload", None)
    return payload if isinstance(payload, dict) else {}


def _payload_has_text(payload: dict, keys: tuple[str, ...]) -> bool:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return True
    return False


def _as_int_list(value: Any) -> list[int]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = value
    else:
        raw_values = [value]

    result: list[int] = []
    for item in raw_values:
        try:
            num = int(item)
        except (TypeError, ValueError):
            continue
        if num > 0:
            result.append(num)
    return result


def _has_file_content(db: Session, project_id: int, file_id: Any) -> bool:
    if not file_id:
        return False
    from app.models.project import ProjectFile

    file_record = db.query(ProjectFile).filter(
        ProjectFile.id == file_id,
        ProjectFile.project_id == project_id,
        ProjectFile.is_active.is_(True),
    ).first()
    return bool(file_record and (file_record.content or "").strip())


def _has_resolved_ui(db: Session, project_id: int, inp: Any) -> bool:
    from app.models.ui_prototype import UIPrototypeScreen
    from app.models.project import ProjectFile

    payload = _payload(inp)
    screen_ids = _as_int_list(payload.get("screen_ids"))
    screen_ids.extend(_as_int_list(payload.get("screen_id")))
    screen_ids.extend(_as_int_list(payload.get("ui_prototype_id")))
    screen_ids = sorted(set(screen_ids))

    if screen_ids:
        return db.query(UIPrototypeScreen.id).filter(
            UIPrototypeScreen.id.in_(screen_ids),
            UIPrototypeScreen.project_id == project_id,
            UIPrototypeScreen.parse_status == "completed",
            UIPrototypeScreen.ui_spec.isnot(None),
        ).first() is not None

    prototype_project_ids = _as_int_list(payload.get("prototype_project_id"))
    prototype_project_ids.extend(_as_int_list(payload.get("ui_project_id")))
    prototype_project_ids = sorted(set(prototype_project_ids))
    if prototype_project_ids:
        return db.query(UIPrototypeScreen.id).filter(
            UIPrototypeScreen.project_id == project_id,
            UIPrototypeScreen.prototype_project_id.in_(prototype_project_ids),
            UIPrototypeScreen.parse_status == "completed",
            UIPrototypeScreen.ui_spec.isnot(None),
        ).first() is not None

    file_id = getattr(inp, "file_id", None)
    if file_id:
        file_record = db.query(ProjectFile).filter(
            ProjectFile.id == file_id,
            ProjectFile.project_id == project_id,
            ProjectFile.resource_type == "ui_mockup",
            ProjectFile.is_active.is_(True),
        ).first()
        if file_record:
            return db.query(UIPrototypeScreen.id).filter(
                UIPrototypeScreen.project_id == project_id,
                UIPrototypeScreen.prototype_name == file_record.file_name,
                UIPrototypeScreen.parse_status == "completed",
                UIPrototypeScreen.ui_spec.isnot(None),
            ).first() is not None

    return db.query(UIPrototypeScreen.id).filter(
        UIPrototypeScreen.project_id == project_id,
        UIPrototypeScreen.parse_status == "completed",
        UIPrototypeScreen.ui_spec.isnot(None),
    ).first() is not None


def _has_resolved_testpoints(db: Session, project_id: int, inp: Any) -> bool:
    from app.models.test_point import TestPoint

    payload = _payload(inp)
    point_ids = _as_int_list(payload.get("test_point_ids"))
    if point_ids:
        return db.query(TestPoint.id).filter(
            TestPoint.id.in_(sorted(set(point_ids))),
            TestPoint.project_id == project_id,
        ).first() is not None

    return db.query(TestPoint.id).filter(TestPoint.project_id == project_id).first() is not None


def _history_counts(db: Session, project_id: int) -> tuple[int, int]:
    from app.models.test_case import TestCase

    base_query = db.query(TestCase).filter(
        TestCase.project_id == project_id,
        TestCase.lifecycle_status != "archived",
        TestCase.is_deleted.is_(False),
    )
    history_count = base_query.count()
    active_count = base_query.filter(TestCase.lifecycle_status == "active").count()
    return history_count, active_count
