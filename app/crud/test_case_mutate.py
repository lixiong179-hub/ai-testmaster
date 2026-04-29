"""
测试用例变更操作模块

提供测试用例（TestCase）的所有变更操作（创建/更新/删除/批量创建），
与 test_case_query.py 共同构成测试用例的完整CRUD能力。
本模块仅包含变更函数，不涉及查询操作。

核心函数概览：
    - create_test_case: 创建单个测试用例
    - update_test_case: 更新测试用例（按kwargs动态更新）
    - delete_test_case: 删除测试用例（硬删除）
    - batch_create_test_cases: 批量创建测试用例（单次commit优化性能）

与Model/Schema的对应关系：
    - Model: app.models.test_case.TestCase
    - 依赖模块: app.crud.test_case_query.get_test_case_by_id（用于更新/删除前的存在性校验）

事务处理方式：
    - 单条操作：自动commit，调用方无需手动管理事务
    - 批量操作：先逐条add到session，最后统一commit，减少事务提交次数提升性能

批量操作性能考虑：
    - batch_create_test_cases 采用"先add后统一commit"策略，
      避免逐条commit导致的多次磁盘IO
    - commit后再逐条refresh获取数据库生成的字段（id、create_time等）

软删除/硬删除：
    - delete_test_case 为硬删除，物理移除数据库记录
    - 如需软删除，应在TestCase模型中增加is_deleted字段
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.test_case import TestCase, TestStep
from app.models.enums import TestCaseLifecycleStatus
from app.crud.test_case_query import get_test_case_by_id


def _create_test_steps(
    db: Session,
    test_case_id: int,
    steps: List[Dict[str, Any]],
) -> None:
    """为测试用例创建结构化步骤记录。"""
    for index, step_data in enumerate(steps, start=1):
        if not isinstance(step_data, dict):
            continue
        step = TestStep(
            test_case_id=test_case_id,
            step_number=index,
            action=step_data.get("action", ""),
            expected_result=step_data.get("expected_result", ""),
            action_type=step_data.get("action_type") or None,
            input_value=step_data.get("input_value") or None,
            target_element=step_data.get("target_element") or None,
            is_business_view=1,
            is_technical_view=1,
        )
        db.add(step)


def create_test_case(
    db: Session,
    case_no: str,
    project_id: int,
    module: str,
    title: str,
    precondition: str,
    steps: Dict[str, Any],
    expected_result: str,
    priority: int,
    case_type: str,
    exec_script: Optional[str] = None,
    generate_status: int = 0,
    lifecycle_status: Optional[str] = None,
    test_point_id: Optional[int] = None,
    summary: Optional[str] = None,
    summary_model_version: Optional[str] = None,
    parent_case_id: Optional[int] = None,
) -> TestCase:
    """
    创建单个测试用例

    创建一条完整的测试用例记录，包含用例编号、所属项目、模块、标题、
    前置条件、步骤、预期结果、优先级、类型等核心字段。

    Args:
        db: 数据库会话
        case_no: 用例编号，全局唯一标识，格式如 TC-PROJ-001
        project_id: 所属项目ID
        module: 模块名称，如"用户管理"、"订单管理"
        title: 用例标题，简要描述测试场景
        precondition: 前置条件，执行用例前需满足的条件
        steps: 测试步骤，JSON格式存储，键为步骤序号，值为步骤描述
        expected_result: 预期结果
        priority: 优先级，1=高/2=中/3=低
        case_type: 用例类型，如functional/performance/security
        exec_script: 执行脚本（可选），自动化用例的脚本路径或内容
        generate_status: 生成状态，默认0=待生成，1=已生成，2=生成失败

    Returns:
        TestCase: 创建成功后的测试用例对象（已commit并refresh）

    Note:
        steps参数对应模型中的steps_json字段，ORM层会自动进行JSON序列化。
    """
    db_test_case = TestCase(
        case_no=case_no,
        project_id=project_id,
        module=module,
        title=title,
        precondition=precondition,
        steps_json=steps,  # steps对应模型中的steps_json字段，ORM自动序列化
        expected_result=expected_result,
        priority=priority,
        case_type=case_type,
        exec_script=exec_script,
        generate_status=generate_status,
        lifecycle_status=lifecycle_status or TestCaseLifecycleStatus.ACTIVE.value,
        test_point_id=test_point_id,
        summary=summary,
        summary_model_version=summary_model_version,
        parent_case_id=parent_case_id,
    )
    db.add(db_test_case)
    db.flush()
    _create_test_steps(db, db_test_case.id, steps if isinstance(steps, list) else [])
    db.commit()
    db.refresh(db_test_case)
    return db_test_case


def update_test_case(
    db: Session,
    test_case_id: int,
    project_id: int,
    **kwargs
) -> Optional[TestCase]:
    """
    更新测试用例

    通过kwargs动态更新用例字段，仅更新传入且模型中存在的字段。
    先通过 get_test_case_by_id 校验用例存在性和项目归属。

    Args:
        db: 数据库会话
        test_case_id: 测试用例ID
        project_id: 项目ID，用于存在性和权限校验
        **kwargs: 需要更新的字段键值对，如title="新标题", priority=1

    Returns:
        Optional[TestCase]: 更新后的测试用例对象，不存在则返回None

    Warning:
        使用 hasattr 校验字段存在性，可防止传入模型中不存在的字段导致异常，
        但不会校验字段值的合法性（如枚举范围），需在Schema层完成。
    """
    test_case = get_test_case_by_id(db, test_case_id, project_id)
    if not test_case:
        return None
    # 仅更新模型中实际存在的字段，忽略无效字段
    for key, value in kwargs.items():
        if hasattr(test_case, key):
            setattr(test_case, key, value)
    db.commit()
    db.refresh(test_case)
    return test_case


def delete_test_case(
    db: Session,
    test_case_id: int,
    project_id: int
) -> bool:
    """
    删除测试用例（硬删除）

    物理删除测试用例记录，数据库中不再保留。删除前通过 get_test_case_by_id
    校验用例存在性和项目归属。

    Args:
        db: 数据库会话
        test_case_id: 测试用例ID
        project_id: 项目ID，用于存在性和权限校验

    Returns:
        bool: 删除成功返回True，用例不存在返回False

    Warning:
        硬删除操作，关联的测试结果、用例-屏幕链接等数据需在调用方处理级联清理。
    """
    test_case = get_test_case_by_id(db, test_case_id, project_id)
    if not test_case:
        return False
    db.delete(test_case)  # 硬删除：物理移除数据库记录
    db.commit()
    return True


def batch_create_test_cases(
    db: Session,
    project_id: int,
    test_cases_data: List[Dict[str, Any]],
    commit: bool = True,
) -> List[TestCase]:
    """
    批量创建测试用例

    一次性创建多条测试用例，采用"先add后统一commit"策略优化性能。
    适用于AI生成用例后批量入库的场景。

    Args:
        db: 数据库会话
        project_id: 所属项目ID，所有用例归属同一项目
        test_cases_data: 用例数据列表，每条数据为字典格式，
            必含字段: case_no, module, title, precondition, steps, expected_result, priority, case_type
            可选字段: exec_script, generate_status, test_point_id, test_category
        commit: 是否在函数内提交事务，默认提交

    Returns:
        List[TestCase]: 创建成功的测试用例列表

    Note:
        性能优化策略：
        1. 逐条db.add()将对象加入session，但不立即commit
        2. 所有对象add完成后，统一执行一次db.commit()
        3. commit后再逐条db.refresh()获取数据库生成的字段

        这种方式将多次事务提交合并为一次，显著减少磁盘IO次数。

    Warning:
        若test_cases_data中某条数据缺少必填字段，会在commit时抛出数据库异常，
        导致整批创建失败并回滚。调用方应确保数据完整性。
    """
    test_cases = []
    for data in test_cases_data:
        test_case = TestCase(
            case_no=data['case_no'],
            project_id=project_id,
            test_point_id=data.get('test_point_id'),
            module=data['module'],
            title=data['title'],
            precondition=data['precondition'],
            steps_json=data['steps'],  # steps对应模型中的steps_json字段
            expected_result=data['expected_result'],
            priority=data['priority'],
            case_type=data['case_type'],
            test_category=data.get('test_category'),
            exec_script=data.get('exec_script'),  # 可选字段，缺失时为None
            generate_status=data.get('generate_status', 0),  # 可选字段，默认0=待生成
            lifecycle_status=data.get('lifecycle_status', TestCaseLifecycleStatus.ACTIVE.value),
            summary=data.get('summary'),
            summary_model_version=data.get('summary_model_version'),
            parent_case_id=data.get('parent_case_id'),
        )
        db.add(test_case)  # 加入session但不commit
        test_cases.append(test_case)

    db.flush()

    for test_case, data in zip(test_cases, test_cases_data):
        _create_test_steps(db, test_case.id, data.get('steps', []))

    if commit:
        # 统一提交：将多次IO合并为一次事务提交，提升批量写入性能
        db.commit()
        # 逐条refresh获取数据库生成的字段（id、create_time等）
        for test_case in test_cases:
            db.refresh(test_case)
    return test_cases
