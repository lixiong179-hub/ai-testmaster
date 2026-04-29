"""测试API端点存在性"""
import requests

BASE_URL = "http://localhost:8000"

# 获取OpenAPI文档
response = requests.get(f"{BASE_URL}/openapi.json")
if response.status_code == 200:
    spec = response.json()

    # 查找project相关的PUT端点
    put_endpoints = []
    for path, methods in spec.get("paths", {}).items():
        if "put" in methods:
            for method in ["put"]:
                endpoint_info = methods[method]
                if "project" in path.lower() or "config" in path.lower():
                    put_endpoints.append({
                        "path": path,
                        "method": method.upper(),
                        "summary": endpoint_info.get("summary", ""),
                        "operationId": endpoint_info.get("operationId", "")
                    })

    print("=" * 60)
    print("所有PUT端点:")
    print("=" * 60)
    for ep in put_endpoints:
        print(f"{ep['method']:6} {ep['path']}")

    print("\n" + "=" * 60)
    print("项目管理相关端点:")
    print("=" * 60)
    for path in spec.get("paths", {}).keys():
        if "project" in path.lower():
            methods = list(spec["paths"][path].keys())
            print(f"{path}: {methods}")
else:
    print(f"获取OpenAPI文档失败: {response.status_code}")
