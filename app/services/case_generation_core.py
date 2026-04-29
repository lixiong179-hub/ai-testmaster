"""用例生成核心Mixin - 上下文构建与内容安全处理。

本模块提供用例生成的核心基础设施，包括上下文数据聚合、内容安全
清洗和常量定义。作为CoreMixin被TestCaseGenerationService组合使用。

核心类:
    - ContentSanitizer: 内容安全清洗工具，防止Prompt注入攻击
    - CoreMixin: 上下文构建Mixin，聚合需求/UI/测试点数据

常量定义:
    - DEFAULT_TEST_POINT_PAGE_SIZE: 测试点默认分页大小(100)
    - MAX_TEST_POINT_PAGE_SIZE: 测试点最大分页大小(500)
    - TEST_CATEGORY_UI_AUTO: UI自动化测试分类标识
    - TEST_CATEGORY_MANUAL: 手工测试分类标识
    - TEST_CATEGORY_API_AUTO: API自动化测试分类标识

依赖关系:
    - app.models.test_point: TestPoint ORM模型
    - app.models.project: ProjectFile ORM模型
    - app.models.ui_prototype: UIPrototypeScreen ORM模型
    - app.crud.test_point: 测试点CRUD操作
    - app.crud.file: 文件CRUD操作
    - app.services.file_content_extractor: 文件内容提取

上下文构建流程:
    1. 加载需求文档内容（指定文件ID或项目全部需求文件）
    2. 加载UI原型数据（指定屏幕ID或文件ID或项目全部UI数据）
    3. 加载测试点数据（指定ID或分页查询）
    4. 返回聚合后的上下文字典
"""
import json
import re
import html
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger

from app.models.test_point import TestPoint
from app.models.project import ProjectFile
from app.models.ui_prototype import UIPrototypeScreen
from app.crud import test_point as test_point_crud
from app.crud import file as file_crud
from app.services.file_content_extractor import get_file_content

# 测试点分页默认值与上限
DEFAULT_TEST_POINT_PAGE_SIZE = 100
MAX_TEST_POINT_PAGE_SIZE = 500

# 用例分类常量，用于标识用例的执行方式
TEST_CATEGORY_UI_AUTO = "ui_automation"
TEST_CATEGORY_MANUAL = "manual"
TEST_CATEGORY_API_AUTO = "api_automation"


class ContentSanitizer:
    """内容安全清洗工具 - 防止Prompt注入攻击与内容截断。

    职责:
        - 过滤AI Prompt注入模式（system指令、模板注入等）
        - 移除Markdown代码块标记和HTML标签
        - 对内容进行HTML转义
        - 截断过长内容防止Token溢出
        - 日志友好的内容摘要

    安全设计:
        采用多层过滤策略：
        1. 移除代码块标记（防止AI误解析为指令）
        2. 移除HTML标签（防止XSS注入到Prompt）
        3. HTML转义特殊字符
        4. 正则匹配已知注入模式并替换为[已过滤]
        5. 长度截断并标注原始长度

    使用场景:
        - 清洗用户输入的需求文档内容
        - 清洗UI描述文本
        - 生成日志友好的内容摘要
    """

    # 已知的Prompt注入模式列表
    INJECTION_PATTERNS = [
        r'```system', r'```prompt', r'忽略.*指令', r'忽略.*规则',
        r'你是一个.*而不是', r'你现在是', r'/system', r'<system>', r'{{.*}}',
    ]

    @classmethod
    def sanitize(cls, content: str, max_length: int = 10000) -> str:
        """清洗内容，防止Prompt注入并截断过长文本。

        清洗流程:
            1. 移除代码块标记（json/yaml/xml/markdown/prompt/system）
            2. 移除剩余代码块标记
            3. 移除HTML标签
            4. HTML转义特殊字符
            5. 过滤已知注入模式
            6. 截断过长内容

        Args:
            content: 待清洗的原始内容。
            max_length: 最大允许长度，默认10000字符。

        Returns:
            清洗后的安全内容字符串。
        """
        if not content:
            return ""
        # 移除代码块标记，防止AI误解析为指令
        content = re.sub(r'```(?:json|yaml|xml|markdown|prompt|system)', '', content, flags=re.IGNORECASE)
        content = re.sub(r'```', '', content)
        # 移除HTML标签，防止XSS注入
        content = re.sub(r'<[^>]+>', '', content)
        # HTML转义特殊字符
        content = html.escape(content)
        # 过滤已知的Prompt注入模式
        for pattern in cls.INJECTION_PATTERNS:
            content = re.sub(pattern, '[已过滤]', content, flags=re.IGNORECASE)
        # 截断过长内容，防止Token溢出
        if len(content) > max_length:
            content = content[:max_length] + f"\n\n[内容已截断，原长度: {len(content)}字符]"
        return content

    @classmethod
    def sanitize_for_log(cls, content: str, max_length: int = 200) -> str:
        """生成日志友好的内容摘要，压缩空白并截断。

        Args:
            content: 原始内容。
            max_length: 摘要最大长度，默认200字符。

        Returns:
            压缩空白后的截断内容。
        """
        if not content:
            return ""
        # 压缩换行和制表符为空格，适合单行日志输出
        content = re.sub(r'[\n\r\t]+', ' ', content)
        if len(content) > max_length:
            return content[:max_length] + "..."
        return content


class CoreMixin:
    """用例生成核心Mixin - 聚合需求文档、UI原型和测试点数据。

    职责:
        - 构建用例生成所需的完整上下文
        - 加载需求文档内容（支持指定文件和全量加载）
        - 加载UI原型数据（屏幕描述和UI规格）
        - 加载测试点数据（支持指定ID和分页查询）
        - 文件内容提取与缓存

    设计意图:
        将上下文构建逻辑从生成流程中抽离，便于:
        1. 上下文数据可被多个生成步骤复用
        2. 独立测试上下文构建逻辑
        3. 支持增量刷新(force_refresh)

    使用场景:
        被TestCaseGenerationService通过多继承组合，
        在生成流程开始前调用get_context_for_generation构建上下文。
    """

    def __init__(self, db: Session) -> None:
        """初始化核心Mixin。

        Args:
            db: 数据库会话，贯穿用例生成生命周期。
        """
        self.db = db

    async def get_context_for_generation(
        self,
        project_id: int,
        user_id: int,
        requirement_file_ids: Optional[List[int]] = None,
        ui_file_ids: Optional[List[int]] = None,
        ui_screen_ids: Optional[List[int]] = None,
        test_point_ids: Optional[List[int]] = None,
        force_refresh: bool = False,
        test_point_page: int = 1,
        test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
    ) -> Dict[str, Any]:
        """构建用例生成所需的完整上下文数据。

        上下文聚合策略（按优先级）:
            需求文档:
                1. 指定requirement_file_ids -> 加载指定文件
                2. 未指定 -> 加载项目全部需求文件
            UI原型:
                1. 指定ui_screen_ids -> 加载指定屏幕（含UI规格）
                2. 指定ui_file_ids -> 加载指定文件及关联屏幕
                3. 均未指定 -> 加载项目全部已解析UI屏幕
            测试点:
                1. 指定test_point_ids -> 加载指定测试点
                2. 未指定 -> 分页查询项目测试点

        Args:
            project_id: 项目ID。
            user_id: 用户ID。
            requirement_file_ids: 需求文件ID列表，可选。
            ui_file_ids: UI文件ID列表，可选。
            ui_screen_ids: UI屏幕ID列表，可选。
            test_point_ids: 测试点ID列表，可选。
            force_refresh: 是否强制刷新文件内容，默认False。
            test_point_page: 测试点分页页码，默认1。
            test_point_page_size: 测试点分页大小，默认100。

        Returns:
            上下文字典，包含:
                - requirement_content: 需求文档内容
                - ui_descriptions: UI描述列表
                - ui_specs: UI规格列表
                - test_points: 测试点列表
                - files_used: 使用的文件ID列表
                - warnings: 警告信息列表
                - cache_info: 缓存信息
                - pagination: 分页信息（仅分页查询时）
        """
        context = {
            "requirement_content": "", "ui_descriptions": [], "ui_specs": [],
            "test_points": [], "files_used": [], "warnings": [], "cache_info": {}
        }

        # === 加载需求文档内容 ===
        if requirement_file_ids:
            # 优先加载指定需求文件
            for file_id in requirement_file_ids:
                file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
                if file_record and file_record.resource_type == "requirement":
                    content = file_record.content or ""
                    if force_refresh or not content:
                        # 强制刷新或内容为空时重新提取
                        content = await get_file_content(file_id)
                    if content:
                        context["requirement_content"] += f"\n\n【{file_record.file_name}】\n{content}"
                        context["files_used"].append(file_id)

        # 未指定需求文件时，加载项目全部需求文件
        if not context["requirement_content"]:
            all_req_files = file_crud.get_project_files_by_type(self.db, project_id, "requirement")
            for file_record in all_req_files:
                content = file_record.content or ""
                if force_refresh or not content:
                    content = await get_file_content(file_record.id)
                if content:
                    context["requirement_content"] += f"\n\n【{file_record.file_name}】\n{content}"
                    context["files_used"].append(file_record.id)

        # === 加载UI原型数据 ===
        if ui_screen_ids:
            # 优先加载指定UI屏幕
            for screen_id in ui_screen_ids:
                screen = self.db.query(UIPrototypeScreen).filter(
                    UIPrototypeScreen.id == screen_id,
                    UIPrototypeScreen.project_id == project_id
                ).first()
                if screen:
                    ui_desc = {
                        "screen_id": screen.id, "screen_name": screen.screen_name,
                        "prototype_name": screen.prototype_name, "parse_status": screen.parse_status,
                        "summary": screen.summary or "", "element_count": screen.element_count or 0,
                        "button_count": screen.button_count or 0, "input_count": screen.input_count or 0,
                        "description": screen.summary or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    # 关联UI规格数据
                    if screen.ui_spec:
                        context["ui_specs"].append({
                            "screen_id": screen.id, "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })
        elif ui_file_ids:
            # 加载指定UI文件及关联的已解析屏幕
            for file_id in ui_file_ids:
                file_record = file_crud.get_file_by_id(self.db, file_id, project_id)
                if file_record and file_record.resource_type == "ui_mockup":
                    ui_desc = {
                        "file_name": file_record.file_name, "file_url": file_record.file_url,
                        "description": file_record.description or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    context["files_used"].append(file_id)
                    # 查找与文件名关联的已解析屏幕
                    linked_screens = self.db.query(UIPrototypeScreen).filter(
                        UIPrototypeScreen.project_id == project_id,
                        UIPrototypeScreen.prototype_name == file_record.file_name,
                        UIPrototypeScreen.parse_status == "completed",
                        UIPrototypeScreen.ui_spec.isnot(None)
                    ).all()
                    for screen in linked_screens:
                        context["ui_specs"].append({
                            "screen_id": screen.id, "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })

        # 未指定UI数据时，加载项目全部已解析UI屏幕
        if not context["ui_descriptions"] and not context["ui_specs"]:
            screens_with_spec = self.db.query(UIPrototypeScreen).filter(
                UIPrototypeScreen.project_id == project_id,
                UIPrototypeScreen.parse_status == "completed",
                UIPrototypeScreen.ui_spec.isnot(None)
            ).order_by(UIPrototypeScreen.screen_order).all()
            if screens_with_spec:
                for screen in screens_with_spec:
                    ui_desc = {
                        "screen_id": screen.id, "screen_name": screen.screen_name,
                        "prototype_name": screen.prototype_name, "parse_status": screen.parse_status,
                        "summary": screen.summary or "", "element_count": screen.element_count or 0,
                        "button_count": screen.button_count or 0, "input_count": screen.input_count or 0,
                        "description": screen.summary or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    if screen.ui_spec:
                        context["ui_specs"].append({
                            "screen_id": screen.id, "screen_name": screen.screen_name,
                            "ui_spec": screen.ui_spec
                        })
            else:
                # 无已解析屏幕时，回退到UI文件列表
                all_ui_files = file_crud.get_project_files_by_type(self.db, project_id, "ui_mockup")
                for file_record in all_ui_files:
                    ui_desc = {
                        "file_name": file_record.file_name, "file_url": file_record.file_url,
                        "description": file_record.description or ""
                    }
                    context["ui_descriptions"].append(ui_desc)
                    context["files_used"].append(file_record.id)

        # === 加载测试点数据 ===
        if test_point_ids:
            # 加载指定测试点
            for point_id in test_point_ids:
                point = test_point_crud.get_test_point_by_id(self.db, point_id, project_id)
                if point:
                    context["test_points"].append({
                        "id": point.id, "module": point.module,
                        "function": point.function, "point": point.point, "priority": point.priority
                    })
        else:
            # 分页查询项目测试点，按优先级排序
            total_count = self.db.query(TestPoint).filter(
                TestPoint.project_id == project_id
            ).count()
            skip = (test_point_page - 1) * test_point_page_size
            all_points = self.db.query(TestPoint).filter(
                TestPoint.project_id == project_id
            ).order_by(TestPoint.priority.asc(), TestPoint.id.asc()).offset(skip).limit(
                min(test_point_page_size, MAX_TEST_POINT_PAGE_SIZE)
            ).all()
            for point in all_points:
                context["test_points"].append({
                    "id": point.id, "module": point.module,
                    "function": point.function, "point": point.point, "priority": point.priority
                })
            context["pagination"] = {
                "page": test_point_page, "page_size": len(all_points),
                "total": total_count, "has_more": (test_point_page * test_point_page_size) < total_count
            }
        return context

    async def _get_file_content(self, file: ProjectFile, force_refresh: bool = False) -> Optional[str]:
        """获取文件内容，支持缓存和强制刷新。

        获取策略:
            1. 文件已提取完成且不强制刷新 -> 直接返回缓存内容
            2. 内容为空或提取状态为pending/failed -> 重新提取
            3. 提取失败 -> 返回现有内容（可能为空）

        Args:
            file: ProjectFile ORM实例。
            force_refresh: 是否强制刷新，默认False。

        Returns:
            文件内容字符串，获取失败时返回None。
        """
        # 优先使用已缓存的内容
        if file.content and file.extract_status == 'completed' and not force_refresh:
            return file.content
        # 内容为空或提取状态异常时重新提取
        if not file.content or file.extract_status in ['pending', 'failed']:
            from app.services.file_content_extractor import FileContentExtractor
            extractor = FileContentExtractor(self.db)
            result = await extractor.extract_file_content(file, force_refresh)
            if result.get("success"):
                return result.get("content")
        return file.content


async def get_test_case_context(
    db: Session,
    project_id: int,
    user_id: int,
    requirement_file_ids: Optional[List[int]] = None,
    ui_file_ids: Optional[List[int]] = None,
    ui_screen_ids: Optional[List[int]] = None,
    test_point_ids: Optional[List[int]] = None,
    test_point_page: int = 1,
    test_point_page_size: int = DEFAULT_TEST_POINT_PAGE_SIZE
) -> Dict[str, Any]:
    """便捷函数 - 获取用例生成上下文，无需手动创建服务实例。

    内部创建TestCaseGenerationService实例并调用get_context_for_generation，
    适用于只需获取上下文而不执行生成的场景。

    Args:
        db: 数据库会话。
        project_id: 项目ID。
        user_id: 用户ID。
        requirement_file_ids: 需求文件ID列表，可选。
        ui_file_ids: UI文件ID列表，可选。
        ui_screen_ids: UI屏幕ID列表，可选。
        test_point_ids: 测试点ID列表，可选。
        test_point_page: 测试点分页页码，默认1。
        test_point_page_size: 测试点分页大小，默认100。

    Returns:
        上下文字典，结构同CoreMixin.get_context_for_generation。
    """
    from app.services.test_case_generation_service import TestCaseGenerationService
    service = TestCaseGenerationService(db)
    return await service.get_context_for_generation(
        project_id=project_id, user_id=user_id,
        requirement_file_ids=requirement_file_ids, ui_file_ids=ui_file_ids,
        ui_screen_ids=ui_screen_ids, test_point_ids=test_point_ids,
        test_point_page=test_point_page, test_point_page_size=test_point_page_size
    )
