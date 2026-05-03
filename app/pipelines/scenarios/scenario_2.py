"""场景 2 流水线 — PRD + 测试点（无 UI）

与场景 1 的差异：
    - 去掉 TestPointAlignment Step（无 UI 不需要对齐）
    - 生成的用例 locator_status=pending（无 UI 无法自动定位）

Pipeline = [S1 SignalGatherer, S11 CaseGeneration, S12 QualityGate, S13 Persist]
"""
from typing import List, Type

from app.pipelines.base import PipelineStep
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.persist import Persist

SCENARIO_2_STEPS: List[Type[PipelineStep]] = [
    SignalGatherer,
    CaseGeneration,
    QualityGate,
    Persist,
]

SCENARIO_2_NAME = "scenario_2_no_ui"
SCENARIO_2_VERSION = "1.0"
