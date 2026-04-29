import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.models.user import User, Base
from app.services.user_service import UserService

async def test_authenticate():
    print("测试用户认证...")
    
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
            # 测试认证
            print("尝试认证用户: admin / password123")
            user = await UserService.authenticate_user(session, "admin", "password123")
            if user:
                print(f"认证成功！用户: {user.username}, 状态: {user.status}")
            else:
                print("认证失败：用户名或密码错误")
                
            # 检查用户是否存在
            from sqlalchemy import select
            result = await session.execute(
                select(User).where(User.username == "admin")
            )
            user = result.scalars().first()
            if user:
                print(f"用户存在: {user.username}, 密码哈希: {user.password[:20]}...")
            else:
                print("用户不存在")
                
    except Exception as e:
        print(f"错误: {str(e)}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_authenticate())
