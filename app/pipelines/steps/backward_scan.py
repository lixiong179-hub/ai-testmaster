"""S6 BackwardScan — 旧用例反向扫描 Step

将历史用例与变更信号对比，输出每条用例的 verdict。
内部使用 BackwardScanService 进行批处理、重试、降级。

核心流程：
    1. 获取 history_fingerprints + raw_signals 产物
    2. 按模块切片，每批 50 用例
    3. 每批：调 AI → 校验 → 失败重试（3次 → 切半 → 单条 → 标 UNCERTAIN）
    4. 输出聚合 verdicts
"""
import hashlib
import json
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.prompts.backward_scan import (
    BACKWARD_SCAN_SYSTEM_PROMPT,
    build_backward_scan_prompt,
)
from app.pipelines.schemas.backward_verdict import (
    BackwardCaseVerdict,
    BackwardVerdict,
    validate_backward_output,
)

BATCH_SIZE = 50
MAX_BATCH_RETRIES = 3


class BackwardScan(PipelineStep):
    """反向扫描 Step — 对比历史用例与变更信号，输出 verdict。"""

    name: ClassVar[str] = "backward_scan"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["history_fingerprints", "raw_signals"]
    produces: ClassVar[List[str]] = ["backward_verdicts"]

    def should_run(self, ctx: PipelineContext) -> bool:
        fingerprints = ctx.get_artifact("history_fingerprints")
        if fingerprints is None:
            return False
        return fingerprints.get("total_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        fingerprints = ctx.get_artifact("history_fingerprints")
        raw_signals = ctx.get_artifact("raw_signals")
        fp_count = 0
        if fingerprints:
            fp_count = fingerprints.get("total_count", 0)
        sig_hash = ""
        if raw_signals:
            sig_hash = hashlib.sha256(
                json.dumps(raw_signals, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()[:16]
        raw = f"{self.name}:{self.version}:fp={fp_count}:sig={sig_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        fingerprints = ctx.get_artifact("history_fingerprints")
        raw_signals = ctx.get_artifact("raw_signals")

        if fingerprints is None or raw_signals is None:
            return StepResult(
                success=False,
                error="缺少 history_fingerprints 或 raw_signals 产物",
            )

        change_signals = _extract_change_signals(raw_signals)
        all_fps = fingerprints.get("fingerprints", [])

        service = BackwardScanService(
            ai_client=ctx.get_ai_client(),
            batch_size=BATCH_SIZE,
        )

        verdicts, stats = service.scan(
            change_signals=change_signals,
            fingerprints=all_fps,
            check_budget=ctx.check_budget,
        )

        payload = {
            "project_id": fingerprints.get("project_id", 0),
            "verdicts": [v.dict() for v in verdicts],
            "total_count": len(verdicts),
            "stats": stats,
        }

        confidence = _compute_scan_confidence(verdicts)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="backward_verdicts",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "total_count": len(verdicts),
                "stats": stats,
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["project_id", "verdicts", "total_count", "stats"]
        return all(k in payload for k in required)

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        fingerprints = ctx.get_artifact("history_fingerprints")
        project_id = 0
        if fingerprints:
            project_id = fingerprints.get("project_id", 0)
            fps = fingerprints.get("fingerprints", [])
            verdicts = [
                BackwardCaseVerdict(
                    case_id=fp["case_id"],
                    verdict=BackwardVerdict.UNCERTAIN,
                    confidence=0.0,
                    hint=f"降级：{str(error)[:100]}",
                )
                for fp in fps
            ]
        else:
            verdicts = []

        return StepResult(
            success=True,
            artifact_payload={
                "project_id": project_id,
                "verdicts": [v.dict() for v in verdicts],
                "total_count": len(verdicts),
                "stats": {
                    "batches": 0,
                    "retries": 0,
                    "degraded": len(verdicts),
                    "auto_corrected": 0,
                },
            },
            artifact_kind="backward_verdicts",
            artifact_confidence=0.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "degraded": True,
                "error": str(error),
            },
            degraded=True,
        )


class BackwardScanService:
    """反向扫描服务 — 批处理 + 重试 + 降级。

    Args:
        ai_client: AI 客户端。
        batch_size: 每批用例数，默认 50。
    """

    def __init__(self, ai_client: Any, batch_size: int = BATCH_SIZE) -> None:
        self.ai_client = ai_client
        self.batch_size = batch_size

    def scan(
        self,
        change_signals: str,
        fingerprints: List[Dict[str, Any]],
        check_budget: Optional[Any] = None,
    ) -> tuple:
        """执行反向扫描。

        Args:
            change_signals: 变更信号文本。
            fingerprints: 用例指纹列表。
            check_budget: 预算检查函数。

        Returns:
            (verdicts, stats) 元组。
        """
        batches = self._slice_by_module(fingerprints)
        all_verdicts: List[BackwardCaseVerdict] = []
        total_retries = 0
        total_degraded = 0
        total_auto_corrected = 0

        for module_label, batch_fps in batches:
            if check_budget is not None and not check_budget():
                logger.warning(
                    "预算不足，跳过模块 {} 剩余批次", module_label,
                )
                for fp in batch_fps:
                    all_verdicts.append(
                        BackwardCaseVerdict(
                            case_id=fp["case_id"],
                            verdict=BackwardVerdict.UNCERTAIN,
                            confidence=0.0,
                            hint="预算不足，跳过扫描",
                        )
                    )
                    total_degraded += 1
                continue

            verdicts, retries, degraded, auto_corrected = self._process_batch(
                change_signals=change_signals,
                batch_fps=batch_fps,
                module_label=module_label,
                check_budget=check_budget,
            )
            all_verdicts.extend(verdicts)
            total_retries += retries
            total_degraded += degraded
            total_auto_corrected += auto_corrected

        stats = {
            "batches": len(batches),
            "retries": total_retries,
            "degraded": total_degraded,
            "auto_corrected": total_auto_corrected,
        }
        return all_verdicts, stats

    def _slice_by_module(
        self, fingerprints: List[Dict[str, Any]],
    ) -> List[tuple]:
        """按模块切片，每批不超过 batch_size。"""
        module_map: Dict[str, List[Dict[str, Any]]] = {}
        for fp in fingerprints:
            module = fp.get("module", "未分类")
            module_map.setdefault(module, []).append(fp)

        batches = []
        for module_label, fps in module_map.items():
            for i in range(0, len(fps), self.batch_size):
                batch = fps[i:i + self.batch_size]
                batches.append((module_label, batch))

        if not batches and fingerprints:
            for i in range(0, len(fingerprints), self.batch_size):
                batch = fingerprints[i:i + self.batch_size]
                batches.append(("全部", batch))

        return batches

    def _process_batch(
        self,
        change_signals: str,
        batch_fps: List[Dict[str, Any]],
        module_label: str,
        check_budget: Optional[Any] = None,
    ) -> tuple:
        """处理单个批次：调 AI → 校验 → 重试 → 降级。"""
        expected_ids = [fp["case_id"] for fp in batch_fps]
        prompt = build_backward_scan_prompt(
            change_signals=change_signals,
            cases=batch_fps,
            module_label=module_label,
        )

        result = self._call_ai_with_retry(
            prompt=prompt,
            expected_ids=expected_ids,
        )

        if result is not None:
            auto_corrected = len(result.auto_corrected)
            return result.output.verdicts, result.retries, 0, auto_corrected

        logger.warning(
            "批次重试耗尽，切半重跑 (module={}, count={})",
            module_label, len(batch_fps),
        )
        return self._fallback_split(
            change_signals=change_signals,
            batch_fps=batch_fps,
            module_label=module_label,
            check_budget=check_budget,
        )

    def _call_ai_with_retry(
        self,
        prompt: str,
        expected_ids: List[int],
    ) -> Optional[Any]:
        """调用 AI 并重试，返回 ValidationResult 或 None。"""
        last_result = None
        for attempt in range(1, MAX_BATCH_RETRIES + 1):
            try:
                response = self.ai_client.complete(
                    prompt=prompt,
                    system=BACKWARD_SCAN_SYSTEM_PROMPT,
                    temperature=0.3,
                    max_tokens=4000,
                    metadata={"step_name": "backward_scan"},
                )
                raw = response.content
                result = validate_backward_output(raw, expected_ids)
                result.retries = attempt - 1
                if result.valid:
                    return result
                last_result = result
                logger.warning(
                    "AI 返回校验失败 (attempt {}/{}): {}",
                    attempt, MAX_BATCH_RETRIES, result.errors,
                )
                _record_json_validation_failure(
                    step_name="backward_scan",
                    detail={"attempt": attempt, "errors": result.errors[:3]},
                )
            except Exception as e:
                logger.warning(
                    "AI 调用异常 (attempt {}/{}): {}",
                    attempt, MAX_BATCH_RETRIES, e,
                )

        if last_result is not None:
            last_result.retries = MAX_BATCH_RETRIES
        return None

    def _fallback_split(
        self,
        change_signals: str,
        batch_fps: List[Dict[str, Any]],
        module_label: str,
        check_budget: Optional[Any] = None,
    ) -> tuple:
        """批次重试耗尽后切半重跑，单条仍失败标 UNCERTAIN。"""
        if len(batch_fps) <= 1:
            return self._mark_uncertain(batch_fps, "批次重试耗尽")

        mid = len(batch_fps) // 2
        left = batch_fps[:mid]
        right = batch_fps[mid:]

        all_verdicts: List[BackwardCaseVerdict] = []
        total_retries = MAX_BATCH_RETRIES
        total_degraded = 0
        total_auto_corrected = 0

        for sub_batch in [left, right]:
            expected_ids = [fp["case_id"] for fp in sub_batch]
            prompt = build_backward_scan_prompt(
                change_signals=change_signals,
                cases=sub_batch,
                module_label=module_label,
            )
            result = self._call_ai_with_retry(
                prompt=prompt,
                expected_ids=expected_ids,
            )

            if result is not None:
                total_retries += result.retries
                total_auto_corrected += len(result.auto_corrected)
                all_verdicts.extend(result.output.verdicts)
            else:
                sub_verdicts, sub_retries, sub_degraded, sub_ac = self._fallback_split(
                    change_signals=change_signals,
                    batch_fps=sub_batch,
                    module_label=module_label,
                    check_budget=check_budget,
                )
                all_verdicts.extend(sub_verdicts)
                total_retries += sub_retries
                total_degraded += sub_degraded
                total_auto_corrected += sub_ac

        return all_verdicts, total_retries, total_degraded, total_auto_corrected

    def _mark_uncertain(
        self, batch_fps: List[Dict[str, Any]], reason: str,
    ) -> tuple:
        """将批次内所有用例标为 UNCERTAIN。"""
        verdicts = [
            BackwardCaseVerdict(
                case_id=fp["case_id"],
                verdict=BackwardVerdict.UNCERTAIN,
                confidence=0.0,
                hint=f"降级：{reason[:80]}",
            )
            for fp in batch_fps
        ]
        return verdicts, 0, len(verdicts), 0


def _extract_change_signals(raw_signals: Dict[str, Any]) -> str:
    """从 raw_signals 产物中提取变更信号文本。"""
    parts = []
    prd = raw_signals.get("prd_content", "")
    if prd:
        parts.append(f"## PRD 变更\n{prd[:3000]}")

    test_points = raw_signals.get("test_points", [])
    if test_points:
        tp_text = json.dumps(test_points, ensure_ascii=False, indent=2)
        parts.append(f"## 测试点\n{tp_text[:2000]}")

    if not parts:
        parts.append("（无明确变更信号）")

    return "\n\n".join(parts)


def _compute_scan_confidence(verdicts: List[BackwardCaseVerdict]) -> float:
    """计算扫描产物的置信度。"""
    if not verdicts:
        return 0.0

    certain = sum(1 for v in verdicts if v.verdict != BackwardVerdict.UNCERTAIN)
    return certain / len(verdicts)


def _record_json_validation_failure(
    step_name: str,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    """记录 F2 JSON 校验失败指标（失败不阻塞业务）。"""
    try:
        from app.services.metrics_service import record_metric
        record_metric("json_validation_failure", step_name=step_name, detail=detail)
    except Exception:
        pass
