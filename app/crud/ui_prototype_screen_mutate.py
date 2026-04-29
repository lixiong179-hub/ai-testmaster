"""
UI原型页面变更操作模块

提供UI原型页面（UIPrototypeScreen）的所有变更操作（创建/更新解析结果/更新解析状态/
更新审核/删除/关联用例/更新排序/批量创建），与 ui_prototype_screen.py 共同构成
UI原型页面的完整CRUD能力。本模块仅包含变更函数，不涉及查询操作。

核心函数概览：
    - create_ui_screen: 创建单个UI页面，初始解析状态为pending
    - update_ui_screen_parse_result: 更新页面解析结果（AI解析完成后调用）
    - update_ui_screen_parse_status: 更新页面解析状态（开始解析/解析失败时调用）
    - update_ui_screen_review: 更新页面审核状态（人工审核时调用）
    - delete_ui_screen: 删除UI页面（级联删除页面-用例关联链接）
    - link_ui_screen_to_test_case: 关联UI页面与测试用例（幂等操作）
    - update_ui_screen_order: 更新页面排序
    - batch_create_ui_screens: 批量创建UI页面（单次commit优化性能）

与Model/Schema的对应关系：
    - Model: app.models.ui_prototype.UIPrototypeScreen
    - Model: app.models.ui_prototype.UIScreenTestCaseLink（页面-用例关联表）

与其他CRUD模块的调用关系：
    - 页面解析完成后应调用 ui_prototype_project.update_prototype_project_stats 更新统计
    - 页面关联用例后，可通过 ui_prototype_screen.get_test_cases_by_screen 查询关联

事务处理方式：
    - 单条操作：自动commit
    - 批量操作：先逐条add到session，最后统一commit

批量操作性能考虑：
    - batch_create_ui_screens 采用"先add后统一commit"策略

软删除/硬删除：
    - delete_ui_screen 为硬删除，同时级联删除UIScreenTestCaseLink关联记录

解析状态枚举：
    - pending: 待解析
    - processing: 解析中
    - completed: 解析完成
    - failed: 解析失败

审核状态枚举：
    - pending: 待审核
    - approved: 审核通过
    - rejected: 审核拒绝
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.ui_prototype import (
    UIPrototypeScreen,
    UIScreenTestCaseLink,
)
from app.utils.db_time import utcnow


def create_ui_screen(
    db: Session,
    project_id: int,
    prototype_name: str,
    screen_name: str,
    original_file_path: Optional[str] = None,
    original_file_name: Optional[str] = None,
    file_type: str = "png",
    file_size: Optional[int] = None,
    screen_order: int = 0,
    created_by: Optional[int] = None,
    prototype_project_id: Optional[int] = None,
) -> UIPrototypeScreen:
    """
    创建单个UI页面

    创建一条UI原型页面记录，初始解析状态为pending。
    通常在导入墨刀原型时批量创建。

    Args:
        db: 数据库会话
        project_id: 所属项目ID
        prototype_name: 原型名称（墨刀项目名称）
        screen_name: 页面名称
        original_file_path: 原始文件路径（可选）
        original_file_name: 原始文件名称（可选）
        file_type: 文件类型，默认"png"
        file_size: 文件大小（字节，可选）
        screen_order: 页面排序序号，默认0
        created_by: 创建者用户ID（可选）
        prototype_project_id: 所属原型项目ID（可选）

    Returns:
        UIPrototypeScreen: 创建成功后的页面对象（已commit并refresh）
    """
    db_screen = UIPrototypeScreen(
        project_id=project_id,
        prototype_name=prototype_name,
        screen_name=screen_name,
        original_file_path=original_file_path,
        original_file_name=original_file_name,
        file_type=file_type,
        file_size=file_size,
        screen_order=screen_order,
        created_by=created_by,
        prototype_project_id=prototype_project_id,
        parse_status="pending",  # 初始解析状态：待解析
    )
    db.add(db_screen)
    db.commit()
    db.refresh(db_screen)
    return db_screen


def update_ui_screen_parse_result(
    db: Session,
    screen_id: int,
    ui_spec: Dict[str, Any],
    parse_model: str,
    summary: Optional[str] = None,
    element_count: int = 0,
    button_count: int = 0,
    input_count: int = 0,
    layout_checks: Optional[List[Dict]] = None,
    navigation_flow: Optional[Dict] = None,
    is_entry_point: bool = False,
    is_end_point: bool = False,
) -> Optional[UIPrototypeScreen]:
    """
    更新页面解析结果

    AI解析完成后调用此函数，将解析结果写入数据库。解析成功时自动将
    parse_status设为completed，并清空之前的错误信息。

    Args:
        db: 数据库会话
        screen_id: 页面ID
        ui_spec: UI规格描述，JSON格式，包含页面元素、布局等详细信息
        parse_model: 解析使用的AI模型名称，如"gpt-4o"、"claude-3"
        summary: 页面摘要（可选），AI生成的页面功能概述
        element_count: 页面元素总数
        button_count: 按钮元素数量
        input_count: 输入框元素数量
        layout_checks: 布局检查结果（可选），JSON列表格式
        navigation_flow: 导航流程（可选），页面间的跳转关系
        is_entry_point: 是否为入口页面（如登录页）
        is_end_point: 是否为终止页面（如支付成功页）

    Returns:
        Optional[UIPrototypeScreen]: 更新后的页面对象，不存在则返回None

    Note:
        解析成功时自动清空parse_error字段，确保错误信息不会残留。
    """
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return None
    screen.ui_spec = ui_spec
    screen.parse_status = "completed"  # 解析成功，更新状态为completed
    screen.parse_model = parse_model
    screen.parse_error = None  # 清空之前的错误信息
    screen.summary = summary
    screen.element_count = element_count
    screen.button_count = button_count
    screen.input_count = input_count
    screen.layout_checks = layout_checks
    screen.navigation_flow = navigation_flow
    screen.is_entry_point = is_entry_point
    screen.is_end_point = is_end_point
    screen.update_time = utcnow()
    db.commit()
    db.refresh(screen)
    return screen


def update_ui_screen_parse_status(
    db: Session,
    screen_id: int,
    status: str,
    error_message: Optional[str] = None,
) -> Optional[UIPrototypeScreen]:
    """
    更新页面解析状态

    在解析开始（processing）或解析失败（failed）时调用。
    解析成功应使用 update_ui_screen_parse_result 而非此函数。

    Args:
        db: 数据库会话
        screen_id: 页面ID
        status: 解析状态，processing/failed
        error_message: 错误信息（可选），解析失败时记录原因

    Returns:
        Optional[UIPrototypeScreen]: 更新后的页面对象，不存在则返回None

    Note:
        仅在error_message非空时更新parse_error字段，
        避免processing状态时误清空之前的错误信息。
    """
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return None
    screen.parse_status = status
    if error_message:
        screen.parse_error = error_message
    screen.update_time = utcnow()
    db.commit()
    db.refresh(screen)
    return screen


def update_ui_screen_review(
    db: Session,
    screen_id: int,
    review_status: str,
    reviewer: Optional[str] = None,
    review_comment: Optional[str] = None,
) -> Optional[UIPrototypeScreen]:
    """
    更新页面审核状态

    人工审核AI解析结果后调用，记录审核状态、审核人和审核意见。

    Args:
        db: 数据库会话
        screen_id: 页面ID
        review_status: 审核状态，approved/rejected/pending
        reviewer: 审核人标识（可选）
        review_comment: 审核意见（可选），拒绝时记录原因

    Returns:
        Optional[UIPrototypeScreen]: 更新后的页面对象，不存在则返回None
    """
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return None
    screen.review_status = review_status
    screen.reviewed_by = reviewer
    screen.reviewed_at = utcnow()  # 使用UTC时间记录审核时间
    screen.review_comment = review_comment
    screen.update_time = utcnow()
    db.commit()
    db.refresh(screen)
    return screen


def delete_ui_screen(db: Session, screen_id: int) -> bool:
    """
    删除UI页面（级联删除关联链接）

    物理删除页面记录，同时删除UIScreenTestCaseLink中所有关联记录。
    确保删除页面后不会留下孤立的页面-用例关联数据。

    Args:
        db: 数据库会话
        screen_id: 页面ID

    Returns:
        bool: 删除成功返回True，页面不存在返回False

    Note:
        级联删除顺序：先删除关联链接，再删除页面本身。
        这样可以避免外键约束导致的删除失败。
    """
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return False
    # 级联删除：先删除页面-用例关联链接，再删除页面本身
    db.query(UIScreenTestCaseLink).filter(
        UIScreenTestCaseLink.screen_id == screen_id
    ).delete()
    db.delete(screen)
    db.commit()
    return True


def link_ui_screen_to_test_case(
    db: Session, screen_id: int, test_case_id: int, link_type: str = "source"
) -> UIScreenTestCaseLink:
    """
    关联UI页面与测试用例（幂等操作）

    创建页面与测试用例的关联链接。若关联已存在，则更新link_type；
    若不存在，则创建新关联。此操作是幂等的，重复调用不会产生重复记录。

    Args:
        db: 数据库会话
        screen_id: 页面ID
        test_case_id: 测试用例ID
        link_type: 链接类型，默认"source"（用例来源于该页面），
            可选"verified"（用例已在该页面上验证）

    Returns:
        UIScreenTestCaseLink: 关联链接对象（已commit并refresh）

    Note:
        幂等性实现：先查询是否已存在相同screen_id+test_case_id的关联，
        存在则更新link_type，不存在则创建新关联。
    """
    # 幂等性检查：若关联已存在，更新link_type
    existing = db.query(UIScreenTestCaseLink).filter(
        UIScreenTestCaseLink.screen_id == screen_id,
        UIScreenTestCaseLink.test_case_id == test_case_id,
    ).first()
    if existing:
        existing.link_type = link_type
        db.commit()
        return existing
    # 关联不存在，创建新记录
    link = UIScreenTestCaseLink(
        screen_id=screen_id, test_case_id=test_case_id, link_type=link_type
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def update_ui_screen_order(
    db: Session, screen_id: int, screen_order: int
) -> Optional[UIPrototypeScreen]:
    """
    更新页面排序

    修改页面的排序序号，用于调整页面在原型中的展示顺序。

    Args:
        db: 数据库会话
        screen_id: 页面ID
        screen_order: 新的排序序号，数值越小越靠前

    Returns:
        Optional[UIPrototypeScreen]: 更新后的页面对象，不存在则返回None
    """
    screen = db.query(UIPrototypeScreen).filter(UIPrototypeScreen.id == screen_id).first()
    if not screen:
        return None
    screen.screen_order = screen_order
    screen.update_time = utcnow()
    db.commit()
    db.refresh(screen)
    return screen


def batch_create_ui_screens(
    db: Session,
    project_id: int,
    screens_data: List[Dict[str, Any]],
    created_by: Optional[int] = None,
    prototype_project_id: Optional[int] = None,
) -> List[UIPrototypeScreen]:
    """
    批量创建UI页面

    一次性创建多条UI页面记录，采用"先add后统一commit"策略优化性能。
    适用于导入墨刀原型时批量创建页面的场景。

    Args:
        db: 数据库会话
        project_id: 所属项目ID，所有页面归属同一项目
        screens_data: 页面数据列表，每条数据为字典格式，
            可选字段: prototype_name, screen_name, file_path, file_name,
                      file_type, file_size, screen_order, prototype_project_id
        created_by: 创建者用户ID（可选）
        prototype_project_id: 默认所属原型项目ID（可选），可被screens_data中的值覆盖

    Returns:
        List[UIPrototypeScreen]: 创建成功的页面列表

    Note:
        性能优化策略：
        1. 逐条db.add()将对象加入session，但不立即commit
        2. 所有对象add完成后，统一执行一次db.commit()
        3. commit后再逐条db.refresh()获取数据库生成的字段

        字段默认值策略：
        - prototype_name: 默认"未命名"
        - screen_name: 默认取file_name，再默认"屏幕"
        - file_type: 默认"png"
        - parse_status: 默认"pending"

    Warning:
        若screens_data中某条数据导致数据库约束异常，会在commit时抛出异常，
        导致整批创建失败并回滚。调用方应确保数据完整性。
    """
    screens = []
    for data in screens_data:
        screen = UIPrototypeScreen(
            project_id=project_id,
            prototype_name=data.get("prototype_name", "未命名"),
            # screen_name优先取screen_name，其次取file_name，最后默认"屏幕"
            screen_name=data.get("screen_name", data.get("file_name", "屏幕")),
            original_file_path=data.get("file_path"),
            original_file_name=data.get("file_name"),
            file_type=data.get("file_type", "png"),
            file_size=data.get("file_size"),
            screen_order=data.get("screen_order", 0),
            created_by=created_by,
            # prototype_project_id: 优先取screens_data中的值，其次取函数参数的值
            prototype_project_id=prototype_project_id or data.get("prototype_project_id"),
            parse_status="pending",  # 初始解析状态：待解析
        )
        db.add(screen)  # 加入session但不commit
        screens.append(screen)
    # 统一提交：将多次IO合并为一次事务提交，提升批量写入性能
    db.commit()
    # 逐条refresh获取数据库生成的字段（id、create_time等）
    for screen in screens:
        db.refresh(screen)
    return screens
