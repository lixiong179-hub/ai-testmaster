#!/usr/bin/env python3
"""
简单测试脚本，将结果写入文件
"""
import sys
import traceback

# 测试结果文件
result_file = "test_results.txt"

def write_result(message):
    """写入测试结果到文件"""
    with open(result_file, "a", encoding="utf-8") as f:
        f.write(message + "\n")
    print(message)

def test_imports():
    """测试模块导入"""
    write_result("=== 测试模块导入 ===")
    
    # 测试基本依赖
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import pydantic
        write_result("✓ 基本依赖导入成功")
    except Exception as e:
        write_result(f"✗ 基本依赖导入失败: {e}")
        write_result(traceback.format_exc())
        return False
    
    # 测试项目模块
    try:
        from app.core.config import settings
        write_result("✓ 配置模块导入成功")
    except Exception as e:
        write_result(f"✗ 配置模块导入失败: {e}")
        write_result(traceback.format_exc())
        return False
    
    try:
        from app.db.database import Base, init_db
        write_result("✓ 数据库模块导入成功")
    except Exception as e:
        write_result(f"✗ 数据库模块导入失败: {e}")
        write_result(traceback.format_exc())
        return False
    
    try:
        from app.api.v1.endpoints import auth, project, test_cases, file, test_task, report, test_point
        write_result("✓ API端点模块导入成功")
    except Exception as e:
        write_result(f"✗ API端点模块导入失败: {e}")
        write_result(traceback.format_exc())
        return False
    
    write_result("✓ 所有模块导入成功")
    return True

def main():
    """主函数"""
    # 清空结果文件
    with open(result_file, "w", encoding="utf-8") as f:
        f.write("测试开始时间: " + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n")
    
    # 运行测试
    success = test_imports()
    
    # 写入测试结果
    with open(result_file, "a", encoding="utf-8") as f:
        f.write("\n=== 测试结果 ===\n")
        f.write(f"测试状态: {'成功' if success else '失败'}\n")
        f.write("测试结束时间: " + __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
    
    print(f"测试完成，结果已写入 {result_file}")
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
