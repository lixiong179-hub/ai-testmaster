from typing import Any, Dict, List, Optional

from loguru import logger

from app.pipelines.prompts.backward_scan import (
    BACKWARD_SCAN_SYSTEM_PROMPT,
    build_backward_scan_prompt,
)
from app.pipelines.schemas.backward_verdict import (
    BackwardCaseVerdict,
    BackwardVerdict,
    validate_backward_output,
)

MAX_BATCH_RETRIES = 3


class BackwardScanService:

    def __init__(self, ai_client: Any, batch_size: int = 50) -> None:
        self.ai_client = ai_client
        self.batch_size = batch_size

    def scan(
        self,
        change_signals: str,
        fingerprints: List[Dict[str, Any]],
        check_budget: Optional[Any] = None,
    ) -> tuple:
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


def _record_json_validation_failure(
    step_name: str,
    detail: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        from app.services.metrics_service import record_metric
        record_metric("json_validation_failure", step_name=step_name, detail=detail)
    except Exception:
        logger.debug("记录JSON校验失败指标失败", exc_info=True)
