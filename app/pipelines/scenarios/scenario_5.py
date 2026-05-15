"""场景 5 流水线 — 旧项目，无新 PRD（反向推断 + 双向扫描 + 评审交互）

适用于已有历史用例但无新 PRD 输入的旧项目。Pipeline 从历史用例反向推断业务能力，
结合双向扫描识别变更，经由 Fusion Matrix 合并后生成变更用例。

Pipeline = [S1 SignalGatherer, S2 HistoryFingerprint, S3 ReverseInfer,
            S5 TestPointAlignment, S6 BackwardScan, S7 ScenarioCandidateExtractor,
            S8 ForwardScan, S9 Reconciliation, S9.5 DecisionDispatch,
            S11 CaseGeneration, S12 QualityGate, S13 Persist]

与场景 4 的差异：
    - 场景 4：直接使用用户提供的测试点 + 双向扫描
    - 场景 5：无 PRD/测试点时，ReverseInfer 从历史用例反向推断业务能力，
              再输入 TestPointAlignment 做对齐，后续流程同场景 4
"""
from typing import List, Type

from app.pipelines.base import PipelineStep
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.history_fingerprint import HistoryFingerprint
from app.pipelines.steps.reverse_infer import ReverseInfer
from app.pipelines.steps.testpoint_alignment import TestPointAlignment
from app.pipelines.steps.backward_scan import BackwardScan
from app.pipelines.steps.scenario_candidates import ScenarioCandidateExtractor
from app.pipelines.steps.forward_scan import ForwardScan
from app.pipelines.steps.reconciliation import Reconciliation
from app.pipelines.steps.decision_dispatch import DecisionDispatch
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.persist import Persist

SCENARIO_5_STEPS: List[Type[PipelineStep]] = [
    SignalGatherer,
    HistoryFingerprint,
    ReverseInfer,
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

SCENARIO_5_NAME = "scenario_5_old_project_no_prd"
SCENARIO_5_VERSION = "5.0"
