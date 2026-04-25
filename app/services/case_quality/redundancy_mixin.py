"""冗余度检测Mixin - 基于 TF-IDF + 余弦相似度检测测试用例中的冗余步骤和逻辑。

升级说明 (T13):
    - 原 SequenceMatcher 替换为 TF-IDF 向量化 + 余弦相似度
    - 阈值按项目规模动态调整，避免小项目误杀、大项目漏检
    - 依赖 numpy 实现轻量版 TF-IDF，无需 scikit-learn

性能优化 (T15):
    - _find_similar_cases 支持项目级嵌入向量缓存（case_text_map），
      避免循环内逐条查询数据库，将 O(N²) 查询降至 O(1)。
"""
from typing import Dict, Any, List, Optional

from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.services.case_quality.models import RedundancyScore
from app.services.case_quality.tfidf_utils import (
    batchComputeSimilarity,
    computeDynamicThreshold,
)


class RedundancyMixin:

    def _analyze_redundancy(
        self,
        test_case: TestCase,
        steps: List[TestStep],
        all_cases: List[TestCase],
        case_text_map: Optional[Dict[int, str]] = None,
    ) -> RedundancyScore:
        """分析冗余度，支持传入预取的嵌入向量缓存。

        Args:
            test_case: 目标测试用例。
            steps: 目标用例步骤列表。
            all_cases: 项目全部用例列表。
            case_text_map: 用例ID到步骤文本的映射（项目级缓存），
                           为None时回退到逐条查询模式。

        Returns:
            RedundancyScore: 冗余度评分。
        """
        score = RedundancyScore()

        # 动态阈值：根据项目用例规模自适应
        totalCases = len(all_cases) + 1
        similarityThreshold = computeDynamicThreshold(totalCases)

        similarCases = self._find_similar_cases(
            test_case, steps, all_cases,
            similarity_threshold=similarityThreshold,
            case_text_map=case_text_map,
        )
        score.similar_case_count = len(similarCases)
        score.similar_cases = similarCases

        # 步骤级重复检测：归一化后精确匹配
        stepTexts = [step.action for step in steps]
        seen: set = set()
        duplicateCount = 0
        for text in stepTexts:
            normalized = text.strip().lower()
            if normalized in seen:
                duplicateCount += 1
            else:
                seen.add(normalized)
        score.duplicate_step_count = duplicateCount

        # 冗余度评分计算
        redundancyPoints = 0.0
        redundancyPoints += min(score.similar_case_count * 1.5, 5)
        redundancyPoints += min(score.duplicate_step_count * 1.0, 3)

        score.score = min(redundancyPoints, 10)

        if score.score <= 2:
            score.level = "low"
        elif score.score <= 5:
            score.level = "moderate"
        else:
            score.level = "high"

        logger.info(
            f"冗余度分析: 相似用例={score.similar_case_count}, "
            f"重复步骤={score.duplicate_step_count}, "
            f"动态阈值={similarityThreshold:.2f}, "
            f"得分={score.score}, 等级={score.level}"
        )
        return score

    def _find_similar_cases(
        self,
        target_case: TestCase,
        target_steps: List[TestStep],
        all_cases: List[TestCase],
        similarity_threshold: float = 0.7,
        case_text_map: Optional[Dict[int, str]] = None,
    ) -> List[Dict[str, Any]]:
        """基于 TF-IDF 余弦相似度查找相似用例，优先使用项目级嵌入向量缓存。

        将目标用例与所有候选用例的步骤文本合并构建统一词汇表，
        批量计算 TF-IDF 余弦相似度，按阈值筛选并返回 Top5。

        当 case_text_map 不为 None 时，直接从缓存获取步骤文本，
        避免对每个 other_case 执行数据库查询（消除 N² 查询）。

        Args:
            target_case: 目标用例。
            target_steps: 目标用例步骤。
            all_cases: 项目全部用例。
            similarity_threshold: 相似度阈值，由 computeDynamicThreshold 动态计算。
            case_text_map: 用例ID到步骤文本的映射（项目级缓存），
                           为None时回退到逐条查询模式。

        Returns:
            List[Dict[str, Any]]: 相似用例列表，按相似度降序排列，最多5条。
        """
        if not all_cases:
            return []

        # 构建目标文档文本
        if case_text_map and target_case.id in case_text_map:
            targetText = case_text_map[target_case.id]
        else:
            targetActions = [step.action.strip().lower() for step in target_steps]
            targetText = " ".join(targetActions)

        if not targetText:
            return []

        # 构建候选文档文本
        candidateTexts: List[str] = []
        candidateCases: List[TestCase] = []
        for case in all_cases:
            if case.id == target_case.id:
                continue
            # 优先使用缓存的步骤文本，避免逐条查询数据库
            if case_text_map and case.id in case_text_map:
                caseText = case_text_map[case.id]
            else:
                caseSteps = self.db.query(TestStep).filter(
                    TestStep.test_case_id == case.id
                ).all()
                caseActions = [step.action.strip().lower() for step in caseSteps]
                caseText = " ".join(caseActions)

            if not caseText:
                continue
            candidateTexts.append(caseText)
            candidateCases.append(case)

        if not candidateTexts:
            return []

        # 批量计算 TF-IDF 余弦相似度
        try:
            simMatrix = batchComputeSimilarity(
                targetTexts=[targetText],
                candidateTexts=candidateTexts,
            )
        except Exception as exc:
            logger.warning(f"TF-IDF 相似度计算异常，降级为空结果: {exc}")
            return []

        # simMatrix shape: (1, n_candidates)
        similarities = simMatrix[0] if simMatrix.size > 0 else []

        # 按阈值筛选
        similar: List[Dict[str, Any]] = []
        for idx, simValue in enumerate(similarities):
            simFloat = float(simValue)
            if simFloat >= similarity_threshold:
                similar.append({
                    "case_id": candidateCases[idx].id,
                    "case_name": candidateCases[idx].title,
                    "similarity": round(simFloat, 4),
                })

        similar.sort(key=lambda x: x["similarity"], reverse=True)
        return similar[:5]
