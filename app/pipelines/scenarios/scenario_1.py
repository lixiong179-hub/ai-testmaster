"""场景 1 流水线 — 新项目，输入齐全（PRD + 测试点 + UI）

Pipeline = [S1 SignalGatherer, S5 TestPointAlignment, S11 CaseGeneration, S12 QualityGate, S13 Persist]
"""
from typing import List, Type

from app.pipelines.base import PipelineStep
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.testpoint_alignment import TestPointAlignment
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.persist import Persist

SCENARIO_1_STEPS: List[Type[PipelineStep]] = [
    SignalGatherer,
    TestPointAlignment,
    CaseGeneration,
    QualityGate,
    Persist,
]

SCENARIO_1_NAME = "scenario_1_full"
SCENARIO_1_VERSION = "1.0"
