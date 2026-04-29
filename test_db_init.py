#!/usr/bin/env python3
"""
测试数据库连接和用户创建
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.user import User, Base
from app.services.user_service import UserService
from app.schemas.user import UserCreate
from app.core.config import settings

async def test_db_connection():
    print("测试数据库连接...")
    
    # 创建数据库引擎
    engine = create_async_engine(
        settings.DATABASE_URL.replace("mysql+pymysql", "mysql+aiomysql"),
        echo=True
    )
    
    try:
        # 创建表结构
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("表结构创建成功")
        
        # 创建会话
        async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with async_session() as session:
            # 检查是否存在admin用户
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            admin_user = result.scalars().first()
            
            if not admin_user:
                print("创建管理员账号...")
                # 创建管理员账号
                admin_data = UserCreate(
                    username="admin",
                    email="admin@example.com",
                    phone="13800138000",
                    password="password123"
                )
                try:
                    user = await UserService.create_user(session, admin_data)
                    print(f"管理员账号创建成功: {user.username}")
                except Exception as e:
                    print(f"创建管理员账号失败: {str(e)}")
            else:
                print("管理员账号已存在")
                
    except Exception as e:
        print(f"数据库操作失败: {str(e)}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_db_connection())
