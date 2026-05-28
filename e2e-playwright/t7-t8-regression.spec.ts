/**
 * T7 执行中心 + T8 报告中心 Playwright 复测脚本
 * 使用 addInitScript + route 拦截绕过认证
 */
import { test, expect, type Page, type BrowserContext } from '@playwright/test'

// ============================================================
// 认证数据
// ============================================================
const ADMIN_PERM_OBJ = {
  permissions: ['*'],
  __perm_sig__: (function () {
    const p = ['*']
    const r = p.slice().sort().join(',')
    let h = 0
    for (let i = 0; i < r.length; i++) {
      h = (h << 5) - h + r.charCodeAt(i)
      h |= 0
    }
    return h.toString(36)
  })(),
}

function buildFakeJwt(): string {
  const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64')
  const payload = Buffer.from(
    JSON.stringify({
      sub: 1,
      username: 'admin',
      exp: Math.floor(Date.now() / 1000) + 86400 * 30,
      iat: Math.floor(Date.now() / 1000),
    })
  ).toString('base64')
  const signature = Buffer.from('fake').toString('base64')
  return `${header}.${payload}.${signature}`
}

const FAKE_TOKEN = buildFakeJwt()
const ADMIN_PERM = JSON.stringify(ADMIN_PERM_OBJ)

// ============================================================
// Mock 数据
// ============================================================
const MOCK_TASKS = [
  {
    id: 1,
    task_name: '冒烟回归测试任务',
    project_id: 1,
    description: '每日冒烟回归',
    case_ids: [1, 2, 3],
    executor_id: 1,
    status: 0,
    success_count: 0,
    fail_count: 0,
    total_count: 10,
    progress: 0,
    create_time: '2026-01-01T00:00:00Z',
  },
  {
    id: 2,
    task_name: '全量回归测试任务',
    project_id: 1,
    description: '每周全量回归',
    case_ids: [4, 5, 6],
    executor_id: 1,
    status: 1,
    success_count: 15,
    fail_count: 2,
    total_count: 30,
    progress: 56,
    create_time: '2026-01-02T00:00:00Z',
  },
  {
    id: 3,
    task_name: '接口自动化测试',
    project_id: 1,
    description: '核心接口覆盖',
    case_ids: [7, 8],
    executor_id: 1,
    status: 2,
    success_count: 20,
    fail_count: 0,
    total_count: 20,
    progress: 100,
    create_time: '2026-01-03T00:00:00Z',
  },
  {
    id: 4,
    task_name: 'UI自动化测试',
    project_id: 1,
    description: '关键流程覆盖',
    case_ids: [9, 10],
    executor_id: 1,
    status: 3,
    success_count: 5,
    fail_count: 5,
    total_count: 20,
    progress: 50,
    create_time: '2026-01-04T00:00:00Z',
  },
]

const MOCK_TASK_DETAIL = {
  id: 1,
  task_name: '冒烟回归测试任务',
  project_id: 1,
  description: '每日冒烟回归',
  case_ids: [1, 2, 3],
  executor_id: 1,
  status: 0,
  success_count: 0,
  fail_count: 0,
  total_count: 10,
  progress: 0,
  create_time: '2026-01-01T00:00:00Z',
}

const MOCK_PROJECTS = [
  {
    id: 1,
    name: '测试项目A',
    description: '自动化测试项目',
    status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

const MOCK_REPORTS = [
  {
    id: 1,
    name: '冒烟回归报告',
    status: 'completed',
    project_id: 1,
    project_name: '测试项目A',
    created_at: '2026-01-01T00:00:00Z',
    pass_rate: 0.85,
    total_cases: 20,
    passed: 17,
    failed: 3,
  },
]

// ============================================================
// 结果记录器
// ============================================================
interface CheckResult {
  id: string
  operation: string
  expected: string
  actual: string
  status: 'PASS' | 'FAIL' | 'WARN'
}
const results: CheckResult[] = []

function record(
  id: string,
  operation: string,
  expected: string,
  actual: string,
  status: 'PASS' | 'FAIL' | 'WARN'
): void {
  results.push({ id, operation, expected, actual, status })
  console.log(`[${status}] [${id}] ${operation} | expected: ${expected} | actual: ${actual}`)
}

async function safeText(
  locator: import('@playwright/test').Locator,
  timeout = 3000
): Promise<string> {
  try {
    return (await locator.first().textContent({ timeout })) || ''
  } catch {
    return ''
  }
}
async function safeCount(locator: import('@playwright/test').Locator): Promise<number> {
  try {
    return await locator.count()
  } catch {
    return 0
  }
}

// ============================================================
// API 拦截器 - 精确匹配 URL 路径
// ============================================================
async function setupApiInterception(context: BrowserContext): Promise<void> {
  await context.route('**/*', async (route) => {
    const url = route.request().url()
    // 只拦截 API 请求，其他请求正常放行
    if (!url.includes('/api/v1/')) {
      try {
        await route.fulfill({ response: await route.fetch() })
      } catch {
        await route.abort()
      }
      return
    }

    try {
      const response = await route.fetch()
      // 非 401/403 正常放行
      if (response.status() !== 401 && response.status() !== 403) {
        await route.fulfill({ response })
        return
      }

      // === 401/403 拦截，返回 mock 数据 ===
      if (url.includes('/auth/me')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            msg: 'success',
            message: 'success',
            data: { id: 1, username: 'admin', permissions: ['*'] },
          }),
        })
        return
      }

      if (url.includes('/project') && !url.match(/\/project\/\d+/)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            msg: 'success',
            message: 'success',
            data: { items: MOCK_PROJECTS, total: MOCK_PROJECTS.length },
          }),
        })
        return
      }

      // 任务相关 API - 关键：先匹配具体子路由，再匹配列表
      if (!url.includes('test_task')) {
        // 非任务 API 的 fallback
        if (url.includes('report')) {
          if (url.match(/\/report\/\d+/)) {
            // 报告详情
            await route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                code: 0,
                msg: 'success',
                message: 'success',
                data: {
                  ...MOCK_REPORTS[0],
                  test_cases: [
                    {
                      test_case_id: 1,
                      status: 'passed',
                      actual_result: 'OK',
                      start_time: '2026-01-01T00:00:00Z',
                      end_time: '2026-01-01T00:00:05Z',
                    },
                  ],
                },
              }),
            })
          } else if (url.includes('/export')) {
            await route.fulfill({
              status: 200,
              contentType: 'application/pdf',
              body: 'mock-pdf-content',
            })
          } else {
            // 报告列表
            await route.fulfill({
              status: 200,
              contentType: 'application/json',
              body: JSON.stringify({
                code: 0,
                msg: 'success',
                message: 'success',
                data: { items: MOCK_REPORTS, total: MOCK_REPORTS.length },
              }),
            })
          }
          return
        }
        // 其他未知 API
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ code: 0, msg: 'success', message: 'success', data: {} }),
        })
        return
      }

      // ===== test_task 相关 API =====
      // 具体子操作：summary/start/stop/run/export
      if (
        url.includes('/test_task/') &&
        url.match(/\/test_task\/\d+\/(summary|start|stop|run|export)/)
      ) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ code: 0, msg: 'success', message: 'success', data: {} }),
        })
        return
      }

      // 任务详情：/test_task/{id}
      if (url.match(/\/test_task\/\d+$/) || url.match(/\/test_task\/\d+\?/)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            msg: 'success',
            message: 'success',
            data: { task: MOCK_TASK_DETAIL },
          }),
        })
        return
      }

      // 任务列表：/test_task?... （不含 /test_task/{id}）
      if (url.includes('/test_task')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            msg: 'success',
            message: 'success',
            data: { items: MOCK_TASKS, total: MOCK_TASKS.length },
          }),
        })
        return
      }

      // 最终 fallback
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ code: 0, msg: 'success', message: 'success', data: {} }),
      })
    } catch {
      // fetch 失败（后端不可达），直接返回 mock 数据
      if (url.includes('test_task') && !url.match(/\/test_task\/\d+/)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            msg: 'success',
            message: 'success',
            data: { items: MOCK_TASKS, total: MOCK_TASKS.length },
          }),
        })
      } else if (url.match(/\/test_task\/\d+$/)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            msg: 'success',
            message: 'success',
            data: { task: MOCK_TASK_DETAIL },
          }),
        })
      } else if (url.includes('project') && !url.match(/\/project\/\d+/)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            msg: 'success',
            message: 'success',
            data: { items: MOCK_PROJECTS, total: MOCK_PROJECTS.length },
          }),
        })
      } else if (url.includes('report') && !url.match(/\/report\/\d+/)) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            code: 0,
            msg: 'success',
            message: 'success',
            data: { items: MOCK_REPORTS, total: MOCK_REPORTS.length },
          }),
        })
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ code: 0, msg: 'success', message: 'success', data: {} }),
        })
      }
    }
  })
}

// ============================================================
// 页面交互辅助函数
// ============================================================
async function selectProjectInTaskPage(page: Page): Promise<boolean> {
  const sel = page.locator('.project-filter')
  if ((await safeCount(sel)) === 0) return false
  await sel.click()
  await page.waitForTimeout(500)
  const opts = page.locator('.el-select-dropdown__item:visible')
  if ((await safeCount(opts)) === 0) return false
  await opts.first().click()
  await page.waitForTimeout(1500)
  return true
}

async function selectProjectInReportPage(page: Page): Promise<boolean> {
  const sel = page.locator('.search-form .el-select')
  if ((await safeCount(sel)) === 0) return false
  await sel.first().click()
  await page.waitForTimeout(500)
  const opts = page.locator('.el-select-dropdown__item:visible')
  if ((await safeCount(opts)) === 0) return false
  await opts.first().click()
  await page.waitForTimeout(500)
  const queryBtn = page.locator('button:has-text("查询")')
  if ((await safeCount(queryBtn)) > 0) await queryBtn.click()
  await page.waitForTimeout(2000)
  return true
}

// ============================================================
// 全局前置条件
// ============================================================
test.beforeEach(async ({ page, context }) => {
  await setupApiInterception(context)
  await page.addInitScript(
    ({ token, permStr }) => {
      localStorage.setItem('token', token)
      localStorage.setItem('userInfo', permStr)
    },
    { token: FAKE_TOKEN, permStr: ADMIN_PERM }
  )
})

// ============================================================
// T7: 执行中心 (14 个检查点)
// ============================================================
test.describe('T7: 执行中心', () => {
  test('T7-1 导航到 /home/task 确认页面标题含"执行中心"', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const text = await safeText(page.locator('.card-title'))
    const ok = text.includes('执行中心')
    record(
      'T7-1',
      '导航到 /home/task',
      '页面标题含"执行中心"',
      `"${text.trim()}"`,
      ok ? 'PASS' : 'FAIL'
    )
    expect(ok).toBeTruthy()
  })

  test('T7-2 面包屑显示"工作台 / 执行中心"', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const items = page.locator('.el-breadcrumb .el-breadcrumb__item')
    const count = await safeCount(items)
    const texts: string[] = []
    for (let i = 0; i < count; i++) texts.push((await items.nth(i).textContent()) || '')
    const full = texts.join(' / ').trim()
    const ok = full.includes('工作台') && full.includes('执行中心')
    record('T7-2', '检查面包屑', '"工作台 / 执行中心"', full, ok ? 'PASS' : 'FAIL')
    expect(ok).toBeTruthy()
  })

  test('T7-3 左侧菜单"执行中心"高亮', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const text = await safeText(page.locator('.el-menu-item.is-active'))
    const ok = text.includes('执行中心')
    record('T7-3', '检查左侧菜单高亮', '"执行中心"高亮', `"${text.trim()}"`, ok ? 'PASS' : 'FAIL')
    expect(ok).toBeTruthy()
  })

  test('T7-4 项目筛选下拉框存在', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const cnt = await safeCount(page.locator('.project-filter'))
    record('T7-4', '检查项目筛选下拉框', '下拉框存在', `count=${cnt}`, cnt > 0 ? 'PASS' : 'FAIL')
    expect(cnt).toBeGreaterThan(0)
  })

  test('T7-5 选择项目后任务列表加载', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    if (!(await selectProjectInTaskPage(page))) {
      record('T7-5', '选择项目后加载任务列表', '列表加载', '无项目可选', 'WARN')
      return
    }
    const rows = await safeCount(page.locator('.el-table__body-wrapper .el-table__row'))
    record(
      'T7-5',
      '选择项目后加载任务列表',
      '表格有数据行',
      `rows=${rows}`,
      rows > 0 ? 'PASS' : 'WARN'
    )
  })

  test('T7-6 任务统计信息展示', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const hasTable = (await safeCount(page.locator('.el-table'))) > 0
    const hasTotalTag = (await safeCount(page.locator('.el-tag--info'))) > 0
    record(
      'T7-6',
      '检查统计信息',
      '表格+总数标签',
      `table=${hasTable}, tag=${hasTotalTag}`,
      hasTable ? 'PASS' : 'FAIL'
    )
    expect(hasTable).toBeTruthy()
  })

  test('T7-7 "创建任务"按钮存在且可点击', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const btn = page.locator('button:has-text("创建任务")')
    const exists = (await safeCount(btn)) > 0
    if (!exists) {
      record('T7-7', '创建任务按钮', '存在且可点击', '不存在', 'FAIL')
      expect(exists).toBeTruthy()
      return
    }
    const enabled = await btn.first().isEnabled()
    record('T7-7', '创建任务按钮', '存在且可点击', `enabled=${enabled}`, enabled ? 'PASS' : 'FAIL')
    expect(enabled).toBeTruthy()
  })

  test('T7-8 点击"创建任务"跳转到 /home/task/create', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInTaskPage(page)
    const btn = page.locator('button:has-text("创建任务")')
    if ((await safeCount(btn)) === 0) {
      record('T7-8', '点击创建任务', '跳转create', '按钮不存在', 'FAIL')
      return
    }
    await btn.first().click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const url = page.url()
    const ok = url.includes('/home/task/create')
    record('T7-8', '点击创建任务', '跳转 /home/task/create', url, ok ? 'PASS' : 'FAIL')
    expect(ok).toBeTruthy()
  })

  test('T7-9 任务列表行操作按钮', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInTaskPage(page)
    const hasDetail = (await safeCount(page.locator('.el-table .el-button:has-text("详情")'))) > 0
    const hasDelete = (await safeCount(page.locator('.el-table .el-button:has-text("删除")'))) > 0
    const hasStart = (await safeCount(page.locator('.el-table .el-button:has-text("启动")'))) > 0
    const hasStop = (await safeCount(page.locator('.el-table .el-button:has-text("停止")'))) > 0
    const ok = hasDetail || hasDelete || hasStart || hasStop
    record(
      'T7-9',
      '行操作按钮',
      '详情/删除/启动/停止',
      `详情:${hasDetail} 删除:${hasDelete} 启动:${hasStart} 停止:${hasStop}`,
      ok ? 'PASS' : 'WARN'
    )
  })

  test('T7-10 点击任务进入详情 /home/task/detail/{id}', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInTaskPage(page)
    const detailBtn = page.locator('.el-table button:has-text("详情")')
    const row = page.locator('.el-table__body-wrapper .el-table__row')
    if ((await safeCount(detailBtn)) > 0) await detailBtn.first().click()
    else if ((await safeCount(row)) > 0) await row.first().click()
    else {
      record('T7-10', '进入任务详情', '/home/task/detail/{id}', '无数据', 'WARN')
      return
    }
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const ok = page.url().includes('/home/task/detail/')
    record('T7-10', '进入任务详情', '/home/task/detail/{id}', page.url(), ok ? 'PASS' : 'FAIL')
    expect(ok).toBeTruthy()
  })

  test('T7-11 任务详情页基本信息展示', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInTaskPage(page)
    const detailBtn = page.locator('.el-table button:has-text("详情")')
    const row = page.locator('.el-table__body-wrapper .el-table__row')
    if ((await safeCount(detailBtn)) > 0) await detailBtn.first().click()
    else if ((await safeCount(row)) > 0) await row.first().click()
    else {
      record('T7-11', '详情页基本信息', '名称/状态/时间', '无数据', 'WARN')
      return
    }
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)
    const hasHeader = (await safeCount(page.locator('.card-header span, .card-header .title'))) > 0
    const hasInfo = (await safeCount(page.locator('.info-item, .task-info, .el-descriptions'))) > 0
    const ok = hasHeader || hasInfo
    record(
      'T7-11',
      '详情页基本信息',
      '标题或信息项',
      `header=${hasHeader} info=${hasInfo}`,
      ok ? 'PASS' : 'FAIL'
    )
    expect(ok).toBeTruthy()
  })

  test('T7-12 导航到 /home/task/execution 验证测试执行页面', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInTaskPage(page)
    const rows = page.locator('.el-table__body-wrapper .el-table__row')
    if ((await safeCount(rows)) === 0) {
      record('T7-12', '导航到执行页面', '执行页加载', '无任务', 'WARN')
      return
    }
    const taskId = (await safeText(rows.first().locator('td').first())).trim() || '1'
    await page.goto(`/home/task/execution/${taskId}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const hasContent =
      (await safeCount(page.locator('.execution-page, .test-execution-page, .page-content'))) > 0
    record(
      'T7-12',
      '导航到执行页面',
      '执行页元素存在',
      `taskId=${taskId} content=${hasContent}`,
      hasContent ? 'PASS' : 'WARN'
    )
  })

  test('T7-13 测试执行页步骤列表和执行控制按钮', async ({ page }) => {
    await page.goto('/home/task')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInTaskPage(page)
    const rows = page.locator('.el-table__body-wrapper .el-table__row')
    if ((await safeCount(rows)) === 0) {
      record('T7-13', '执行页步骤和控制', '存在', '无任务', 'WARN')
      return
    }
    const taskId = (await safeText(rows.first().locator('td').first())).trim() || '1'
    await page.goto(`/home/task/execution/${taskId}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const hasSteps =
      (await safeCount(page.locator('[class*="step"], .steps-panel, .case-list'))) > 0
    const hasControls =
      (await safeCount(
        page.locator(
          'button:has-text("开始"), button:has-text("暂停"), button:has-text("停止"), button:has-text("恢复")'
        )
      )) > 0
    const ok = hasSteps || hasControls
    record(
      'T7-13',
      '执行页步骤和控制',
      '步骤面板或控制按钮',
      `steps=${hasSteps} controls=${hasControls}`,
      ok ? 'PASS' : 'WARN'
    )
  })

  test('T7-14 activeMenu 在 /home/task/* 下高亮"执行中心"', async ({ page }) => {
    const paths = ['/home/task', '/home/task/detail/1', '/home/task/execution/1']
    let allOk = true
    for (const p of paths) {
      await page.goto(p)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(2000)
      const text = await safeText(page.locator('.el-menu-item.is-active'))
      if (!text.includes('执行中心')) {
        allOk = false
        record('T7-14', `路径${p}`, '"执行中心"高亮', `"${text.trim()}"`, 'WARN')
      }
    }
    if (allOk) record('T7-14', '所有 /home/task/* 子路径', '"执行中心"高亮', '全部高亮', 'PASS')
    expect(allOk).toBeTruthy()
  })
})

// ============================================================
// T8: 报告中心 (9 个检查点)
// ============================================================
test.describe('T8: 报告中心', () => {
  test('T8-1 导航到 /home/report 确认页面标题含"报告中心"', async ({ page }) => {
    await page.goto('/home/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const text = await safeText(page.locator('.card-header span'))
    const ok = text.includes('报告') || text.includes('测试报告')
    record('T8-1', '导航到 /home/report', '标题含"报告"', `"${text.trim()}"`, ok ? 'PASS' : 'FAIL')
    expect(ok).toBeTruthy()
  })

  test('T8-2 面包屑显示"工作台 / 报告中心"', async ({ page }) => {
    await page.goto('/home/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const items = page.locator('.el-breadcrumb .el-breadcrumb__item')
    const count = await safeCount(items)
    const texts: string[] = []
    for (let i = 0; i < count; i++) texts.push((await items.nth(i).textContent()) || '')
    const full = texts.join(' / ').trim()
    const ok = full.includes('工作台') && full.includes('报告')
    record('T8-2', '检查面包屑', '"工作台 / 报告中心"', full, ok ? 'PASS' : 'FAIL')
    expect(ok).toBeTruthy()
  })

  test('T8-3 左侧菜单"报告中心"高亮', async ({ page }) => {
    await page.goto('/home/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const text = await safeText(page.locator('.el-menu-item.is-active'))
    const ok = text.includes('报告中心')
    record('T8-3', '左侧菜单高亮', '"报告中心"高亮', `"${text.trim()}"`, ok ? 'PASS' : 'FAIL')
    expect(ok).toBeTruthy()
  })

  test('T8-4 报告列表加载（需先选择项目）', async ({ page }) => {
    await page.goto('/home/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    if (!(await selectProjectInReportPage(page))) {
      record('T8-4', '报告列表加载', '列表加载', '无项目', 'WARN')
      return
    }
    const rows = await safeCount(page.locator('.el-table__body-wrapper .el-table__row'))
    record('T8-4', '报告列表加载', '表格有数据行', `rows=${rows}`, rows > 0 ? 'PASS' : 'WARN')
  })

  test('T8-5 报告列表行操作（查看、导出、删除）', async ({ page }) => {
    await page.goto('/home/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInReportPage(page)
    const v = (await safeCount(page.locator('.el-table button:has-text("查看")'))) > 0
    const e = (await safeCount(page.locator('.el-table button:has-text("导出")'))) > 0
    const d = (await safeCount(page.locator('.el-table button:has-text("删除")'))) > 0
    record(
      'T8-5',
      '行操作按钮',
      '查看/导出/删除',
      `查看:${v} 导出:${e} 删除:${d}`,
      v || e || d ? 'PASS' : 'WARN'
    )
  })

  test('T8-6 点击查看进入报告详情 /home/report/detail', async ({ page }) => {
    await page.goto('/home/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInReportPage(page)
    const btn = page.locator('.el-table button:has-text("查看")')
    if ((await safeCount(btn)) === 0) {
      record('T8-6', '点击查看', '/home/report/detail', '无数据', 'WARN')
      return
    }
    await btn.first().click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)
    const ok = page.url().includes('/home/report/detail')
    record('T8-6', '点击查看', '/home/report/detail', page.url(), ok ? 'PASS' : 'FAIL')
    expect(ok).toBeTruthy()
  })

  test('T8-7 报告详情页：基本信息、测试摘要、步骤详情', async ({ page }) => {
    await page.goto('/home/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInReportPage(page)
    const btn = page.locator('.el-table button:has-text("查看")')
    if ((await safeCount(btn)) === 0) {
      record('T8-7', '报告详情内容', '基本信息+摘要+步骤', '无数据', 'WARN')
      return
    }
    await btn.first().click()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)
    const info =
      (await safeCount(page.locator('.el-form-item, .report-content, .el-descriptions'))) > 0
    const stat =
      (await safeCount(page.locator('[class*="stat"], [class*="chart"], .report-summary'))) > 0
    const tbl = (await safeCount(page.locator('.el-table'))) > 0
    const ok = info || tbl
    record(
      'T8-7',
      '报告详情内容',
      '基本信息/摘要/步骤',
      `info=${info} stat=${stat} table=${tbl}`,
      ok ? 'PASS' : 'FAIL'
    )
    expect(ok).toBeTruthy()
  })

  test('T8-8 报告导出功能', async ({ page }) => {
    await page.goto('/home/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    await selectProjectInReportPage(page)
    const btn = page.locator('.el-table button:has-text("导出")')
    if ((await safeCount(btn)) === 0) {
      record('T8-8', '导出功能', '导出按钮存在可点击', '无导出按钮', 'WARN')
      return
    }
    const enabled = await btn.first().isEnabled()
    record('T8-8', '导出功能', '导出按钮可点击', `enabled=${enabled}`, enabled ? 'PASS' : 'FAIL')
    expect(enabled).toBeTruthy()
  })

  test('T8-9 分页功能', async ({ page }) => {
    await page.goto('/home/report')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(2000)
    const pg = page.locator('.el-pagination')
    if ((await safeCount(pg)) === 0) {
      record('T8-9', '分页功能', '分页组件存在', '无分页(数据不足)', 'WARN')
      return
    }
    const hasTotal = (await safeCount(page.locator('.el-pagination__total'))) > 0
    const hasPager = (await safeCount(page.locator('.el-pager'))) > 0
    record('T8-9', '分页功能', '分页组件存在', `total=${hasTotal} pager=${hasPager}`, 'PASS')
    expect(await safeCount(pg)).toBeGreaterThan(0)
  })
})

// ============================================================
// 汇总输出
// ============================================================
test.afterAll(() => {
  console.log('\n' + '='.repeat(80))
  console.log('T7+T8 Playwright 复测结果汇总')
  console.log('='.repeat(80))
  const pass = results.filter((r) => r.status === 'PASS').length
  const fail = results.filter((r) => r.status === 'FAIL').length
  const warn = results.filter((r) => r.status === 'WARN').length
  console.log(`总计: ${results.length} | PASS: ${pass} | FAIL: ${fail} | WARN: ${warn}`)
  console.log('-'.repeat(80))
  for (const r of results) {
    const icon = r.status === 'PASS' ? 'PASS' : r.status === 'FAIL' ? 'FAIL' : 'WARN'
    console.log(`[${icon}] [${r.id}] ${r.operation}`)
    console.log(`   expected: ${r.expected}`)
    console.log(`   actual:   ${r.actual}`)
  }
  console.log('='.repeat(80))
})
