# Alembic 迁移规范

## 命名规范

**新文件必须遵守**以下命名格式（不可重命名已存在文件，会破坏 alembic 历史）：

```
<YYYYMMDD_HHMM>-<revision_id>_<slug>.py
```

示例：
```
20260727_1430-a1b2c3d4e5f6_add_self_healing_audits.py
```

### 历史命名风格（已废弃，不再使用）

项目中存在三种历史命名风格，**仅为兼容已存在迁移**，新增迁移不得使用：

| 风格 | 示例 | 状态 |
|---|---|---|
| 无日期前缀 | `add_ai_call_log.py` | 已废弃 |
| 日期前缀 | `20260627_add_xxx.py` | 已废弃 |
| 完整格式 | `2026_06_09_1034-54cbd326407e_add_xxx.py` | 推荐（与新版规范等价） |

## 创建新迁移

```bash
# 自动生成（推荐）
alembic revision --autogenerate -m "add self healing audits"

# 手动创建
alembic revision -m "add self healing audits"
```

创建后请重命名为上述规范格式（保留 revision id）。

## 必备内容

每个迁移文件必须包含：

1. `revision` 与 `downgrade_revision` 链路
2. `upgrade()` 函数
3. `downgrade()` 函数（**必须**，不可省略）

## 验证

```bash
# 仅验证最新迁移的 downgrade（PR CI 用）
python scripts/verify_migrations.py --check-downgrade --last

# 验证全量迁移链路（日常 CI 用）
python scripts/verify_migrations.py --full
```

## 注意事项

- 不要修改已发布迁移的 `revision` 或 `downgrade_revision`
- 不要删除已发布迁移文件
- 多分支并行开发产生分叉时，使用 `alembic merge` 创建合并迁移
- 大表变更（加列、加索引）需评估锁表影响，必要时使用 `op.batch_alter_table`
