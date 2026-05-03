# 测试数据标注集

## 概述

为 M3 阶段 Pipeline 质量回归与 M4 先验/后验质量分验证提供基准数据集。
三个项目覆盖全部核心场景，数据以 JSON 文件形式存储于各项目子目录，
通过 `scripts/prepare_test_data.py` 幂等导入测试数据库。

## 项目矩阵

| 项目 | 目录 | 场景 | 输入信号 | 标注内容 |
|---|---|---|---|---|
| Alpha | `project_alpha/` | 1（全输入新项目） | PRD + 测试点 + UI | 预期用例 |
| Beta | `project_beta/` | 4（旧项目双向扫描） | 50 历史用例 + 新 PRD + UI 变更 | 预期 verdicts |
| Gamma | `project_gamma/` | 3（仅 UI 新项目） | UI 原型 | 预期反推能力 |

## 文件清单

### project_alpha/

| 文件 | 用途 |
|---|---|
| `project.json` | 项目元数据（名称、类型、描述） |
| `prd.json` | PRD 需求描述，按模块分段 |
| `test_points.json` | 测试点列表 |
| `ui_prototype.json` | UI 原型屏信息 |
| `expected_cases.json` | 预期生成的测试用例 |

### project_beta/

| 文件 | 用途 |
|---|---|
| `project.json` | 项目元数据 |
| `historical_cases.json` | 50 条历史用例（case_no, title, module, steps_json, summary） |
| `new_prd.json` | 新的 PRD 需求变更 |
| `ui_changes.json` | UI 变更描述 |
| `expected_verdicts.json` | 50 条预期 verdict 标注 |

### project_gamma/

| 文件 | 用途 |
|---|---|
| `project.json` | 项目元数据 |
| `ui_prototype.json` | UI 原型屏信息 |
| `expected_inference.json` | 预期的反推业务能力 |

## expected_verdicts.json 格式

```json
[
  {
    "case_no": "HIST-001",
    "verdict": "VALID|NEEDS_MODIFY|DEPRECATE|MERGE|NEW",
    "confidence": 0.95,
    "note": "判定依据说明"
  }
]
```

## expected_inference.json 格式

```json
[
  {
    "name": "用户登录",
    "key": "user_login",
    "description": "用户通过凭证登录系统",
    "confidence": 0.9,
    "supporting_evidence": "登录页面包含用户名、密码输入框和登录按钮"
  }
]
```

## expected_cases.json 格式

每个条目包含：`title`, `module`, `precondition`, `steps`, `expected_result`, `priority`, `case_type`。

## 导入脚本

```bash
python scripts/prepare_test_data.py [--project alpha|beta|gamma|all]
```
幂等操作：先删除该项目已有数据，再从 JSON annotations 插入。
