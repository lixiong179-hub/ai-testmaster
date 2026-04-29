"""用例生成步骤Mixin - 生成流程编排、用例持久化与批量生成。

本模块实现测试用例生成的完整流程编排，包括单点生成、批量生成、
用例数据持久化和前置条件自动解析。作为StepsMixin被
TestCaseGenerationService组合使用。

核心类:
    - StepsMixin: 生成流程Mixin，编排完整的用例生成流程

设计模式:
    作为Mixin模块，通过多继承组合到TestCaseGenerationService中，提供:
    - generate_test_case_for_point: 单个测试点生成用例
    - generate_test_cases_batch: 批量生成用例（流式进度推送）
    - _save_test_case: 用例数据持久化
    - _build_ui_description: UI描述文本构建

依赖关系:
    - app.models.test_case: TestCase/TestStep ORM模型
    - app.models.project: Project ORM模型
    - app.utils.ai_client: AI客户端工具
    - app.core.config: 配置管理
    - app.services.case_generation_core: ContentSanitizer和分类常量

生成流程:
    generate_test_cases_batch:
        1. 获取上下文 -> 2. 遍历测试点 -> 3. AI生成用例
        -> 4. 持久化用例 -> 5. 自动解析前置条件 -> 6. 推送进度

    generate_test_case_for_point:
        1. 构建UI描述 -> 2. 判断用例分类 -> 3. 调用AI生成

流式设计:
    generate_test_cases_batch使用AsyncGenerator实现流式进度推送，
    前端可实时展示生成进度和中间结果。
"""
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.models.project import Project
from app.utils.ai_client import AIServiceError
from app.core.config import settings
from app.services.case_generation_core import (
    ContentSanitizer,
    TEST_CATEGORY_UI_AUTO,
    TEST_CATEGORY_MANUAL,
    TEST_CATEGORY_API_AUTO,
)


class StepsMixin:
    """生成流程Mixin - 编排用例生成的完整流程。

    职责:
        - 单个测试点的用例生成与分类判断
        - 批量用例生成的流式进度推送
        - AI生成结果的数据库持久化
        - 前置条件的自动解析
        - UI描述文本的构建

    设计意图:
        将生成流程编排从AI调用和上下文构建中抽离，便于:
        1. 独立修改生成流程不影响AI调用逻辑
        2. 支持不同的生成策略（单点/批量/增量）
        3. 流式进度推送与业务逻辑解耦

    使用场景:
        被TestCaseGenerationService通过多继承组合，
        对外提供generate_test_case_for_point和generate_test_cases_batch接口。
    """

    async def generate_test_case_for_point(
        self,
        context: Dict[str, Any],
        test_point: Dict[str, Any],
        project_id: int,
        case_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """为单个测试点生成测试用例。

        生成流程:
            1. 构建UI描述文本
            2. 清洗需求文档和UI描述内容
            3. 判断用例分类（UI自动化/手工/API自动化）
            4. 组装生成上下文
            5. 调用AI生成用例

        用例分类判断逻辑:
            - 无UI信息 -> 手工测试(manual)
            - 有UI信息且含交互元素关键词 -> UI自动化(ui_automation)
            - 有UI信息但无交互元素 -> 手工测试(manual)

        Args:
            context: 上下文字典，包含requirement_content/ui_descriptions/ui_specs。
            test_point: 测试点信息，包含module/function/point/priority。
            project_id: 项目ID。
            case_type: 指定用例类型，可选，覆盖自动判断。

        Returns:
            AI生成的用例数据字典。
        """
        # 构建UI描述文本
        ui_description = self._build_ui_description(context.get("ui_descriptions", []))

        # 清洗内容，防止Prompt注入
        requirement_content = ContentSanitizer.sanitize(context.get("requirement_content", ""))
        ui_description = ContentSanitizer.sanitize(ui_description)

        # 判断是否有UI信息和需求信息
        has_ui = bool(ui_description and ui_description.strip()) or bool(context.get("ui_specs", []))
        has_requirement = bool(requirement_content and requirement_content.strip())

        # 自动判断用例分类
        if not has_ui:
            case_category = TEST_CATEGORY_MANUAL
        else:
            # 检测UI描述中是否包含交互元素关键词
            ui_keywords = ['按钮', '表单', '输入框', '下拉框', '复选框', '单选框', '链接', '导航',
                          'button', 'input', 'form', 'dropdown', 'checkbox', 'radio', 'link', 'menu']
            ui_has_interactive = any(k in ui_description.lower() for k in ui_keywords)
            case_category = TEST_CATEGORY_UI_AUTO if ui_has_interactive else TEST_CATEGORY_MANUAL

        # 组装生成上下文，case_type可覆盖自动判断
        generation_context = {
            "requirement_content": requirement_content,
            "ui_description": ui_description,
            "ui_specs": context.get("ui_specs", []),
            "test_point": test_point,
            "case_type": case_type if case_type else "ui_automation",
            "case_category": case_type if case_type else case_category
        }

        # 调用AI生成用例
        generated_case = await self._generate_case_with_ai(generation_context)
        return generated_case

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

    def _get_default_case(self, test_point: Dict[str, Any]) -> Dict[str, Any]:
        """已废弃方法 - AI生成失败时不再返回默认用例。

        按照项目规则，禁止TODO与空占位，AI生成失败应直接抛出异常，
        不应返回可能不准确的默认用例。

        Raises:
            AIServiceError: 始终抛出，提示AI生成失败。
        """
        logger.error("调用了已废弃的 _get_default_case 方法，不应发生！")
        raise AIServiceError("AI生成失败，无法返回默认测试用例")

    async def generate_test_cases_batch(
        self,
        project_id: int,
        user_id: int,
        test_point_ids: Optional[List[int]] = None,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_page: int = 1,
        test_point_page_size: int = 100,
        case_type: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """批量生成测试用例，通过AsyncGenerator流式推送进度。

        生成流程:
            1. 获取上下文信息（5%进度）
            2. 遍历测试点逐个生成（10%-95%进度）
            3. 每个用例生成后持久化并推送进度
            4. 汇总生成结果（100%进度）

        进度推送格式:
            - progress: 进度百分比(0-100)
            - message: 进度描述
            - status: 状态(running/warning/success/partial/error)
            - current/total: 当前/总数
            - case: 已生成的用例摘要

        Args:
            project_id: 项目ID。
            user_id: 用户ID。
            test_point_ids: 测试点ID列表，可选。
            requirement_file_ids: 需求文件ID列表，可选。
            ui_file_ids: UI文件ID列表，可选。
            ui_screen_ids: UI屏幕ID列表，可选。
            test_point_page: 测试点分页页码，默认1。
            test_point_page_size: 测试点分页大小，默认100。
            case_type: 指定用例类型，可选。

        Yields:
            进度信息字典，包含progress/message/status等字段。
        """
        # 阶段1：获取上下文
        yield {"progress": 5, "message": "获取上下文信息", "status": "running"}
        context = await self.get_context_for_generation(
            project_id=project_id, user_id=user_id,
            requirement_file_ids=requirement_file_ids, ui_file_ids=ui_file_ids,
            ui_screen_ids=ui_screen_ids, test_point_ids=test_point_ids,
            test_point_page=test_point_page, test_point_page_size=test_point_page_size
        )

        # 推送上下文警告信息
        warnings = context.get("warnings", [])
        if warnings:
            for warning in warnings[:3]:
                yield {"progress": 5, "message": warning, "status": "warning"}

        test_points = context.get("test_points", [])
        total = len(test_points)
        if total == 0:
            yield {"progress": 100, "message": "没有找到测试点", "status": "warning", "data": []}
            return

        pagination = context.get("pagination", {})
        yield {
            "progress": 10, "message": f"开始生成{total}个测试用例",
            "status": "running", "total": total, "pagination": pagination
        }

        # 阶段2：逐个生成用例
        created_cases = []
        failed_count = 0
        primary_requirement_file_id = requirement_file_ids[0] if requirement_file_ids else None

        for i, test_point in enumerate(test_points):
            try:
                # 为单个测试点生成用例
                generated_case = await self.generate_test_case_for_point(
                    context=context, test_point=test_point,
                    project_id=project_id, case_type=case_type
                )
                # 持久化生成的用例
                case = await self._save_test_case(
                    project_id=project_id, generated_case=generated_case,
                    test_point=test_point, requirement_file_id=primary_requirement_file_id
                )
                created_cases.append(case)

                # 推送进度（10%-95%区间）
                progress = int(10 + (i + 1) / total * 85)
                yield {
                    "progress": progress, "message": f"已生成{i + 1}/{total}个测试用例",
                    "status": "running", "current": i + 1, "total": total,
                    "case": {
                        "id": case.id,
                        "title": ContentSanitizer.sanitize_for_log(case.title),
                        "module": case.module
                    }
                }
            except Exception as e:
                # 单个用例生成失败不影响整体流程
                failed_count += 1
                logger.error(f"生成测试用例失败: {e}")
                yield {
                    "progress": int(10 + (i + 1) / total * 85),
                    "message": f"生成第{i + 1}个用例失败: {str(e)}",
                    "status": "running", "error": True, "failed_count": failed_count
                }

        # 阶段3：汇总结果
        yield {
            "progress": 100,
            "message": f"完成！成功{len(created_cases)}个，失败{failed_count}个",
            "status": "success" if failed_count == 0 else "partial",
            "total": total, "created": len(created_cases), "failed": failed_count,
            "pagination": pagination,
            "cases": [{"id": c.id, "title": ContentSanitizer.sanitize_for_log(c.title)} for c in created_cases]
        }

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
