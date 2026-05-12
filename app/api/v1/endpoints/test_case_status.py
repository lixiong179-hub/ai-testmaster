from typing import Optional

"""
测试用例状态端点模块

本模块定义测试用例状态相关的API端点，包括工作流状态管理和纠正状态管理。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - GET  /{test_case_id}/workflow                - 获取用例工作流状态
    - POST /{test_case_id}/workflow/transition     - 工作流状态转换
    - GET  /{test_case_id}/correction-status       - 获取纠正状态
    - POST /{test_case_id}/start-correction        - 开始纠正
    - POST /{test_case_id}/submit-verification     - 提交验证

权限要求: 所有端点需要Bearer令牌认证

业务说明:
    - 工作流状态: draft -> review -> approved/rejected -> deprecated
    - 纠正状态: None -> failed_correction -> correcting -> verifying -> verified
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.test_case import TestCase
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from loguru import logger

router = APIRouter()

WORKFLOW_TRANSITIONS = {
    # 工作流状态转换规则：定义每个状态允许转换到的目标状态
    'draft': ['review', 'deprecated'],
    'review': ['approved', 'rejected', 'draft'],
    'approved': ['deprecated', 'review'],
    'rejected': ['draft', 'deprecated'],
    'deprecated': ['draft']
}

STATUS_LABELS = {
    # 工作流状态中文标签映射
    'draft': '草稿',
    'review': '评审中',
    'approved': '已通过',
    'rejected': '已驳回',
    'deprecated': '已废弃'
}


class WorkflowTransitionRequest(BaseModel):
    """工作流状态转换请求模型"""
    target_status: str
    comment: Optional[str] = None

    @field_validator('target_status')
    @classmethod
    def validate_target_status(cls, v: str) -> str:
        valid_statuses = ['draft', 'review', 'approved', 'rejected', 'deprecated']
        if v not in valid_statuses:
            raise ValueError(f'无效的目标状态: {v}，有效值为: {valid_statuses}')
        return v


@router.get("/{test_case_id}/workflow")
async def get_test_case_workflow(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取测试用例工作流状态

    查询指定测试用例的当前工作流状态及允许的状态转换列表。

    路径参数:
        - test_case_id: 测试用例ID

    响应格式:
        - current_status: 当前状态
        - allowed_transitions: 允许转换的状态列表

    权限要求: 需要Bearer令牌认证
    """
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    current_status = getattr(test_case, 'workflow_status', 'draft') or 'draft'
    allowed_transitions = WORKFLOW_TRANSITIONS.get(current_status, [])

    return create_response(data={
        "test_case_id": test_case_id,
        "current_status": current_status,
        "current_status_label": STATUS_LABELS.get(current_status, current_status),
        "allowed_transitions": [
            {"status": s, "label": STATUS_LABELS.get(s, s)}
            for s in allowed_transitions
        ],
        "workflow_history": []
    })


@router.post("/{test_case_id}/workflow/transition")
async def transition_test_case_workflow(
    test_case_id: int,
    request: WorkflowTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    工作流状态转换

    将测试用例的工作流状态从当前状态转换到目标状态。
    仅允许按预定义的转换规则进行状态切换。

    路径参数:
        - test_case_id: 测试用例ID

    请求参数(WorkflowTransitionRequest):
        - target_status: 目标状态
        - comment: 转换备注（可选）

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 400: 不允许的状态转换
        HTTPException 404: 测试用例不存在
    """
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not test_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="测试用例不存在"
        )

    current_status = getattr(test_case, 'workflow_status', 'draft') or 'draft'
    allowed_transitions = WORKFLOW_TRANSITIONS.get(current_status, [])

    if request.target_status not in allowed_transitions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不允许从 '{STATUS_LABELS.get(current_status, current_status)}' 转换到 '{STATUS_LABELS.get(request.target_status, request.target_status)}'，允许的转换: {[STATUS_LABELS.get(s, s) for s in allowed_transitions]}"
        )

    try:
        old_status = current_status
        test_case.workflow_status = request.target_status
        db.commit()

        logger.info(
            f"[工作流转换] 用户ID={current_user.id}, 用例ID={test_case_id}, "
            f"状态: {old_status} -> {request.target_status}, 备注: {request.comment or '无'}"
        )

        new_allowed = WORKFLOW_TRANSITIONS.get(request.target_status, [])

        return create_response(data={
            "test_case_id": test_case_id,
            "previous_status": old_status,
            "previous_status_label": STATUS_LABELS.get(old_status, old_status),
            "current_status": request.target_status,
            "current_status_label": STATUS_LABELS.get(request.target_status, request.target_status),
            "allowed_transitions": [
                {"status": s, "label": STATUS_LABELS.get(s, s)}
                for s in new_allowed
            ],
            "comment": request.comment,
            "message": f"状态已从 '{STATUS_LABELS.get(old_status, old_status)}' 转换为 '{STATUS_LABELS.get(request.target_status, request.target_status)}'"
        })
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"工作流状态转换失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="工作流状态转换失败"
        )


CORRECTION_STATUS_TRANSITIONS = {
    # 纠正状态转换规则：定义纠正流程中各状态允许的转换
    None: ['failed_correction'],
    'failed_correction': ['correcting'],
    'correcting': ['verifying', 'failed_correction'],
    'verifying': ['verified', 'failed_correction', 'correcting'],
    'verified': ['failed_correction']
}

CORRECTION_STATUS_LABELS = {
    # 纠正状态中文标签映射
    'failed_correction': '执行失败',
    'correcting': '纠正中',
    'verifying': '验证中',
    'verified': '验证通过'
}


@router.get("/{test_case_id}/correction-status")
async def get_correction_status(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取纠正状态

    查询指定测试用例的当前纠正状态及允许的状态转换。

    路径参数:
        - test_case_id: 测试用例ID

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 404: 测试用例不存在
    """
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试用例不存在")

    current_status = getattr(test_case, 'correction_status', None)
    allowed = CORRECTION_STATUS_TRANSITIONS.get(current_status, [])

    return create_response(data={
        "test_case_id": test_case_id,
        "correction_status": current_status,
        "correction_status_label": CORRECTION_STATUS_LABELS.get(current_status, '无'),
        "allowed_transitions": [
            {"status": s, "label": CORRECTION_STATUS_LABELS.get(s, s)}
            for s in allowed
        ]
    })


@router.post("/{test_case_id}/start-correction")
async def start_correction(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    开始纠正

    将测试用例进入纠正模式。仅当用例处于无状态、执行失败或纠正中时允许操作。
    已验证通过或正在验证中的用例不允许开始纠正。

    路径参数:
        - test_case_id: 测试用例ID

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 400: 当前状态不允许开始纠正
        HTTPException 404: 测试用例不存在
    """
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试用例不存在")

    current_status = getattr(test_case, 'correction_status', None)
    if current_status not in [None, 'failed_correction', 'correcting']:
        if current_status == 'verified':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用例已验证通过，无需纠正")
        if current_status == 'verifying':
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用例正在验证中，请等待验证结果")

    try:
        test_case.correction_status = 'correcting'
        db.commit()

        logger.info(f"[纠正开始] 用户ID={current_user.id}, 用例ID={test_case_id}")

        return create_response(data={
            "test_case_id": test_case_id,
            "correction_status": "correcting",
            "correction_status_label": CORRECTION_STATUS_LABELS['correcting'],
            "message": "已进入纠正模式"
        })
    except Exception as e:
        db.rollback()
        logger.error(f"开始纠正失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="开始纠正失败")


@router.post("/{test_case_id}/submit-verification")
async def submit_verification(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    提交验证

    将纠正完成的测试用例提交验证。仅当用例处于"纠正中"状态时允许操作。

    路径参数:
        - test_case_id: 测试用例ID

    权限要求: 需要Bearer令牌认证

    Raises:
        HTTPException 400: 当前状态非"纠正中"
        HTTPException 404: 测试用例不存在
    """
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id).first()
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="测试用例不存在")

    current_status = getattr(test_case, 'correction_status', None)
    if current_status != 'correcting':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"当前状态为'{CORRECTION_STATUS_LABELS.get(current_status, '无')}'，只有'纠正中'状态才能提交验证"
        )

    try:
        test_case.correction_status = 'verifying'
        db.commit()

        logger.info(f"[提交验证] 用户ID={current_user.id}, 用例ID={test_case_id}")

        return create_response(data={
            "test_case_id": test_case_id,
            "correction_status": "verifying",
            "correction_status_label": CORRECTION_STATUS_LABELS['verifying'],
            "message": "已提交验证"
        })
    except Exception as e:
        db.rollback()
        logger.error(f"提交验证失败: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="提交验证失败")
