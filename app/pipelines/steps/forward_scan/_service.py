from typing import Any, Dict, List

from loguru import logger

from app.pipelines.steps.forward_scan._types import (
    ForwardVerdict,
    CoarseMatch,
    FORWARD_SCAN_SYSTEM_PROMPT,
    SIMILARITY_THRESHOLD,
    TOP_K,
)
from app.pipelines.steps.forward_scan._parsing import _parse_forward_response
from app.services.case_quality.tfidf_utils import batchComputeSimilarity


class ForwardScanService:
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
