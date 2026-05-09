"""Pipeline 回归测试共享 fixtures

提供标注集数据加载、MockAIClient 配置、迭代/项目 setup 等共享能力。
所有回归测试使用真实 MySQL + MockAIClient，不调用真实 AI 服务。
"""
import json
from pathlib import Path
from typing import List

import pytest

from app.ai.mock_client import MockAIClient
from app.models.iteration import Iteration, IterationInput
from app.models.test_case import TestCase
from app.models.test_point import TestPoint
from app.models.pipeline import PipelineRun
from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner
from app.pipelines.scenarios import get_scenario

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_annotation(project: str, filename: str):
    """加载标注集 JSON 文件"""
    filepath = _DATA_DIR / f"project_{project}" / filename
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def alpha_project_data() -> dict:
    """加载 Alpha 项目标注集（场景 1）"""
    return {
        "project": load_annotation("alpha", "project.json"),
        "prd": load_annotation("alpha", "prd.json"),
        "test_points": load_annotation("alpha", "test_points.json"),
        "ui_prototype": load_annotation("alpha", "ui_prototype.json"),
        "expected_cases": load_annotation("alpha", "expected_cases.json"),
    }


@pytest.fixture
def beta_project_data() -> dict:
    """加载 Beta 项目标注集（场景 4）"""
    return {
        "project": load_annotation("beta", "project.json"),
        "historical_cases": load_annotation("beta", "historical_cases.json"),
        "new_prd": load_annotation("beta", "new_prd.json"),
        "ui_changes": load_annotation("beta", "ui_changes.json"),
        "expected_verdicts": load_annotation("beta", "expected_verdicts.json"),
    }


@pytest.fixture
def gamma_project_data() -> dict:
    """加载 Gamma 项目标注集（场景 3）"""
    return {
        "project": load_annotation("gamma", "project.json"),
        "ui_prototype": load_annotation("gamma", "ui_prototype.json"),
        "expected_inference": load_annotation("gamma", "expected_inference.json"),
    }


def _make_mock_ai(case_response: list) -> MockAIClient:
    """创建预配置的 MockAIClient"""
    client = MockAIClient()
    client.set_response("case_generation", json.dumps(case_response))
    return client


def _setup_iteration_with_inputs(
    db, project_id: int, input_kinds: List[str], project_data: dict
) -> Iteration:
    """创建迭代并添加输入"""
    iteration = Iteration(
        project_id=project_id,
        name="regression_test",
        status="draft",
    )
    db.add(iteration)
    db.flush()

    for kind in input_kinds:
        content = json.dumps(project_data.get(kind, {}))
        inp = IterationInput(
            iteration_id=iteration.id,
            kind=kind,
            payload=project_data.get(kind, {}),
            content_hash=str(hash(content)),
        )
        db.add(inp)

    db.flush()
    return iteration


def run_scenario(db, iteration_id: int, scenario_id: int, ai_client: MockAIClient, user_id: int) -> PipelineRun:
    """运行指定场景的 Pipeline"""
    scenario = get_scenario(scenario_id)
    run = PipelineRun(
        iteration_id=iteration_id,
        pipeline_version=scenario["version"],
        input_hash=f"regression_s{scenario_id}",
        status="pending",
    )
    db.add(run)
    db.flush()

    ctx = PipelineContext(
        db=db,
        ai_client=ai_client,
        run=run,
        iteration_id=iteration_id,
        user_id=user_id,
        config={},
    )

    runner = PipelineRunner(scenario["name"], scenario["steps"])
    runner.run(ctx)
    return run
