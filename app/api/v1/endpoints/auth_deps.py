"""
认证依赖项模块

本模块提供FastAPI的依赖注入组件，用于JWT令牌校验和项目权限控制。
所有需要用户身份认证的端点均可通过 Depends(get_current_user) 获取当前用户对象。

核心组件:
    - oauth2_scheme: OAuth2密码模式的令牌提取器，从请求头Authorization中提取Bearer令牌
    - get_current_user: 解析JWT令牌并返回当前用户对象（依赖注入函数）
    - require_project_owner: 校验当前用户是否为指定项目的所有者
    - ProjectAccessChecker: 可实例化的项目权限校验器，适用于需要多次权限检查的场景

路由前缀: 无（本模块不定义路由，仅提供依赖项）
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.user import User
from app.utils.jwt_utils import verify_access_token

# OAuth2令牌提取器，指定登录端点路径用于Swagger文档自动生成
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    获取当前登录用户

    从请求头中提取JWT令牌，解析并验证后返回对应的用户对象。
    优先按user_id查找用户，若令牌中无user_id则按username查找。

    依赖注入: 其他端点通过 Depends(get_current_user) 使用

    Args:
        token: JWT访问令牌（由oauth2_scheme自动从请求头提取）
        db: 数据库会话

    Returns:
        User: 当前登录用户对象

    Raises:
        HTTPException 401: 令牌无效、用户不存在或解析异常
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = verify_access_token(token)
        user_id = payload.get("sub")
        username = payload.get("username")
        if not user_id and not username:
            raise credentials_exception
        
        # 先尝试按 user_id 查找，如果不行就按 username 查找
        if user_id:
            user = db.query(User).filter(User.id == int(user_id)).first()
        else:
            user = db.query(User).filter(User.username == username).first()
        
        if user is None:
            raise credentials_exception
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise credentials_exception


async def require_project_owner(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """
    校验当前用户是否为项目所有者

    检查指定项目是否属于当前登录用户，用于需要项目级权限控制的端点。

    依赖注入: 端点通过 Depends(require_project_owner) 使用

    Args:
        project_id: 项目ID（从路径参数获取）
        current_user: 当前登录用户（由get_current_user注入）
        db: 数据库会话

    Returns:
        User: 当前用户对象（校验通过后原样返回，便于链式依赖）

    Raises:
        HTTPException 403: 当前用户非项目所有者
    """
    from app.models.project import Project
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    return current_user


class ProjectAccessChecker:
    """
    项目权限校验器

    可实例化的权限检查类，适用于同一请求中需要对多个项目进行权限校验的场景。
    避免在每个端点中重复编写权限查询逻辑。

    用法:
        checker = ProjectAccessChecker(db, current_user)
        checker.check_project_access(project_id)
    """

    def __init__(self, db: Session, user: User) -> None:
        """
        初始化权限校验器

        Args:
            db: 数据库会话
            user: 当前登录用户
        """
        self.db = db
        self.user = user

    def check_project_access(self, project_id: int) -> None:
        """
        检查当前用户是否有权操作指定项目

        Args:
            project_id: 待检查的项目ID

        Raises:
            HTTPException 403: 当前用户非项目所有者
        """
        from app.models.project import Project
        project = self.db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == self.user.id
        ).first()
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )
