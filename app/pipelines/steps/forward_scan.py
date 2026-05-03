"""S6 ForwardScan — 新候选场景正向扫描 Step

将候选场景与历史用例指纹做匹配，输出 EXISTING/MODIFY/NEW 标签。
内部使用 ForwardScanService 进行两阶段匹配：TF-IDF 粗筛 + LLM 精筛。

核心流程：
    1. 获取 scenario_candidates + history_fingerprints 产物
    2. 对每个候选场景，用 TF-IDF 余弦相似度召回 top-5 最相似历史用例
    3. 若 top-5 最高分 < 0.5，直接标 NEW（跳过 LLM）
    4. 否则调 LLM 精筛，输出 label + matched_case_id + reason
    5. 输出 forward_verdicts 产物
"""
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Optional

from loguru import logger

from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.services.case_quality.tfidf_utils import batchComputeSimilarity

FORWARD_SCAN_SYSTEM_PROMPT = """你是一个测试用例分析专家，负责判断新提出的测试场景候选与历史用例的关系。

输入：
- 一个候选场景的描述、所属模块、优先级、推荐理由
- 与该场景最相似的 5 个历史用例（含标题、摘要、相似度分值）

你的任务：
1. 如果候选场景与某个历史用例高度相似（内容几乎一致），判断为 EXISTING
2. 如果候选场景与某个历史用例部分相似但需调整（如新增步骤、变更校验逻辑），判断为 MODIFY
3. 如果候选场景与所有历史用例都不相似，判断为 NEW

输出 JSON 格式：
{
    "label": "EXISTING" | "MODIFY" | "NEW",
    "matched_case_id": 整数或 null,
    "matched_title": "历史用例标题（EXISTING/MODIFY 时必填，NEW 时为空字符串）",
    "confidence": 0.0~1.0 浮点数,
    "reason": "判断理由（50 字以内）"
}

判断标准：
- EXISTING：历史用例场景描述与候选完全匹配，无需修改 → matched_case_id 为最匹配的 ID
- MODIFY：历史用例部分匹配，但候选场景有新增要素 → matched_case_id 为需修改的 ID
- NEW：无任何历史用例可匹配 → matched_case_id 为 null，matched_title 为空字符串
"""

SIMILARITY_THRESHOLD = 0.5
TOP_K = 5


@dataclass
class ForwardVerdict:
    """正向扫描 verdict — 候选场景的分类结果。

    Attributes:
        candidate_index: 候选场景在原始列表中的索引。
        candidate_description: 候选场景描述。
        label: EXISTING / MODIFY / NEW。
        matched_case_id: 匹配到的历史用例 ID（NEW 时为 None）。
        matched_title: 匹配到的历史用例标题（NEW 时为空字符串）。
        matched_similarity: 最匹配用例的 TF-IDF 相似度（NEW 时为 0.0）。
        confidence: 置信度 0.0~1.0。
        reason: 判断理由。
    """
    candidate_index: int
    candidate_description: str
    label: str
    matched_case_id: Optional[int]
    matched_title: str
    matched_similarity: float
    confidence: float
    reason: str


@dataclass
class CoarseMatch:
    """粗筛匹配结果。

    Attributes:
        case_id: 历史用例 ID。
        title: 历史用例标题。
        summary: 历史用例摘要。
        similarity: TF-IDF 余弦相似度。
    """
    case_id: int
    title: str
    summary: str
    similarity: float


class ForwardScan(PipelineStep):
    """正向扫描 Step — 将候选场景与历史用例匹配，输出标签。"""

    name: ClassVar[str] = "forward_scan"
    version: ClassVar[str] = "1.0"
    requires: ClassVar[List[str]] = ["scenario_candidates", "history_fingerprints"]
    produces: ClassVar[List[str]] = ["forward_verdicts"]

    def should_run(self, ctx: PipelineContext) -> bool:
        candidates = ctx.get_artifact("scenario_candidates")
        if candidates is None:
            return False
        return candidates.get("total_count", 0) > 0

    def cache_key(self, ctx: PipelineContext) -> str:
        candidates = ctx.get_artifact("scenario_candidates")
        fingerprints = ctx.get_artifact("history_fingerprints")

        cand_count = 0
        cand_desc_hash = ""
        if candidates:
            cand_count = candidates.get("total_count", 0)
            descs = [c.get("description", "") for c in candidates.get("candidates", [])]
            cand_desc_hash = hashlib.sha256(
                json.dumps(sorted(descs), ensure_ascii=False).encode()
            ).hexdigest()[:16]

        fp_count = 0
        fp_id_hash = ""
        if fingerprints:
            fp_count = fingerprints.get("total_count", 0)
            fp_ids = sorted([
                fp.get("case_id", 0)
                for fp in fingerprints.get("fingerprints", [])
            ])
            fp_id_hash = hashlib.sha256(
                json.dumps(fp_ids, ensure_ascii=False).encode()
            ).hexdigest()[:16]

        raw = f"{self.name}:{self.version}:c={cand_count}:{cand_desc_hash}:fp={fp_count}:{fp_id_hash}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def execute(self, ctx: PipelineContext) -> StepResult:
        candidates = ctx.get_artifact("scenario_candidates")
        fingerprints = ctx.get_artifact("history_fingerprints")

        if candidates is None:
            return StepResult(
                success=False,
                error="缺少 scenario_candidates 产物",
            )

        candidate_list = candidates.get("candidates", [])
        if not candidate_list:
            return StepResult(
                success=False,
                error="候选场景列表为空",
            )

        all_fps = []
        if fingerprints:
            all_fps = fingerprints.get("fingerprints", [])

        service = ForwardScanService(ai_client=ctx.ai_client)

        verdicts = service.scan(
            candidates=candidate_list,
            fingerprints=all_fps,
        )

        payload = {
            "project_id": candidates.get("project_id", 0),
            "verdicts": [_verdict_to_dict(v) for v in verdicts],
            "total_count": len(verdicts),
            "stats": _compute_stats(verdicts),
        }

        confidence = _compute_forward_confidence(verdicts)

        return StepResult(
            success=True,
            artifact_payload=payload,
            artifact_kind="forward_verdicts",
            artifact_confidence=confidence,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "total_count": len(verdicts),
            },
        )

    def validate_output(self, payload: Dict[str, Any]) -> bool:
        required = ["project_id", "verdicts", "total_count", "stats"]
        return all(k in payload for k in required) and payload["total_count"] == len(payload["verdicts"])

    def fallback(self, ctx: PipelineContext, error: Exception) -> Optional[StepResult]:
        candidates = ctx.get_artifact("scenario_candidates")
        project_id = 0
        if candidates:
            project_id = candidates.get("project_id", 0)
            candidate_list = candidates.get("candidates", [])
            verdicts = [
                ForwardVerdict(
                    candidate_index=i,
                    candidate_description=c.get("description", ""),
                    label="NEW",
                    matched_case_id=None,
                    matched_title="",
                    matched_similarity=0.0,
                    confidence=0.0,
                    reason=f"降级：{str(error)[:100]}",
                )
                for i, c in enumerate(candidate_list)
            ]
        else:
            verdicts = []

        return StepResult(
            success=True,
            artifact_payload={
                "project_id": project_id,
                "verdicts": [_verdict_to_dict(v) for v in verdicts],
                "total_count": len(verdicts),
                "stats": _compute_stats(verdicts),
            },
            artifact_kind="forward_verdicts",
            artifact_confidence=0.0,
            artifact_provenance={
                "step": self.name,
                "version": self.version,
                "degraded": True,
                "error": str(error),
            },
            degraded=True,
        )


class ForwardScanService:
    """正向扫描服务 — TF-IDF 粗筛 + LLM 精筛。

    Args:
        ai_client: AI 客户端。
        similarity_threshold: 粗筛阈值，top-1 低于此值直接标 NEW。
        top_k: 召回数量，默认 5。
    """

    def __init__(
        self,
        ai_client: Any,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        top_k: int = TOP_K,
    ) -> None:
        self.ai_client = ai_client
        self.similarity_threshold = similarity_threshold
        self.top_k = top_k

    def scan(
        self,
        candidates: List[Dict[str, Any]],
        fingerprints: List[Dict[str, Any]],
    ) -> List[ForwardVerdict]:
        """执行正向扫描。

        Args:
            candidates: 候选场景列表 [{description, module, priority, reason}]。
            fingerprints: 历史用例指纹列表 [{case_id, title, summary, module}]。

        Returns:
            ForwardVerdict 列表。
        """
        if not candidates:
            return []

        if not fingerprints:
            return [
                ForwardVerdict(
                    candidate_index=i,
                    candidate_description=c.get("description", ""),
                    label="NEW",
                    matched_case_id=None,
                    matched_title="",
                    matched_similarity=0.0,
                    confidence=0.8,
                    reason="无历史用例可匹配",
                )
                for i, c in enumerate(candidates)
            ]

        coarse_results = self._coarse_screening(candidates, fingerprints)

        verdicts: List[ForwardVerdict] = []
        for i, (candidate, matches) in enumerate(zip(candidates, coarse_results)):
            top_matches = matches[:self.top_k]
            top_score = top_matches[0].similarity if top_matches else 0.0

            if top_score < self.similarity_threshold:
                verdicts.append(
                    ForwardVerdict(
                        candidate_index=i,
                        candidate_description=candidate.get("description", ""),
                        label="NEW",
                        matched_case_id=None,
                        matched_title="",
                        matched_similarity=top_score,
                        confidence=0.85,
                        reason=f"TF-IDF 相似度 {top_score:.2f} 低于阈值 {self.similarity_threshold}",
                    )
                )
                continue

            verdict = self._refined_screening(candidate, top_matches)
            verdict.candidate_index = i
            verdict.candidate_description = candidate.get("description", "")
            verdict.matched_similarity = top_score
            verdicts.append(verdict)

        return verdicts

    def _coarse_screening(
        self,
        candidates: List[Dict[str, Any]],
        fingerprints: List[Dict[str, Any]],
    ) -> List[List[CoarseMatch]]:
        """TF-IDF 粗筛：为每个候选场景计算与所有历史用例的相似度，取 top_k。

        Args:
            candidates: 候选场景列表。
            fingerprints: 历史用例指纹列表。

        Returns:
            每个候选场景对应的 CoarseMatch 列表（按相似度降序）。
        """
        cand_texts = [
            f"{c.get('description', '')} {c.get('reason', '')}"[:200]
            for c in candidates
        ]
        fp_texts = [
            f"{fp.get('title', '')} {fp.get('summary', '')}"[:200]
            for fp in fingerprints
        ]

        sim_matrix = batchComputeSimilarity(cand_texts, fp_texts)

        results: List[List[CoarseMatch]] = []
        for i in range(len(candidates)):
            matches = []
            for j in range(len(fingerprints)):
                score = float(sim_matrix[i, j]) if sim_matrix.size > 0 else 0.0
                fp = fingerprints[j]
                matches.append(
                    CoarseMatch(
                        case_id=fp.get("case_id", 0),
                        title=fp.get("title", ""),
                        summary=fp.get("summary", ""),
                        similarity=score,
                    )
                )
            matches.sort(key=lambda m: m.similarity, reverse=True)
            results.append(matches)

        return results

    def _refined_screening(
        self,
        candidate: Dict[str, Any],
        top_matches: List[CoarseMatch],
    ) -> ForwardVerdict:
        """LLM 精筛：对候选场景 + top_k 匹配结果做深度判定。

        Args:
            candidate: 候选场景 dict。
            top_matches: 粗筛 top_k 结果。

        Returns:
            ForwardVerdict（candidate_index 未填充，由调用方设置）。
        """
        prompt = self._build_prompt(candidate, top_matches)

        try:
            response = self.ai_client.complete(
                prompt=prompt,
                system=FORWARD_SCAN_SYSTEM_PROMPT,
                temperature=0.2,
                max_tokens=500,
                metadata={"step_name": "forward_scan"},
            )
            raw = response.content
        except Exception as e:
            logger.warning("LLM 精筛 AI 调用失败: {}", e)
            top_score = top_matches[0].similarity if top_matches else 0.0
            return ForwardVerdict(
                candidate_index=-1,
                candidate_description=candidate.get("description", ""),
                label="NEW",
                matched_case_id=None,
                matched_title="",
                matched_similarity=top_score,
                confidence=0.0,
                reason=f"LLM 调用失败降级: {str(e)[:80]}",
            )

        return _parse_forward_response(raw, candidate, top_matches)

    def _build_prompt(
        self,
        candidate: Dict[str, Any],
        top_matches: List[CoarseMatch],
    ) -> str:
        """构建 LLM 精筛 prompt。

        Args:
            candidate: 候选场景 dict。
            top_matches: 粗筛 top_k 结果。

        Returns:
            拼接好的 prompt 字符串。
        """
        lines = [
            "## 候选场景",
            f"- 描述: {candidate.get('description', '')}",
            f"- 模块: {candidate.get('module', '')}",
            f"- 优先级: {candidate.get('priority', '')}",
            f"- 推荐理由: {candidate.get('reason', '')}",
            "",
            "## 相似历史用例（按相似度降序）",
        ]

        for idx, match in enumerate(top_matches, 1):
            lines.append(
                f"{idx}. [{match.case_id}] {match.title} (相似度 {match.similarity:.2f})"
            )
            lines.append(f"   摘要: {match.summary[:100]}")

        return "\n".join(lines)


def _parse_forward_response(
    raw: str,
    candidate: Dict[str, Any],
    top_matches: List[CoarseMatch],
) -> ForwardVerdict:
    """解析 LLM 精筛响应为 ForwardVerdict。

    Args:
        raw: LLM 原始响应文本。
        candidate: 候选场景 dict。
        top_matches: 粗筛 top_k 结果，用于校验 matched_case_id 是否合法。

    Returns:
        ForwardVerdict，解析失败时返回降级 NEW。
    """
    data = _try_parse_json(raw)
    if data is None:
        return ForwardVerdict(
            candidate_index=-1,
            candidate_description=candidate.get("description", ""),
            label="NEW",
            matched_case_id=None,
            matched_title="",
            matched_similarity=top_matches[0].similarity if top_matches else 0.0,
            confidence=0.0,
            reason="LLM 响应 JSON 解析失败，降级为 NEW",
        )

    label = data.get("label", "NEW")
    if label not in ("EXISTING", "MODIFY", "NEW"):
        label = "NEW"

    matched_case_id = data.get("matched_case_id")
    matched_title = data.get("matched_title", "")

    if label in ("EXISTING", "MODIFY"):
        if not isinstance(matched_case_id, int) or isinstance(matched_case_id, bool) or not matched_title:
            label = "NEW"
            matched_case_id = None
            matched_title = ""
        elif not _is_valid_match(matched_case_id, top_matches):
            label = "NEW"
            matched_case_id = None
            matched_title = ""

    if label == "NEW":
        matched_case_id = None
        matched_title = ""

    confidence = data.get("confidence", 0.7)
    if not isinstance(confidence, (int, float)):
        confidence = 0.7
    confidence = max(0.0, min(1.0, float(confidence)))

    reason = data.get("reason", "")
    if not isinstance(reason, str) or not reason.strip():
        reason = candidate.get("description", "无理由")
    reason = reason[:100]

    return ForwardVerdict(
        candidate_index=-1,
        candidate_description=candidate.get("description", ""),
        label=label,
        matched_case_id=matched_case_id,
        matched_title=matched_title,
        matched_similarity=top_matches[0].similarity if top_matches else 0.0,
        confidence=confidence,
        reason=reason,
    )


def _try_parse_json(raw: str) -> Optional[Dict[str, Any]]:
    """尝试多种方式解析 JSON。

    Args:
        raw: LLM 原始响应。

    Returns:
        解析后的 dict，失败返回 None。
    """
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass

    match = re.search(r'\{[\s\S]*\}', raw)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _is_valid_match(case_id: int, top_matches: List[CoarseMatch]) -> bool:
    """校验 matched_case_id 是否在 top_k 匹配列表中。

    Args:
        case_id: LLM 返回的 case_id。
        top_matches: 粗筛结果列表。

    Returns:
        True 如果 case_id 在列表中。
    """
    valid_ids = {m.case_id for m in top_matches}
    return case_id in valid_ids


def _verdict_to_dict(v: ForwardVerdict) -> Dict[str, Any]:
    """将 ForwardVerdict 转为可序列化的 dict。

    Args:
        v: ForwardVerdict 实例。

    Returns:
        可 JSON 序列化的 dict。
    """
    return {
        "candidate_index": v.candidate_index,
        "candidate_description": v.candidate_description,
        "label": v.label,
        "matched_case_id": v.matched_case_id,
        "matched_title": v.matched_title,
        "matched_similarity": v.matched_similarity,
        "confidence": v.confidence,
        "reason": v.reason,
    }


def _compute_stats(verdicts: List[ForwardVerdict]) -> Dict[str, int]:
    """计算 verdict 统计信息。

    Args:
        verdicts: ForwardVerdict 列表。

    Returns:
        各类标签计数字典。
    """
    existing = sum(1 for v in verdicts if v.label == "EXISTING")
    modify = sum(1 for v in verdicts if v.label == "MODIFY")
    new = sum(1 for v in verdicts if v.label == "NEW")
    return {"existing": existing, "modify": modify, "new": new}


def _compute_forward_confidence(verdicts: List[ForwardVerdict]) -> float:
    """计算正向扫描产物的整体置信度。

    Args:
        verdicts: ForwardVerdict 列表。

    Returns:
        float: 平均置信度。
    """
    if not verdicts:
        return 0.0
    return sum(v.confidence for v in verdicts) / len(verdicts)
