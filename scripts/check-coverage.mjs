/**
 * 覆盖率门槛校验
 *
 * vitest 0.34 的 `coverage.thresholds` 在同版本中存在未生效的问题，
 * 因此改为在跑完覆盖率后解析 json-summary 报告自行校验，保证 CI 可阻断。
 *
 * 用法：npm run test:coverage
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const SUMMARY_PATH = resolve(process.cwd(), 'coverage/coverage-summary.json')

/**
 * 覆盖率门槛（%），随测试补充逐步上调。
 * 当前实测：行 69.34 / 语句 69.34 / 函数 71.73 / 分支 85.78，
 * 门槛保留约 3 个点的波动余量。
 */
const THRESHOLDS = {
  lines: 66,
  statements: 66,
  functions: 69,
  branches: 84,
}

const LABELS = {
  lines: '行',
  statements: '语句',
  functions: '函数',
  branches: '分支',
}

let summary
try {
  summary = JSON.parse(readFileSync(SUMMARY_PATH, 'utf8'))
} catch {
  console.error(`[coverage] 未找到覆盖率摘要：${SUMMARY_PATH}`)
  console.error('[coverage] 请先执行 `npm run test:coverage`')
  process.exit(1)
}

const total = summary.total ?? {}
let failed = false

for (const [key, min] of Object.entries(THRESHOLDS)) {
  const pct = Number(total[key]?.pct ?? 0)
  const passed = pct >= min
  if (!passed) failed = true
  console.log(`${passed ? '✓' : '✗'} ${LABELS[key]}覆盖率 ${pct}%（门槛 ${min}%）`)
}

if (failed) {
  console.error('[coverage] 覆盖率未达门槛，请补充测试或确认门槛是否需要调整')
  process.exit(1)
}

console.log('[coverage] 覆盖率检查通过')
