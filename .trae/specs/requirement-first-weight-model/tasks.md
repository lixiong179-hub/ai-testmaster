# Tasks

- [x] Task 1: 重构 `_build_weight_model()` 函数 — 替代现有的 `source_count` 分支逻辑
  - [x] 1.1 在 `ai_client.py` 中新建 `_build_weight_model(has_ui, has_requirement, has_test_point)` 函数
  - [x] 1.2 实现5种数据源组合场景的权重描述生成（场景1-5）
  - [x] 1.3 每个场景包含：权重百分比、角色定位（核心依据/生成范围/验收标准）、示例
  - [x] 1.4 返回 `(weight_desc, weight_example, weight_warning)` 三元组

- [x] Task 2: 重写 prompt 权重部分和约束条款
  - [x] 2.1 替换 `generate_test_case_enhanced()` 中旧的 `if source_count == 3 / elif == 2 / else` 逻辑为调用 `_build_weight_model()`
  - [x] 2.2 重写"重要约束"部分，增加3条防偏离规则：
    - 功能边界守则：操作必须在需求文档中有对应描述
    - 测试点不越界：不能超出需求功能边界
    - 需求完整性校验：确认覆盖每个主要功能点
  - [x] 2.3 更新各场景的 section 标题标注（如"需求文档(核心依据60%)"而非简单的"功能依据"）

- [x] Task 3: 新增 `_build_weight_model` 单元测试
  - [x] 3.1 测试场景1（三者齐全）：验证返回的 weight_desc 包含 "需求文档.*60%" 或 "核心依据"
  - [x] 3.2 测试场景2（需求+UI）：验证需求75% + UI25%
  - [x] 3.3 测试场景3（需求+测试点）：验证需求70% + 测试点30%
  - [x] 3.4 测试场景4（仅需求）：验证需求100%且包含"逐条覆盖"
  - [x] 3.5 测试场景5（无需求）：验证警告提示包含"缺少需求文档"
  - [x] 3.6 测试边界：全部 False 时返回合理默认值

- [x] Task 4: 运行全量测试确认无回归
  - [x] 4.1 运行 `test_case_edit_features.py` 全部测试
  - [x] 4.2 确认原有 24 个测试全部通过
  - [x] 4.3 确认无语法错误（diagnostics 零错误）

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1]
- [Task 4] depends on [Task 1, Task 2, Task 3]
