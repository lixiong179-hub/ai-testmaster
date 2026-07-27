# 下一步行动计划

## 一、遗漏建议清单

### 高优先级（必须完成）

| 序号 | 建议内容 | 影响范围 | 目标 |
|------|----------|----------|------|
| 1 | 安装 @vue/test-utils 补充前端组件测试 | 前端质量 | EdgeConditionDialog 测试覆盖≥95% |
| 2 | 补充 PromptBuilder 单元测试 | 后端质量 | build_graph_prompt/build_linear_prompt 覆盖 |
| 3 | 补充 API 端点集成测试（graph模式） | 接口质量 | 验证流式/非流式端点 graph 分支 |

### 中优先级（建议完成）

| 序号 | 建议内容 | 影响范围 | 目标 |
|------|----------|----------|------|
| 4 | 编写 CHANGELOG.md 记录所有变更 | 文档规范 | 完整记录功能变更、修复、优化 |
| 5 | 流式端点压力测试 | 性能 | 验证 SSE 高并发稳定性 |
| 6 | 前端 E2E 测试（Cypress） | 端到端 | 流程图编辑器完整交互验证 |

---

## 二、实施计划

### Phase 1: 测试补充（2h）

**责任人:** 开发工程师
**完成时限:** 2026-04-21

#### 1.1 安装 @vue/test-utils
```bash
cd frontend && npm install --save-dev @vue/test-utils@2
```

#### 1.2 补充 EdgeConditionDialog 组件测试
- 测试文件: `src/components/case/__tests__/EdgeConditionDialog.spec.ts`
- 覆盖场景: 创建/编辑/取消/重置/条件标签切换

#### 1.3 补充 PromptBuilder 单元测试
- 测试文件: `tests/test_prompt_builder.py`
- 覆盖场景: build_graph_prompt（空数据/主干/全类型/无效source）、build_linear_prompt

#### 1.4 补充 API 端点集成测试
- 测试文件: `tests/test_api_ai_enhanced_graph.py`
- 覆盖场景: graph模式请求/响应、流式SSE推送、请求体大小限制

### Phase 2: 文档编写（0.5h）

**责任人:** 开发工程师
**完成时限:** 2026-04-21

#### 2.1 编写 CHANGELOG.md
- 记录所有新增功能、bug修复、优化改进
- 遵循 Keep a Changelog 格式

### Phase 3: 验证（0.5h）

**责任人:** 开发工程师
**完成时限:** 2026-04-21

#### 3.1 全量测试执行
```bash
# Python
pytest tests/test_flow_tree_mixin.py tests/test_flow_sort_schema.py tests/test_prompt_builder.py tests/test_api_ai_enhanced_graph.py -v

# TypeScript
npx vue-tsc --noEmit

# 前端组件测试
npm run test
```

#### 3.2 文档完整性检查
- 技术设计文档是否更新
- CHANGELOG 是否完整
- 代码注释是否规范

---

## 三、开发规范要求

### 代码风格
- Python: 4空格缩进，行宽≤120，强制类型注解
- TS: 禁用any，强制空值处理，异步统一async/await

### 测试规范
- 核心分支覆盖率≥95%
- 正常、空值、异常、边界用例全覆盖
- 使用真实测试库，执行后自动清理

### 文档规范
- 公开方法必须加类型注解与文档注释
- 只注释业务原因与边界场景，禁止无效注释
- 变更必须记录到 CHANGELOG

### 安全规范
- 所有外部输入必须经过模型校验
- 请求体大小限制（nodes≤100, edges≤200）
- 日志脱敏敏感字段

---

## 四、验收标准

| 检查项 | 验收标准 | 验证方式 |
|--------|----------|----------|
| TypeScript类型检查 | 0 errors | `vue-tsc --noEmit` |
| Python单元测试 | 全部通过 | `pytest tests/` |
| 前端组件测试 | 全部通过 | `npm run test` |
| 代码覆盖率 | ≥95% | `pytest --cov` |
| 文档完整性 | CHANGELOG + 技术设计 | 人工检查 |
