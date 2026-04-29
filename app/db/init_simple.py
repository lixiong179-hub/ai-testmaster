"""
简单数据库初始化脚本 - 使用原生SQL创建基础表和默认管理员

本模块是数据库初始化的轻量级方案，直接使用原生 SQL（DDL）创建表结构，
不依赖 SQLAlchemy ORM 模型定义。

核心函数概览：
- init_database(): 创建基础表（users/projects/project_files）并插入默认管理员

与 init_data.py 的区别：
    init_data.py:
        - 使用 ORM 模型（User, Role, Permission等）操作数据库
        - 功能完整：创建管理员 + 角色 + 权限 + 角色分配
        - 依赖所有 ORM 模型类已正确定义
        - 适用于正常部署流程

    init_simple.py（本模块）:
        - 使用原生 SQL DDL 语句创建表
        - 功能精简：仅创建3张基础表 + 默认管理员
        - 不依赖任何 ORM 模型，仅需数据库引擎可用
        - 适用于以下场景：
          1. 最简初始化：快速搭建最小可用数据库
          2. 紧急修复：ORM 模型存在bug时，用原生SQL绕过
          3. 独立部署：不需要完整RBAC权限系统的轻量部署
          4. 排查问题：排除ORM层干扰，直接验证数据库连通性

依赖关系：
- app.db.database.primary_engine: 主数据库引擎
- app.utils.jwt_utils.get_password_hash: 密码哈希工具

注意事项：
    本模块仅创建3张核心表，不包含角色、权限、测试用例等业务表。
    如需完整的表结构初始化，请使用 init_data.py 或 init_db()。
"""
from app.db.database import primary_engine
from app.utils.jwt_utils import get_password_hash
from sqlalchemy import text


def init_database():
    """
    使用原生SQL初始化数据库 - 创建基础表并插入默认管理员

    本函数执行以下操作：
    1. 创建 users 表 - 用户基础信息表
    2. 创建 projects 表 - 项目信息表
    3. 创建 project_files 表 - 项目文件关联表
    4. 插入默认管理员用户 - admin / password123

    所有建表语句使用 CREATE TABLE IF NOT EXISTS，保证幂等性：
    多次执行不会报错，已存在的表不会被修改。

    注意：
        本函数不创建角色、权限等RBAC相关表，仅保证最基础的用户和项目功能可用。
    """
    with primary_engine.connect() as conn:
        # ============================================================
        # 创建 users 表 - 用户基础信息表
        # ============================================================
        # 字段说明：
        #   id: 自增主键
        #   username: 用户名，唯一索引，用于登录
        #   email: 邮箱，唯一索引，用于通知和找回密码
        #   password_hash: 密码哈希值（bcrypt），禁止存储明文
        #   is_active: 账号是否启用，软删除标记
        #   is_superuser: 是否超级管理员，跳过权限检查
        #   create_time: 创建时间，自动填充当前时间
        #   update_time: 更新时间，自动更新为当前时间
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id INT PRIMARY KEY AUTO_INCREMENT,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            is_superuser BOOLEAN DEFAULT FALSE,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """))

        # ============================================================
        # 创建 projects 表 - 项目信息表
        # ============================================================
        # 字段说明：
        #   id: 自增主键
        #   name: 项目名称
        #   user_id: 项目所有者，外键关联 users.id，级联删除
        #   description: 项目描述
        #   status: 项目状态（1=活跃，0=归档），默认1
        #   config: 项目配置，JSON格式存储灵活配置项
        #   create_time / update_time: 时间戳
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS projects (
            id INT PRIMARY KEY AUTO_INCREMENT,
            name VARCHAR(255) NOT NULL,
            user_id INT NOT NULL,
            description TEXT,
            status INT DEFAULT 1,
            config JSON,
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """))

        # ============================================================
        # 创建 project_files 表 - 项目文件关联表
        # ============================================================
        # 字段说明：
        #   id: 自增主键
        #   project_id: 所属项目，外键关联 projects.id，级联删除
        #   file_name: 文件名，最长500字符（支持中文文件名）
        #   file_type: 文件类型（如 pdf/xlsx/docx/py 等）
        #   file_url: 文件存储路径或URL
        #   file_source: 文件来源（file=本地上传，git=仓库同步），默认'file'
        #   size: 文件大小（字节）
        #   upload_time: 上传时间
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS project_files (
            id INT PRIMARY KEY AUTO_INCREMENT,
            project_id INT NOT NULL,
            file_name VARCHAR(500) NOT NULL,
            file_type VARCHAR(50) NOT NULL,
            file_url VARCHAR(1000) NOT NULL,
            file_source VARCHAR(20) DEFAULT 'file',
            size INT,
            upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """))

        # ============================================================
        # 插入默认管理员用户 - 幂等检查
        # ============================================================
        # 先查询 admin 用户是否已存在，避免重复插入违反唯一约束
        result = conn.execute(text("SELECT id FROM users WHERE username = 'admin'"))
        if not result.fetchone():
            # 使用参数化查询插入管理员，防止SQL注入
            # 密码通过 get_password_hash() 进行 bcrypt 哈希，不存储明文
            password_hash = get_password_hash("password123")
            conn.execute(
                text("INSERT INTO users (username, email, password_hash, is_active) VALUES (:username, :email, :password_hash, :is_active)"),
                {
                    "username": "admin",
                    "email": "admin@example.com",
                    "password_hash": password_hash,
                    "is_active": True
                }
            )
            print("默认管理员用户创建成功: admin / password123")
        else:
            print("管理员用户已存在")

        # 提交所有DDL和DML操作
        conn.commit()
        print("数据库初始化完成")


if __name__ == "__main__":
    """
    命令行入口 - 执行最简数据库初始化

    使用场景：
    1. 快速搭建开发环境：仅需基础表和管理员即可开始开发
    2. 紧急修复：ORM模型异常时，用原生SQL确保核心表存在
    3. 轻量部署：不需要完整RBAC系统的场景

    执行方式：
        python -m app.db.init_simple
    """
    init_database()
