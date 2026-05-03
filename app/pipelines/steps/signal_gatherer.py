"""S1 SignalGatherer — 信号采集 Step

从迭代输入中采集需求文档、UI 原型、测试点等信号，
构建 Pipeline 后续 Step 所需的统一上下文产物。
"""
import hashlib
import json
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext


class SignalGatherer(PipelineStep):
    """信号采集 Step — 从迭代输入加载 PRD / UI / 测试点。"""

    name: ClassVar[str] = "signal_gatherer"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = []
    produces: ClassVar[List[str]] = ["raw_signals"]

    def should_run(self, ctx: PipelineContext) -> bool:
        return True

    def cache_key(self, ctx: PipelineContext) -> str:
        from app.models.iteration import Iteration

        iteration = ctx.db.query(Iteration).filter_by(id=ctx.iteration_id).first()
        if not iteration:
            return ""
        input_hashes = []
        for inp in sorted(iteration.inputs, key=lambda i: i.id):
            input_hashes.append(inp.content_hash or "")
        raw = f"{self.name}:{self.version}:{':'.join(input_hashes)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        from app.models.iteration import Iteration

        iteration = ctx.db.query(Iteration).filter_by(id=ctx.iteration_id).first()
        if not iteration:
            return StepResult(
                success=False,
                error=f"迭代 {ctx.iteration_id} 不存在",
            )

        project_id = iteration.project_id

        prd_content = ""
        ui_descriptions: List[Dict[str, Any]] = []
        ui_specs: List[Dict[str, Any]] = []
        test_points: List[Dict[str, Any]] = []
        file_ids_used: List[int] = []

        for inp in iteration.inputs:
            try:
                if inp.kind == "prd":
                    content = _load_file_content(ctx, inp.file_id, project_id)
                    if content:
                        prd_content += f"\n\n{content}"
                    if inp.file_id:
                        file_ids_used.append(inp.file_id)

                elif inp.kind == "prototype":
                    ui_desc, ui_spec, fids = _load_ui_from_input(ctx, inp, project_id)
                    ui_descriptions.extend(ui_desc)
                    ui_specs.extend(ui_spec)
                    file_ids_used.extend(fids)

                elif inp.kind == "testpoint":
                    points = _load_test_points_from_input(ctx, inp, project_id)
                    test_points.extend(points)

                elif inp.kind == "xmind":
                    content = _load_file_content(ctx, inp.file_id, project_id)
                    if content:
                        xmind_payload = {}
                        if inp.payload and isinstance(inp.payload, dict):
                            xmind_payload = dict(inp.payload)
                        xmind_payload["xmind_content"] = content
                        test_points.extend(_parse_xmind_to_testpoints(xmind_payload, project_id))

            except Exception as e:
                logger.error("信号采集失败 kind={} file_id={}: {}", inp.kind, inp.file_id, e)

        if not prd_content and not ui_descriptions and not test_points:
            return StepResult(
                success=False,
                error="迭代无有效输入信号（PRD/UI/测试点均为空）",
            )

        payload = {
            "iteration_id": ctx.iteration_id,
            "project_id": project_id,
            "prd_content": prd_content.strip(),
            "ui_descriptions": ui_descriptions,
            "ui_specs": ui_specs,
            "test_points": test_points,
            "file_ids_used": file_ids_used,
            "has_ui": len(ui_specs) > 0,
            "has_prd": bool(prd_content.strip()),
            "has_testpoints": len(test_points) > 0,
            "is_old_project": _check_is_old_project(ctx, project_id),
        }

        confidence = _compute_signal_confidence(payload)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="raw_signals",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "input_count": len(iteration.inputs),
                "file_ids": file_ids_used,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["iteration_id", "project_id", "prd_content", "test_points"]
        return all(k in payload for k in required)

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        return StepResult(
            success=False,
            error=f"信号采集降级: {error}",
            degraded=True,
        )


def _load_file_content(ctx: PipelineContext, file_id: Optional[int], project_id: int) -> str:
    if not file_id:
        return ""
    from app.crud import file as file_crud

    file_record = file_crud.get_file_by_id(ctx.db, file_id, project_id)
    if not file_record:
        return ""
    return file_record.content or ""


def _load_ui_from_input(
    ctx: PipelineContext, inp: Any, project_id: int
) -> tuple[List[Dict], List[Dict], List[int]]:
    from app.models.ui_prototype import UIPrototypeScreen
    from app.crud import file as file_crud

    ui_descriptions = []
    ui_specs = []
    file_ids = []

    if inp.payload and isinstance(inp.payload, dict):
        screen_ids = inp.payload.get("screen_ids", [])
        if screen_ids:
            for screen_id in screen_ids:
                screen = ctx.db.query(UIPrototypeScreen).filter(
                    UIPrototypeScreen.id == screen_id,
                    UIPrototypeScreen.project_id == project_id,
                ).first()
                if screen:
                    ui_descriptions.append({
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "description": screen.summary or "",
                    })
                    if screen.ui_spec:
                        ui_specs.append({
                            "screen_id": screen.id,
                            "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec,
                        })

    if not ui_descriptions and inp.file_id:
        file_record = file_crud.get_file_by_id(ctx.db, inp.file_id, project_id)
        if file_record and file_record.resource_type == "ui_mockup":
            file_ids.append(inp.file_id)
            screens = ctx.db.query(UIPrototypeScreen).filter(
                UIPrototypeScreen.project_id == project_id,
                UIPrototypeScreen.prototype_name == file_record.file_name,
                UIPrototypeScreen.parse_status == "completed",
            ).all()
            for screen in screens:
                ui_descriptions.append({
                    "screen_id": screen.id,
                    "screen_name": screen.screen_name,
                    "description": screen.summary or "",
                })
                if screen.ui_spec:
                    ui_specs.append({
                        "screen_id": screen.id,
                        "screen_name": screen.screen_name,
                        "ui_spec": screen.ui_spec,
                    })

    if not ui_descriptions:
        screens = ctx.db.query(UIPrototypeScreen).filter(
            UIPrototypeScreen.project_id == project_id,
            UIPrototypeScreen.parse_status == "completed",
            UIPrototypeScreen.ui_spec.isnot(None),
        ).order_by(UIPrototypeScreen.screen_order).all()
        for screen in screens:
            ui_descriptions.append({
                "screen_id": screen.id,
                "screen_name": screen.screen_name,
                "description": screen.summary or "",
            })
            ui_specs.append({
                "screen_id": screen.id,
                "screen_name": screen.screen_name,
                "ui_spec": screen.ui_spec,
            })

    return ui_descriptions, ui_specs, file_ids


def _load_test_points_from_input(
    ctx: PipelineContext, inp: Any, project_id: int
) -> List[Dict[str, Any]]:
    from app.models.test_point import TestPoint

    if inp.payload and isinstance(inp.payload, dict):
        point_ids = inp.payload.get("test_point_ids", [])
        if point_ids:
            points = ctx.db.query(TestPoint).filter(
                TestPoint.id.in_(point_ids),
                TestPoint.project_id == project_id,
            ).all()
            return [_format_test_point(p) for p in points]

    points = ctx.db.query(TestPoint).filter(
        TestPoint.project_id == project_id,
    ).order_by(TestPoint.priority.asc(), TestPoint.id.asc()).all()
    return [_format_test_point(p) for p in points]


def _check_is_old_project(ctx: PipelineContext, project_id: int) -> bool:
    from app.models.test_case import TestCase as TC
    count = ctx.db.query(TC).filter(
        TC.project_id == project_id,
        TC.lifecycle_status == "active",
    ).count()
    return count > 0


def _parse_xmind_to_testpoints(payload: Dict[str, Any], project_id: int) -> List[Dict[str, Any]]:
    xmind_content = payload.get("xmind_content", "")
    if not xmind_content:
        return []
    try:
        data = json.loads(xmind_content) if isinstance(xmind_content, str) else xmind_content
    except (json.JSONDecodeError, TypeError):
        return []

    if not isinstance(data, list):
        data = [data]

    results = []
    for idx, item in enumerate(data):
        if isinstance(item, dict):
            results.append({
                "id": -(idx + 1),
                "module": item.get("module", "xmind"),
                "function": item.get("function", ""),
                "point": item.get("point", item.get("title", f"xmind节点{idx+1}")),
                "priority": item.get("priority", 3),
            })
    return results


def _format_test_point(point: Any) -> Dict[str, Any]:
    function = ""
    if point.ai_prompt:
        try:
            data = json.loads(point.ai_prompt)
            if isinstance(data, dict):
                function = str(data.get("function", "") or "")
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    return {
        "id": point.id,
        "module": point.module,
        "function": function,
        "point": point.point,
        "priority": point.priority,
    }


def _compute_signal_confidence(payload: Dict[str, Any]) -> float:
    score = 0.0
    if payload.get("has_prd"):
        score += 0.4
    if payload.get("has_ui"):
        score += 0.3
    if payload.get("has_testpoints"):
        score += 0.3
    return min(score, 1.0)
