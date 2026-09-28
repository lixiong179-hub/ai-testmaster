"""Phase 3 Task 3: MFA 多因子认证 API 端点。

端点概览：
    - POST /auth/mfa/setup         : 生成 TOTP 密钥与 otpauth URI（需认证）
    - POST /auth/mfa/verify        : 校验动态码并启用 MFA（需认证）
    - POST /auth/mfa/disable       : 禁用 MFA（需认证 + 当前 TOTP 码）
    - POST /auth/mfa/backup-codes  : 重新生成备份码（需认证 + 当前 TOTP 码）
    - POST /auth/mfa/login         : MFA 登录验证（密码验证后调用）

设计要点：
    - setup 阶段不持久化 secret，verify 通过后才写入 DB（防中间状态泄露）
    - login 阶段使用 mfa_pending_token 关联密码已验证的会话（短 TTL）
    - 备份码消费后立即持久化剩余列表（一次性）
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth_deps import get_current_user
from app.core.config import settings
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.mfa_service import MFAService
from app.utils.db_time import utcnow
from app.utils.jwt_utils import create_access_token, decode_token

router = APIRouter()

# MFA pending token 的 TTL（分钟）：密码验证后等待 MFA 验证的窗口
_MFA_PENDING_TOKEN_TTL_MINUTES = 5

# MFA 服务实例（无状态，可复用）
_mfa_service = MFAService()


@router.post("/mfa/setup", response_model=ApiResponse, summary="MFA 设置 — 生成密钥",
             description="生成 TOTP 密钥与 otpauth URI。密钥仅返回一次，需调用 /mfa/verify 确认后持久化。")
async def mfa_setup(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> dict:
    """生成 TOTP 密钥与 otpauth URI（不持久化，verify 通过后才写入 DB）。"""
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA 已启用，如需重置请先调用 /mfa/disable",
        )

    secret = _mfa_service.generate_totp_secret()
    uri = _mfa_service.get_totp_uri(
        secret=secret,
        account=current_user.email or current_user.username,
        issuer=settings.APP_NAME,
    )

    return create_response(
        data={
            "secret": secret,
            "otpauth_uri": uri,
            "qr_instructions": "使用 Google Authenticator / Microsoft Authenticator 扫描 QR 码或手动输入密钥",
        }
    )


@router.post("/mfa/verify", response_model=ApiResponse, summary="MFA 验证 — 启用 MFA",
             description="校验 TOTP 动态码，通过后持久化密钥并启用 MFA，同时生成备份码。")
async def mfa_verify(
    secret: str = Form(...),
    code: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> dict:
    """校验 TOTP 动态码并启用 MFA。"""
    if current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA 已启用",
        )

    if not _mfa_service.verify_totp_code(secret=secret, code=code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="动态码校验失败，请重试",
        )

    # 校验通过，持久化密钥并启用 MFA
    current_user.mfa_secret = secret
    current_user.mfa_enabled = True
    # 生成备份码
    plaintext_codes, hashed_codes = _mfa_service.generate_backup_codes()
    current_user.mfa_backup_codes = hashed_codes
    await db.commit()

    logger.info(f"[MFA] 用户 {current_user.id} 启用 MFA 成功")

    return create_response(
        data={
            "mfa_enabled": True,
            "backup_codes": plaintext_codes,
            "backup_code_warning": "请妥善保存备份码，每个仅可使用一次。丢失将无法恢复账户。",
        }
    )


@router.post("/mfa/disable", response_model=ApiResponse, summary="MFA 禁用",
             description="禁用 MFA。需提供当前有效的 TOTP 动态码以防止恶意禁用。")
async def mfa_disable(
    code: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> dict:
    """禁用 MFA（需当前 TOTP 码确认）。"""
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA 未启用",
        )

    # 优先校验 TOTP 码
    verified = _mfa_service.verify_totp_code(
        secret=current_user.mfa_secret or "",
        code=code,
    )

    # TOTP 失败时尝试备份码
    backup_consumed = False
    if not verified and current_user.mfa_backup_codes:
        verified, remaining = _mfa_service.verify_and_consume_backup_code(
            stored_hashed_codes=current_user.mfa_backup_codes,
            submitted_code=code,
        )
        if verified:
            current_user.mfa_backup_codes = remaining
            backup_consumed = True

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="动态码或备份码校验失败",
        )

    current_user.mfa_secret = None
    current_user.mfa_enabled = False
    current_user.mfa_backup_codes = None
    await db.commit()

    logger.info(f"[MFA] 用户 {current_user.id} 禁用 MFA (backup_consumed={backup_consumed})")

    return create_response(data={"mfa_enabled": False})


@router.post("/mfa/backup-codes", response_model=ApiResponse, summary="MFA 备份码重新生成",
             description="重新生成 10 个备份码（旧备份码全部失效）。需提供当前 TOTP 动态码。")
async def mfa_regenerate_backup_codes(
    code: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(async_get_db),
) -> dict:
    """重新生成备份码（需当前 TOTP 码确认）。"""
    if not current_user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MFA 未启用",
        )

    if not _mfa_service.verify_totp_code(
        secret=current_user.mfa_secret or "",
        code=code,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="动态码校验失败",
        )

    plaintext_codes, hashed_codes = _mfa_service.generate_backup_codes()
    current_user.mfa_backup_codes = hashed_codes
    await db.commit()

    logger.info(f"[MFA] 用户 {current_user.id} 重新生成备份码")

    return create_response(
        data={
            "backup_codes": plaintext_codes,
            "backup_code_warning": "旧备份码已全部失效，请妥善保存新备份码。",
        }
    )


@router.post("/mfa/login", response_model=ApiResponse, summary="MFA 登录验证",
             description="密码验证后提交 TOTP 动态码完成登录。mfa_pending_token 由 /login 在 MFA 启用时返回。")
async def mfa_login(
    mfa_pending_token: str = Form(...),
    code: str = Form(...),
    db: AsyncSession = Depends(async_get_db),
) -> dict:
    """MFA 登录验证：校验 mfa_pending_token + TOTP 码，返回正式 access_token + refresh_token。"""
    from app.utils.jwt_utils import (
        create_refresh_token_with_jti,
    )
    from app.services.session_service import SessionService
    from starlette.requests import Request
    from datetime import timedelta

    # 解码 mfa_pending_token
    try:
        payload = decode_token(mfa_pending_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="mfa_pending_token 无效或已过期",
        )

    if payload.get("type") != "mfa_pending":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌类型错误，需要 mfa_pending_token",
        )

    user_id = int(payload.get("sub", 0))
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="mfa_pending_token 缺少用户标识",
        )

    # 查询用户
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.mfa_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或 MFA 未启用",
        )

    # 校验 TOTP 码
    verified = _mfa_service.verify_totp_code(
        secret=user.mfa_secret or "",
        code=code,
    )

    # TOTP 失败时尝试备份码
    backup_consumed = False
    if not verified and user.mfa_backup_codes:
        verified, remaining = _mfa_service.verify_and_consume_backup_code(
            stored_hashed_codes=user.mfa_backup_codes,
            submitted_code=code,
        )
        if verified:
            user.mfa_backup_codes = remaining
            backup_consumed = True

    if not verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="动态码或备份码校验失败",
        )

    # 创建正式会话
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token, jti = create_refresh_token_with_jti({"sub": str(user.id)})

    # 创建 UserSession 记录（绑定 refresh_jti）
    refresh_expires_at = utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    session_service = SessionService(db=db)
    await session_service.create_session(
        user_id=user.id,
        refresh_jti=jti,
        expires_at=refresh_expires_at,
        ip_address=payload.get("ip", ""),
        user_agent=payload.get("ua", ""),
    )

    # 更新登录信息
    user.last_login_time = utcnow()
    user.login_count = (user.login_count or 0) + 1
    await db.commit()

    logger.info(f"[MFA] 用户 {user.id} MFA 登录成功 (backup_consumed={backup_consumed})")

    return create_response(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "mfa_required": False,
        }
    )


def create_mfa_pending_token(user_id: int, ip: str, user_agent: str) -> str:
    """创建 MFA pending token（密码验证通过但 MFA 待验证时使用）。

    Args:
        user_id: 用户 ID
        ip: 客户端 IP
        user_agent: User-Agent

    Returns:
        str: 短 TTL 的 mfa_pending_token
    """
    from datetime import timedelta
    from app.utils.jwt_utils import _encode_token

    token, _ = _encode_token(
        data={"sub": str(user_id), "ip": ip, "ua": user_agent},
        token_type="mfa_pending",
        expires_delta=timedelta(minutes=_MFA_PENDING_TOKEN_TTL_MINUTES),
    )
    return token
