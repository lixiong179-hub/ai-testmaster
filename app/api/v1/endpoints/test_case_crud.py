"""测试用例CRUD端点模块（async 版本）thin wrapper。

本模块为测试用例基础增删改查API端点的聚合入口，路由处理函数与工具函数拆分至:
    - _test_case_crud_helpers.py   共享工具函数（merge_test_data_to_steps / create_steps_and_test_data）
    - _test_case_crud_routes.py    创建与查询路由处理函数（create / list / detail）
    - _test_case_crud_mutations.py 更新与删除路由处理函数（update / delete）

router 定义保留在此文件中，通过 router.add_api_route 注册拆分文件中的路由处理函数。

路由前缀: /testCase（由父模块test_case.py注册）
标签: 测试用例管理

端点概览:
    - POST   /                    - 创建测试用例（含步骤和测试数据）
    - GET    /                    - 查询测试用例列表（分页、按项目/需求文件筛选）
    - GET    /{test_case_id}      - 获取用例详情
    - PUT    /{test_case_id}      - 更新用例（含步骤重建）
    - DELETE /{test_case_id}      - 软删除单个用例

权限要求: 所有端点需要Bearer令牌认证

迁移说明（P0 服务 async 化）:
    消除所有 db.run_sync() 包裹，内联 DB 操作改为 select() + await db.execute()。
    create_steps_and_test_data 改为 async，供本模块与 test_case_crud_batch 共享。

公开符号通过本文件 re-export，保持 import 路径不变
（from app.api.v1.endpoints.test_case_crud import xxx）。
"""
from fastapi import APIRouter

from app.api.v1.endpoints._test_case_crud_helpers import (
    merge_test_data_to_steps,
    create_steps_and_test_data,
)
from app.api.v1.endpoints._test_case_crud_routes import (
    create_test_case,
    get_test_cases,
    get_test_case,
)
from app.api.v1.endpoints._test_case_crud_mutations import (
    update_test_case,
    delete_test_case,
)

router = APIRouter()

router.add_api_route("/", create_test_case, methods=["POST"])
router.add_api_route("/", get_test_cases, methods=["GET"])
router.add_api_route("/{test_case_id}", get_test_case, methods=["GET"])
router.add_api_route("/{test_case_id}", update_test_case, methods=["PUT"])
router.add_api_route("/{test_case_id}", delete_test_case, methods=["DELETE"])

__all__ = [
    "router",
    "merge_test_data_to_steps",
    "create_steps_and_test_data",
    "create_test_case",
    "get_test_cases",
    "get_test_case",
    "update_test_case",
    "delete_test_case",
]
