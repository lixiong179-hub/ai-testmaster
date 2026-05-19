"""
Test Case Generation Service - 验证与保存Mixin
包含测试用例保存到数据库、前置条件解析等逻辑
"""
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.models.project import Project
from app.core.config import settings
from app.core.constants import DEFAULT_AI_FALLBACK_CASE_TYPE, normalize_priority
from app.services.test_case_generation.quality_validator import compute_quality_score


class TestCaseGenerationValidateMixin:
    """测试用例生成服务 - 验证与保存Mixin"""

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
        case_no = f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        steps = generated_case.get("steps", [])
        case_test_data = generated_case.get("test_data")
        steps_json = []
        for i, step in enumerate(steps):
            step_entry = {
                "step": step.get("step", str(i + 1)),
                "description": step.get("description", ""),
                "action": step.get("action", "执行"),
                "expected_result": step.get("expected_result", ""),
                "param": step.get("param", ""),
                "action_type": step.get("action_type", ""),
                "input_value": step.get("input_value", ""),
                "target_element": step.get("target_element", ""),
                "test_data": step.get("test_data", []),
            }
            if i == 0 and case_test_data:
                step_entry["test_data"] = case_test_data
            steps_json.append(step_entry)

        case_type = generated_case.get("case_type") or generated_case.get("test_category") or DEFAULT_AI_FALLBACK_CASE_TYPE
        case_category = generated_case.get("case_category", "")
        test_category_value = generated_case.get("test_category") or case_type
        if case_category and case_category not in str(test_category_value):
            test_category_value = f"{case_category},{test_category_value}"
        quality_score = compute_quality_score([generated_case]) if case_category else None

        test_case = TestCase(
            project_id=project_id,
            requirement_file_id=requirement_file_id,
            test_point_id=test_point.get("id"),
            case_no=case_no,
            module=generated_case.get("module", test_point.get("module", "AI生成")),
            title=generated_case.get("title") or test_point.get("point") or "(无标题)",
            precondition=generated_case.get("precondition", ""),
            steps_json=steps_json,
            expected_result=generated_case.get("expected_result", ""),
            priority=normalize_priority(generated_case.get("priority", test_point.get("priority", 2))),
            case_type=case_type,
            test_category=test_category_value,
            parent_case_id=generated_case.get("parent_case_id"),
            ai_change_type=generated_case.get("change_type"),
            generate_status=1,
            prior_quality_score=quality_score,
        )

        self.db.add(test_case)
        self.db.flush()

        for i, step in enumerate(steps):
            test_step = TestStep(
                test_case_id=test_case.id,
                step_number=i + 1,
                action=step.get("action", step.get("description", step.get("step", "执行"))),
                expected_result=step.get("expected_result", step.get("param", "预期结果正常")),
                action_type=step.get("action_type", ""),
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

                project = self.db.query(Project).filter(Project.id == project_id).first()
                project_url = ""
                if project:
                    project_url = getattr(project, 'test_object_url', '') or ''

                parsed_steps = await parse_precondition_to_steps(
                    precondition_text=test_case.precondition,
                    project_url=project_url
                )

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
