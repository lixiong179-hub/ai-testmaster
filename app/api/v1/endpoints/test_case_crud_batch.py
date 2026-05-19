"""
测试用例批量操作端点模块

本模块定义测试用例的批量操作API端点，包括批量恢复、批量软删除和批量创建。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST /batch-create  - 批量创建测试用例（含步骤和测试数据，单事务）
    - POST /batch-restore - 批量恢复已删除的用例
    - POST /batch-delete  - 批量软删除用例

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 单次最多操作500个用例
    - 删除为软删除（is_deleted标记），支持批量恢复
    - 批量创建在单个数据库事务中完成，全部成功或全部回滚
"""
from app.utils.db_time import utcnow
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.test_case import TestCase
from app.models.project import Project
from app.models.user import User
from app.schemas.test_case import TestCaseCreate
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.test_case_crud import merge_test_data_to_steps, create_steps_and_test_data
from app.core.exception import create_response
from loguru import logger

router = APIRouter()


class BatchCreateRequest(BaseModel):
    """批量创建请求模型，限制单次最多创建200个用例"""
    cases: list[TestCaseCreate]

    @field_validator('cases')
    @classmethod
    def validate_cases(cls, v: list[TestCaseCreate]) -> list[TestCaseCreate]:
        if not v:
            raise ValueError('用例列表不能为空')
        if len(v) > 200:
            raise ValueError(f'一次最多创建200个用例，当前: {len(v)}')
        return v


@router.post("/batch-create")
async def batch_create_test_cases(
    request: BatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量创建测试用例（含步骤和测试数据，单事务）

    所有用例在同一事务中创建，任一失败则全部回滚，保证数据一致性。

    请求参数(BatchCreateRequest):
        - cases: TestCaseCreate列表（最多200个）
    响应格式:
        - success_count: 成功创建数量
        - fail_count: 失败数量
        - created_ids: 成功创建的用例ID列表
        - errors: 失败详情列表
    权限要求: 需要Bearer令牌认证
    """
    if not request.cases:
        return create_response(data={
            "success_count": 0,
            "fail_count": 0,
            "created_ids": [],
            "errors": [],
            "total": 0,
            "message": "没有需要创建的用例",
        })

    # 验证所有用例的项目归属
    project_ids = {tc.project_id for tc in request.cases}
    authorized_projects = db.query(Project.id).filter(
        Project.id.in_(project_ids),
        Project.user_id == current_user.id,
    ).all()
    authorized_project_ids = {p[0] for p in authorized_projects}

    unauthorized = project_ids - authorized_project_ids
    if unauthorized:
        return create_response(data={
            "success_count": 0,
            "fail_count": len(request.cases),
            "created_ids": [],
            "errors": [f"无权限操作项目: {pid}" for pid in unauthorized],
            "total": len(request.cases),
            "message": f"无权限操作项目: {', '.join(str(p) for p in unauthorized)}",
        })

    created_ids: list[int] = []
    errors: list[str] = []

    try:
        for test_case in request.cases:
            new_test_case = TestCase(
                project_id=test_case.project_id,
                case_no=test_case.case_no or f"CASE{test_case.project_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{len(created_ids)}",
                module=test_case.module,
                title=test_case.title,
                precondition=test_case.precondition,
                steps_json=merge_test_data_to_steps(test_case),
                expected_result=test_case.expected_result,
                priority=test_case.priority,
                case_type=test_case.case_type,
                exec_script=test_case.exec_script,
                generate_status=test_case.generate_status,
                lifecycle_status=test_case.lifecycle_status,
                test_point_id=test_case.test_point_id,
                summary=test_case.summary,
                summary_model_version=test_case.summary_model_version,
                parent_case_id=test_case.parent_case_id,
                ai_change_type=test_case.ai_change_type,
                test_category=test_case.test_category if test_case.test_category else None,
            )

            db.add(new_test_case)
            db.flush()

            create_steps_and_test_data(test_case, new_test_case.id, db)

            created_ids.append(new_test_case.id)

        db.commit()
        logger.info(
            f"[批量创建] 用户ID={current_user.id}, 用户名={current_user.username}, "
            f"成功创建{len(created_ids)}个用例, IDs={created_ids}"
        )
        return create_response(data={
            "success_count": len(created_ids),
            "fail_count": 0,
            "created_ids": created_ids,
            "errors": [],
            "total": len(request.cases),
            "message": f"全部创建成功，共 {len(created_ids)} 条",
        })
    except Exception as e:
        db.rollback()
        logger.error(f"[批量创建] 事务回滚: {e}")
        return create_response(data={
            "success_count": len(created_ids),
            "fail_count": len(request.cases) - len(created_ids),
            "created_ids": created_ids,
            "errors": [str(e)],
            "total": len(request.cases),
            "message": f"批量创建失败: {e}",
        })


class BatchRestoreRequest(BaseModel):
    """批量恢复请求模型，限制单次最多恢复500个用例"""
    caseIds: list[int]

    @field_validator('caseIds')
    @classmethod
    def validate_case_ids(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError('用例ID列表不能为空')
        if len(v) > 500:
            raise ValueError(f'一次最多恢复500个用例，当前: {len(v)}')
        return v


class BatchDeleteRequest(BaseModel):
    """批量删除请求模型，限制单次最多删除500个用例"""
    caseIds: list[int]

    @field_validator('caseIds')
    @classmethod
    def validate_case_ids(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError('用例ID列表不能为空')
        if len(v) > 500:
            raise ValueError(f'一次最多删除500个用例，当前: {len(v)}')
        return v


@router.post("/batch-restore")
async def batch_restore_test_cases(
    request: BatchRestoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量恢复已删除的测试用例
    将已软删除的用例恢复为正常状态，清除删除时间标记。
    单次最多恢复500个用例。

    请求参数(BatchRestoreRequest):
        - caseIds: 用例ID列表（最多500个）
    响应格式:
        - success_count: 成功恢复数量
        - fail_count: 失败数量
        - not_found_ids: 未找到的用例ID列表
    权限要求: 需要Bearer令牌认证，只允许恢复自己项目的用例
    """
    case_ids = request.caseIds
    success_count = 0
    fail_count = 0
    not_found_ids = []

    # 只恢复属于当前用户项目的已删除用例
    deleted_cases = db.query(TestCase).join(Project).filter(
        TestCase.id.in_(case_ids),
        TestCase.is_deleted == True,
        Project.user_id == current_user.id
    ).all()

    existing_ids = {case.id for case in deleted_cases}
    not_found_ids = [id for id in case_ids if id not in existing_ids]

    restored_case_ids = []
    for test_case in deleted_cases:
        try:
            test_case.is_deleted = False
            test_case.deleted_at = None
            success_count += 1
            restored_case_ids.append(test_case.id)
        except Exception as e:
            logger.error(f"恢复用例 {test_case.id} 失败: {e}")
            fail_count += 1

    db.commit()

    logger.info(
        f"[批量恢复] 用户ID={current_user.id}, 用户名={current_user.username}, "
        f"恢复用例IDs={restored_case_ids}, 成功={success_count}, 失败={fail_count}, 未找到={len(not_found_ids)}"
    )

    return create_response(data={
        "success_count": success_count,
        "fail_count": fail_count,
        "not_found_count": len(not_found_ids),
        "not_found_ids": not_found_ids,
        "restored_ids": restored_case_ids,
        "total": len(case_ids),
        "message": f"恢复完成：成功 {success_count} 个，失败 {fail_count} 个，未找到 {len(not_found_ids)} 个"
    })


@router.post("/batch-delete")
async def batch_delete_test_cases(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量软删除测试用例
    将指定用例标记为已删除（is_deleted=True），记录删除时间。
    单次最多删除500个用例。已删除的用例可通过批量恢复接口恢复。

    请求参数(BatchDeleteRequest):
        - caseIds: 用例ID列表（最多500个）
    响应格式:
        - success_count: 成功删除数量
        - fail_count: 失败数量
        - not_found_ids: 未找到的用例ID列表
    权限要求: 需要Bearer令牌认证，只允许删除自己项目的用例
    """
    case_ids = request.caseIds
    success_count = 0
    fail_count = 0
    not_found_ids = []

    # 只删除属于当前用户项目的用例
    existing_cases = db.query(TestCase).join(Project).filter(
        TestCase.id.in_(case_ids),
        TestCase.is_deleted.is_(False),
        Project.user_id == current_user.id
    ).all()

    existing_ids = {case.id for case in existing_cases}
    not_found_ids = [id for id in case_ids if id not in existing_ids]

    deleted_case_ids = []
    for test_case in existing_cases:
        try:
            test_case.is_deleted = True
            test_case.deleted_at = utcnow()
            success_count += 1
            deleted_case_ids.append(test_case.id)
        except Exception as e:
            logger.error(f"删除用例 {test_case.id} 失败: {e}")
            fail_count += 1

    db.commit()

    logger.info(
        f"[批量删除] 用户ID={current_user.id}, 用户名={current_user.username}, "
        f"删除用例IDs={deleted_case_ids}, 成功={success_count}, 失败={fail_count}, 未找到={len(not_found_ids)}"
    )

    return create_response(data={
        "success_count": success_count,
        "fail_count": fail_count,
        "not_found_count": len(not_found_ids),
        "not_found_ids": not_found_ids,
        "deleted_ids": deleted_case_ids,
        "total": len(case_ids),
        "message": f"删除完成：成功 {success_count} 个，失败 {fail_count} 个，未找到 {len(not_found_ids)} 个"
    })
