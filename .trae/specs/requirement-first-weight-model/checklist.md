# Checklist

## Task 1: `_build_weight_model()` 函数
- [x] 函数签名正确：接收 `has_ui, has_requirement, has_test_point` 三个 bool 参数
- [x] 返回三元组 `(weight_desc, weight_example, weight_warning)`
- [x] 场景1（三者齐全）：weight_desc 包含 "60%" 需求权重标注
- [x] 场景1（三者齐全）：需求文档角色为"核心依据"，测试点为"生成范围"，UI为"验收标准"
- [x] 场景2（需求+UI）：需求75% + UI25%
- [x] 场景3（需求+测试点）：需求70% + 测试点30%，强调"不能超出需求边界"
- [x] 场景4（仅需求）：100% + "逐条覆盖每个功能点"
- [x] 场景5（无需求）：包含"缺少需求文档可能导致偏离"警告
- [x] 全部 False 时返回合理默认值不报错

## Task 2: Prompt 权重重写
- [x] 旧的 `source_count == 3/2/else` 分支逻辑已被替换为 `_build_weight_model()` 调用
- [x] prompt 中数据源 section 标题动态显示（有则带角色标注，无则标"未提供"）
- [x] 约束条款包含"功能边界守则"：操作必须在需求中有对应描述
- [x] 约束条款包含"测试点不越界"：不能超出需求功能边界
- [x] 约束条款包含"需求完整性校验"：确认覆盖每个主要功能点
- [x] 约束条款总数 >= 10 条

## Task 3: 单元测试
- [x] 测试文件中新增 `TestBuildWeightModel` 类
- [x] 至少5个场景测试用例（对应5种数据源组合）
- [x] 边界测试（全部False）
- [x] 所有新测试通过 (8 passed)

## Task 4: 回归验证
- [x] 原有 91 个测试全部通过（0 failed）
- [x] ai_client.py diagnostics 零错误
- [x] 无 SyntaxError 或 ImportError
