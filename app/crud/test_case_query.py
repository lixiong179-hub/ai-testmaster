"""
测试用例查询操作模块

提供测试用例（TestCase）的所有只读查询操作，与 test_case_mutate.py 共同构成
测试用例的完整CRUD能力。本模块仅包含查询函数，不涉及任何数据变更。

核心函数概览：
    - get_test_case_by_id: 根据ID+项目ID获取单条用例
    - get_test_case_by_case_no: 根据用例编号获取单条用例（全局唯一编号查询）
    - get_test_cases_by_project: 获取项目用例列表（支持多条件动态过滤+分页）
    - get_test_cases_by_project_and_user: 获取用户项目用例列表（JOIN Project实现权限隔离）
    - get_test_cases_count: 获取用例数量（用于分页计算总条数）
    - get_failed_test_cases: 获取生成失败的用例（generate_status=2）

与Model/Schema的对应关系：
    - Model: app.models.test_case.TestCase
    - 关联Model: app.models.project.Project（JOIN查询用于用户权限过滤）

查询条件构建逻辑：
    - 动态过滤：根据可选参数（module/priority/case_type/generate_status）逐步追加filter
    - 权限隔离：通过JOIN Project表，确保用户只能查询自己项目下的用例
    - 分页：使用 offset/limit 实现传统分页

性能考虑：
    - generate_status 使用 `is not None` 判断而非布尔判断，因为0也是有效值
    - JOIN查询在Project表上有user_id索引支撑，性能可控
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.test_case import TestCase
from app.models.project import Project


def get_test_case_by_id(
    db: Session,
    test_case_id: int,
    project_id: int
) -> Optional[TestCase]:
    """
    根据ID获取测试用例

    通过测试用例ID和项目ID联合过滤，确保在项目维度下定位唯一用例，
    防止跨项目访问用例数据。

    Args:
        db: 数据库会话
        test_case_id: 测试用例ID
        project_id: 项目ID，用于项目维度隔离

    Returns:
        Optional[TestCase]: 测试用例对象，不存在则返回None
    """
    return db.query(TestCase).filter(
        TestCase.id == test_case_id,
        TestCase.project_id == project_id
    ).first()


def get_test_case_by_case_no(
    db: Session,
    case_no: str
) -> Optional[TestCase]:
    """
    根据用例编号获取测试用例

    用例编号（case_no）在系统中全局唯一，可直接通过编号定位用例，
    无需项目ID过滤。常用于用例编号扫描、去重校验等场景。

    Args:
        db: 数据库会话
        case_no: 用例编号，全局唯一标识

    Returns:
        Optional[TestCase]: 测试用例对象，不存在则返回None

    Note:
        此函数未做用户权限过滤，调用方需自行校验访问权限。
    """
    return db.query(TestCase).filter(TestCase.case_no == case_no).first()


def get_test_cases_by_project(
    db: Session,
    project_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    case_type: Optional[str] = None,
    generate_status: Optional[int] = None,
    lifecycle_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TestCase]:
    """
    获取项目的测试用例列表（支持多条件动态过滤+分页）

    以项目ID为基准，根据可选参数动态构建查询条件。
    仅传入的过滤参数才会被追加到WHERE子句中，未传入的参数不参与过滤。

    Args:
        db: 数据库会话
        project_id: 项目ID
        module: 模块名称（可选），精确匹配
        priority: 优先级（可选），精确匹配，1=高/2=中/3=低
        case_type: 用例类型（可选），精确匹配，如functional/performance/security
        generate_status: 生成状态（可选），0=待生成/1=已生成/2=生成失败
        skip: 跳过记录数，用于分页偏移
        limit: 返回记录上限

    Returns:
        List[TestCase]: 符合条件的测试用例列表

    Note:
        - generate_status 使用 `is not None` 判断，因为0是有效值（待生成），
          不能用布尔判断否则0会被当作False跳过
        - 此函数未做用户权限过滤，适用于内部调用；对外接口应使用
          get_test_cases_by_project_and_user
    """
    query = db.query(TestCase).filter(TestCase.project_id == project_id)
    # 动态追加过滤条件：仅当参数非空时才加入WHERE子句
    if module:
        query = query.filter(TestCase.module == module)
    if priority:
        query = query.filter(TestCase.priority == priority)
    if case_type:
        query = query.filter(TestCase.case_type == case_type)
    # generate_status=0 是有效值，必须用 is not None 判断
    if generate_status is not None:
        query = query.filter(TestCase.generate_status == generate_status)
    if lifecycle_status is not None:
        query = query.filter(TestCase.lifecycle_status == lifecycle_status)
    return query.offset(skip).limit(limit).all()


def get_test_cases_by_project_and_user(
    db: Session,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    case_type: Optional[str] = None,
    generate_status: Optional[int] = None,
    lifecycle_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[TestCase]:
    """
    获取用户项目的测试用例列表（带权限过滤+多条件动态过滤+分页）

    通过JOIN Project表实现用户权限隔离，确保用户只能查询自己项目下的用例。
    过滤逻辑与 get_test_cases_by_project 一致，额外增加了用户维度校验。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID，通过JOIN Project表实现权限隔离
        module: 模块名称（可选）
        priority: 优先级（可选）
        case_type: 用例类型（可选）
        generate_status: 生成状态（可选）
        skip: 跳过记录数
        limit: 返回记录上限

    Returns:
        List[TestCase]: 符合条件的测试用例列表

    Note:
        JOIN Project表会增加查询复杂度，但Project表数据量通常较小，
        且user_id字段有索引支撑，性能影响可控。
    """
    # JOIN Project表：通过Project.user_id实现用户权限隔离
    query = db.query(TestCase).join(Project).filter(
        TestCase.project_id == project_id,
        Project.user_id == user_id
    )
    # 动态追加过滤条件
    if module:
        query = query.filter(TestCase.module == module)
    if priority:
        query = query.filter(TestCase.priority == priority)
    if case_type:
        query = query.filter(TestCase.case_type == case_type)
    if generate_status is not None:
        query = query.filter(TestCase.generate_status == generate_status)
    if lifecycle_status is not None:
        query = query.filter(TestCase.lifecycle_status == lifecycle_status)
    return query.offset(skip).limit(limit).all()


def get_test_cases_count(
    db: Session,
    project_id: int,
    user_id: int,
    module: Optional[str] = None,
    priority: Optional[int] = None,
    case_type: Optional[str] = None,
    generate_status: Optional[int] = None,
    lifecycle_status: Optional[str] = None
) -> int:
    """
    获取测试用例数量（带权限过滤+多条件动态过滤）

    用于分页计算总条数，查询条件与 get_test_cases_by_project_and_user 一致，
    但仅返回count值而非完整对象列表，减少数据传输开销。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID
        module: 模块名称（可选）
        priority: 优先级（可选）
        case_type: 用例类型（可选）
        generate_status: 生成状态（可选）

    Returns:
        int: 符合条件的用例数量

    Note:
        使用 COUNT(*) 查询，不加载完整对象，性能优于先all()再len()。
    """
    query = db.query(TestCase).join(Project).filter(
        TestCase.project_id == project_id,
        Project.user_id == user_id
    )
    if module:
        query = query.filter(TestCase.module == module)
    if priority:
        query = query.filter(TestCase.priority == priority)
    if case_type:
        query = query.filter(TestCase.case_type == case_type)
    if generate_status is not None:
        query = query.filter(TestCase.generate_status == generate_status)
    if lifecycle_status is not None:
        query = query.filter(TestCase.lifecycle_status == lifecycle_status)
    return query.count()


def get_failed_test_cases(
    db: Session,
    project_id: int,
    user_id: int
) -> List[TestCase]:
    """
    获取生成失败的测试用例

    查询指定项目下 generate_status=2（生成失败）的用例，
    用于错误排查和重试操作。

    Args:
        db: 数据库会话
        project_id: 项目ID
        user_id: 用户ID，通过JOIN Project实现权限隔离

    Returns:
        List[TestCase]: 生成失败的测试用例列表

    Note:
        - generate_status枚举值：0=待生成, 1=已生成, 2=生成失败
        - 此查询未加分页，适用于失败用例数量较少的场景；
          若失败用例可能较多，建议增加limit参数
    """
    return db.query(TestCase).join(Project).filter(
        TestCase.project_id == project_id,
        Project.user_id == user_id,
        TestCase.generate_status == 2  # 2=生成失败
    ).all()
