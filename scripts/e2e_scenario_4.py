"""
M2-T13 场景 4 端到端测试脚本

用法:
    python -m scripts.e2e_scenario_4 --project-id <project_id> [--iteration-id <iteration_id>]

前置条件:
    - 项目中需有历史 TestCase（至少 1 条）
    - Iteration 已创建，关联了 testpoint/PRD 输入
    - 环境变量已配置数据库连接

功能:
    1. 验证场景 4 配置是否存在
    2. 创建 PipelineRun
    3. 执行场景 4 Pipeline（SignalGatherer → HistoryFingerprint → ... → Persist）
    4. 输出每步执行状态和耗时
    5. 打印最终 summary
"""
import argparse
import sys
import time
from loguru import logger

from app.db.database import SessionLocal
from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner
from app.pipelines.scenarios import get_scenario
from app.ai.openai_client import OpenAIClient
from app.ai.fallback_client import FallbackAIClient
from app.core.config import settings
from app.services import pipeline_service, iteration_service


def _create_ai_client(model_name=None):
    primary = OpenAIClient(
        model=model_name or settings.AI_MODEL_NAME,
        api_key=settings.AI_API_KEY,
        base_url=settings.AI_BASE_URL,
        temperature=settings.AI_TEMPERATURE,
        max_tokens=settings.AI_MAX_TOKENS,
    )
    if settings.AI_FALLBACK_MODEL_NAME:
        fallback = OpenAIClient(
            model=settings.AI_FALLBACK_MODEL_NAME,
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL,
        )
        return FallbackAIClient(primary=primary, fallback=fallback)
    return primary


def validate_project(db, project_id):
    from app.models.project import Project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise SystemExit(f"项目 ID={project_id} 不存在")
    return project


def validate_iteration(db, iteration_id, project_id):
    from app.models.iteration import Iteration
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
    if not iteration:
        raise SystemExit(f"Iteration ID={iteration_id} 不存在")
    if iteration.project_id != project_id:
        raise SystemExit(f"Iteration ID={iteration_id} 不属于项目 ID={project_id}")
    if iteration.status not in ("draft", "in_pipeline"):
        raise SystemExit(f"Iteration 状态 '{iteration.status}' 不允许启动 Pipeline")
    return iteration


def check_history_cases(db, project_id):
    from app.models.test_case import TestCase
    count = db.query(TestCase).filter(
        TestCase.project_id == project_id,
        TestCase.lifecycle_status.in_(["active", "draft", "pending_review"]),
    ).count()
    return count


def main():
    parser = argparse.ArgumentParser(description="场景 4 端到端测试")
    parser.add_argument("--project-id", type=int, required=True, help="项目 ID")
    parser.add_argument("--iteration-id", type=int, default=None, help="Iteration ID（不提供则选最新 draft）")
    parser.add_argument("--ai-model", type=str, default=None, help="AI 模型名称")
    parser.add_argument("--dry-run", action="store_true", help="试运行（不持久化）")
    args = parser.parse_args()

    db = SessionLocal()
    project_id = args.project_id

    try:
        project = validate_project(db, project_id)
        logger.info("项目: {} (ID={})", project.name, project.id)

        if args.iteration_id:
            iteration = validate_iteration(db, args.iteration_id, project_id)
        else:
            from app.models.iteration import Iteration
            iteration = (
                db.query(Iteration)
                .filter(
                    Iteration.project_id == project_id,
                    Iteration.status.in_(["draft", "in_pipeline"]),
                )
                .order_by(Iteration.id.desc())
                .first()
            )
            if not iteration:
                raise SystemExit(f"项目 ID={project_id} 无可用 Iteration（状态需要 draft/in_pipeline）")

        logger.info("Iteration: {} (ID={}, status={})", iteration.name, iteration.id, iteration.status)

        history_count = check_history_cases(db, project_id)
        logger.info("历史用例数: {}", history_count)
        if history_count < 3:
            logger.warning("历史用例不足 3 条，部分 Step 可能 skip 或 degrade")

        scenario = get_scenario(4)
        if not scenario:
            raise SystemExit("场景 4 配置未注册")

        logger.info("场景 4 Pipeline: {} (version={})", scenario["name"], scenario["version"])
        logger.info("步骤数: {}", len(scenario["steps"]))
        for step_cls in scenario["steps"]:
            logger.info("  - {} (requires={}, produces={})", step_cls.name, step_cls.requires, step_cls.produces)

        input_hash = pipeline_service.compute_input_hash(iteration.inputs)
        run = pipeline_service.create_run(
            db=db,
            iteration_id=iteration.id,
            input_hash=input_hash,
            pipeline_version=scenario["version"],
        )
        db.flush()

        if iteration.status == "draft":
            iteration_service.transition_iteration_status(db, iteration.id, "in_pipeline")

        ai_client = _create_ai_client(args.ai_model)

        ctx = PipelineContext(
            db=db,
            ai_client=ai_client,
            run=run,
            iteration_id=iteration.id,
            user_id=1,
            config={"dry_run": args.dry_run},
        )

        runner = PipelineRunner(scenario["name"], scenario["steps"])

        t0 = time.time()
        runner.run(ctx)
        elapsed = time.time() - t0

        db.commit()
        db.refresh(run)

        logger.info("=" * 60)
        logger.info("Pipeline 执行完成: status={}, 耗时={:.1f}s", run.status, elapsed)
        logger.info("Pause payload: {}", run.pause_payload)
        logger.info("Steps:")
        for step in sorted(run.steps, key=lambda s: s.id):
            logger.info(
                "  - {}: status={}, retries={}, degraded={}",
                step.step_name, step.status, step.retried_count, step.degraded,
            )

        artifact_kinds = sorted(set(a.kind for a in run.artifacts))
        logger.info("Artifacts: {}", artifact_kinds)

        if run.status == "completed":
            logger.info("测试通过: 场景 4 Pipeline 正常运行完成")
            sys.exit(0)
        elif run.status == "waiting_for_user":
            logger.info("Pipeline 暂停等待用户确认: {}", run.pause_payload)
            sys.exit(0)
        else:
            logger.error("测试失败: Pipeline 状态 = {}", run.status)
            if run.error:
                logger.error("错误: {}", run.error)
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        db.rollback()
        logger.exception("未预期的异常: {}", e)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
