# 现有用例质量基线报告

> 采集时间：2026-05-01 16:24:22
> 相似度阈值：0.85（基于标题文本的 SequenceMatcher 相似度）

---

## 汇总

| 指标 | 值 |
|------|----|
| 项目数 | 1 |
| 用例总数 | 1 |
| 人工评审通过率 | N/A（无评审记录） |
| 执行通过率 | N/A（无执行记录） |
| 平均步骤数 | 1.00 |
| 用例修改率 | 0.0% |
| 相似用例比率 | 0.0% |

---

## 按项目明细

### 测试项目（ID=100417）

| 指标 | 值 |
|------|----|
| 用例总数 | 1 |
| 人工评审通过率 | N/A（已评审0/1） |
| 执行通过率 | N/A（已执行0次） |
| 平均步骤数 | 1.0 |
| 用例修改率 | 0.0% |
| 相似用例对数 | 0（占0.0%） |
| CodeReview 记录数 | 0 |

**模块分布**：
> 链接管理模块(1)

---

## 指标说明

| 指标 | 计算方式 | 数据来源 |
|------|----------|----------|
| 用例总数 | `COUNT(*) WHERE project_id = ? AND is_deleted = 0` | test_cases |
| 人工评审通过率 | `approved / (approved + rejected + needs_optimization) * 100` | test_cases.review_status |
| 执行通过率 | `passed / total * 100` | test_case_executions.status |
| 平均步骤数 | `AVG(LEN(steps_json))` | test_cases.steps_json |
| 用例修改率 | `(update_time > create_time) / total * 100` | test_cases |
| 相似用例比率 | 标题 SequenceMatcher >= 0.85 / total * 100 | test_cases.title |
