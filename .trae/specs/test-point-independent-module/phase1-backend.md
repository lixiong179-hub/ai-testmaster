# Phase 1: 后端数据模型与API（11个任务）

---

## T1.1: 数据库模型改造 - TestPoint新增created_by字段

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 后端开发 |
| **预计工时** | 0.5 小时 |
| **依赖关系** | T0.2 |
| **时间节点** | Phase1 第1个任务，必须在T1.3前完成 |

---

### 目标描述

在TestPoint数据模型中新增`created_by`字段，用于记录测试点的创建人。该字段可空，以确保历史数据兼容性。

---

### 具体实施步骤

1. **打开并编辑模型文件**
   - 打开 `app/models/test_point.py`
   - 在 `TestPoint` 类中新增字段定义
   - 建议位置：放在 `create_time` 字段附近

2. **字段定义代码**
   ```python
   created_by = Column(String(100), nullable=True, comment="创建人用户名")
   ```

3. **验证修改**
   - 检查无需新增导入（String/Column已存在）
   - 确认字段类型正确（String(100)足够存储用户名）
   - 确认nullable=True（历史数据兼容）
   - 确认有中文注释

4. **验证模型导入**
   - 运行 `python -c "from app.models.test_point import TestPoint; print('Model OK')"`
   - 确认无导入错误

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| 源代码文件 | `app/models/test_point.py` |
| 参考模型 | `app/models/test_case.py` - 查看如何定义类似字段 |
| 项目规范 | `.trae\rules\project_rules.md` |

---

### 预期成果标准（可量化）

- [ ] 字段定义完整：包含类型、约束、注释
- [ ] 遵循项目代码规范：变量命名lowerCamelCase
- [ ] 字段设置为可空（nullable=True）
- [ ] 模型导入验证通过：无语法或导入错误

---

---

## T1.2: 数据库模型改造 - TestCase新增test_point_id字段

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 后端开发 |
| **预计工时** | 0.5 小时 |
| **依赖关系** | T0.2 |
| **时间节点** | Phase1 第2个任务，必须在T1.3前完成 |

---

### 目标描述

在TestCase数据模型中新增`test_point_id`字段，建立TestCase与TestPoint的直接关联关系。

---

### 具体实施步骤

1. **打开并编辑模型文件**
   - 打开 `app/models/test_case.py`
   - 在 `TestCase` 类中新增外键字段

2. **字段定义代码**
   ```python
   test_point_id = Column(
       Integer, 
       ForeignKey("test_points.id", ondelete="SET NULL"), 
       nullable=True, 
       index=True, 
       comment="关联测试点ID"
   )
   ```

3. **添加relationship关系**
   ```python
   test_point = relationship("TestPoint", backref="test_cases")
   ```

4. **验证修改并导入测试**

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| 源代码文件 | `app/models/test_case.py` |
| TestPoint模型 | `app/models/test_point.py` |
| 项目规范 | `.trae\rules\project_rules.md` |

---

### 预期成果标准（可量化）

- [ ] 外键字段定义完整：包含类型、约束、外键关系
- [ ] relationship关系正确配置
- [ ] 字段设置为可空（nullable=True）
- [ ] 模型导入验证通过

---

---

## T1.3: 编写Alembic数据库迁移脚本

| 属性 | 内容 |
|------|------|
| **优先级** | 🔴 高 |
| **负责人** | 后端开发 |
| **预计工时** | 1 小时 |
| **依赖关系** | T1.1, T1.2 |
| **时间节点** | Phase1 第3个任务 |

---

### 目标描述

创建Alembic数据库迁移脚本，实现字段新增和完整的回滚逻辑。

---

### 具体实施步骤

1. **生成迁移脚本**
   ```bash
   alembic revision --autogenerate -m "Add created_by to test_points and test_point_id to test_cases"
   ```

2. **检查并完善迁移脚本**
   - 确认upgrade()包含两个新字段和index
   - 确认downgrade()包含完整回滚逻辑

3. **在测试环境验证迁移**
   ```bash
   alembic upgrade head
   # 验证变更正确
   alembic downgrade -1
   # 再次升级确认
   alembic upgrade head
   ```

---

### 所需资源清单

| 资源 | 说明 |
|------|------|
| Alembic配置 | `alembic.ini` |
| 迁移目录 | `alembic/versions/` |
| 项目规范 | `.trae\rules\project_rules.md` |

---

### 预期成果标准（可量化）

- [ ] 迁移脚本文件正确生成
- [ ] upgrade()和downgrade()函数完整
- [ ] 测试环境迁移验证通过
- [ ] 迁移文件已加入Git

---

---

## T1.4-T1.11: 其他任务摘要

完整的Phase1剩余8个任务包括：
- T1.4: 完善test_point CRUD - 新增筛选条件
- T1.5: 新增CRUD - 获取测试点关联的测试用例
- T1.6: 完善后端Schema - 新增测试点相关Schema
- T1.7: 新增查询API - 获取测试点关联的测试用例
- T1.8: 新增/完善API - 测试点列表查询
- T1.9: 新增权限点定义与权限系统集成
- T1.10: 新增/完善API - 批量生成测试用例
- T1.11: 后端单元测试编写（覆盖率≥95%）

---

### 后端单元测试验收标准（可量化）

- [ ] 单元测试覆盖所有新增功能
- [ ] 测试覆盖正常、空值、异常、边界场景
- [ ] 所有测试通过
- [ ] 测试覆盖率 ≥95%

---

### 相关参考资料

| 参考 | 文件路径 |
|------|---------|
| 项目规范 | `.trae\rules\project_rules.md` |
| Alembic文档 | https://alembic.sqlalchemy.org/ |
