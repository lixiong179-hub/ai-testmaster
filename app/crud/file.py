"""
文件CRUD操作模块

提供项目文件（ProjectFile）的增删改查数据库操作。项目文件管理需求文档、
设计文档等上传资源，支持文件提取状态跟踪、资源类型分类、迭代关联等。

核心函数概览：
    - create_project_file: 创建文件记录，初始提取状态为pending
    - update_file_content: 更新文件提取内容和状态（提取完成后调用）
    - update_file_resource_type: 更新文件资源类型
    - get_project_files: 获取项目文件列表（支持活跃状态/迭代过滤，按上传时间倒序）
    - get_project_files_by_type: 根据资源类型获取项目文件
    - get_file_by_id: 根据ID获取文件（带项目ID过滤）
    - delete_file: 删除文件（支持软删除/硬删除）
    - permanent_delete_file: 物理删除文件（硬删除的快捷方式）
    - get_project_files_by_iteration: 根据迭代ID获取项目文件

与Model/Schema的对应关系：
    - Model: app.models.project.ProjectFile

与其他CRUD模块的调用关系：
    - 文件是测试用例生成的输入源，提取后的content供AI分析
    - 文件可关联迭代（iteration_id），实现按迭代管理文件

事务处理方式：
    - 所有写操作均自动commit

软删除/硬删除：
    - delete_file 默认为软删除（is_active=False），支持permanent参数切换为硬删除
    - permanent_delete_file 是硬删除的快捷方式

提取状态枚举：
    - pending: 待提取
    - processing: 提取中
    - completed: 提取完成
    - failed: 提取失败

资源类型枚举：
    - requirement: 需求文档
    - design: 设计文档
    - api_doc: API文档
    - other: 其他
"""
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.project import ProjectFile
from typing import List, Optional
from app.utils.db_time import utcnow


def create_project_file(db: Session, project_id: int, file_name: str, file_type: str,
                       file_url: str, file_source: str = "file", size: Optional[int] = None,
                       resource_type: str = "other", description: str = None,
                       iteration_id: Optional[int] = None) -> ProjectFile:
    """
    创建项目文件记录

    上传文件后创建数据库记录，初始提取状态为pending。
    文件内容提取为异步流程，由后台任务调用 update_file_content 更新。

    Args:
        db: 数据库会话
        project_id: 所属项目ID
        file_name: 文件名称
        file_type: 文件类型，如pdf/docx/xlsx/png等
        file_url: 文件存储路径或URL
        file_source: 文件来源，默认"file"，也可为"url"等
        size: 文件大小（字节），可选
        resource_type: 资源类型，默认"other"，可选requirement/design/api_doc
        description: 文件描述，可选
        iteration_id: 关联迭代ID，可选，用于按迭代管理文件

    Returns:
        ProjectFile: 创建成功后的文件对象（已commit并refresh）
    """
    db_file = ProjectFile(
        project_id=project_id,
        file_name=file_name,
        file_type=file_type,
        file_url=file_url,
        file_source=file_source,
        size=size,
        resource_type=resource_type,
        description=description,
        extract_status="pending",  # 初始提取状态：待提取
        is_active=True,  # 默认为活跃状态，软删除时设为False
        iteration_id=iteration_id
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file


def update_file_content(db: Session, file_id: int, content: str, extract_status: str,
                        extract_error: str = None) -> Optional[ProjectFile]:
    """
    更新文件提取内容和状态

    文件内容提取完成后调用此函数更新提取结果。提取成功时记录内容，
    提取失败时记录错误信息。

    Args:
        db: 数据库会话
        file_id: 文件ID
        content: 提取的文本内容
        extract_status: 提取状态，completed/failed
        extract_error: 提取错误信息（可选），失败时记录原因

    Returns:
        Optional[ProjectFile]: 更新后的文件对象，不存在则返回None

    Note:
        使用 utcnow() 记录提取完成时间，确保多时区环境下时间一致性。
    """
    db_file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not db_file:
        return None
    db_file.content = content
    db_file.extract_status = extract_status
    db_file.extract_error = extract_error
    db_file.extracted_at = utcnow()  # 使用UTC时间，避免时区问题
    db.commit()
    db.refresh(db_file)
    return db_file


def update_file_resource_type(db: Session, file_id: int, project_id: int,
                               resource_type: str) -> Optional[ProjectFile]:
    """
    更新文件资源类型

    修改文件的资源类型分类，带项目ID过滤确保数据隔离。

    Args:
        db: 数据库会话
        file_id: 文件ID
        project_id: 项目ID，用于权限校验
        resource_type: 新的资源类型，如requirement/design/api_doc/other

    Returns:
        Optional[ProjectFile]: 更新后的文件对象，不存在则返回None
    """
    db_file = db.query(ProjectFile).filter(
        ProjectFile.id == file_id,
        ProjectFile.project_id == project_id
    ).first()
    if not db_file:
        return None
    db_file.resource_type = resource_type
    db.commit()
    db.refresh(db_file)
    return db_file


def get_project_files(db: Session, project_id: int, is_active: bool = True,
                      iteration_id: Optional[int] = None) -> List[ProjectFile]:
    """
    获取项目文件列表（支持活跃状态/迭代过滤，按上传时间倒序）

    按上传时间倒序排列，最新上传的文件排在前面。
    支持按活跃状态和迭代ID过滤。

    Args:
        db: 数据库会话
        project_id: 项目ID
        is_active: 是否只查询活跃文件，默认True（排除已软删除的文件）
        iteration_id: 迭代ID（可选），None表示查询未关联迭代的文件，
                      正整数表示按迭代ID精确匹配，不传此参数则不过滤迭代

    Returns:
        List[ProjectFile]: 文件列表，按上传时间倒序

    Note:
        iteration_id 参数语义变更（原 -1 哨兵值已废弃）：
        - 不传 iteration_id：不过滤迭代，返回所有文件
        - iteration_id=None（显式传入None）：查询 iteration_id IS NULL 的文件（未关联迭代）
        - iteration_id=正整数：按迭代ID精确匹配
    """
    query = db.query(ProjectFile).filter(ProjectFile.project_id == project_id)
    if is_active is not None:
        query = query.filter(ProjectFile.is_active == is_active)
    # 迭代过滤：None表示未关联迭代的文件，正整数按迭代ID精确匹配
    if iteration_id is not None:
        if iteration_id <= 0:
            # 兼容旧调用：<=0 的值统一视为"未关联迭代"，查询 IS NULL
            query = query.filter(ProjectFile.iteration_id.is_(None))
        else:
            query = query.filter(ProjectFile.iteration_id == iteration_id)
    return query.order_by(ProjectFile.upload_time.desc()).all()


def get_project_files_by_type(db: Session, project_id: int, resource_type: str) -> List[ProjectFile]:
    """
    根据资源类型获取项目文件

    查询指定资源类型的活跃文件，按上传时间倒序排列。
    常用于获取某类文档（如所有需求文档）供AI分析。

    Args:
        db: 数据库会话
        project_id: 项目ID
        resource_type: 资源类型，如requirement/design/api_doc/other

    Returns:
        List[ProjectFile]: 符合类型的活跃文件列表
    """
    return db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.resource_type == resource_type,
        ProjectFile.is_active == True  # 仅查询活跃文件，排除已软删除的
    ).order_by(ProjectFile.upload_time.desc()).all()


def get_file_by_id(db: Session, file_id: int, project_id: int) -> Optional[ProjectFile]:
    """
    根据ID获取文件，带项目ID过滤

    通过文件ID和项目ID联合过滤，确保在项目维度下定位唯一文件。

    Args:
        db: 数据库会话
        file_id: 文件ID
        project_id: 项目ID，用于项目维度隔离

    Returns:
        Optional[ProjectFile]: 文件对象，不存在则返回None
    """
    return db.query(ProjectFile).filter(
        ProjectFile.id == file_id,
        ProjectFile.project_id == project_id
    ).first()


def delete_file(db: Session, file_id: int, project_id: int, permanent: bool = False) -> bool:
    """
    删除文件，带项目ID过滤

    默认为软删除（is_active=False），文件记录仍保留在数据库中。
    可通过permanent参数切换为硬删除，物理移除数据库记录。

    Args:
        db: 数据库会话
        file_id: 文件ID
        project_id: 项目ID，用于权限校验
        permanent: 是否物理删除，默认False（软删除）

    Returns:
        bool: 删除成功返回True，文件不存在返回False

    Note:
        软删除仅将is_active设为False，文件记录仍保留在数据库中，
        可通过查询is_active=True过滤掉已删除的文件。
    """
    db_file = get_file_by_id(db, file_id, project_id)
    if not db_file:
        return False

    if permanent:
        db.delete(db_file)  # 硬删除：物理移除数据库记录
    else:
        db_file.is_active = False  # 软删除：标记为不活跃，记录仍保留
    db.commit()
    return True


def permanent_delete_file(db: Session, file_id: int, project_id: int) -> bool:
    """
    物理删除文件（硬删除的快捷方式）

    等同于 delete_file(permanent=True)，提供更明确的语义。

    Args:
        db: 数据库会话
        file_id: 文件ID
        project_id: 项目ID，用于权限校验

    Returns:
        bool: 删除成功返回True，文件不存在返回False
    """
    return delete_file(db, file_id, project_id, permanent=True)


def get_project_files_by_iteration(db: Session, project_id: int,
                                    iteration_id: int) -> List[ProjectFile]:
    """
    根据迭代ID获取项目文件

    查询指定迭代关联的所有文件，按上传时间倒序排列。
    不区分活跃状态，包含已软删除的文件。

    Args:
        db: 数据库会话
        project_id: 项目ID
        iteration_id: 迭代ID

    Returns:
        List[ProjectFile]: 关联该迭代的文件列表

    Note:
        此查询未过滤is_active，会包含已软删除的文件。
        如需仅查询活跃文件，应在调用方或此函数中增加过滤条件。
    """
    return db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.iteration_id == iteration_id
    ).order_by(ProjectFile.upload_time.desc()).all()


async def update_file_content_async(
    db: AsyncSession,
    file_id: int,
    content: str,
    extract_status: str,
    extract_error: str = None
) -> Optional[ProjectFile]:
    """
    更新文件提取内容和状态（异步版本）

    update_file_content 的异步实现，文件内容提取完成后调用此函数更新提取结果。

    Args:
        db: 异步数据库会话
        file_id: 文件ID
        content: 提取的文本内容
        extract_status: 提取状态，completed/failed
        extract_error: 提取错误信息（可选），失败时记录原因

    Returns:
        Optional[ProjectFile]: 更新后的文件对象，不存在则返回None
    """
    result = await db.execute(
        select(ProjectFile).where(ProjectFile.id == file_id)
    )
    db_file = result.scalars().first()
    if not db_file:
        return None
    db_file.content = content
    db_file.extract_status = extract_status
    db_file.extract_error = extract_error
    db_file.extracted_at = utcnow()
    await db.commit()
    await db.refresh(db_file)
    return db_file
