#!/usr/bin/env python3
"""
手动初始化数据库并创建默认管理员账号
"""
import asyncio
from app.db.database import init_db

async def main():
    print("开始初始化数据库...")
    await init_db()
    print("数据库初始化完成！")

if __name__ == "__main__":
    asyncio.run(main())
