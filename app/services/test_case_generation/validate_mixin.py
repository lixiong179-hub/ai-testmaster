"""
Test Case Generation Service - 验证与保存Mixin（聚合层）
从原 validate_mixin.py 拆分为薄聚合层：继承 UiValidation + QualityGate 两个子Mixin，
保留 _case_title_exists 与 _save_test_case（DB 持久化逻辑）。
"""
import inspect
from typing import Dict, Any, Optional
from loguru import logger
from sqlalchemy.exc import IntegrityError

from app.models.test_case import TestCase, TestStep
from app.core.config import settings
from app.services.test_case_generation.quality_validator import compute_quality_score
from app.services.quality.grade import grade_status_to_letter
from app.services.case_number_service import CaseNumberService
from app.services.case_quality.history_cache import invalidate_project_cache
from app.services.test_case_generation._ui_validation_mixin import TestCaseGenerationUiValidationMixin
from app.services.test_case_generation._quality_gate_mixin import TestCaseGenerationQualityGateMixin


class AIGenerationError(Exception):
    """AI 生成质量门禁阻断异常（spec L71）。

    业务原因：rejected 状态用例阻断入库时抛出此异常，与普通 ValueError 区分，
    便于上层（batch_mixin 的 except 分支）按异常类型精准识别质量门禁拦截，
    而非笼统捕获所有 ValueError。
    """


class TestCaseGenerationValidateMixin(
    TestCaseGenerationUiValidationMixin,
    TestCaseGenerationQualityGateMixin,
):
    """测试用例生成服务 - 验证与保存Mixin（聚合层）。

    继承 UiValidation（UI 元素可执行性校验）+ QualityGate（动作修正/质量门禁/优先级），
    本类保留 DB 持久化逻辑（_case_title_exists / _save_test_case）。
    """

    def _case_title_exists(self, project_id: int, title: str) -> bool:
        if not title:
            return False
        # R3 修复：with_for_update() 在 InnoDB REPEATABLE READ 下对 (project_id, title)
        # 索引加 gap lock，使 check-then-insert 原子化，消除并发竞态导致的重复 title。
        # 依赖 ix_test_cases_project_title 索引（见 models/test_case.py __table_args__）。
        existing = self.db.query(TestCase.id).filter(
            TestCase.project_id == project_id,
            TestCase.is_deleted == False,  # noqa: E712
            TestCase.generate_status == 1,
            TestCase.title == title,
        ).with_for_update().first()
        return existing is not None

    async def _save_test_case(
        self,
        project_id: int,
        generated_case: Dict[str, Any],
        test_point: Dict[str, Any],
        requirement_file_id: Optional[int] = None
    ) -> TestCase:
        """
        保存测试用例到数据库

        Args:
            project_id: 项目ID
            generated_case: 生成的用例数据
            test_point: 来源测试点
            requirement_file_id: 关联的需求文件ID（可选）

        Returns:
            保存的测试用例对象
        """
        case_no = CaseNumberService.generate(project_id, self.db)

        steps = generated_case.get("steps", [])
        case_test_data = generated_case.get("test_data")
        steps_json = []
        for i, step in enumerate(steps):
            raw_action_type = step.get("action_type", "")
            corrected_action_type = self._correct_action_type(
                step.get("action", ""), raw_action_type
            )
            step_entry = {
                "step": step.get("step", str(i + 1)),
                "description": step.get("description", ""),
                "action": step.get("action", "执行"),
                "expected_result": step.get("expected_result", ""),
                "param": step.get("param", ""),
                "action_type": corrected_action_type,
                "input_value": step.get("input_value", ""),
                "target_element": step.get("target_element", ""),
                "test_data": step.get("test_data", []),
            }
            if i == 0 and case_test_data:
                step_entry["test_data"] = case_test_data
            steps_json.append(step_entry)

        case_type = self._normalize_case_type(
            generated_case.get("case_type"),
            generated_case.get("test_category"),
        )
        case_category = (generated_case.get("case_category") or "").strip()
        test_category_value = case_type

        raw_precondition = generated_case.get("precondition", "")
        cleaned_precondition = self._clean_precondition(raw_precondition)
        title = (
            generated_case.get("title")
            or test_point.get("point")
            or "(untitled)"
        ).strip()

        if self._case_title_exists(project_id, title):
            raise ValueError(f"duplicate generated case title: {title}")

        case_for_quality = dict(generated_case)
        case_for_quality.update({
            "title": title,
            "precondition": cleaned_precondition,
            "steps": steps_json,
            "case_type": case_type,
            "case_category": case_category,
        })
        quality_score = compute_quality_score([case_for_quality])
        quality_issues, gate_status = self._quality_gate_issues(
            case_for_quality,
            quality_score,
            ui_specs=generated_case.get("_context_ui_specs"),
            project_id=project_id,
            db=self.db,
        )
        if quality_issues:
            issue_text = "; ".join(quality_issues[:3])
            raise AIGenerationError(f"generated case failed quality gate: {issue_text}")
        if gate_status == "warning":
            logger.warning(
                f"generated case passed gate with warning status (title={title})"
            )
        pending_review = gate_status == "pending_review"
        priority = self._resolve_generated_priority(case_for_quality, test_point)

        # Task 17.3: 由 grade_status 映射质量等级（A=passed/B=warning/C=pending_review/D=rejected）
        quality_grade = grade_status_to_letter(gate_status)

        test_case = TestCase(
            project_id=project_id,
            requirement_file_id=requirement_file_id,
            test_point_id=test_point.get("id"),
            case_no=case_no,
            module=generated_case.get("module", test_point.get("module", "AI生成")),
            title=title,
            precondition=cleaned_precondition,
            steps_json=steps_json,
            expected_result=generated_case.get("expected_result", ""),
            priority=priority,
            case_type=case_type,
            test_category=test_category_value,
            parent_case_id=generated_case.get("parent_case_id"),
            ai_change_type=generated_case.get("change_type"),
            generate_status=1,
            prior_quality_score=quality_score,
            quality_grade=quality_grade,
            lifecycle_status="pending_review" if pending_review else "draft",
        )

        # 并发安全：_case_title_exists 是 check-then-insert 非原子操作，
        # 在 batch_mixin 的 Semaphore(3) 并发下可能两个协程同时通过检查后并发写入。
        # 捕获 IntegrityError 兜底（若 DB 加了唯一约束则可防御；无约束时前置检查仍生效）
        try:
            self.db.add(test_case)
            self.db.flush()
        except IntegrityError as e:
            self.db.rollback()
            if "title" in str(e).lower() or "duplicate" in str(e).lower():
                raise ValueError(
                    f"concurrent duplicate generated case title: {title}"
                ) from e
            raise

        # 新用例入库后精准失效该项目的历史用例缓存，避免后续查询返回陈旧数据
        invalidate_project_cache(project_id)

        for i, step in enumerate(steps):
            raw_action_type = step.get("action_type", "")
            corrected_action_type = self._correct_action_type(
                step.get("action", step.get("description", step.get("step", "执行"))),
                raw_action_type
            )
            test_step = TestStep(
                test_case_id=test_case.id,
                step_number=i + 1,
                action=step.get("action", step.get("description", step.get("step", "执行"))),
                expected_result=step.get("expected_result", step.get("param", "预期结果正常")),
                action_type=corrected_action_type,
                input_value=step.get("input_value", ""),
                target_element=step.get("target_element", ""),
                is_business_view=1,
                is_technical_view=1
            )
            self.db.add(test_step)

        self.db.commit()
        self.db.refresh(test_case)

        if settings.AUTO_PARSE_PRECONDITION and test_case.precondition and test_case.precondition.strip():
            try:
                from app.utils.ai_client import parse_precondition_to_steps
                from app.models.test_case import TestCasePreconditionStep

                parsed_steps = parse_precondition_to_steps(
                    precondition=test_case.precondition
                )
                if inspect.isawaitable(parsed_steps):
                    parsed_steps = await parsed_steps

                if parsed_steps:
                    for idx, step_data in enumerate(parsed_steps):
                        pc_step = TestCasePreconditionStep(
                            test_case_id=test_case.id,
                            step_number=idx + 1,
                            action=step_data.get("action", ""),
                            action_type=step_data.get("action_type", "click"),
                            input_value=step_data.get("input_value", ""),
                            target_element=step_data.get("target_element", ""),
                            expected_result=step_data.get("expected_result", ""),
                            has_locator=0,
                            locator_status="pending"
                        )
                        self.db.add(pc_step)
                    self.db.commit()
                    logger.info(f"自动解析前置条件成功，生成 {len(parsed_steps)} 个步骤 (用例ID={test_case.id})")
            except Exception as e:
                logger.warning(f"自动解析前置条件失败 (用例ID={test_case.id}): {e}")

        return test_case
