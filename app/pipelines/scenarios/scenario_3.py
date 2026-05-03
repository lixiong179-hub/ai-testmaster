"""场景 3 流水线 — 仅 UI 输入的新项目

适用于无 PRD、无历史用例的全新项目，仅提供 UI 原型。
Pipeline 从 UI 反推业务能力，提取候选场景，对齐后生成用例。

Pipeline = [S1 SignalGatherer, S3 ReverseInfer, S7 ScenarioCandidateExtractor,
            S5 TestPointAlignment, S11 CaseGeneration, S12 QualityGate, S13 Persist]

关键流程：
    1. SignalGatherer 收集 UI 输入信号（has_ui=True, has_prd=False, has_testpoints=False）
    2. ReverseInfer 从 UI 反推 inferred_capabilities + uncertain_questions
       - 置信度 < 0.7 时自动暂停（pause_for_confirmation），等待用户补全
    3. ScenarioCandidateExtractor 从 UI 提取候选测试场景
       - 无历史指纹时模块列表为空，AI 自行归纳模块
    4. TestPointAlignment 四源对齐：用户测试点(空) + UI + 反推能力 + 场景候选
    5. CaseGeneration 基于对齐后的测试点生成用例
    6. QualityGate 计算先验质量分
    7. Persist 落库（lifecycle_status=draft → pending_review）

与场景 1 的差异：
    - 场景 1：PRD + 测试点 + UI（信号齐全）
    - 场景 3：仅 UI（信号极缺），依赖 AI 反推补全业务上下文
"""
from typing import List, Type

from app.pipelines.base import PipelineStep
from app.pipelines.steps.signal_gatherer import SignalGatherer
from app.pipelines.steps.reverse_infer import ReverseInfer
from app.pipelines.steps.scenario_candidates import ScenarioCandidateExtractor
from app.pipelines.steps.testpoint_alignment import TestPointAlignment
from app.pipelines.steps.case_generation import CaseGeneration
from app.pipelines.steps.quality_gate import QualityGate
from app.pipelines.steps.persist import Persist

SCENARIO_3_STEPS: List[Type[PipelineStep]] = [
    SignalGatherer,
    ReverseInfer,
    ScenarioCandidateExtractor,
    TestPointAlignment,
    CaseGeneration,
    QualityGate,
    Persist,
]

SCENARIO_3_NAME = "scenario_3_ui_only"
SCENARIO_3_VERSION = "3.0"
