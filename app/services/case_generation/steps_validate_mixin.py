"""步骤验证与持久化Mixin - UI描述构建、用例保存与步骤校验。

本模块提供测试用例生成过程中的UI描述构建、用例数据持久化和
前置条件自动解析逻辑。作为StepsValidateMixin被StepsMixin组合使用。

核心类:
    - StepsValidateMixin: 步骤验证与持久化Mixin

设计模式:
    作为Mixin模块，通过多继承组合到StepsMixin中，提供:
    - _build_ui_description: UI描述文本构建
    - _save_test_case: 用例数据持久化

依赖关系:
    - app.models.test_case: TestCase/TestStep ORM模型
    - app.models.project: Project ORM模型
    - app.core.config: 配置管理
    - app.services.case_generation.core_mixin: ContentSanitizer和分类常量
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.models.project import Project
from app.core.config import settings
from app.services.case_generation.core_mixin import (
    ContentSanitizer,
    TEST_CATEGORY_MANUAL,
)


class StepsValidateMixin:
    """步骤验证与持久化Mixin - UI描述构建和用例数据持久化。

    职责:
        - 将UI描述列表构建为统一的文本描述
        - AI生成用例的数据库持久化
        - 测试步骤JSON构建与TestStep记录创建
        - 前置条件的自动解析（配置开关控制）

    设计意图:
        将用例保存和UI描述构建从生成流程编排中抽离，便于:
        1. 独立修改持久化逻辑不影响生成流程
        2. 支持不同的存储策略
        3. 统一处理前置条件解析

    使用场景:
        被StepsMixin通过多继承组合，
        在generate_test_case_for_point和generate_test_cases_batch中调用。
    """

    def _build_ui_description(self, ui_descriptions: List[Dict[str, Any]]) -> str:
        """将UI描述列表构建为统一的文本描述。

        支持两种UI描述格式:
            1. 屏幕格式（含screen_name/summary/element_count等）
            2. 文件格式（含file_name/file_url/description等）

        Args:
            ui_descriptions: UI描述字典列表。

        Returns:
            拼接后的UI描述文本。
        """
        if not ui_descriptions:
            return ""
        parts = []
        for ui_desc in ui_descriptions:
            if ui_desc.get("screen_name"):
                # 屏幕格式：包含名称、功能摘要和元素统计
                name = ui_desc["screen_name"]
                summary = ui_desc.get("summary", "")
                element_count = ui_desc.get("element_count", 0)
                button_count = ui_desc.get("button_count", 0)
                input_count = ui_desc.get("input_count", 0)
                desc_parts = [f"【{name}】"]
                if summary:
                    desc_parts.append(f"功能：{summary}")
                if element_count:
                    desc_parts.append(f"元素：{element_count}个（按钮{button_count}个，输入框{input_count}个）")
                parts.append("\n".join(desc_parts))
            else:
                # 文件格式：包含文件名和描述
                name = ui_desc.get("screen_name") or ui_desc.get("file_name") or ui_desc.get("name", "未命名")
                file_id = ui_desc.get("file_id", "")
                content = ui_desc.get("content", "")
                description = ui_desc.get("description", "")
                if content:
                    parts.append(f"【{name}】\n{content}")
                elif description:
                    parts.append(f"【{name}】\n{description}")
                else:
                    parts.append(f"【{name}】(文件ID: {file_id}，内容待提取)")
        return "\n\n".join(parts)

    async def _save_test_case(
        self,
        project_id: int,
        generated_case: Dict[str, Any],
        test_point: Dict[str, Any],
        requirement_file_id: Optional[int] = None
    ) -> TestCase:
        """将AI生成的用例数据持久化到数据库。

        持久化流程:
            1. 生成唯一用例编号
            2. 创建TestCase记录
            3. 创建TestStep记录
            4. 自动解析前置条件（如果配置开启）

        Args:
            project_id: 项目ID。
            generated_case: AI生成的用例数据字典。
            test_point: 关联的测试点信息。
            requirement_file_id: 关联的需求文件ID，可选。

        Returns:
            持久化后的TestCase ORM实例。
        """
        # 生成唯一用例编号，格式: CASE{项目ID}-{时间戳+微秒}
        case_no = f"CASE{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # 构建步骤JSON
        steps = generated_case.get("steps", [])
        steps_json = []
        for i, step in enumerate(steps):
            steps_json.append({
                "step": step.get("step", str(i + 1)),
                "description": step.get("description", ""),
                "action": step.get("action", "执行"),
                "expected_result": step.get("expected_result", ""),
                "param": step.get("param", "")
            })

        # 创建TestCase记录
        test_case = TestCase(
            project_id=project_id,
            requirement_file_id=requirement_file_id,
            test_point_id=test_point.get("id"),
            case_no=case_no,
            module=generated_case.get("module", test_point.get("module", "AI生成")),
            title=generated_case.get("title", test_point.get("function", "测试用例")),
            precondition=generated_case.get("precondition", ""),
            steps_json=steps_json,
            expected_result=generated_case.get("expected_result", ""),
            priority=generated_case.get("priority", test_point.get("priority", 2)),
            case_type=generated_case.get("case_type") or generated_case.get("test_category") or "manual",
            test_category=generated_case.get("case_category", TEST_CATEGORY_MANUAL),
            generate_status=1  # 标记为AI生成
        )
        self.db.add(test_case)
        self.db.flush()  # 获取test_case.id用于关联步骤

        # 创建TestStep记录
        for i, step in enumerate(steps):
            test_step = TestStep(
                test_case_id=test_case.id,
                step_number=i + 1,
                action=step.get("action", step.get("description", step.get("step", "执行"))),
                expected_result=step.get("expected_result", step.get("param", "预期结果正常")),
                is_business_view=1,  # 默认在业务视图显示
                is_technical_view=1   # 默认在技术视图显示
            )
            self.db.add(test_step)

        self.db.commit()
        self.db.refresh(test_case)

        # 自动解析前置条件（配置开关控制）
        if settings.AUTO_PARSE_PRECONDITION and test_case.precondition and test_case.precondition.strip():
            try:
                from app.utils.ai_client import parse_precondition_to_steps
                from app.models.test_case import TestCasePreconditionStep

                # 获取项目URL用于前置条件解析
                project = self.db.query(Project).filter(Project.id == project_id).first()
                project_url = ""
                if project:
                    project_url = getattr(project, 'test_object_url', '') or ''

                # 调用AI解析前置条件为可执行步骤
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
                # 前置条件解析失败不影响用例保存
                logger.warning(f"自动解析前置条件失败 (用例ID={test_case.id}): {e}")

        return test_case
