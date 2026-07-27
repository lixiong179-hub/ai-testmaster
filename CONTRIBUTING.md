# 贡献指南

感谢参与本项目！请遵循以下规范。

## 开发环境

```bash
# 后端
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head

# 前端
npm ci
npm run dev
```

## 代码规范

### 通用
- 单文件 ≤ 350 行（后端硬性红线，前端力争遵守）
- 行宽 ≤ 120
- 4 空格缩进（前端 TS/Vue 2 空格）
- 公开方法必须加类型注解与文档注释
- 仅注释业务原因与边界场景，禁止无效注释

### Python
- 变量函数 lowerCamelCase，类 UpperCamelCase，常量 UPPER_SNAKE_CASE
- 强制类型注解
- IO 统一 with 管理
- 字符串只用 f-string

### TypeScript/Vue
- 禁用 any，强制空值处理
- 异步统一 async/await
- Vue 组件统一 PascalCase
- API 文件统一 camelCase
- 样式文件统一 .scss

## 提交前检查

```bash
# 后端
ruff check app
pytest tests/api tests/crud tests/services --tb=short -q

# 前端
npm run lint
npx vue-tsc --noEmit
npx vitest run
```

## 提交规范

使用 Conventional Commits：

```
<type>(<scope>): <subject>

<body>
```

- type：feat / fix / docs / style / refactor / perf / test / chore / build / ci
- scope：模块名（如 case、pipeline、execution）
- subject：祈使句，≤ 50 字符

示例：
```
feat(case): 支持批量导出测试用例为 Excel
fix(execution): 修复 N+1 查询导致任务详情加载缓慢
```

## 数据库迁移

新增迁移必须包含 `downgrade` 函数，并通过 `scripts/verify_migrations.py` 验证：

```bash
python scripts/verify_migrations.py --check-downgrade --last   # PR CI
python scripts/verify_migrations.py --full                     # 日常 CI
```

迁移文件命名规范（新文件必须遵守）：
```
<YYYYMMDD_HHMM>-<revision_id>_<slug>.py
```

## PR 流程

1. 从 `develop` 切出特性分支 `feature/<scope>-<topic>`
2. 完成开发并补充测试（核心分支覆盖率 ≥ 95%）
3. 本地通过所有检查
4. 提交 PR 至 `develop`，等待 CR 通过与 CI 全绿
5. 合并后删除特性分支

## 行为准则

保持专业、尊重、建设性的讨论风格。
