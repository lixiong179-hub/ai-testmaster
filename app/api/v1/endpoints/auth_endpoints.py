"""
认证端点模块

本模块定义认证相关的API端点，包括用户登录、注册、验证码获取和当前用户信息查询。

路由前缀: /auth（由父模块auth.py注册）
标签: 认证管理

端点概览:
    - GET  /captcha            - 获取验证码（开发模式直接返回文本）
    - GET  /captcha/generate   - 获取验证码（别名路径）
    - POST /login              - 用户登录（支持表单和JSON两种请求格式）
    - POST /register           - 用户注册
    - GET  /me                 - 获取当前登录用户信息

权限要求:
    - /captcha, /captcha/generate, /login, /register: 无需认证
    - /me: 需要Bearer令牌认证
"""
import random
import string
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from sqlalchemy.orm import Session
from app.core.exception import create_response
from loguru import logger
from app.db.database import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.api.v1.endpoints.auth_deps import get_current_user
from app.utils.jwt_utils import verify_password, get_password_hash, create_access_token

router = APIRouter()


def get_client_ip(request: Request) -> str:
    """
    获取客户端真实IP地址

    优先从X-Forwarded-For请求头中获取（反向代理场景），
    取第一个IP作为真实客户端地址；若无代理头则使用直连IP。

    Args:
        request: FastAPI请求对象

    Returns:
        str: 客户端IP地址
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("/captcha", response_model=dict)
@router.get("/captcha/generate", response_model=dict)
async def get_captcha():
    """
    获取验证码（开发模式）

    当前为开发模式，直接返回明文验证码文本。
    生产环境应替换为图形验证码或短信验证码。

    Returns:
        dict: 包含captcha_id和验证码文本的响应
    """
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    captcha_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
    return create_response(
        data={
            "captcha_id": captcha_id,
            "code": captcha_text,
            "message": "验证码获取成功（开发模式，直接返回文本）"
        }
    )


@router.post("/login", response_model=dict)
async def login(
    request: Request,
    username: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    captcha_id: Optional[str] = Form(None),
    captcha_code: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    用户登录

    支持表单(Form)和JSON两种请求格式。当表单参数为空时，尝试从请求体JSON中解析。
    登录成功后返回JWT访问令牌和用户基本信息。

    请求参数:
        - username: 用户名（必填）
        - password: 密码（必填）
        - captcha_id: 验证码ID（可选，暂未校验）
        - captcha_code: 验证码内容（可选，暂未校验）

    响应格式:
        - access_token: JWT令牌
        - token_type: "bearer"
        - user: 用户基本信息（id, username, email, is_active）

    权限要求: 无需认证

    Raises:
        HTTPException 400: 参数验证失败
        HTTPException 401: 用户名或密码错误
        HTTPException 403: 账号已被禁用
        HTTPException 500: 服务器内部错误
    """
    try:
        # 优先尝试从表单参数获取，若为空则从JSON请求体解析
        if username is None or password is None:
            try:
                json_data = await request.json()
                username = json_data.get("username")
                password = json_data.get("password")
                captcha_id = captcha_id or json_data.get("captcha_id")
                captcha_code = captcha_code or json_data.get("captcha_code")
            except:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="参数验证失败"
                )
        
        if not username or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供用户名和密码"
            )
        
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        # 检查账号是否被禁用
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已被禁用"
            )
        if not verify_password(password, user.password_hash):
            logger.warning(f"登录失败(密码错误): username={username}, ip={get_client_ip(request)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )
        logger.info(f"用户登录成功: username={user.username}, ip={get_client_ip(request)}")
        # 生成JWT访问令牌，包含用户ID和用户名
        access_token = create_access_token({"sub": str(user.id), "username": user.username})
        return create_response(
            data={
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_active": user.is_active
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"登录异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败，请稍后重试"
        )


@router.post("/register", response_model=dict)
async def register(
    register_data: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    用户注册

    创建新用户账号，注册成功后返回用户基本信息。
    用户名和邮箱需唯一，密码经过哈希处理后存储。

    请求参数(RegisterRequest):
        - username: 用户名（3-50字符）
        - password: 密码（至少6位）
        - email: 邮箱地址（可选，若提供则需唯一）

    响应格式:
        - id: 新用户ID
        - username: 用户名
        - email: 邮箱
        - message: "注册成功"

    权限要求: 无需认证

    Raises:
        HTTPException 400: 用户名已存在/邮箱已注册/参数校验失败
        HTTPException 500: 服务器内部错误
    """
    try:
        username = register_data.username
        password = register_data.password
        email = register_data.email
        # 校验用户名唯一性
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在"
            )
        # 校验邮箱唯一性（仅当提供了邮箱时）
        if email and db.query(User).filter(User.email == email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被注册"
            )
        # 用户名长度校验
        if len(username) < 3 or len(username) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名长度需在3-50之间"
            )
        # 密码长度校验
        if len(password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密码长度不能少于6位"
            )
        # 密码哈希处理后存储，禁止明文存储
        new_user = User(
            username=username,
            password_hash=get_password_hash(password),
            email=email,
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"用户注册成功: username={username}")
        return create_response(
            data={
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "message": "注册成功"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"注册异常: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前登录用户信息

    通过JWT令牌认证后，返回当前用户的详细信息。

    请求参数: 无（通过Authorization请求头传递Bearer令牌）

    响应格式:
        - id: 用户ID
        - username: 用户名
        - email: 邮箱
        - is_active: 是否激活
        - create_time: 创建时间

    权限要求: 需要Bearer令牌认证
    """
    return create_response(
        data={
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "create_time": current_user.create_time
        }
    )
