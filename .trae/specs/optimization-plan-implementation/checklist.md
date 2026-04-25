# Checklist

## M1 · 急救包（P0）

### T1: 重定义 coverage 指标
- [ ] `coverage_mixin.py` 新增 `requirement_coverage` 计算（基于 test_point_id 命中）
- [ ] `coverage_mixin.py` 新增 `ui_element_coverage` 计算（基于 target_element 命中 UI Spec elements）
- [ ] `analyzer_mixin.py` 传入 project 上下文以获取需求/UI 数据
- [ ] 加权公式 `requirement_coverage × 0.5 + ui_element_coverage × 0.3 + locator_coverage × 0.2` 实现正确
- [ ] 向后兼容退化逻辑（缺 requirement/ui_spec 时退化为 locator-only）
- [ ] `suggestion_mixin._generate_optimization_suggestions` 根据新维度重写建议文案
- [ ] `GET /cases/{id}/quality` 返回三维度分解数据
- [ ] 测试用例覆盖率 ≥ 95%（正常/空值/异常/边界）
- [ ] 创建含 1 个需求文档 + 3 张 UI 原型的测试项目，生成 5 条用例，综合分应 ≥ 70
- [ ] 旧用例重新跑分不崩溃

### T2: 打通 UI 原型 → 测试点提取链路
- [ ] `ai_analysis_service.py` 新增 `extract_test_points_from_ui_specs(screen_ids)` 方法
- [ ] 新端点 `POST /test-point/extract-from-ui` 可正常调用
- [ ] UI 提取 Prompt 模板已添加
- [ ] 前端 `TestPointExtractDialog.vue` 增加"从 UI 原型提取"Tab
- [ ] 项目只上传 3 张 UI 原型、未上传需求文档时，ExtractDialog 能拉出 ≥ 5 条测试点建议
- [ ] 保存后进入 ai-generate 的 batch 生成流程能正常完成

### T3: 修复批量解析越权风险
- [ ] `parse_endpoints.py` 全量校验 screen_ids 项目归属
- [ ] 构造含他人 screen_id 的请求返回 403
- [ ] 正常批量解析请求通过校验
- [ ] 单元测试覆盖安全场景

### T4: 修复 Windows 下路径白名单
- [ ] `config.py` 新增 `UI_PROTOTYPE_DIR` 配置项
- [ ] `core_mixin._read_image_file` 使用 `pathlib.Path.resolve()` 做前缀校验
- [ ] Windows / Linux 下 vision 模式解析均通过
- [ ] 路径穿越测试（`../../etc/passwd`）仍被拦截

### T5: 合并需求上传入口 + 多文件批量
- [ ] 后端 `POST /file/batch-upload` 端点可用
- [ ] `RequirementUploader.vue` 组件支持拖拽 + 批量 + 预览 + resource_type 下拉
- [ ] 单次拖入 10 个混合类型文件（doc/pdf/png），一次请求上传完，resource_type 自动识别正确
- [ ] 三个页面上传 UI 视觉一致、表现一致
- [ ] magic 校验、路径隔离、size 限制等校验规则不降级

## M2 · 架构瘦身（P1）

### T6: 合并 endpoints 文件
- [ ] test_point 子模块合并完成（test_point.py + test_point_extract.py）
- [ ] test_case_ai 子模块合并完成（test_case_ai.py + test_case_ai_stream.py）
- [ ] 所有 URL path 不变
- [ ] `main.py` 中 `include_router` 顺序正确
- [ ] 回归测试通过

### T7: 统一 PromptBuilder
- [ ] `app/services/prompt_builder.py` 新建，`PromptBuilder` 类定义完整
- [ ] `for_test_case(mode='graph'|'linear')` 入口可用
- [ ] `for_test_point_extraction()` 入口可用
- [ ] `for_ui_extraction()` 入口可用
- [ ] UI Spec 格式化函数唯一（无重复逻辑）
- [ ] 所有调用方迁移到新 PromptBuilder
- [ ] 旧 Prompt 构建文件已删除
- [ ] 各模式 Prompt 输出与旧逻辑一致

### T8: 拆分 ai-generate.vue
- [ ] E2E 冒烟测试（创建项目→生成→保存）已编写并作为回归基线
- [ ] `stores/useGenerateStore.ts` 已创建（formData / contextPreview / generatedCases 集中管理）
- [ ] `ContextSelectPanel.vue` 已抽取
- [ ] `FlowSortEditor.vue` 已接入 Pinia Store
- [ ] `GeneratePreviewPanel.vue` 已抽取
- [ ] 主视图 `ai-generate.vue` ≤ 500 行
- [ ] E2E 回归测试通过，功能不变

### T9: 删除旧向导页
- [ ] `test-point-extract.vue` 路由已下线
- [ ] `test-point-extract.vue` 文件已删除
- [ ] 入口统一为 `test-point-management/ExtractDialog`
- [ ] 过渡提示已添加

### T10: iteration_id 去哨兵值
- [ ] 后端模型改为 `Optional[int]`
- [ ] 前端发送 `undefined` / 省略字段，不再做 `0→-1` 转换
- [ ] 数据库迁移脚本已编写（事务中完成，带唯一迁移版本号）
- [ ] 迁移回滚脚本已编写
- [ ] `UPDATE project_file SET iteration_id=NULL WHERE iteration_id=-1` 执行成功
- [ ] 测试用例覆盖（正常/空值/迁移前后）

## M3 · 体验升级（P2）

### T11: 项目工作台页
- [ ] `GET /projects/{id}/workspace-summary` 端点可用（缓存 TTL 30s）
- [ ] 工作台页面展示需求数、UI 解析进度条、测试点数、用例数、质量分、"下一步建议"按钮

### T12: few-shot 强化 Prompt
- [ ] test_data 的 normal/boundary/abnormal 各有 1 个示例
- [ ] 目标空值率 < 20%

### T13: 冗余度算法升级
- [ ] TF-IDF 向量化实现完成
- [ ] 余弦相似度计算实现完成
- [ ] 阈值按项目规模动态调整
- [ ] 测试用例覆盖

### T14: 测试点聚类后生成
- [ ] K-means 或层次聚类实现完成（共享 T13 向量化）
- [ ] 相近测试点合并为一条数据驱动用例
- [ ] AI 调用数减少
- [ ] 测试用例覆盖

### T15: N² 查询修复
- [ ] `analyze_project_quality` 预取 `all_cases` 传给每次 analyzer
- [ ] 项目级缓存一次嵌入向量
- [ ] 性能测试验证无 N² 查询

### T16: 清理调试产物
- [ ] `captcha_debug_*.png` 已删除
- [ ] `ai_response_debug.txt` 已删除
- [ ] `ocr_debug.log` 已删除
- [ ] `.gitignore` 已扩展

### T17: UI 解析进度真 SSE
- [ ] `parse_endpoints` 增加 `/stream` 版本
- [ ] 单屏/批量都推送 progress
- [ ] 前端换掉 `setInterval` 模拟

### T18: action_type 中英文/同义词
- [ ] `infer_action_type` 关键词表扩展（中英文 + 同义词）
- [ ] `steps_mixin` 关键词表扩展
- [ ] 单测覆盖

### T19: flow_sort token 保护
- [ ] PromptBuilder 在 `nodes > 阈值` 时做概要化
- [ ] 保留主流程完整，分支/异常只保留名称

### T20: precondition 语义放宽
- [ ] 识别需求文档含"注册"/"登录"等关键词的场景
- [ ] AI 允许把登录写成可测步骤
- [ ] 输出校验层兼容两种模式

## 项目开发规范合规检查

- [ ] 所有 Python 文件变量函数 lowerCamelCase，类 UpperCamelCase，常量 UPPER_SNAKE_CASE
- [ ] 所有 Python 文件 4 空格缩进，行宽 ≤ 120
- [ ] 所有 Python 公开方法有类型注解与文档注释
- [ ] Python 强制类型注解，IO 统一 with 管理，字符串只用 f-string
- [ ] TS 禁用 any，强制空值处理，异步统一 async/await
- [ ] 单文件 ≤ 300 行（T8 主视图 ≤ 500 行例外）
- [ ] SQL 仅用参数化/列表传参
- [ ] 密钥禁用硬编码，统一环境变量读取
- [ ] 所有外部输入经过模型校验
- [ ] 禁止循环内执行 SQL
- [ ] 核心分支覆盖率 ≥ 95%
- [ ] 禁止 TODO 与空占位
- [ ] IO/网络/解析强制异常捕获
- [ ] 库表变更附带迁移与回滚
