"""Pipeline 运行管理端点

提供触发 Pipeline 运行、查询运行状态、恢复暂停的 Pipeline 等功能。
子模块拆分:
    - pipeline_schemas    - 请求模型
    - pipeline_deps       - 权限校验
    - pipeline_precheck   - 场景4预检
    - pipeline_resume     - Pipeline恢复 + AI客户端工厂
    - pipeline_artifacts  - 反推摘要、信号补充与取消运行
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from loguru import logger

from app.db.database import get_db
from app.models.user import User
from app.models.pipeline import PipelineRun
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response

# 从子模块导入请求模型（保持外部 import 路径兼容）
from app.api.v1.endpoints.pipeline_schemas import (
    PipelineRunRequest,
    PipelineResumeRequest,
    SupplementSignalsRequest,
    Scenario4PrecheckRequest,
)
# 从子模块导入权限校验（保持外部 import 路径兼容）
from app.api.v1.endpoints.pipeline_deps import (
    verify_project_access as _verify_project_access,
    verify_iteration_access as _verify_iteration_access,
)
# 从子模块导入 AI 客户端工厂
from app.api.v1.endpoints.pipeline_resume import create_ai_client as _create_ai_client
# 从子模块导入版本重跑指标记录
from app.api.v1.endpoints.pipeline_artifacts import record_version_rerun_metric as _record_version_rerun_metric
# 从子模块重新导出端点函数，保持外部 import 路径兼容
from app.api.v1.endpoints.pipeline_precheck import precheck_scenario_4
from app.api.v1.endpoints.pipeline_resume import resume_pipeline
from app.api.v1.endpoints.pipeline_artifacts import get_inferred_summary, supplement_signals, get_pipeline_summary

__all__ = [
    "PipelineRunRequest",
    "PipelineResumeRequest",
    "SupplementSignalsRequest",
    "Scenario4PrecheckRequest",
    "_verify_project_access",
    "precheck_scenario_4",
    "resume_pipeline",
    "get_inferred_summary",
    "supplement_signals",
    "get_pipeline_summary",
]

router = APIRouter(prefix="/pipeline", tags=["Pipeline管理"])

# 将子模块路由注册到主路由
from app.api.v1.endpoints.pipeline_precheck import router as _precheck_router
from app.api.v1.endpoints.pipeline_resume import router as _resume_router
from app.api.v1.endpoints.pipeline_artifacts import router as _artifacts_router
from app.api.v1.endpoints.pipeline_dashboard import router as _dashboard_router
from app.api.v1.endpoints.pipeline_dashboard._trends import router as _dashboard_trends_router
from app.api.v1.endpoints.pipeline_metrics import router as _metrics_router

router.include_router(_precheck_router)
router.include_router(_resume_router)
router.include_router(_dashboard_router)
router.include_router(_dashboard_trends_router)
router.include_router(_metrics_router)
router.include_router(_artifacts_router)


@router.post("/iteration/{iteration_id}/run", response_model=dict)
async def run_pipeline(
    iteration_id: int,
    body: PipelineRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """触发 Pipeline 运行。"""
    try:
        iteration = _verify_iteration_access(db, iteration_id, current_user)

        if iteration.status not in ("draft", "in_pipeline"):
            raise HTTPException(
                status_code=400,
                detail=f"迭代状态 '{iteration.status}' 不允许启动 Pipeline",
            )

        from app.pipelines.scenarios import get_scenario, validate_scenario_inputs
        scenario_config = get_scenario(body.scenario)
        if not scenario_config:
            raise HTTPException(status_code=400, detail=f"场景 {body.scenario} 不存在")

        validation_errors = validate_scenario_inputs(db, iteration, body.scenario)
        if validation_errors:
            raise HTTPException(
                status_code=400,
                detail="；".join(validation_errors),
            )

        from app.services import pipeline_service
        from app.pipelines.runner import PipelineRunner
        from app.pipelines.context import PipelineContext

        input_hash = pipeline_service.compute_input_hash(iteration.inputs)
        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration_id,
            input_hash=input_hash,
            pipeline_version=scenario_config["version"],
            triggered_by=current_user.id,
        )
        db.flush()

        existing_runs = (
            db.query(PipelineRun)
            .filter(
                PipelineRun.iteration_id == iteration_id,
                PipelineRun.id != run.id,
            )
            .count()
        )
        current_version = scenario_config.get("version", "1.0")
        if existing_runs > 0 and current_version != "1.0":
            last_run = (
                db.query(PipelineRun)
                .filter(
                    PipelineRun.iteration_id == iteration_id,
                    PipelineRun.id != run.id,
                )
                .order_by(PipelineRun.id.desc())
                .first()
            )
            if last_run and last_run.pipeline_version != current_version:
                _record_version_rerun_metric(
                    db, iteration_id=iteration_id,
                    detail={
                        "old_version": last_run.pipeline_version,
                        "new_version": current_version,
                    },
                )

        if iteration.status == "draft":
            from app.services.iteration_service import transition_iteration_status
            transition_iteration_status(db, iteration_id, "in_pipeline")

        ai_client = _create_ai_client(body.ai_model)

        ctx = PipelineContext(
            db=db,
            ai_client=ai_client,
            run=run,
            iteration_id=iteration_id,
            user_id=current_user.id,
            config={"dry_run": body.dry_run, "scenario": body.scenario},
        )

        runner = PipelineRunner(scenario_config["name"], scenario_config["steps"])
        runner.run(ctx)

        db.commit()
        db.refresh(run)

        return create_response(
            data={
                "run_id": run.id,
                "pipeline_run_id": run.id,
                "iteration_id": iteration_id,
                "status": run.status,
                "scenario": body.scenario,
            },
            msg="Pipeline 运行完成",
        )

    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error("Pipeline 运行失败: {}", e)
        raise HTTPException(status_code=500, detail="Pipeline 运行失败")


@router.get("/{run_id}", response_model=dict)
async def get_pipeline_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询 Pipeline 运行状态。"""
    try:
        from app.services import pipeline_service

        run = pipeline_service.get_run(db, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline 运行不存在")

        _verify_iteration_access(db, run.iteration_id, current_user)

        steps_data = []
        for step in run.steps:
            steps_data.append({
                "id": step.id,
                "step_name": step.step_name,
                "status": step.status,
                "started_at": step.started_at,
                "finished_at": step.finished_at,
                "error": step.error,
                "retried_count": step.retried_count,
                "degraded": step.degraded,
            })

        artifacts_data = []
        for artifact in run.artifacts:
            artifacts_data.append({
                "id": artifact.id,
                "kind": artifact.kind,
                "confidence": artifact.confidence,
                "schema_version": artifact.schema_version,
                "created_at": artifact.created_at,
            })

        return create_response(
            data={
                "id": run.id,
                "iteration_id": run.iteration_id,
                "input_hash": run.input_hash,
                "pipeline_version": run.pipeline_version,
                "status": run.status,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "error": run.error,
                "pause_payload": run.pause_payload,
                "triggered_by": run.triggered_by,
                "steps": steps_data,
                "artifacts": artifacts_data,
            },
            msg="获取成功",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取 Pipeline 状态失败")
