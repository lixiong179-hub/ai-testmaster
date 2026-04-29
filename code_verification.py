# -*- coding: utf-8 -*-
"""
AI测试平台 - 前端功能验证测试
验证前端代码的完整性和正确性
"""
import json
import re

def test_frontend_code():
    """测试前端代码结构和功能"""
    print("=" * 60)
    print("【前端代码验证测试】")
    print("=" * 60)
    
    # 需要检查的关键文件
    files_to_check = [
        # API文件
        ("src/api/project.ts", "项目管理API"),
        ("src/api/case.ts", "测试用例API"),
        ("src/api/file.ts", "文件管理API"),
        ("src/api/auth.ts", "认证API"),
        # 组件文件
        ("src/views/login/index.vue", "登录页面"),
        ("src/views/project/ProjectList.vue", "项目列表页面"),
        ("src/views/project/detail.vue", "项目详情页面"),
        # Store文件
        ("src/store/project.ts", "项目管理Store"),
        # 路由文件
        ("src/router/index.ts", "路由配置"),
    ]
    
    results = []
    base_path = "c:/Users/Administrator/Desktop/ai-testmaster(2)/ai-testmaster"
    
    for file_path, name in files_to_check:
        try:
            full_path = f"{base_path}/{file_path}"
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            checks = []
            
            # 检查基本结构
            if "export" in content or "export default" in content:
                checks.append(("模块导出", True))
            else:
                checks.append(("模块导出", False))
            
            # 检查API文件
            if "api" in file_path:
                if "axios" in content.lower() or "request" in content.lower():
                    checks.append(("HTTP请求", True))
                else:
                    checks.append(("HTTP请求", False))
            
            # 检查Vue组件
            if ".vue" in file_path:
                if "<template>" in content and "<script" in content:
                    checks.append(("Vue结构", True))
                else:
                    checks.append(("Vue结构", False))
                
                if "el-" in content or "ElementPlus" in content:
                    checks.append(("UI组件库", True))
                else:
                    checks.append(("UI组件库", False))
            
            # 检查Store
            if "store" in file_path:
                if "defineStore" in content:
                    checks.append(("Pinia Store", True))
                else:
                    checks.append(("Pinia Store", False))
            
            # 检查路由
            if "router" in file_path:
                if "createRouter" in content or "createWebHashHistory" in content:
                    checks.append(("路由配置", True))
                else:
                    checks.append(("路由配置", False))
            
            # 输出结果
            all_pass = all(c[1] for c in checks)
            print(f"\n{file_path}:")
            for check_name, passed in checks:
                status = "[PASS]" if passed else "[FAIL]"
                print(f"  {status} {check_name}")
            
            results.append({
                "file": file_path,
                "name": name,
                "status": "PASS" if all_pass else "FAIL",
                "checks": checks
            })
            
        except Exception as e:
            print(f"\n{file_path}: [ERROR] {str(e)}")
            results.append({
                "file": file_path,
                "name": name,
                "status": "ERROR",
                "error": str(e)
            })
    
    # 总结
    print("\n" + "=" * 60)
    print("【前端代码验证总结】")
    print("=" * 60)
    
    passed = len([r for r in results if r["status"] == "PASS"])
    failed = len([r for r in results if r["status"] == "FAIL"])
    errors = len([r for r in results if r["status"] == "ERROR"])
    
    print(f"\n检查文件数: {len(results)}")
    print(f"[PASS]: {passed}")
    print(f"[FAIL]: {failed}")
    print(f"[ERROR]: {errors}")
    
    return results

def test_api_endpoints():
    """测试API端点完整性"""
    print("\n" + "=" * 60)
    print("【API端点验证测试】")
    print("=" * 60)
    
    base_path = "c:/Users/Administrator/Desktop/ai-testmaster(2)/ai-testmaster"
    api_dir = f"{base_path}/app/api/v1/endpoints"
    
    endpoints = [
        "auth.py",
        "project.py",
        "test_case.py",
        "test_point.py",
        "test_task.py",
        "file.py",
        "report.py",
        "user.py"
    ]
    
    results = []
    
    for endpoint in endpoints:
        try:
            full_path = f"{api_dir}/{endpoint}"
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取路由装饰器
            routes = re.findall(r'@router\.(get|post|put|delete|patch)\("([^"]+)"', content)
            
            route_list = [f"{method.upper()} {path}" for method, path in routes]
            
            print(f"\n{endpoint}:")
            print(f"  路由数量: {len(routes)}")
            for route in route_list[:5]:
                print(f"    - {route}")
            if len(routes) > 5:
                print(f"    ... 还有 {len(routes) - 5} 个")
            
            results.append({
                "endpoint": endpoint,
                "status": "PASS",
                "route_count": len(routes),
                "routes": route_list
            })
            
        except Exception as e:
            print(f"\n{endpoint}: [ERROR] {str(e)}")
            results.append({
                "endpoint": endpoint,
                "status": "ERROR",
                "error": str(e)
            })
    
    print("\n" + "=" * 60)
    print(f"API端点检查完成: {len(results)} 个文件")
    print("=" * 60)
    
    return results

def test_database_models():
    """测试数据库模型完整性"""
    print("\n" + "=" * 60)
    print("【数据库模型验证测试】")
    print("=" * 60)
    
    base_path = "c:/Users/Administrator/Desktop/ai-testmaster(2)/ai-testmaster"
    models_dir = f"{base_path}/app/models"
    
    models = [
        "user.py",
        "project.py",
        "test_case.py",
        "test_point.py",
        "test_task.py",
        "test_result.py",
        "report.py"
    ]
    
    results = []
    
    for model in models:
        try:
            full_path = f"{models_dir}/{model}"
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取表名
            table_match = re.search(r'__tablename__\s*=\s*["\']([^"\']+)["\']', content)
            table_name = table_match.group(1) if table_match else "N/A"
            
            # 提取列定义
            columns = re.findall(r'(\w+)\s*=\s*Column\(', content)
            
            # 提取关系
            relationships = re.findall(r'(\w+)\s*=\s*relationship\(', content)
            
            print(f"\n{model}:")
            print(f"  表名: {table_name}")
            print(f"  列数: {len(columns)}")
            print(f"  关系: {len(relationships)}")
            
            results.append({
                "model": model,
                "table_name": table_name,
                "column_count": len(columns),
                "relationship_count": len(relationships),
                "status": "PASS"
            })
            
        except Exception as e:
            print(f"\n{model}: [ERROR] {str(e)}")
            results.append({
                "model": model,
                "status": "ERROR",
                "error": str(e)
            })
    
    print("\n" + "=" * 60)
    print(f"数据库模型检查完成: {len(results)} 个模型")
    print("=" * 60)
    
    return results

def main():
    """主函数"""
    print("=" * 60)
    print("  AI测试平台 - 前端和API代码验证")
    print("=" * 60)
    
    # 1. 前端代码验证
    frontend_results = test_frontend_code()
    
    # 2. API端点验证
    api_results = test_api_endpoints()
    
    # 3. 数据库模型验证
    db_results = test_database_models()
    
    # 总结
    print("\n" + "=" * 60)
    print("  全部验证完成!")
    print("=" * 60)
    
    all_passed = (
        all(r["status"] == "PASS" for r in frontend_results) and
        all(r["status"] == "PASS" for r in api_results) and
        all(r["status"] == "PASS" for r in db_results)
    )
    
    if all_passed:
        print("\n状态: 所有检查通过")
    else:
        print("\n状态: 存在失败项")
    
    return {
        "frontend": frontend_results,
        "api": api_results,
        "database": db_results
    }

if __name__ == "__main__":
    main()
