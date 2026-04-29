#!/usr/bin/env python3
"""
测试前后端代码的语法和导入情况
"""
import os
import sys
import subprocess

def test_backend_imports():
    """测试后端模块导入"""
    print("=== 测试后端模块导入 ===")
    try:
        # 测试基本依赖
        import fastapi
        import uvicorn
        import sqlalchemy
        import pydantic
        print("✓ 基本依赖导入成功")
        
        # 测试项目模块
        from app.core.config import settings
        print("✓ 配置模块导入成功")
        
        from app.db.database import Base, init_db
        print("✓ 数据库模块导入成功")
        
        from app.api.v1.endpoints import auth, project, test_cases, file, test_task, report, test_point
        print("✓ API端点模块导入成功")
        
        print("✓ 后端模块导入全部成功")
        return True
    except Exception as e:
        print(f"✗ 后端模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_frontend_syntax():
    """测试前端代码语法"""
    print("\n=== 测试前端代码语法 ===")
    try:
        # 检查前端TypeScript编译
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd="d:\\PythonFile\\ai-testmaster",
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("✓ 前端TypeScript编译成功")
            return True
        else:
            print(f"✗ 前端TypeScript编译失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 测试前端语法失败: {e}")
        return False

def test_api_paths():
    """测试API路径配置"""
    print("\n=== 测试API路径配置 ===")
    try:
        # 检查前端API路径配置
        import json
        with open("d:\\PythonFile\\ai-testmaster\\.env.local", "r", encoding="utf-8") as f:
            env_content = f.read()
        print("✓ 前端环境配置文件读取成功")
        
        # 检查后端API路由配置
        from app.main import app
        print("✓ 后端API路由配置成功")
        
        print("✓ API路径配置测试成功")
        return True
    except Exception as e:
        print(f"✗ API路径配置测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试前后端代码...\n")
    
    backend_result = test_backend_imports()
    frontend_result = test_frontend_syntax()
    api_result = test_api_paths()
    
    print("\n=== 测试结果汇总 ===")
    print(f"后端模块导入: {'✓ 成功' if backend_result else '✗ 失败'}")
    print(f"前端语法检查: {'✓ 成功' if frontend_result else '✗ 失败'}")
    print(f"API路径配置: {'✓ 成功' if api_result else '✗ 失败'}")
    
    if backend_result and frontend_result and api_result:
        print("\n🎉 所有测试通过！前后端代码自检成功。")
        return 0
    else:
        print("\n❌ 部分测试失败，需要修复问题。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
