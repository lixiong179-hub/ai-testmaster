# 测试点独立管理模块 - 详细开发任务文档

---

## 文档说明

本文档为测试点独立管理模块的详细开发任务清单，包含每个任务的：
- 明确的目标描述
- 具体的实施步骤
- 所需资源清单
- 预期成果标准
- 时间节点要求
- 相关参考资料链接

---

## Phase 1: 后端数据模型与API (预计 1~2 天)

---

### T1.1: 数据库模型改造 - TestPoint新增created_by字段

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 后端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | 无 |
| **时间节点** | Phase1第1个任务，必须在T1.3前完成 |

---

#### 目标描述

在TestPoint数据模型中新增`created_by`字段，用于记录测试点的创建人。该字段可空，以确保历史数据兼容性。

---

#### 具体实施步骤

1. 打开 `app/models/test_point.py` 文件
2. 在 `TestPoint` 类中新增字段定义：
   ```python
   created_by = Column(String(100), nullable=True, comment="创建人用户名")
   ```
3. 检查并确保导入正确（无需新导入）
4. 验证字段位置（建议放在create_time附近）
5. 确保遵循项目代码规范（变量命名、注释等）

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 源代码文件 | `app/models/test_point.py` |
| 项目规范 | `.trae/rules/project_rules.md` - 变量命名、注释规范 |
| 参考模型 | `app/models/test_case.py` - 查看如何定义类似字段 |

---

#### 预期成果标准

- 字段定义完整，包含类型、约束、注释
- 遵循项目代码规范（lowerCamelCase变量名、注释齐全）
- 字段设置为可空（nullable=True）以确保历史数据兼容
- 文件语法正确，无编译错误

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| TestPoint模型 | `app/models/test_point.py` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T1.2: 数据库模型改造 - TestCase新增test_point_id字段

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 后端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | 无 |
| **时间节点** | Phase1第2个任务，必须在T1.3前完成 |

---

#### 目标描述

在TestCase数据模型中新增`test_point_id`字段，建立TestCase与TestPoint的直接关联关系。该字段可空，确保历史数据兼容性。同时添加relationship关系。

---

#### 具体实施步骤

1. 打开 `app/models/test_case.py` 文件
2. 在 `TestCase` 类中新增外键字段：
   ```python
   test_point_id = Column(Integer, ForeignKey("test_points.id", ondelete="SET NULL"), nullable=True, index=True, comment="关联测试点ID")
   ```
3. 添加relationship关系（建议放在其他relationships附近）：
   ```python
   test_point = relationship("TestPoint", backref="test_cases")
   ```
4. 确保字段设置为可空（nullable=True）
5. 确保ondelete="SET NULL"以保留用例当测试点删除时

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 源代码文件 | `app/models/test_case.py` |
| TestPoint模型 | `app/models/test_point.py` - 查看关联模型 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 外键字段定义完整，包含类型、约束、注释
- relationship关系正确配置
- 字段设置为可空（nullable=True）以确保历史数据兼容
- ondelete="SET NULL"正确设置
- 文件语法正确

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| TestCase模型 | `app/models/test_case.py` |
| TestPoint模型 | `app/models/test_point.py` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T1.3: 编写Alembic数据库迁移脚本

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 后端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T1.1、T1.2 |
| **时间节点** | Phase1第3个任务，必须在T1.4前完成 |

---

#### 目标描述

创建Alembic数据库迁移脚本，实现：
1. 新增test_points.created_by字段
2. 新增test_cases.test_point_id字段
3. 添加index到新增字段
4. 包含完整的回滚脚本

---

#### 具体实施步骤

1. 进入项目根目录，确保Python虚拟环境已激活
2. 执行命令生成迁移模板：
   ```bash
   alembic revision --autogenerate -m "Add created_by to test_points and test_point_id to test_cases"
   ```
3. 打开生成的迁移文件（位于 `alembic/versions/`）
4. 检查自动生成的迁移脚本，确保：
   - upgrade()函数包含新增字段和index
   - downgrade()函数包含删除字段和index
5. 验证回滚逻辑完整
6. 在测试环境执行迁移验证：
   ```bash
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| Alembic配置 | `alembic.ini` |
| 迁移目录 | `alembic/versions/` |
| 项目规范 | `.trae/rules/project_rules.md` - 数据库变更要求 |

---

#### 预期成果标准

- 迁移脚本文件正确生成
- upgrade()函数正确实现字段新增
- downgrade()函数正确实现字段删除（完整回滚）
- index正确添加到新字段
- 迁移脚本在测试环境验证通过（升级和降级均正常）

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| Alembic文档 | [Alembic官方文档](https://alembic.sqlalchemy.org/) |
| 项目规范 | `.trae/rules/project_rules.md` |
| 现有迁移示例 | `alembic/versions/` 目录下的其他迁移文件 |

---

### T1.4: 完善test_point CRUD - 新增按创建人筛选

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 后端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T1.1 |
| **时间节点** | Phase1第4个任务 |

---

#### 目标描述

完善`app/crud/test_point.py`中的查询功能，新增按创建人筛选的能力，同时更新create_test_point函数以支持设置created_by字段。

---

#### 具体实施步骤

1. 打开 `app/crud/test_point.py`
2. 更新 `create_test_point` 函数，新增可选参数 `created_by`：
   ```python
   def create_test_point(..., created_by: Optional[str] = None) -> TestPoint:
       db_test_point = TestPoint(
           ...,
           created_by=created_by
       )
   ```
3. 更新 `get_test_points_by_project` 函数，新增可选参数 `created_by`：
   ```python
   def get_test_points_by_project(..., created_by: Optional[str] = None, ...):
       if created_by:
           query = query.filter(TestPoint.created_by == created_by)
   ```
4. 更新 `get_test_points_by_project_and_user` 函数，新增可选参数 `created_by`：
   ```python
   def get_test_points_by_project_and_user(..., created_by: Optional[str] = None, ...):
       if created_by:
           query = query.filter(TestPoint.created_by == created_by)
   ```
5. 更新 `get_test_points_count` 函数，新增可选参数 `created_by`
6. 为所有修改添加完整的类型注解和文档注释

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 源代码文件 | `app/crud/test_point.py` |
| 项目规范 | `.trae/rules/project_rules.md` - 类型注解、注释规范 |

---

#### 预期成果标准

- create_test_point函数支持设置created_by
- 查询函数均支持按created_by筛选
- 完整的类型注解
- 完整的文档注释
- 遵循项目代码规范

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有CRUD实现 | `app/crud/test_point.py` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T1.5: 完善test_point CRUD - 新增关联需求筛选

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 后端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T1.1 |
| **时间节点** | Phase1第5个任务 |

---

#### 目标描述

完善CRUD查询功能，新增按requirement_id筛选的能力，支持按关联需求过滤测试点。

---

#### 具体实施步骤

1. 打开 `app/crud/test_point.py`
2. 更新 `get_test_points_by_project` 函数，新增可选参数 `requirement_id`
3. 更新 `get_test_points_by_project_and_user` 函数，新增可选参数 `requirement_id`
4. 更新 `get_test_points_count` 函数，新增可选参数 `requirement_id`
5. 添加过滤逻辑：
   ```python
   if requirement_id:
       query = query.filter(TestPoint.requirement_id == requirement_id)
   ```
6. 为所有修改添加类型注解和文档注释

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 源代码文件 | `app/crud/test_point.py` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 查询函数均支持按requirement_id筛选
- 完整的类型注解
- 完整的文档注释
- 遵循项目代码规范

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有CRUD实现 | `app/crud/test_point.py` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T1.6: 新增查询接口 - 获取测试点关联的测试用例

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 后端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T1.2 |
| **时间节点** | Phase1第6个任务 |

---

#### 目标描述

在test_point_query模块中新增接口，用于获取指定测试点关联的所有测试用例，支持分页查询。

---

#### 具体实施步骤

1. 打开 `app/api/v1/endpoints/test_point_query.py`
2. 创建新的CRUD函数（或在现有文件中）：
   ```python
   def get_test_cases_by_test_point(
       db: Session,
       test_point_id: int,
       project_id: int,
       skip: int = 0,
       limit: int = 100
   ) -> List[TestCase]:
       from app.models.test_case import TestCase
       query = db.query(TestCase).filter(
           TestCase.test_point_id == test_point_id,
           TestCase.project_id == project_id,
           TestCase.is_deleted == False
       )
       return query.offset(skip).limit(limit).all()
   
   def get_test_cases_by_test_point_count(
       db: Session,
       test_point_id: int,
       project_id: int
   ) -> int:
       from app.models.test_case import TestCase
       query = db.query(TestCase).filter(
           TestCase.test_point_id == test_point_id,
           TestCase.project_id == project_id,
           TestCase.is_deleted == False
       )
       return query.count()
   ```
3. 在API模块中新增端点：
   ```python
   @router.get("/{test_point_id}/test-cases", response_model=...)
   async def get_test_point_test_cases(...):
       ...
   ```
4. 确保添加权限验证（复用现有权限机制）
5. 添加完整的类型注解和文档注释
6. 创建或更新Schema（如需要）

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| API端点文件 | `app/api/v1/endpoints/test_point_query.py` |
| TestCase模型 | `app/models/test_case.py` |
| 项目规范 | `.trae/rules/project_rules.md` |
| Schema定义 | `app/schemas/test_case.py` |

---

#### 预期成果标准

- 新增API端点正常工作
- 支持分页查询
- 权限验证完整
- 完整的类型注解和文档注释
- 遵循项目代码规范

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有查询端点 | `app/api/v1/endpoints/test_point_query.py` |
| TestCase CRUD示例 | `app/crud/test_case.py` |

---

### T1.7: 新增测试点批量生成用例接口

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 后端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | 无 |
| **时间节点** | Phase1第7个任务 |

---

#### 目标描述

新增接口，支持从测试点列表直接批量触发AI生成测试用例，复用现有的AI生成能力。

---

#### 具体实施步骤

1. 查找现有的AI生成测试用例的实现（很可能在test_case_mutate或类似文件中）
2. 在 `app/api/v1/endpoints/test_point_mutate.py` 中新增批量生成端点
3. 实现端点逻辑：
   - 接收测试点ID列表
   - 验证测试点存在且属于当前项目
   - 复用现有AI生成逻辑
   - 建立test_point_id关联
   - 返回生成结果
4. 考虑是否需要异步处理（可选，取决于性能要求）
5. 添加完整的类型注解和文档注释

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 变更端点文件 | `app/api/v1/endpoints/test_point_mutate.py` |
| AI生成实现 | 查找现有用例生成代码 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 批量生成接口正常工作
- 正确建立test_point_id关联
- 复用现有AI生成能力
- 完整的类型注解和文档注释
- 遵循项目代码规范

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有变更端点 | `app/api/v1/endpoints/test_point_mutate.py` |
| 用例生成示例 | 查找现有AI生成用例的代码 |

---

### T1.8: 新增权限点定义 (test_point:read/create/update/delete)

| 属性 | 内容 |
|------|------|
| **优先级** | 中 |
| **负责人** | 后端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | 无 |
| **时间节点** | Phase1第8个任务 |

---

#### 目标描述

在权限常量定义模块中新增测试点相关的权限点，用于后续权限控制。

---

#### 具体实施步骤

1. 查找项目中现有的权限常量定义文件（可能在 `app/core/` 或 `app/utils/` 目录）
2. 新增权限常量：
   ```python
   TEST_POINT_READ = "test_point:read"
   TEST_POINT_CREATE = "test_point:create"
   TEST_POINT_UPDATE = "test_point:update"
   TEST_POINT_DELETE = "test_point:delete"
   ```
3. 确保常量命名符合项目规范
4. 如使用枚举，将新权限加入枚举

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 权限定义文件 | 查找现有权限常量文件 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 权限常量定义完整
- 命名符合项目规范
- 文件语法正确

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有权限定义 | 查找项目中的权限常量文件 |

---

### T1.9: API层权限校验集成

| 属性 | 内容 |
|------|------|
| **优先级** | 中 |
| **负责人** | 后端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T1.8 |
| **时间节点** | Phase1第9个任务 |

---

#### 目标描述

在测试点相关的API端点中集成权限验证装饰器，确保API访问受权限控制。

---

#### 具体实施步骤

1. 查找项目中现有的权限验证装饰器实现
2. 在test_point_query.py中为查询端点添加TEST_POINT_READ权限
3. 在test_point_mutate.py中为创建/更新/删除端点添加相应权限
4. 确保权限装饰器正确应用
5. 验证权限校验逻辑正常

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| API端点文件 | `app/api/v1/endpoints/test_point_query.py`、`test_point_mutate.py` |
| 权限装饰器 | 查找现有权限验证实现 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 查询端点有TEST_POINT_READ权限校验
- 创建端点有TEST_POINT_CREATE权限校验
- 更新端点有TEST_POINT_UPDATE权限校验
- 删除端点有TEST_POINT_DELETE权限校验
- 权限校验正常工作

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有权限装饰器 | 查找项目中的权限验证实现 |

---

### T1.10: 后端单元测试

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 后端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T1.4-T1.9 |
| **时间节点** | Phase1第10个任务，必须完成才能进入Phase2 |

---

#### 目标描述

为所有新增的后端功能编写单元测试，确保测试覆盖率≥95%。

---

#### 具体实施步骤

1. 查找项目中现有的测试文件（可能在 `tests/` 或 `app/tests/` 目录）
2. 为新增的CRUD函数编写单元测试
3. 为新增的API端点编写单元测试
4. 确保测试覆盖正常、边界、异常场景
5. 运行测试并验证通过
6. 确保测试覆盖率≥95%

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 测试目录 | 查找项目中的测试文件 |
| 项目规范 | `.trae/rules/project_rules.md` - 测试覆盖率要求 |
| 现有测试示例 | 查找项目中的其他单元测试 |

---

#### 预期成果标准

- 单元测试文件完整
- 测试覆盖所有新增功能
- 测试覆盖正常、边界、异常场景
- 所有测试通过
- 测试覆盖率≥95%

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目规范 | `.trae/rules/project_rules.md` |
| 现有测试示例 | 查找项目中的其他单元测试 |

---

## Phase 2: 前端列表页开发 (预计 2~3 天)

---

### T2.1: 创建测试点列表页组件 (src/views/test-point/TestPointList.vue)

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 2小时 |
| **依赖关系** | 无 |
| **时间节点** | Phase2第1个任务 |

---

#### 目标描述

创建测试点列表页的Vue组件，参考TestCaseList.vue的结构和风格，确保UI一致性。

---

#### 具体实施步骤

1. 创建目录 `src/views/test-point/`
2. 复制 `src/views/case/TestCaseList.vue` 作为模板，重命名为 `TestPointList.vue`
3. 修改模板内容以适配测试点场景：
   - 页面标题改为"测试点列表"
   - 统计卡片改为测试点相关的统计
   - 表格列改为测试点字段（模块、功能、测试点、优先级、创建人、创建时间等）
   - 移除与测试用例相关的字段（如用例类型、生成状态等）
4. 保留视图切换功能（列表/卡片）
5. 保留加载状态和空状态
6. 确保风格与项目一致

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 参考页面 | `src/views/case/TestCaseList.vue` |
| 项目规范 | `.trae/rules/project_rules.md` - Vue组件规范 |
| Element Plus组件库 | 项目已安装 |

---

#### 预期成果标准

- 页面结构完整
- 风格与项目一致
- 包含基本的页面布局
- 包含视图切换功能
- 包含加载状态和空状态

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| TestCaseList.vue | `src/views/case/TestCaseList.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T2.2: 创建测试点状态管理 (src/store/testPoint.ts)

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | 无 |
| **时间节点** | Phase2第2个任务 |

---

#### 目标描述

创建测试点的Pinia状态管理Store，管理测试点列表、筛选条件、加载状态等。

---

#### 具体实施步骤

1. 参考 `src/store/analysis.ts` 或其他Store的结构
2. 创建 `src/store/testPoint.ts`
3. 定义state：
   ```typescript
   state: () => ({
     testPoints: [] as TestPoint[],
     selectedTestPoints: [] as number[],
     filter: { ... } as TestPointFilter,
     loading: false,
     viewMode: 'list' as 'list' | 'grid'
   })
   ```
4. 定义actions：
   - fetchTestPoints()
   - setFilter()
   - selectTestPoint()
   - toggleViewMode()
5. 定义getters（如需要）
6. 添加TypeScript类型定义
7. 在main.ts中注册Store（如需要）

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 参考Store | `src/store/analysis.ts` 或其他Store |
| 项目规范 | `.trae/rules/project_rules.md` - TypeScript规范 |
| Pinia文档 | [Pinia官方文档](https://pinia.vuejs.org/) |

---

#### 预期成果标准

- Store结构完整
- TypeScript类型定义完整
- 基本的state、actions、getters定义
- 遵循项目代码规范

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有Store示例 | `src/store/analysis.ts` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T2.3: 完善API封装 (src/api/testPoint.ts) - 新增CRUD方法

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | 无 |
| **时间节点** | Phase2第3个任务 |

---

#### 目标描述

完善测试点API封装，新增完整的CRUD方法，以及获取关联测试用例、批量生成用例等方法。

---

#### 具体实施步骤

1. 打开 `src/api/testPoint.ts`（如果不存在则创建）
2. 新增API方法：
   ```typescript
   // 查询
   export const getTestPointList = async (params: any) => { ... }
   export const getTestPointDetail = async (id: number) => { ... }
   export const getTestPointTestCases = async (id: number, params: any) => { ... }
   
   // 变更
   export const createTestPoint = async (data: any) => { ... }
   export const updateTestPoint = async (id: number, data: any) => { ... }
   export const deleteTestPoint = async (id: number) => { ... }
   export const batchDeleteTestPoints = async (ids: number[]) => { ... }
   export const batchGenerateTestCases = async (testPointIds: number[]) => { ... }
   ```
3. 确保使用统一的request封装
4. 添加TypeScript类型定义
5. 确保错误处理完整

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| API封装文件 | `src/api/testPoint.ts` |
| 参考API示例 | `src/api/` 目录下的其他API文件 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- API方法完整
- TypeScript类型定义完整
- 统一的request封装使用
- 错误处理完整
- 遵循项目代码规范

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有API示例 | `src/api/` 目录下的其他API文件 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T2.4: 完善类型定义 (src/types/testPoint.ts) - 新增关联用例类型

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | 无 |
| **时间节点** | Phase2第4个任务 |

---

#### 目标描述

完善测试点TypeScript类型定义，新增TestPoint、TestPointFilter、TestPointForm等类型，以及关联用例的类型。

---

#### 具体实施步骤

1. 打开或创建 `src/types/testPoint.ts`
2. 定义类型：
   ```typescript
   export interface TestPoint {
     id: number
     project_id: number
     module: string
     function: string
     point: string
     priority: number
     create_time: string
     created_by?: string
     requirement_id?: number
     ai_prompt?: string
     // 额外字段（前端计算）
     test_case_count?: number
   }
   
   export interface TestPointFilter {
     module?: string
     priority?: number | null
     created_by?: string
     requirement_id?: number | null
     keyword?: string
     // 分页
     skip?: number
     limit?: number
   }
   
   export interface TestPointForm {
     module: string
     function: string
     point: string
     priority: number
     ai_prompt?: string
   }
   ```
3. 确保类型与后端Schema一致
4. 确保类型定义完整

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 类型定义文件 | `src/types/testPoint.ts` |
| 参考类型示例 | `src/types/` 目录下的其他类型文件 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 类型定义完整
- TypeScript类型正确
- 与后端Schema一致
- 遵循项目代码规范

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有类型示例 | `src/types/` 目录下的其他类型文件 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T2.5: 实现列表展示功能（表格/卡片视图切换）

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 2小时 |
| **依赖关系** | T2.1-T2.4 |
| **时间节点** | Phase2第5个任务 |

---

#### 目标描述

在TestPointList.vue中实现测试点列表的完整展示功能，支持表格视图和卡片视图切换。

---

#### 具体实施步骤

1. 打开 `src/views/test-point/TestPointList.vue`
2. 引入testPoint Store：
   ```typescript
   import { useTestPointStore } from '@/store/testPoint'
   const testPointStore = useTestPointStore()
   ```
3. 在onMounted中调用fetchTestPoints()
4. 实现表格视图：
   - 定义表格列（模块、功能、测试点、优先级、创建人、创建时间、操作列）
   - 实现分页功能
5. 实现卡片视图：
   - 每个卡片展示测试点基本信息
   - 卡片布局美观
6. 实现视图切换逻辑
7. 确保数据正确渲染
8. 添加loading状态

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| testPoint Store | `src/store/testPoint.ts` |
| 项目规范 | `.trae/rules/project_rules.md` |
| TestCaseList参考 | `src/views/case/TestCaseList.vue` |

---

#### 预期成果标准

- 列表正常渲染
- 表格视图正常工作
- 卡片视图正常工作
- 视图切换流畅
- 分页功能正常
- Loading状态正常
- 数据正确显示

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| TestCaseList.vue | `src/views/case/TestCaseList.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T2.6: 实现筛选栏（模块、优先级、创建人、创建时间、关联需求）

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1.5小时 |
| **依赖关系** | T2.5 |
| **时间节点** | Phase2第6个任务 |

---

#### 目标描述

在TestPointList.vue中实现筛选栏功能，支持按模块、优先级、创建人、创建时间、关联需求等条件筛选。

---

#### 具体实施步骤

1. 在TestPointList.vue中添加筛选栏布局（放在统计卡片下方）
2. 实现各筛选条件组件：
   - 模块：el-select，支持输入搜索
   - 优先级：el-select，选项为高/中/低
   - 创建人：el-select或el-input
   - 创建时间：el-date-picker，范围选择
   - 关联需求：el-select
   - 关键词搜索：el-input
3. 实现"重置"和"查询"按钮
4. 实现筛选逻辑：
   - 点击"查询"调用Store的setFilter和fetchTestPoints
   - 点击"重置"清空筛选条件并重新查询
5. 确保筛选栏样式美观，与项目风格一致
6. 实现防抖优化（如需要）

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| testPoint Store | `src/store/testPoint.ts` |
| Element Plus组件 | 项目已安装 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 筛选栏完整
- 各筛选条件正常工作
- 筛选结果正确
- 重置功能正常
- 样式美观
- 用户体验良好

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| TestCaseList.vue筛选栏 | `src/views/case/TestCaseList.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T2.7: 实现新增测试点弹窗

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T2.3 |
| **时间节点** | Phase2第7个任务 |

---

#### 目标描述

实现新增测试点的弹窗组件，包含表单验证、提交等功能。

---

#### 具体实施步骤

1. 在TestPointList.vue中添加新增按钮（页面右上角）
2. 实现新增弹窗（el-dialog）
3. 实现表单（el-form）：
   - 模块：el-input（必填）
   - 功能：el-input（必填）
   - 测试点：el-input（必填）
   - 优先级：el-select（必填）
   - AI提示词：el-input（可选）
4. 添加表单验证（必填字段验证）
5. 实现提交逻辑：
   - 验证表单
   - 调用createTestPoint API
   - 显示成功/失败消息
   - 关闭弹窗
   - 刷新列表
6. 实现取消逻辑
7. 确保样式美观

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| API封装 | `src/api/testPoint.ts` |
| Element Plus组件 | 项目已安装 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 新增弹窗正常显示
- 表单验证完整
- 提交功能正常
- 取消功能正常
- 成功/失败消息显示
- 列表自动刷新
- 样式美观

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目中其他弹窗示例 | 查找项目中其他新增弹窗 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T2.8: 实现编辑测试点弹窗

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T2.3、T2.7 |
| **时间节点** | Phase2第8个任务 |

---

#### 目标描述

实现编辑测试点的弹窗功能，支持数据回填和保存更新。

---

#### 具体实施步骤

1. 在表格操作列添加"编辑"按钮
2. 复用新增弹窗的UI（或创建单独的编辑组件）
3. 实现数据回填：
   - 点击编辑按钮时，加载测试点详情
   - 将数据填充到表单
4. 实现保存逻辑：
   - 验证表单
   - 调用updateTestPoint API
   - 显示成功/失败消息
   - 关闭弹窗
   - 刷新列表
5. 实现取消逻辑
6. 确保样式一致

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| API封装 | `src/api/testPoint.ts` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 编辑弹窗正常显示
- 数据正确回填
- 保存功能正常
- 取消功能正常
- 成功/失败消息显示
- 列表自动刷新
- 样式美观

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目中其他编辑弹窗 | 查找项目中的编辑弹窗示例 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T2.9: 实现删除/批量删除功能

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T2.3 |
| **时间节点** | Phase2第9个任务 |

---

#### 目标描述

实现测试点的单条删除和批量删除功能，包含确认弹窗。

---

#### 具体实施步骤

1. 实现表格多选功能：
   - 添加el-table-column type="selection"
   - 在Store中管理selectedTestPoints
2. 实现批量删除按钮（在页面右上角，仅在有选择项时显示）
3. 实现单条删除按钮（在表格操作列）
4. 实现确认弹窗（el-popconfirm或el-dialog）
5. 实现删除逻辑：
   - 显示确认弹窗
   - 用户确认后调用删除API
   - 显示成功/失败消息
   - 刷新列表
   - 清空选择
6. 确保提示信息清晰

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| API封装 | `src/api/testPoint.ts` |
| testPoint Store | `src/store/testPoint.ts` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 表格多选正常工作
- 批量删除按钮正确显示
- 单条删除按钮正常工作
- 确认弹窗正常显示
- 删除功能正常
- 成功/失败消息显示
- 列表自动刷新
- 选择自动清空

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| TestCaseList删除功能 | `src/views/case/TestCaseList.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T2.10: 列表页统计卡片（总数、高/中/低优先级、已生成用例数）

| 属性 | 内容 |
|------|------|
| **优先级** | 中 |
| **负责人** | 前端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T2.5 |
| **时间节点** | Phase2第10个任务 |

---

#### 目标描述

在测试点列表页添加统计卡片，展示测试点总数、高/中/低优先级数量、已生成用例数等统计数据。

---

#### 具体实施步骤

1. 在TestPointList.vue中添加统计卡片区域（页面顶部，筛选栏上方）
2. 实现统计卡片UI（参考TestCaseList的统计卡片）
3. 实现统计计算逻辑（前端计算或后端返回）：
   - 测试点总数
   - 高优先级数量
   - 中优先级数量
   - 低优先级数量
   - 已生成用例数（如有关联用例数据）
4. 添加点击筛选功能（点击某个统计卡片，自动设置对应的筛选条件）
5. 确保样式美观，与项目一致

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| testPoint Store | `src/store/testPoint.ts` |
| TestCaseList参考 | `src/views/case/TestCaseList.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 统计卡片完整显示
- 统计数据正确
- 点击筛选功能正常
- 样式美观
- 与项目风格一致

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| TestCaseList统计卡片 | `src/views/case/TestCaseList.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

## Phase 3: 路由与菜单配置 (预计 0.5 天)

---

### T3.1: 新增路由配置 (src/router/index.ts)

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T2.1 |
| **时间节点** | Phase3第1个任务 |

---

#### 目标描述

在路由配置中新增测试点列表页的路由，使用懒加载。

---

#### 具体实施步骤

1. 打开 `src/router/index.ts`
2. 在合适的位置新增测试点管理路由：
   ```typescript
   {
     path: '/home/test-point',
     name: 'TestPointList',
     component: () => import('@/views/test-point/TestPointList.vue'),
     meta: {
       title: '测试点管理',
       requiresAuth: true
     }
   }
   ```
3. 确保路由配置正确，meta标签完整
4. 确保使用懒加载（() => import()）

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 路由配置文件 | `src/router/index.ts` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 路由配置正确
- 使用懒加载
- meta标签完整
- 路由跳转正常

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有路由配置 | `src/router/index.ts` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T3.2: 新增菜单配置

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T3.1 |
| **时间节点** | Phase3第2个任务 |

---

#### 目标描述

在侧边栏菜单中新增"测试点管理"菜单项，确保正常显示和跳转。

---

#### 具体实施步骤

1. 查找项目中菜单配置的位置（可能在layout组件、menu组件或配置文件中）
2. 新增"测试点管理"菜单项：
   - 菜单名称：测试点管理
   - 路由路径：/home/test-point
   - 菜单图标：选择合适的icon（如Document或List）
3. 确保菜单配置正确
4. 确保菜单正常显示在侧边栏
5. 确保点击菜单正确跳转

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 菜单配置文件 | 查找项目中的菜单配置位置 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 菜单项正常显示
- 菜单图标正确
- 点击跳转正常
- 菜单位置合理

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 现有菜单配置 | 查找项目中的菜单配置 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T3.3: 原测试点提取页面新增"跳转到列表"入口

| 属性 | 内容 |
|------|------|
| **优先级** | 中 |
| **负责人** | 前端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T3.1 |
| **时间节点** | Phase3第3个任务 |

---

#### 目标描述

在原测试点提取页面（test-point-extract.vue）新增"跳转到测试点列表"的快捷入口。

---

#### 具体实施步骤

1. 打开原测试点提取页面（查找位置）
2. 在页面合适的位置新增按钮：
   - 按钮文本：跳转到测试点列表
   - 按钮样式：合适的样式
   - 点击事件：router.push('/home/test-point')
3. 确保按钮位置合理，不影响原有功能
4. 确保跳转正常

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 原测试点提取页面 | 查找文件位置 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 按钮正常显示
- 点击跳转正常
- 按钮位置合理
- 不影响原有功能

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T3.4: 原需求分析页面新增"跳转到列表"入口

| 属性 | 内容 |
|------|------|
| **优先级** | 中 |
| **负责人** | 前端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T3.1 |
| **时间节点** | Phase3第4个任务 |

---

#### 目标描述

在原需求分析页面新增"跳转到测试点列表"的快捷入口。

---

#### 具体实施步骤

1. 打开原需求分析页面（AnalysisPage.vue）
2. 在页面合适的位置新增按钮：
   - 按钮文本：跳转到测试点列表
   - 按钮样式：合适的样式
   - 点击事件：router.push('/home/test-point')
3. 确保按钮位置合理，不影响原有功能
4. 确保跳转正常

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 原需求分析页面 | `src/views/AnalysisPage.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 按钮正常显示
- 点击跳转正常
- 按钮位置合理
- 不影响原有功能

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| AnalysisPage.vue | `src/views/AnalysisPage.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

## Phase 4: 关系可视化与权限集成 (预计 1~2 天)

---

### T4.1: 实现测试点→测试用例关联弹窗

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1.5小时 |
| **依赖关系** | T1.6、T2.3 |
| **时间节点** | Phase4第1个任务 |

---

#### 目标描述

实现测试点关联测试用例的弹窗，展示该测试点生成的所有测试用例列表，支持跳转到用例详情。

---

#### 具体实施步骤

1. 在TestPointList.vue中实现关联用例弹窗组件
2. 实现弹窗UI：
   - 弹窗标题：关联测试用例
   - 用例列表展示（表格形式）
   - 分页功能
   - 关闭按钮
3. 实现加载关联用例逻辑：
   - 点击"查看用例"按钮时
   - 调用getTestPointTestCases API
   - 显示loading状态
4. 实现跳转到用例详情：
   - 表格中添加"查看详情"链接或按钮
   - 点击跳转到测试用例详情页
5. 确保样式美观，与项目一致

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| API封装 | `src/api/testPoint.ts` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 弹窗正常显示
- 用例列表正常加载
- 分页功能正常
- 跳转到详情正常
- Loading状态正常
- 样式美观

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目中其他弹窗示例 | 查找项目中的弹窗示例 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T4.2: 列表页新增"已生成用例数"列

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T4.1 |
| **时间节点** | Phase4第2个任务 |

---

#### 目标描述

在测试点列表表格中新增"已生成用例数"列，显示每个测试点已生成的测试用例数量，点击可查看关联用例。

---

#### 具体实施步骤

1. 在TestPointList.vue的表格中新增列：
   ```vue
   <el-table-column label="已生成用例数" width="120">
     <template #default="{ row }">
       <el-link type="primary" @click="showTestCases(row)">
         {{ row.test_case_count || 0 }}
       </el-link>
     </template>
   </el-table-column>
   ```
2. 实现showTestCases函数：打开关联用例弹窗
3. 确保数据正确显示（需要后端返回或前端计算）
4. 确保点击事件正常
5. 确保样式美观

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- "已生成用例数"列正常显示
- 数据正确
- 点击事件正常
- 样式美观

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T4.3: 实现单条测试点生成用例功能

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T1.7、T2.3 |
| **时间节点** | Phase4第3个任务 |

---

#### 目标描述

实现单条测试点直接生成测试用例的功能，包含进度展示。

---

#### 具体实施步骤

1. 在表格操作列新增"生成用例"按钮
2. 实现生成用例逻辑：
   - 点击按钮时显示确认弹窗
   - 用户确认后调用batchGenerateTestCases API
   - 显示loading状态或进度
   - 生成完成后显示成功/失败消息
   - 刷新列表（更新test_case_count）
3. 实现进度展示（如需要）
4. 确保用户体验良好

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| API封装 | `src/api/testPoint.ts` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- "生成用例"按钮正常显示
- 确认弹窗正常
- 生成功能正常
- 进度展示正常（如有）
- 成功/失败消息显示
- 列表自动刷新
- 关联关系正确建立

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目中其他AI生成示例 | 查找项目中的AI生成示例 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T4.4: 实现批量测试点生成用例功能

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 前端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T4.3 |
| **时间节点** | Phase4第4个任务 |

---

#### 目标描述

实现批量测试点生成测试用例的功能，复用单条生成的逻辑。

---

#### 具体实施步骤

1. 在页面右上角（批量操作区域）新增"批量生成用例"按钮（仅在有选择项时显示）
2. 实现批量生成逻辑：
   - 点击按钮时显示确认弹窗（显示选择的测试点数量）
   - 用户确认后调用batchGenerateTestCases API
   - 显示loading状态或进度
   - 生成完成后显示成功/失败消息
   - 刷新列表
   - 清空选择
3. 确保与单条生成的风格一致
4. 确保用户体验良好

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| API封装 | `src/api/testPoint.ts` |
| testPoint Store | `src/store/testPoint.ts` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- "批量生成用例"按钮正确显示
- 确认弹窗正常（显示数量）
- 批量生成功能正常
- 进度展示正常
- 成功/失败消息显示
- 列表自动刷新
- 选择自动清空

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目中其他批量操作示例 | 查找项目中的批量操作示例 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T4.5: 权限指令集成（按钮/菜单级权限控制）

| 属性 | 内容 |
|------|------|
| **优先级** | 中 |
| **负责人** | 前端开发 |
| **预计工时** | 1小时 |
| **依赖关系** | T1.8、T1.9 |
| **时间节点** | Phase4第5个任务 |

---

#### 目标描述

在前端集成权限控制，实现按钮级和菜单级的权限隐藏/置灰。

---

#### 具体实施步骤

1. 查找项目中现有的权限指令实现（如v-permission或类似）
2. 在菜单配置中添加权限控制（如需要）
3. 在TestPointList.vue中为按钮添加权限控制：
   - "新增测试点"按钮：test_point:create
   - "编辑"按钮：test_point:update
   - "删除"按钮：test_point:delete
   - "生成用例"按钮：test_point:create（或其他合适权限）
4. 确保权限指令正确应用
5. 验证权限控制正常工作

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 权限指令实现 | 查找项目中的权限指令 |
| TestPointList.vue | `src/views/test-point/TestPointList.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 菜单权限控制正常（如有）
- 按钮权限控制正常
- 无权限时按钮隐藏或置灰
- 权限控制逻辑正确

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目中其他权限示例 | 查找项目中的权限控制示例 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

## Phase 5: 测试与回归 (预计 1~2 天)

---

### T5.1: 功能测试 - 测试点列表页完整功能

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 测试 |
| **预计工时** | 1小时 |
| **依赖关系** | T2.1-T4.5 |
| **时间节点** | Phase5第1个任务 |

---

#### 目标描述

对测试点列表页的所有功能进行完整测试，确保所有功能正常工作，无控制台报错。

---

#### 具体实施步骤

1. 准备测试环境
2. 按checklist逐项测试：
   - 页面加载正常
   - 列表显示正常
   - 视图切换正常
   - 筛选功能正常
   - 新增功能正常
   - 编辑功能正常
   - 删除功能正常
   - 批量删除功能正常
   - 生成用例功能正常
   - 查看关联用例功能正常
   - 统计卡片正常
   - 分页功能正常
3. 检查控制台有无报错
4. 记录测试结果
5. 验证所有功能正常

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 测试环境 | 已准备好的测试环境 |
| 验收清单 | `.trae/specs/test-point-independent-module/checklist.md` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 所有功能正常工作
- 无控制台报错
- 测试记录完整
- 通过验收清单

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 验收清单 | `.trae/specs/test-point-independent-module/checklist.md` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T5.2: 兼容性测试 - 原需求分析页面

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 测试 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T3.4 |
| **时间节点** | Phase5第2个任务 |

---

#### 目标描述

测试原需求分析页面的所有功能，确保兼容性，不影响原有功能。

---

#### 具体实施步骤

1. 打开原需求分析页面（AnalysisPage.vue）
2. 测试原有功能是否正常：
   - 页面加载正常
   - 需求分析功能正常
   - 测试点提取功能正常
   - 其他原有功能正常
3. 测试新增的"跳转到列表"按钮是否正常
4. 检查控制台有无报错
5. 记录测试结果

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 原需求分析页面 | `src/views/AnalysisPage.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 原页面所有功能正常
- 新增跳转按钮正常
- 无控制台报错
- 测试记录完整

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| AnalysisPage.vue | `src/views/AnalysisPage.vue` |
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T5.3: 兼容性测试 - 原测试点提取页面

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 测试 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T3.3 |
| **时间节点** | Phase5第3个任务 |

---

#### 目标描述

测试原测试点提取页面的所有功能，确保兼容性，不影响原有功能。

---

#### 具体实施步骤

1. 打开原测试点提取页面
2. 测试原有功能是否正常：
   - 页面加载正常
   - 测试点提取功能正常
   - 其他原有功能正常
3. 测试新增的"跳转到列表"按钮是否正常
4. 检查控制台有无报错
5. 记录测试结果

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 原测试点提取页面 | 查找文件位置 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 原页面所有功能正常
- 新增跳转按钮正常
- 无控制台报错
- 测试记录完整

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T5.4: 兼容性测试 - 原AI生成用例流程

| 属性 | 内容 |
|------|------|
| **优先级** | 高 |
| **负责人** | 测试 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T4.3、T4.4 |
| **时间节点** | Phase5第4个任务 |

---

#### 目标描述

测试原AI生成用例流程的所有功能，确保兼容性，不影响原有功能。

---

#### 具体实施步骤

1. 测试原有AI生成用例流程是否正常：
   - 从需求分析生成用例
   - 从测试点提取生成用例
   - 其他原有生成方式
2. 验证生成的用例是否正确
3. 检查控制台有无报错
4. 记录测试结果

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 原AI生成用例流程 | 查找原有流程入口 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 原有流程所有功能正常
- 生成的用例正确
- 无控制台报错
- 测试记录完整

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T5.5: 性能测试 - 列表加载响应时间 < 1s

| 属性 | 内容 |
|------|------|
| **优先级** | 中 |
| **负责人** | 测试 |
| **预计工时** | 0.5小时 |
| **依赖关系** | T2.5 |
| **时间节点** | Phase5第5个任务 |

---

#### 目标描述

测试测试点列表页的加载性能，确保响应时间<1秒。

---

#### 具体实施步骤

1. 准备测试数据（创建一定数量的测试点）
2. 打开浏览器开发者工具（Network面板）
3. 访问测试点列表页
4. 记录页面加载时间
5. 记录API响应时间
6. 验证响应时间<1秒
7. 如不达标，分析性能瓶颈并优化

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| 测试环境 | 已准备好的测试环境 |
| 浏览器开发者工具 | Chrome DevTools或其他 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- 页面加载正常
- 响应时间<1秒
- 性能测试记录完整
- 如有瓶颈已优化

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目规范 | `.trae/rules/project_rules.md` |

---

### T5.6: E2E测试 - 完整流程覆盖

| 属性 | 内容 |
|------|------|
| **优先级** | 中 |
| **负责人** | 测试 |
| **预计工时** | 1小时 |
| **依赖关系** | T5.1-T5.5 |
| **时间节点** | Phase5第6个任务，必须完成才能上线 |

---

#### 目标描述

编写和执行E2E测试，覆盖主要的用户流程。

---

#### 具体实施步骤

1. 查找项目中现有的E2E测试框架和示例
2. 编写E2E测试用例，覆盖主要流程：
   - 访问测试点列表页
   - 新增测试点
   - 编辑测试点
   - 筛选测试点
   - 生成测试用例
   - 查看关联用例
   - 删除测试点
3. 执行E2E测试
4. 验证所有测试通过
5. 记录测试结果

---

#### 所需资源清单

| 资源 | 说明 |
|------|------|
| E2E测试框架 | 查找项目中的E2E测试框架 |
| 现有E2E示例 | 查找项目中的E2E测试示例 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

#### 预期成果标准

- E2E测试用例完整
- 所有测试通过
- 测试记录完整
- 主要流程覆盖

---

#### 相关参考资料链接

| 参考 | 文件路径 |
|------|----------|
| 项目中现有E2E测试 | 查找项目中的E2E测试示例 |
| 项目规范 | `.trae/rules/project_rules.md` |

---

## 附录：关键文件清单

| 文件类型 | 文件路径 | 说明 |
|----------|----------|------|
| **后端** | | |
| 模型文件 | `app/models/test_point.py` | TestPoint模型 |
| 模型文件 | `app/models/test_case.py` | TestCase模型 |
| CRUD文件 | `app/crud/test_point.py` | 测试点CRUD |
| API端点 | `app/api/v1/endpoints/test_point*.py` | 测试点API |
| 迁移脚本 | `alembic/versions/` | 数据库迁移 |
| **前端** | | |
| 列表页面 | `src/views/test-point/TestPointList.vue` | 测试点列表页 |
| Store | `src/store/testPoint.ts` | 测试点状态管理 |
| API封装 | `src/api/testPoint.ts` | 测试点API封装 |
| 类型定义 | `src/types/testPoint.ts` | 测试点类型定义 |
| 路由配置 | `src/router/index.ts` | 路由配置 |
| **文档** | | |
| 规划文档 | `.trae/documents/test_point_management_module_plan.md` | 规划方案 |
| Spec文档 | `.trae/specs/test-point-independent-module/spec.md` | 需求规格 |
| 任务清单 | `.trae/specs/test-point-independent-module/tasks.md` | 任务清单 |
| 验收清单 | `.trae/specs/test-point-independent-module/checklist.md` | 验收清单 |
| 详细任务 | `.trae/specs/test-point-independent-module/tasks_detailed.md` | 本文档 |

---

**文档版本** | v1.0
**创建日期** | 2026-04-23
**最后更新** | 2026-04-23
