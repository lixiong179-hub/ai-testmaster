"""场景 4 流水线 — 旧项目，双向扫描 + 评审交互

适用于已有历史用例的项目（>0 条），通过双向扫描识别 KEEP / NEEDS_MODIFY /
DEPRECATE / ADD_NEW，经 Fusion Matrix 合并后生成变更用例。

Pipeline = [S1 SignalGatherer, S2 HistoryFingerprint, S5 TestPointAlignment,
            S6 BackwardScan, S7 ScenarioCandidateExtractor, S8 ForwardScan,
            S9 Reconciliation, S9.5 DecisionDispatch, S11 CaseGeneration,
            S12 QualityGate, S13 Persist]

与场景 2/3 的差异：
    - 具有历史用例，需要 HistoryFingerprint + 双向扫描
    - 不对齐 UI 测试点（无 UI 输入时 skip TestPointAlignment）
    - DecisionDispatch 将 merged_verdicts 转化为 generation_tasks 驱动 CaseGeneration
"""
from typing import List, Type

from app.pipelines.base import PipelineStep
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.history_fingerprint import HistoryFingerprint
from app.pipelines.steps.testpoint_alignment import TestPointAlignment
from app.pipelines.steps.backward_scan import BackwardScan
from app.pipelines.steps.scenario_candidates import ScenarioCandidateExtractor
from app.pipelines.steps.forward_scan import ForwardScan
from app.pipelines.steps.reconciliation import Reconciliation
from app.pipelines.steps.decision_dispatch import DecisionDispatch
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.persist import Persist

SCENARIO_4_STEPS: List[Type[PipelineStep]] = [
    SignalGatherer,
    HistoryFingerprint,
    TestPointAlignment,
    BackwardScan,
    ScenarioCandidateExtractor,
    ForwardScan,
    Reconciliation,
    DecisionDispatch,
    CaseGeneration,
    QualityGate,
    Persist,
]

SCENARIO_4_NAME = "scenario_4_regression"
SCENARIO_4_VERSION = "4.0"
