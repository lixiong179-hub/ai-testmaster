"""冗余度检测Mixin - 检测测试用例中的冗余步骤和逻辑。
"""
from typing import Dict, Any, List, Optional
from loguru import logger
from difflib import SequenceMatcher

from app.models.test_case import TestCase, TestStep
from app.services.case_quality.models import RedundancyScore


class RedundancyMixin:

    def _analyze_redundancy(self, test_case: TestCase, steps: List[TestStep], all_cases: List[TestCase]) -> RedundancyScore:
        score = RedundancyScore()

        similar_cases = self._find_similar_cases(test_case, steps, all_cases)
        score.similar_case_count = len(similar_cases)
        score.similar_cases = similar_cases

        step_texts = [step.action for step in steps]
        seen = set()
        duplicate_count = 0
        for text in step_texts:
            normalized = text.strip().lower()
            if normalized in seen:
                duplicate_count += 1
            else:
                seen.add(normalized)
        score.duplicate_step_count = duplicate_count

        redundancy_points = 0.0
        redundancy_points += min(score.similar_case_count * 1.5, 5)
        redundancy_points += min(score.duplicate_step_count * 1.0, 3)

        score.score = min(redundancy_points, 10)

        if score.score <= 2:
            score.level = "low"
        elif score.score <= 5:
            score.level = "moderate"
        else:
            score.level = "high"

        logger.info(f"冗余度分析: 相似用例={score.similar_case_count}, 重复步骤={score.duplicate_step_count}, 得分={score.score}, 等级={score.level}")
        return score

    def _find_similar_cases(
        self,
        target_case: TestCase,
        target_steps: List[TestStep],
        all_cases: List[TestCase],
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        similar = []
        target_actions = [step.action.strip().lower() for step in target_steps]
        target_text = " ".join(target_actions)

        for case in all_cases:
            if case.id == target_case.id:
                continue

            case_steps = self.db.query(TestStep).filter(
                TestStep.test_case_id == case.id
            ).all()
            case_actions = [step.action.strip().lower() for step in case_steps]
            case_text = " ".join(case_actions)

            if not target_text or not case_text:
                continue

            similarity = SequenceMatcher(None, target_text, case_text).ratio()

            if similarity >= similarity_threshold:
                similar.append({
                    "case_id": case.id,
                    "case_name": case.title,
                    "similarity": round(similarity, 2),
                })

        similar.sort(key=lambda x: x["similarity"], reverse=True)
        return similar[:5]
