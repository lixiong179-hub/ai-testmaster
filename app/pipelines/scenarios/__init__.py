"""场景流水线注册表

提供场景配置查询接口，供 API 端点和 Pipeline Runner 使用。
"""
from typing import Any, Dict, Optional

from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.testpoint_alignment import TestPointAlignment
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.persist import Persist
from app.pipelines.steps.history_fingerprint import HistoryFingerprint
from app.pipelines.steps.backward_scan import BackwardScan
from app.pipelines.steps.forward_scan import ForwardScan
from app.pipelines.steps.reconciliation import Reconciliation
from app.pipelines.steps.scenario_candidates import ScenarioCandidateExtractor
from app.pipelines.steps.reverse_infer import ReverseInfer


_SCENARIO_REGISTRY: Dict[int, Dict[str, Any]] = {
    1: {
        "name": "scenario_1_full",
        "version": "1.0",
        "description": "新项目，输入齐全（PRD + 测试点 + UI）",
        "steps": [SignalGatherer, TestPointAlignment, CaseGeneration, QualityGate, Persist],
    },
    2: {
        "name": "scenario_2_no_ui",
        "version": "2.0",
        "description": "PRD + 测试点（无 UI），用例 locator_status=pending",
        "steps": [SignalGatherer, CaseGeneration, QualityGate, Persist],
    },
    3: {
        "name": "scenario_3_ui_only",
        "version": "3.0",
        "description": "新项目，仅 UI 输入（反推业务能力 + 候选提取 + 对齐 + 生成）",
        "steps": [SignalGatherer, ReverseInfer, ScenarioCandidateExtractor, TestPointAlignment, CaseGeneration, QualityGate, Persist],
    },
    4: {
        "name": "scenario_4_regression",
        "version": "4.0",
        "description": "旧项目，双向扫描 + 评审交互（HistoryFingerprint → Backward → Forward → Reconciliation → CaseGeneration）",
        "steps": [
            SignalGatherer,
            HistoryFingerprint,
            TestPointAlignment,
            BackwardScan,
            ScenarioCandidateExtractor,
            ForwardScan,
            Reconciliation,
            CaseGeneration,
            QualityGate,
            Persist,
        ],
    },
    5: {
        "name": "scenario_5_old_project_no_prd",
        "version": "5.0",
        "description": "旧项目无新PRD（历史反推 + 双向扫描 + 对齐 + 生成）",
        "steps": [
            SignalGatherer,
            HistoryFingerprint,
            ReverseInfer,
            TestPointAlignment,
            BackwardScan,
            ScenarioCandidateExtractor,
            ForwardScan,
            Reconciliation,
            CaseGeneration,
            QualityGate,
            Persist,
        ],
    },
}


def get_scenario(scenario_id: int) -> Optional[Dict[str, Any]]:
    """按场景编号获取配置。"""
    return _SCENARIO_REGISTRY.get(scenario_id)


def get_scenario_by_version(pipeline_version: str) -> Optional[Dict[str, Any]]:
    """按 pipeline_version 反查场景配置。"""
    for config in _SCENARIO_REGISTRY.values():
        if config["version"] == pipeline_version:
            return config
    return None


def list_scenarios() -> Dict[int, Dict[str, Any]]:
    """列出所有已注册场景。"""
    return dict(_SCENARIO_REGISTRY)
