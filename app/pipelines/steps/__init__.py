"""
Pipeline Steps 模块

本模块包含所有 Pipeline Step 的具体实现。
每个 Step 实现 PipelineStep Protocol，声明 name/version/requires/produces。
"""
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.testpoint_alignment import TestPointAlignment
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.execution_validation import ExecutionValidation
from app.pipelines.steps.persist import Persist
from app.pipelines.steps.history_fingerprint import HistoryFingerprint
from app.pipelines.steps.backward_scan import BackwardScan
from app.pipelines.steps.forward_scan import ForwardScan
from app.pipelines.steps.reconciliation import Reconciliation
from app.pipelines.steps.scenario_candidates import ScenarioCandidateExtractor
from app.pipelines.steps.reverse_infer import ReverseInfer
from app.pipelines.steps.decision_dispatch import DecisionDispatch

__all__ = [
    "SignalGatherer",
    "TestPointAlignment",
    "CaseGeneration",
    "QualityGate",
    "ExecutionValidation",
    "Persist",
    "HistoryFingerprint",
    "BackwardScan",
    "ForwardScan",
    "Reconciliation",
    "ScenarioCandidateExtractor",
    "ReverseInfer",
    "DecisionDispatch",
]
