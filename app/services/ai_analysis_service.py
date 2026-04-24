"""AI分析服务 - 分析需求文档并提取结构化测试点。

本模块提供AI驱动的需求分析能力，通过DeepSeek AI分析项目需求文档，
自动提取结构化测试点。支持流式进度推送，便于前端实时展示分析状态。

核心类:
    - AIAnalysisService: AI分析服务，提供需求分析和测试点提取

核心函数:
    - extract_test_points_from_content: 从文本内容提取测试点的便捷函数

依赖关系:
    - app.models.project: Project/ProjectFile ORM模型
    - app.models.test_point: TestPoint ORM模型
    - app.crud.test_point: 测试点批量创建
    - app.utils.ai_client: AI客户端（DeepSeek API流式调用）
    - app.services.ai_analysis_utils: 工具函数模块

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
from typing import List, Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session
from app.models.project import Project, ProjectFile
from app.crud.test_point import batch_create_test_points
from app.utils.ai_client import ai_client
from app.services.ai_analysis_utils import (
    read_file_content,
    generate_analysis_prompt,
    parse_ai_response,
)
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
