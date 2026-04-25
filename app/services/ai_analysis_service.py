"""AI分析服务 - 分析需求文档并提取结构化测试点。

本模块提供AI驱动的需求分析能力，通过DeepSeek AI分析项目需求文档，
自动提取结构化测试点。支持流式进度推送，便于前端实时展示分析状态。

核心类:
    - AIAnalysisService: AI分析服务，提供需求分析和测试点提取

核心函数:
    - extract_test_points_from_content: 从文本内容提取测试点的便捷函数
    - extract_test_points_from_ui_specs: 从UI原型屏幕提取测试点的便捷函数

依赖关系:
    - app.models.project: Project/ProjectFile ORM模型
    - app.models.ui_prototype: UIPrototypeScreen ORM模型
    - app.models.test_point: TestPoint ORM模型
    - app.crud.test_point: 测试点批量创建
    - app.utils.ai_client: AI客户端（DeepSeek API流式调用）
    - app.services.ai_analysis_utils: 工具函数模块
    - app.utils.ai_client_prompt: UI规格描述构建

分析流程:
    1. 校验项目权限
    2. 获取项目文件内容
    3. 构建分析Prompt
    4. 调用DeepSeek AI流式分析
    5. 解析AI响应提取测试点
    6. 批量持久化测试点

流式设计:
    analyze_project使用AsyncGenerator实现流式进度推送，
    前端可实时展示分析进度和中间状态。
"""
import json
from typing import List, Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session
from app.models.project import Project, ProjectFile
from app.models.ui_prototype import UIPrototypeScreen
from app.crud.test_point import batch_create_test_points
from app.utils.ai_client import ai_client
from app.services.ai_analysis_utils import (
    read_file_content,
    generate_analysis_prompt,
    parse_ai_response,
)
from app.utils.ai_client_prompt import build_ui_spec_description
from loguru import logger


class AIAnalysisService:
    """AI分析服务 - 分析需求文档并提取结构化测试点。

    职责:
        - 读取项目文件内容
        - 构建AI分析Prompt
        - 调用DeepSeek AI进行需求分析
        - 解析AI响应提取测试点
        - 批量创建测试点记录

    使用场景:
        - 项目需求分析页面触发分析
        - 从需求文档自动提取测试点
        - 增量分析新增需求文件

    设计意图:
        采用静态方法设计，服务不持有状态，数据库会话由调用方传入。
        流式分析结果通过AsyncGenerator推送，支持实时进度展示。
    """

    @staticmethod
    def get_project_files_content(db: Session, project_id: int) -> str:
        """获取项目下所有文件和URL的内容汇总。

        按文件来源区分处理:
            - file类型: 读取本地文件内容
            - URL类型: 记录URL和文件类型信息

        Args:
            db: 数据库会话。
            project_id: 项目ID。

        Returns:
            所有文件内容的汇总文本。
        """
        files = db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()
        content = []

        for file in files:
            if file.file_source == 'file':
                file_content = read_file_content(file.file_url)
                content.append(f"文件: {file.file_name}\n内容:\n{file_content}\n")
            else:
                content.append(f"URL: {file.file_url}\n类型: {file.file_type}\n")

        return '\n'.join(content)

    @staticmethod
    async def analyze_project(
        db: Session,
        project_id: int,
        user_id: int,
        username: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """分析项目需求并提取测试点，流式推送分析进度。

        分析流程:
            1. 校验项目权限（user_id匹配）
            2. 获取项目文件内容
            3. 调用DeepSeek AI流式分析
            4. 解析测试点数据
            5. 批量创建测试点记录

        Args:
            db: 数据库会话。
            project_id: 项目ID。
            user_id: 用户ID，用于权限校验。
            username: 用户名，用于记录测试点创建人。

        Yields:
            进度信息字典，包含:
                - progress: 进度百分比(0-100)
                - message: 进度描述
                - status: 状态(running/success/error)
        """
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()

        if not project:
            yield {"progress": 0, "message": "无权限操作此项目", "status": "error"}
            return

        yield {"progress": 10, "message": "开始分析项目需求", "status": "running"}

        try:
            content = AIAnalysisService.get_project_files_content(db, project_id)
            if not content:
                yield {"progress": 20, "message": "项目下无文件或URL", "status": "error"}
                return

            yield {"progress": 30, "message": "获取项目文件内容完成", "status": "running"}
            yield {"progress": 50, "message": "调用DeepSeek AI分析需求", "status": "running"}

            async for chunk in ai_client.analyze_requirements_stream(content):
                if "data" in chunk:
                    test_points_data = chunk.get("data", [])
                    if test_points_data:
                        parsed_test_points = parse_ai_response(test_points_data)
                        if parsed_test_points:
                            test_points = batch_create_test_points(
                                db=db,
                                project_id=project_id,
                                test_points_data=parsed_test_points,
                                created_by=username,
                            )
                            yield {"progress": 100, "message": f"分析完成，提取{len(test_points)}个测试点", "status": "success"}
                            return
                else:
                    progress = chunk.get("progress", 50)
                    message = chunk.get("message", "AI分析中...")
                    yield {"progress": progress, "message": message, "status": "running"}

            yield {"progress": 100, "message": "未提取到测试点", "status": "error"}

        except Exception as e:
            logger.error(f"分析项目失败: {e}")
            yield {"progress": 50, "message": f"分析失败: {str(e)}", "status": "error"}
            return


# 全局AI分析服务实例，便于直接使用
aio_analysis_service = AIAnalysisService()


async def extract_test_points_from_content(
    content: str,
    project_id: int,
    user_id: int
) -> List[Dict[str, Any]]:
    """从文本内容中提取测试点的便捷函数。

    不创建测试点记录，仅返回解析后的测试点数据列表。
    适用于需要预览测试点再决定是否保存的场景。

    Args:
        content: 需求文档文本内容。
        project_id: 项目ID。
        user_id: 用户ID。

    Returns:
        测试点数据列表，提取失败时返回空列表。
    """
    if not content:
        return []

    try:
        async for chunk in ai_client.analyze_requirements_stream(content):
            if "data" in chunk:
                test_points_data = chunk.get("data", [])
                if test_points_data:
                    return parse_ai_response(test_points_data)
        return []
    except Exception as e:
        logger.error(f"AI提取测试点失败: {e}")
        return []


def _build_ui_extract_content(screens: List[UIPrototypeScreen]) -> str:
    """将UI原型屏幕的ui_spec数据构建为AI可理解的文本内容。

    按"页面 x 可交互元素 x 流程边"三维组织内容，
    确保AI能从UI规格中提取全面的测试点。

    Args:
        screens: UI原型屏幕ORM对象列表。

    Returns:
        格式化后的UI规格文本，供AI分析。
    """
    sections: List[str] = []
    for screen in screens:
        ui_spec = screen.ui_spec
        if not ui_spec or not isinstance(ui_spec, dict):
            sections.append(
                f"页面：{screen.screen_name}\n状态：尚未完成AI解析，无ui_spec数据\n"
            )
            continue

        screen_desc = build_ui_spec_description(ui_spec, screen_name=screen.screen_name)
        sections.append(screen_desc)

        # 补充导航流程信息（navigation_flow 字段独立于 ui_spec）
        nav_flow = screen.navigation_flow
        if nav_flow and isinstance(nav_flow, dict):
            flows = nav_flow.get("flows", [])
            if flows:
                flow_lines: List[str] = []
                for flow in flows:
                    if isinstance(flow, dict):
                        from_page = flow.get("from", "")
                        to_page = flow.get("to", "")
                        trigger = flow.get("trigger", "")
                        flow_lines.append(f"  - {from_page} → {to_page}（触发：{trigger}）")
                    else:
                        flow_lines.append(f"  - {flow}")
                if flow_lines:
                    sections[-1] += f"\n\n页面跳转流程：\n" + "\n".join(flow_lines)

    return "\n\n".join(sections) if sections else ""


def _build_ui_extract_prompt(ui_content: str) -> str:
    """构建从UI原型提取测试点的专用Prompt。

    三维提取策略：
        - 页面维度：每个页面的功能、区域结构、布局约束
        - 可交互元素维度：按钮点击、输入框校验、链接跳转等交互操作
        - 流程边维度：页面间跳转、导航关系、入口/出口

    Args:
        ui_content: 格式化后的UI规格文本。

    Returns:
        完整的AI分析Prompt。
    """
    prompt = (
        "你是一名专业的UI测试工程师，请根据以下UI原型规格信息，提取结构化的测试点。\n\n"
        "## 提取策略（三维覆盖）\n"
        "1. **页面维度**：每个页面的核心功能验证、区域布局正确性、页面状态切换\n"
        "2. **可交互元素维度**：按钮点击响应、输入框校验规则、链接跳转、下拉选择等\n"
        "3. **流程边维度**：页面间跳转逻辑、导航路径、入口/出口验证\n\n"
        "## UI原型规格信息\n"
        f"{ui_content}\n\n"
        "## 输出要求\n"
        "请按照以下格式提取测试点：\n"
        "1. 按模块（页面）分组，每个模块下的测试点要逻辑清晰\n"
        "2. 每个测试点必须包含：\n"
        "   - module: 模块名称（通常为页面名称）\n"
        "   - function: 功能名称（交互元素或流程名称）\n"
        "   - point: 测试点描述（具体、可执行、可验证）\n"
        "   - priority: 优先级（1高/2中/3低）\n"
        "3. 测试点要求：\n"
        "   - 覆盖每个可交互元素的正常操作和异常操作\n"
        "   - 覆盖页面间跳转的正向流程和异常流程\n"
        "   - 覆盖布局约束和UI适配相关的验证点\n"
        "   - 输入框需覆盖：空值、边界值、非法字符、超长输入\n"
        "   - 按钮需覆盖：点击响应、禁用状态、重复点击\n\n"
        "请严格以JSON格式输出：\n[\n  {\n"
        '    "module": "页面名称",\n    "function": "交互元素/流程名称",\n'
        '    "point": "具体测试点描述",\n'
        '    "priority": 1\n  }\n]\n\n'
        "重要要求：只输出JSON，确保格式正确，测试点详细具体，优先级合理，"
        "覆盖所有可交互元素和流程边，至少输出5个测试点\n"
    )
    return prompt


async def extract_test_points_from_ui_specs(
    screen_ids: List[int],
    project_id: int,
    db: Session,
) -> List[Dict[str, Any]]:
    """从UI原型屏幕的ui_spec中提取测试点。

    遍历指定屏幕的ui_spec数据，按"页面 x 可交互元素 x 流程边"三维
    生成测试点建议。调用AI流式生成，复用现有SSE模板。

    Args:
        screen_ids: UI原型屏幕ID列表。
        project_id: 项目ID，用于权限校验和数据隔离。
        db: 数据库会话。

    Returns:
        测试点数据列表，提取失败时返回空列表。
    """
    if not screen_ids:
        return []

    try:
        # 查询指定屏幕，确保属于当前项目
        screens = (
            db.query(UIPrototypeScreen)
            .filter(
                UIPrototypeScreen.id.in_(screen_ids),
                UIPrototypeScreen.project_id == project_id,
            )
            .order_by(UIPrototypeScreen.screen_order)
            .all()
        )
        if not screens:
            logger.warning(f"未找到项目{project_id}下的指定UI屏幕: {screen_ids}")
            return []

        # 构建UI规格文本
        ui_content = _build_ui_extract_content(screens)
        if not ui_content:
            logger.warning(f"UI屏幕{screen_ids}无有效ui_spec数据")
            return []

        # 构建专用Prompt
        prompt = _build_ui_extract_prompt(ui_content)

        # 调用AI流式分析（复用analyze_requirements_stream，传入Prompt作为content）
        async for chunk in ai_client.analyze_requirements_stream(prompt):
            if "data" in chunk:
                test_points_data = chunk.get("data", [])
                if test_points_data:
                    return parse_ai_response(test_points_data)
        return []
    except Exception as e:
        logger.error(f"从UI原型提取测试点失败: {e}")
        return []
