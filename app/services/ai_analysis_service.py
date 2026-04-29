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
    - app.core.config: 配置管理

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
import os
import re
import json
from typing import List, Dict, Any, Generator, AsyncGenerator
from sqlalchemy.orm import Session
from app.models.project import Project, ProjectFile
from app.models.test_point import TestPoint
from app.crud.test_point import batch_create_test_points
from app.utils.ai_client import ai_client
from app.core.config import settings
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
    def read_file_content(file_path: str) -> str:
        """读取本地文件内容。

        Args:
            file_path: 文件绝对路径。

        Returns:
            文件内容字符串，读取失败时返回错误信息。
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取文件失败: {file_path}, 错误: {e}")
            return f"文件读取失败: {str(e)}"

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
                # 本地文件：读取实际内容
                file_content = AIAnalysisService.read_file_content(file.file_url)
                content.append(f"文件: {file.file_name}\n内容:\n{file_content}\n")
            else:
                # URL链接：仅记录元信息
                content.append(f"URL: {file.file_url}\n类型: {file.file_type}\n")

        return '\n'.join(content)

    @staticmethod
    def generate_analysis_prompt(content: str) -> str:
        """生成AI需求分析的Prompt。

        Prompt结构:
            1. 角色设定（专业测试工程师）
            2. 项目需求内容
            3. 提取要求（按模块分组、包含优先级）
            4. 输出格式定义（JSON数组）

        Args:
            content: 项目文件内容汇总文本。

        Returns:
            完整的分析Prompt字符串。
        """
        prompt = (
            "你是一名专业的测试工程师，请根据以下项目需求内容，提取结构化的测试点。\n"
            "\n"
            "项目需求内容：\n"
            "{REQ_CONTENT_PLACEHOLDER}\n"
            "\n"
            "请按照以下格式提取测试点：\n"
            "1. 按模块分组\n"
            "2. 每个测试点包含：模块名称、功能名称、测试点描述、优先级（1高/2中/3低）\n"
            "3. 测试点必须具体、可执行\n"
            "4. 覆盖正常场景和异常场景\n"
            "\n"
            "输出格式必须为JSON，结构如下：\n"
            "[\n"
            "  {\n"
            '    "module": "模块名称",\n'
            '    "function": "功能名称",\n'
            '    "point": "测试点描述",\n'
            "    \"priority\": 1\n"
            "  }\n"
            "]\n"
            "\n"
            "请确保输出的JSON格式正确，并且测试点描述清晰、具体、可执行。"
        ).replace("{REQ_CONTENT_PLACEHOLDER}", content)
        return prompt

    @staticmethod
    def parse_ai_response(test_points_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """解析AI响应，提取并标准化测试点数据。

        标准化处理:
            - 缺失字段填充默认值
            - 保留原始AI响应作为ai_prompt字段
            - 过滤掉无测试点描述的条目

        Args:
            test_points_data: AI返回的测试点数据列表。

        Returns:
            标准化后的测试点数据列表。
        """
        test_points = []

        try:
            for point_data in test_points_data:
                test_point = {
                    'module': point_data.get('module', '未命名模块'),
                    'function': point_data.get('function', '未命名功能'),
                    'point': point_data.get('point', ''),
                    'priority': point_data.get('priority', 2),
                    'ai_prompt': json.dumps(point_data)  # 保留原始AI响应
                }
                # 过滤掉无测试点描述的条目
                if test_point['point']:
                    test_points.append(test_point)
        except Exception as e:
            logger.error(f"解析AI响应失败: {e}")

        return test_points

    @staticmethod
    async def analyze_project(
        db: Session,
        project_id: int,
        user_id: int
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

        Yields:
            进度信息字典，包含:
                - progress: 进度百分比(0-100)
                - message: 进度描述
                - status: 状态(running/success/error)
        """
        # 校验项目权限
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == user_id
        ).first()

        if not project:
            yield {"progress": 0, "message": "无权限操作此项目", "status": "error"}
            return

        yield {"progress": 10, "message": "开始分析项目需求", "status": "running"}

        try:
            # 获取项目文件内容
            content = AIAnalysisService.get_project_files_content(db, project_id)
            if not content:
                yield {"progress": 20, "message": "项目下无文件或URL", "status": "error"}
                return

            yield {"progress": 30, "message": "获取项目文件内容完成", "status": "running"}

            # 调用AI分析
            yield {"progress": 50, "message": "调用DeepSeek AI分析需求", "status": "running"}

            # 使用流式调用，实时推送分析进度
            async for chunk in ai_client.analyze_requirements_stream(content):
                if "data" in chunk:
                    # 分析完成，获取测试点数据
                    test_points_data = chunk.get("data", [])
                    if test_points_data:
                        parsed_test_points = AIAnalysisService.parse_ai_response(test_points_data)
                        if parsed_test_points:
                            # 批量创建测试点
                            test_points = batch_create_test_points(db, project_id, parsed_test_points)
                            yield {"progress": 100, "message": f"分析完成，提取{len(test_points)}个测试点", "status": "success"}
                            return
                else:
                    # 实时进度推送
                    progress = chunk.get("progress", 50)
                    message = chunk.get("message", "AI分析中...")
                    yield {"progress": progress, "message": message, "status": "running"}

            # 分析完成但无数据
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

    prompt = AIAnalysisService.generate_analysis_prompt(content)

    try:
        # 使用AI流式分析，获取最终测试点数据
        async for chunk in ai_client.analyze_requirements_stream(content):
            if "data" in chunk:
                test_points_data = chunk.get("data", [])
                if test_points_data:
                    return AIAnalysisService.parse_ai_response(test_points_data)

        return []
    except Exception as e:
        logger.error(f"AI提取测试点失败: {e}")
        return []
