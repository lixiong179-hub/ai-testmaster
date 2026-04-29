#!/usr/bin/env python3
"""
测试模块导入情况
"""
import sys

try:
    print("Testing imports...")
    # 测试基本模块
    import fastapi
    import uvicorn
    import sqlalchemy
    import pydantic
    print("Basic modules imported successfully")
    
    # 测试项目模块
    from app.core.config import settings
    print("Config imported successfully")
    
    from app.db.database import init_db, check_db_connection
    print("Database imported successfully")
    
    from app.api.v1.endpoints import auth, project, test_cases, file, test_task, report, test_point
    print("API endpoints imported successfully")
    
    print("All imports successful!")
    
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
