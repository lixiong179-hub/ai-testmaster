#!/usr/bin/env python3
"""
测试数据库查询，检查管理员账号是否存在
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.user import User, Base
from app.core.config import settings

async def test_db_query():
    print("测试数据库查询...")
    
    # 创建数据库引擎
    engine = create_async_engine(
        settings.DATABASE_URL.replace("mysql+pymysql", "mysql+aiomysql"),
        echo=True
    )
    
    try:
        # 创建会话
        async_session = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        async with async_session() as session:
            # 查询所有用户
            result = await session.execute(
                select(User)
            )
            users = result.scalars().all()
            
            print(f"数据库中共有 {len(users)} 个用户")
            for user in users:
                print(f"用户ID: {user.id}, 用户名: {user.username}, 邮箱: {user.email}, 手机号: {user.phone}, 状态: {user.status}")
                
            # 检查是否存在admin用户
            admin_result = await session.execute(
                select(User).where(User.username == "admin")
            )
            admin_user = admin_result.scalars().first()
            
            if admin_user:
                print(f"\n管理员账号存在: {admin_user.username}")
            else:
                print("\n管理员账号不存在")
                
    except Exception as e:
        print(f"错误: {str(e)}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_db_query())
