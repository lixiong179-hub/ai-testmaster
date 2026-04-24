"""
测试点CRUD操作模块

提供测试点（TestPoint）的增删改查数据库操作。测试点是测试用例生成的前置输入，
描述系统中需要测试的功能点，AI根据测试点自动生成对应的测试用例。

核心函数概览：
    - create_test_point: 创建单个测试点
    - get_test_point_by_id: 根据ID获取测试点（带项目隔离）
    - get_test_points_by_project: 获取项目的测试点列表（支持模块/优先级过滤+分页）
    - get_test_points_by_project_and_user: 获取用户项目测试点列表（JOIN Project权限隔离）
    - update_test_point: 更新测试点（按kwargs动态更新）
    - delete_test_point: 删除测试点（硬删除）
    - get_test_points_count: 获取测试点数量（用于分页计算）
    - batch_create_test_points: 批量创建测试点（单次commit优化性能）

与Model/Schema的对应关系：
    - Model: app.models.test_point.TestPoint
    - 关联Model: app.models.project.Project（JOIN查询用于用户权限过滤）

与其他CRUD模块的调用关系：
    - 测试点是 test_case_mutate.batch_create_test_cases 的上游输入
    - AI生成流程：测试点 -> AI分析 -> 测试用例

事务处理方式：
    - 所有写操作均自动commit
    - 批量操作采用"先add后统一commit"策略

软删除/硬删除：
    - delete_test_point 为硬删除，物理移除数据库记录
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.test_point import TestPoint
from app.models.project import Project


def create_test_point(
    db: Session,
    project_id: int,
    module: str,
    function: str,
    point: str,
    priority: int,
    ai_prompt: Optional[str] = None,
    created_by: Optional[str] = None,
    requirement_id: Optional[int] = None,
) -> TestPoint:
    """
    创建测试点

    创建一条测试点记录，测试点描述系统中需要测试的功能点，
    是AI生成测试用例的核心输入。

    Args:
        db: 数据库会话
        project_id: 所属项目ID
        module: 模块名称，如"用户管理"、"订单管理"
        function: 功能名称，如"登录"、"注册"
        point: 测试点描述，具体需要测试的场景或条件
        priority: 优先级，1=高/2=中/3=低
        ai_prompt: AI分析时的提示词（可选），用于引导AI生成更精准的测试用例
        created_by: 创建人用户名（可选）
        requirement_id: 关联需求ID（可选）

    Returns:
        TestPoint: 创建成功后的测试点对象（已commit并refresh）
    """
    db_test_point = TestPoint(
        project_id=project_id,
        module=module,
        function=function,
        point=point,
        priority=priority,
        ai_prompt=ai_prompt,
        created_by=created_by,
        requirement_id=requirement_id,
    )
    db.add(db_test_point)
    db.commit()
    db.refresh(db_test_point)
    return db_test_point


def get_test_point_by_id(
    db: Session,
    test_point_id: int,
    project_id: int
) -> Optional[TestPoint]:
    """
    根据ID获取测试点

    通过测试点ID和项目ID联合过滤，确保在项目维度下定位唯一测试点，
    防止跨项目访问测试点数据。

    Args:
        db: 数据库会话
        test_point_id: 测试点ID
        project_id: 项目ID，用于项目维度隔离

    Returns:
        TestPoint: 测试点对象，不存在则返回None
    """
    return db.query(TestPoint).filter(
        TestPoint.id == test_point_id,
        TestPoint.project_id == project_id
    ).first()


def get_test_points_by_project(
    db: Session,
    project_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TestPoint]:
    """
    获取项目的测试点列表（支持模块/优先级过滤+分页）

    以项目ID为基准，根据可选参数动态构建查询条件。
    此函数未做用户权限过滤，适用于内部调用。

    Args:
        db: 数据库会话
        project_id: 项目ID
        module: 模块名称（可选），精确匹配
        priority: 优先级（可选），精确匹配
        skip: 跳过记录数，用于分页偏移
        limit: 返回记录上限

    Returns:
        List[TestPoint]: 符合条件的测试点列表
    """
    query = db.query(TestPoint).filter(TestPoint.project_id == project_id)

    # 动态追加过滤条件
    if module:
        query = query.filter(TestPoint.module == module)

    if priority:
        query = query.filter(TestPoint.priority == priority)

    return query.offset(skip).limit(limit).all()


def get_test_points_by_project_and_user(
    db: Session,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TestPoint]:
    """
    获取用户项目的测试点列表（多项目隔离）

    通过JOIN Project表实现用户权限隔离，确保用户只能查询自己项目下的测试点。
    过滤逻辑与 get_test_points_by_project 一致，额外增加了用户维度校验。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID，通过JOIN Project表实现权限隔离
        module: 模块名称（可选）
        priority: 优先级（可选）
        skip: 跳过记录数
        limit: 返回记录上限

    Returns:
        List[TestPoint]: 符合条件的测试点列表
    """
    # JOIN Project表：通过Project.user_id实现用户权限隔离
    query = db.query(TestPoint).join(Project).filter(
        TestPoint.project_id == project_id,
        Project.user_id == user_id
    )

    if module:
        query = query.filter(TestPoint.module == module)

    if priority:
        query = query.filter(TestPoint.priority == priority)

    return query.offset(skip).limit(limit).all()


def update_test_point(
    db: Session,
    test_point_id: int,
    project_id: int,
    **kwargs
) -> Optional[TestPoint]:
    """
    更新测试点

    通过kwargs动态更新测试点字段，仅更新传入且模型中存在的字段。
    先通过 get_test_point_by_id 校验测试点存在性和项目归属。

    Args:
        db: 数据库会话
        test_point_id: 测试点ID
        project_id: 项目ID，用于存在性和权限校验
        **kwargs: 需要更新的字段键值对

    Returns:
        TestPoint: 更新后的测试点对象，不存在则返回None

    Warning:
        使用 hasattr 校验字段存在性，可防止传入模型中不存在的字段导致异常，
        但不会校验字段值的合法性，需在Schema层完成。
    """
    test_point = get_test_point_by_id(db, test_point_id, project_id)
    if not test_point:
        return None

    # 仅更新模型中实际存在的字段，忽略无效字段
    for key, value in kwargs.items():
        if hasattr(test_point, key):
            setattr(test_point, key, value)

    db.commit()
    db.refresh(test_point)
    return test_point


def delete_test_point(
    db: Session,
    test_point_id: int,
    project_id: int
) -> bool:
    """
    删除测试点（硬删除）

    物理删除测试点记录，数据库中不再保留。删除前通过 get_test_point_by_id
    校验测试点存在性和项目归属。

    Args:
        db: 数据库会话
        test_point_id: 测试点ID
        project_id: 项目ID，用于存在性和权限校验

    Returns:
        bool: 删除成功返回True，测试点不存在返回False
    """
    test_point = get_test_point_by_id(db, test_point_id, project_id)
    if not test_point:
        return False

    db.delete(test_point)  # 硬删除：物理移除数据库记录
    db.commit()
    return True


def get_test_points_count(
    db: Session,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None
) -> int:
    """
    获取测试点数量（带权限过滤+多条件动态过滤）

    用于分页计算总条数，查询条件与 get_test_points_by_project_and_user 一致，
    但仅返回count值而非完整对象列表。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID
        module: 模块名称（可选）
        priority: 优先级（可选）

    Returns:
        int: 符合条件的测试点数量
    """
    query = db.query(TestPoint).join(Project).filter(
        TestPoint.project_id == project_id,
        Project.user_id == user_id
    )

    if module:
        query = query.filter(TestPoint.module == module)

    if priority:
        query = query.filter(TestPoint.priority == priority)

    return query.count()


def batch_create_test_points(
    db: Session,
    project_id: int,
    test_points_data: List[Dict[str, Any]],
    created_by: Optional[str] = None,
    commit: bool = True,
) -> List[TestPoint]:
    """
    批量创建测试点

    一次性创建多条测试点，采用"先add后统一commit"策略优化性能。
    适用于AI分析需求文档后批量生成测试点的场景。

    Args:
        db: 数据库会话
        project_id: 所属项目ID，所有测试点归属同一项目
        test_points_data: 测试点数据列表，每条数据为字典格式，
            必含字段: module, function, point, priority
            可选字段: ai_prompt, requirement_id, created_by
        created_by: 默认创建人用户名；当单条数据未显式传入 created_by 时使用
        commit: 是否在函数内提交事务，默认提交

    Returns:
        List[TestPoint]: 创建成功的测试点列表

    Note:
        性能优化策略：
        1. 逐条db.add()将对象加入session，但不立即commit
        2. 所有对象add完成后，统一执行一次db.commit()
        3. commit后再逐条db.refresh()获取数据库生成的字段

    Warning:
        若test_points_data中某条数据缺少必填字段，会在commit时抛出数据库异常，
        导致整批创建失败并回滚。调用方应确保数据完整性。
    """
    test_points = []
    for data in test_points_data:
        test_point = TestPoint(
            project_id=project_id,
            module=data['module'],
            function=data['function'],
            point=data['point'],
            priority=data['priority'],
            ai_prompt=data.get('ai_prompt'),  # 可选字段，缺失时为None
            created_by=data.get('created_by', created_by),
            requirement_id=data.get('requirement_id'),
        )
        db.add(test_point)  # 加入session但不commit
        test_points.append(test_point)

    # 统一flush，确保批量创建后对象已分配主键
    db.flush()

    if commit:
        # 统一提交：将多次IO合并为一次事务提交，提升批量写入性能
        db.commit()
        # 逐条refresh获取数据库生成的字段（id、create_time等）
        for test_point in test_points:
            db.refresh(test_point)

    return test_points
