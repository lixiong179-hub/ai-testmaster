"""
数据库初始化数据脚本 - RBAC权限模型与默认管理员初始化

本模块负责在数据库首次创建后，填充系统运行所需的基础数据，包括：
1. 默认管理员用户（admin）
2. 默认角色（admin / test）
3. 默认权限（基于 resource:action 编码规范）
4. 管理员与角色的关联关系

核心类/函数概览：
- _db_session(): 内部数据库会话上下文管理器，供本模块各函数复用
- init_admin_user(): 创建默认管理员用户（幂等）
- init_roles_and_permissions(): 创建默认角色和权限（幂等）
- assign_role_to_admin(): 将管理员角色分配给admin用户（幂等）
- __main__入口: 完整的初始化流程（删表 -> 建表 -> 填充数据）

依赖关系：
- app.db.database.get_db: 获取数据库会话
- app.db.database.init_db / drop_db: 数据库表结构管理
- app.models.*: ORM模型定义（User, Role, Permission, user_role等）
- app.utils.jwt_utils.get_password_hash: 密码哈希工具

设计原则：
- 幂等性：所有初始化函数均先检查数据是否已存在，避免重复创建
- RBAC模型：采用"用户-角色-权限"三层模型，权限编码遵循 resource:action 规范
- 独立性：每个函数可独立调用，也可通过 __main__ 入口完整执行

与 init_simple.py 的区别：
    init_data.py 使用 ORM 模型操作数据库，功能完整但依赖所有模型类已正确定义；
    init_simple.py 使用原生 SQL，不依赖 ORM 模型，适用于模型未就绪时的紧急初始化。
"""
from contextlib import contextmanager
from typing import Generator
import os
import secrets
import warnings
from sqlalchemy.orm import Session
from app.db.database import get_db, init_db
from app.models.user import User, Role, Permission, user_role
from app.models.project import Project, ProjectFile
from app.models.test_case import TestCase, TestStep
from app.models.test_task import TestTask
from app.models.test_result import TestResult
from app.models.report import TestReport
from app.utils.jwt_utils import get_password_hash


@contextmanager
def _db_session() -> Generator[Session, None, None]:
    """
    内部数据库会话上下文管理器

    封装 get_db() 生成器为上下文管理器，供本模块内的初始化函数统一使用。
    与 database.py 中 get_db_context() 的区别：
    - get_db_context() 使用 PrimarySessionLocal 直接创建会话，自动 commit
    - _db_session() 复用 get_db() 的会话管理逻辑，不自动 commit（由调用方控制）

    设计原因：初始化函数需要在业务逻辑中手动 commit（如先 add 再 commit），
    因此不使用自动 commit 的 get_db_context()。

    Yields:
        Session: 数据库会话实例

    Raises:
        Exception: 数据库操作异常时回滚后重新抛出
    """
    db = next(get_db())
    try:
        yield db
    except Exception:
        db.rollback()  # 异常时回滚，保证数据一致性
        raise
    finally:
        db.close()  # 确保会话关闭，释放数据库连接


def init_admin_user() -> User:
    """
    创建默认管理员用户（幂等操作）

    如果 admin 用户不存在则创建，已存在则跳过。
    密码优先从 ADMIN_INITIAL_PASSWORD 环境变量读取，
    未配置时使用 secrets.token_urlsafe(16) 生成随机密码并输出警告。

    Returns:
        User: 管理员用户对象（新建或已存在的）

    注意：
        密码通过 get_password_hash() 进行 bcrypt 哈希存储，不存明文。
        生产环境必须通过环境变量 ADMIN_INITIAL_PASSWORD 设置强密码。
    """
    with _db_session() as db:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            password = os.environ.get("ADMIN_INITIAL_PASSWORD") or secrets.token_urlsafe(16)
            if not os.environ.get("ADMIN_INITIAL_PASSWORD"):
                warnings.warn(
                    "未设置 ADMIN_INITIAL_PASSWORD，已生成随机管理员密码。"
                    "请通过环境变量 ADMIN_INITIAL_PASSWORD 配置！",
                    UserWarning
                )
            admin_user = User(
                username="admin",
                email="admin@example.com",
                password_hash=get_password_hash(password),
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print(f"默认管理员用户创建成功: admin / {password}")
        else:
            print("管理员用户已存在")
        return admin_user


def init_roles_and_permissions() -> Role:
    """
    创建默认角色和权限（幂等操作）

    初始化 RBAC（基于角色的访问控制）模型的基础数据：

    1. 角色初始化：
       - admin: 管理员角色，拥有用户管理、角色管理、权限管理的全部权限
       - test: 测试人员角色，拥有测试用例和测试任务的增删改权限

    2. 权限初始化：
       权限编码遵循 resource:action 命名规范，例如：
       - user:create  -> 用户模块的创建权限
       - test_case:delete -> 测试用例模块的删除权限

       当前权限类型均为 "menu"（菜单级权限），后续可扩展为 "button"（按钮级）
       或 "api"（接口级）实现更细粒度的权限控制。

    Returns:
        Role: 管理员角色对象（新建或已存在的）

    权限编码命名规范（resource:action）：
        resource: 业务资源名称，如 user / role / permission / test_case / test_task
        action: 操作类型，如 create / update / delete / assign_role
        完整编码示例：user:create, test_case:update, role:delete
    """
    with _db_session() as db:
        # ============================================================
        # 角色初始化 - 先检查是否已存在admin角色，避免重复创建
        # ============================================================
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            # 管理员角色：拥有系统管理相关的全部权限
            admin_role = Role(
                name="admin",
                desc="管理员角色",
                permissions=["user:create", "user:update", "user:delete", "user:assign_role", "role:create", "role:update", "role:delete", "permission:create", "permission:update", "permission:delete"]
            )
            db.add(admin_role)

            # 测试人员角色：仅拥有测试用例和测试任务的增删改权限
            test_role = Role(
                name="test",
                desc="测试人员角色",
                permissions=["test_case:create", "test_case:update", "test_case:delete", "test_task:create", "test_task:update", "test_task:delete"]
            )
            db.add(test_role)

            db.commit()
            print("默认角色创建成功")
        else:
            print("角色已存在")

        # ============================================================
        # 权限初始化 - 仅当权限表为空时创建，避免与手动配置的权限冲突
        # ============================================================
        if db.query(Permission).count() == 0:
            permissions = [
                # ---- 用户管理权限 ----
                Permission(name="用户创建", code="user:create", type="menu", parent_id=None),
                Permission(name="用户更新", code="user:update", type="menu", parent_id=None),
                Permission(name="用户删除", code="user:delete", type="menu", parent_id=None),
                Permission(name="用户分配角色", code="user:assign_role", type="menu", parent_id=None),
                # ---- 角色管理权限 ----
                Permission(name="角色创建", code="role:create", type="menu", parent_id=None),
                Permission(name="角色更新", code="role:update", type="menu", parent_id=None),
                Permission(name="角色删除", code="role:delete", type="menu", parent_id=None),
                # ---- 权限管理权限 ----
                Permission(name="权限创建", code="permission:create", type="menu", parent_id=None),
                Permission(name="权限更新", code="permission:update", type="menu", parent_id=None),
                Permission(name="权限删除", code="permission:delete", type="menu", parent_id=None),
                # ---- 测试用例权限 ----
                Permission(name="测试用例创建", code="test_case:create", type="menu", parent_id=None),
                Permission(name="测试用例更新", code="test_case:update", type="menu", parent_id=None),
                Permission(name="测试用例删除", code="test_case:delete", type="menu", parent_id=None),
                # ---- 测试任务权限 ----
                Permission(name="测试任务创建", code="test_task:create", type="menu", parent_id=None),
                Permission(name="测试任务更新", code="test_task:update", type="menu", parent_id=None),
                Permission(name="测试任务删除", code="test_task:delete", type="menu", parent_id=None),
            ]
            db.add_all(permissions)
            db.commit()
            print("默认权限创建成功")
        else:
            print("权限已存在")

        return admin_role


def assign_role_to_admin(admin_user_id: int, admin_role_id: int) -> None:
    """
    将管理员角色分配给admin用户（幂等操作）

    操作 user_role 关联表（多对多中间表），建立用户与角色的绑定关系。
    先检查是否已存在关联记录，避免重复插入导致唯一约束冲突。

    Args:
        admin_user_id: 管理员用户的ID
        admin_role_id: 管理员角色的ID

    Raises:
        Exception: 数据库操作异常时回滚后重新抛出

    注意：
        user_role 是 SQLAlchemy 的 Table 对象（非 ORM 模型），
        需使用 insert().values() 语法操作，而非 db.add()。
    """
    with _db_session() as db:
        # 幂等检查：查询 user_role 关联表中是否已存在该绑定关系
        existing = db.query(user_role).filter(
            user_role.c.user_id == admin_user_id,
            user_role.c.role_id == admin_role_id
        ).first()
        if not existing:
            # 使用 Core 层的 insert 语法操作关联表（user_role 是 Table 对象，非 ORM 模型）
            db.execute(
                user_role.insert().values(user_id=admin_user_id, role_id=admin_role_id)
            )
            db.commit()
            print("管理员角色分配成功")
        else:
            print("管理员角色已分配")


if __name__ == "__main__":
    """
    完整的数据库初始化流程入口

    执行顺序：
    1. 删除现有表结构 - 清空旧数据，确保干净的初始状态
    2. 初始化表结构 - 根据 ORM 模型创建所有表 + 智能同步字段
    3. 创建管理员用户 - admin / password123
    4. 创建角色和权限 - admin角色 + test角色 + 16个基础权限
    5. 分配管理员角色 - 将admin角色绑定到admin用户

    警告：此流程会删除所有数据，仅用于首次部署或开发环境重置！
    """
    # 步骤1：删除现有的表结构（含所有数据）
    print("删除现有数据库表结构...")
    from app.db.database import drop_db
    drop_db()
    print("现有数据库表结构已删除")

    # 步骤2：初始化数据库表结构（create_all + smart_sync）
    print("初始化数据库表结构...")
    init_db()
    print("数据库表结构初始化完成")

    # 步骤3：创建默认管理员用户
    print("创建默认管理员用户...")
    admin_user = init_admin_user()
    admin_role = init_roles_and_permissions()

    # 步骤4：将管理员角色分配给admin用户
    if admin_user and admin_role:
        print("给管理员用户分配角色...")
        assign_role_to_admin(admin_user.id, admin_role.id)

    print("初始化完成")
