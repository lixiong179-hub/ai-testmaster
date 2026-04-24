import sys
sys.path.insert(0, '.')
import asyncio
from app.db.database import get_db
from app.api.v1.endpoints.ui_prototype.parse_endpoints import parse_ui_screens
from app.schemas.ui_prototype import UIScreenParseRequest
from app.models.user import User
from fastapi import Depends
from contextlib import contextmanager
from sqlalchemy.orm import Session
from app.db.database import PrimarySessionLocal
from loguru import logger

logger.add("api_debug.log", level="DEBUG")

# 模拟依赖项
@contextmanager
def mock_db_session():
    db = PrimarySessionLocal()
    try:
        yield db
    finally:
        db.close()

# 模拟用户
def mock_get_current_user():
    with mock_db_session() as db:
        return db.query(User).filter(User.id == 1).first()

async def test_api_direct():
    # 模拟请求体
    request = UIScreenParseRequest(
        screen_ids=[12],
        prototype_project_id=2,
        parse_mode="text"
    )

    try:
        with mock_db_session() as db:
            user = mock_get_current_user()
            logger.info(f"Calling parse_ui_screens with: {request}")
            result = await parse_ui_screens(request, db, user)
            logger.info(f"Result: {result}")
            print(f"Success!")
            print(f"Result: {result}")
    except Exception as e:
        logger.exception(f"Error: {e}")
        print(f"Error: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    print("=== 直接测试 parse_ui_screens API ===")
    asyncio.run(test_api_direct())