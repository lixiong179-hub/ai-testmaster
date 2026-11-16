import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  getProjectList: vi.fn(),
  getAudits: vi.fn(),
  rollbackAudit: vi.fn(),
}))

vi.mock('@/api/project', () => ({
  ProjectAPI: { getProjectList: mocks.getProjectList },
  default: { getProjectList: mocks.getProjectList },
}))

vi.mock('@/api/selfHealing', () => ({
  default: { getAudits: mocks.getAudits, rollbackAudit: mocks.rollbackAudit },
  failureTypeOptions: [{ label: '选择器失效', value: 'selector_not_found' }],
  strategyOptions: [{ label: 'AI 重定位', value: 'ai_relocate' }],
}))

import { failureTypeOptions, strategyOptions, useAuditList } from '../useAuditList'

type Ctx = ReturnType<typeof useAuditList>
type Audit = Ctx['audits']['value'][number]

const host = createComposableHost<Ctx>(() => useAuditList())
let ctx: Ctx

function makeAudit(overrides: Partial<Audit> = {}): Audit {
  return {
    id: 1,
    test_case_id: 10,
    failure_type: 'selector_not_found',
    strategy_used: 'ai_relocate',
    confidence: 0.9,
    created_at: '2026-06-15T10:00:00',
    old_locator: '#old',
    new_locator: '#new',
    ...overrides,
  } as Audit
}

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
  mocks.getProjectList.mockResolvedValue({ data: { items: [{ id: 9, name: '项目A' }] } })
  mocks.getAudits.mockResolvedValue({ data: { items: [makeAudit()], total: 1 } })
  mocks.rollbackAudit.mockResolvedValue({ code: 200, data: { message: '' } })
})

describe('useAuditList — 加载', () => {
  it('挂载后加载项目与审计列表', async () => {
    await mountHost()

    expect(mocks.getProjectList).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(mocks.getAudits).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    expect(ctx.projects.value).toHaveLength(1)
    expect(ctx.audits.value).toHaveLength(1)
    expect(ctx.pagination.total).toBe(1)
    expect(ctx.loading.value).toBe(false)
  })

  it('选中项目后请求带上 project_id', async () => {
    await mountHost()
    ctx.filters.projectId = 9
    mocks.getAudits.mockClear()

    ctx.handleSearch()
    await flushPromises()

    expect(mocks.getAudits).toHaveBeenCalledWith({ page: 1, page_size: 20, project_id: 9 })
  })

  it('项目加载失败时提示 Error 信息', async () => {
    mocks.getProjectList.mockRejectedValue(new Error('项目服务异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('项目服务异常')
  })

  it('项目加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getProjectList.mockRejectedValue(undefined)

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取项目列表失败')
  })

  it('审计列表失败时提示错误并清空数据', async () => {
    mocks.getAudits.mockRejectedValue(new Error('审计服务异常'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('审计服务异常')
    expect(ctx.audits.value).toEqual([])
    expect(ctx.pagination.total).toBe(0)
    expect(ctx.loading.value).toBe(false)
  })

  it('审计列表失败且非 Error 时使用兜底文案', async () => {
    mocks.getAudits.mockRejectedValue(undefined)

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取自愈审计列表失败')
  })

  it('响应缺少 items 时降级为空', async () => {
    mocks.getAudits.mockResolvedValue({ data: {} })

    await mountHost()

    expect(ctx.audits.value).toEqual([])
    expect(ctx.pagination.total).toBe(0)
  })
})

describe('useAuditList — 客户端过滤', () => {
  it('未设置条件时返回全部数据', async () => {
    await mountHost()

    expect(ctx.filteredAudits.value).toHaveLength(1)
  })

  it('按失败类型过滤', async () => {
    await mountHost()
    ctx.audits.value = [
      makeAudit({ id: 1, failure_type: 'selector_not_found' }),
      makeAudit({ id: 2, failure_type: 'timeout' }),
    ]

    ctx.filters.failureType = 'timeout'

    expect(ctx.filteredAudits.value.map((a) => a.id)).toEqual([2])
  })

  it('按置信度区间过滤', async () => {
    await mountHost()
    ctx.audits.value = [
      makeAudit({ id: 1, confidence: 0.3 }),
      makeAudit({ id: 2, confidence: 0.6 }),
      makeAudit({ id: 3, confidence: 0.95 }),
    ]

    ctx.filters.confidenceMin = 0.5
    expect(ctx.filteredAudits.value.map((a) => a.id)).toEqual([2, 3])

    ctx.filters.confidenceMax = 0.9
    expect(ctx.filteredAudits.value.map((a) => a.id)).toEqual([2])
  })

  it('置信度为空且指定区间时视为不匹配', async () => {
    await mountHost()
    ctx.audits.value = [makeAudit({ id: 1, confidence: null as never }), makeAudit({ id: 2 })]
    ctx.filters.confidenceMin = 0.1

    expect(ctx.filteredAudits.value.map((a) => a.id)).toEqual([2])
  })

  it('按日期范围过滤，非法时间被排除', async () => {
    await mountHost()
    ctx.audits.value = [
      makeAudit({ id: 1, created_at: '2026-06-10T10:00:00' }),
      makeAudit({ id: 2, created_at: '2026-06-20T10:00:00' }),
      makeAudit({ id: 3, created_at: 'invalid' }),
    ]

    ctx.filters.dateRange = ['2026-06-01T00:00:00', '2026-06-15T23:59:59']

    expect(ctx.filteredAudits.value.map((a) => a.id)).toEqual([1])
  })

  it('日期范围不完整时不做过滤', async () => {
    await mountHost()
    ctx.filters.dateRange = ['2026-06-01'] as never

    expect(ctx.filteredAudits.value).toHaveLength(1)
  })
})

describe('useAuditList — 项目名与分页交互', () => {
  it('currentProjectName 三种展示', async () => {
    await mountHost()

    expect(ctx.currentProjectName.value).toBe('-')

    ctx.filters.projectId = 9
    expect(ctx.currentProjectName.value).toBe('项目A')

    ctx.filters.projectId = 404
    expect(ctx.currentProjectName.value).toBe('项目#404')
  })

  it('搜索重置页码', async () => {
    await mountHost()
    ctx.pagination.page = 3
    mocks.getAudits.mockClear()

    ctx.handleSearch()
    await flushPromises()

    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getAudits).toHaveBeenCalledTimes(1)
  })

  it('重置清空所有筛选并回到第一页', async () => {
    await mountHost()
    ctx.filters.projectId = 9
    ctx.filters.failureType = 'timeout'
    ctx.filters.confidenceMin = 0.5
    ctx.filters.confidenceMax = 0.9
    ctx.filters.dateRange = ['2026-06-01', '2026-06-30']
    ctx.pagination.page = 2
    mocks.getAudits.mockClear()

    ctx.handleReset()
    await flushPromises()

    expect(ctx.filters).toEqual({
      projectId: undefined,
      failureType: '',
      confidenceMin: undefined,
      confidenceMax: undefined,
      dateRange: null,
    })
    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getAudits).toHaveBeenCalledTimes(1)
  })

  it('调整每页条数后回到第一页', async () => {
    await mountHost()
    ctx.pagination.page = 2
    mocks.getAudits.mockClear()

    ctx.handleSizeChange(50)
    await flushPromises()

    expect(ctx.pagination.pageSize).toBe(50)
    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getAudits).toHaveBeenCalledWith({ page: 1, page_size: 50 })
  })

  it('切换页码后加载对应页', async () => {
    await mountHost()
    mocks.getAudits.mockClear()

    ctx.handleCurrentChange(3)
    await flushPromises()

    expect(ctx.pagination.page).toBe(3)
    expect(mocks.getAudits).toHaveBeenCalledWith({ page: 3, page_size: 20 })
  })

  it('详情弹窗开关', async () => {
    await mountHost()
    const row = makeAudit()

    ctx.openDetail(row)
    expect(ctx.currentAudit.value).toEqual(row)
    expect(ctx.detailVisible.value).toBe(true)

    ctx.closeDetail()
    expect(ctx.currentAudit.value).toBeNull()
    expect(ctx.detailVisible.value).toBe(false)
  })

  it('导出的选项常量可直接使用', () => {
    expect(failureTypeOptions).toHaveLength(1)
    expect(strategyOptions).toHaveLength(1)
  })
})

describe('useAuditList — 回滚', () => {
  it('确认后回滚成功并刷新列表', async () => {
    await mountHost()
    mocks.getAudits.mockClear()

    ctx.handleRollback(makeAudit({ id: 7 }))
    await flushPromises()

    expect(mocks.rollbackAudit).toHaveBeenCalledWith(7)
    expect(ElMessage.success).toHaveBeenCalledWith('回滚成功')
    expect(mocks.getAudits).toHaveBeenCalledTimes(1)
    expect(ctx.rollingBack.value).toBe(false)
  })

  it('接口返回自定义消息时优先展示', async () => {
    mocks.rollbackAudit.mockResolvedValue({ code: 200, data: { message: '已回滚到旧选择器' } })
    await mountHost()

    ctx.handleRollback(makeAudit())
    await flushPromises()

    expect(ElMessage.success).toHaveBeenCalledWith('已回滚到旧选择器')
  })

  it('接口返回非 200 时提示错误', async () => {
    mocks.rollbackAudit.mockResolvedValue({ code: 500, message: '审计记录不存在' })
    await mountHost()

    ctx.handleRollback(makeAudit())
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('审计记录不存在')
    expect(ctx.rollingBack.value).toBe(false)
  })

  it('请求异常时提示 Error 信息', async () => {
    mocks.rollbackAudit.mockRejectedValue(new Error('回滚接口异常'))
    await mountHost()

    ctx.handleRollback(makeAudit())
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('回滚接口异常')
  })

  it('请求异常且非 Error 时使用兜底文案', async () => {
    mocks.rollbackAudit.mockRejectedValue(undefined)
    await mountHost()

    ctx.handleRollback(makeAudit())
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('回滚失败')
  })

  it('取消确认时不调用接口', async () => {
    await mountHost()
    mockCancel()

    ctx.handleRollback(makeAudit())
    await flushPromises()

    expect(mocks.rollbackAudit).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })
})
