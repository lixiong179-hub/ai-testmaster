import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { createComposableHost, silenceElMessage } from '@/test-utils'
import type { AuditLogItem } from '@/api/auditLog'

const mocks = vi.hoisted(() => ({ getLogs: vi.fn() }))

vi.mock('@/api/auditLog', () => ({
  default: { getLogs: mocks.getLogs },
}))

import { actionOptions, targetKindOptions, useAuditLog } from '../useAuditLog'

type Ctx = ReturnType<typeof useAuditLog>

const host = createComposableHost<Ctx>(() => useAuditLog())
let ctx: Ctx

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

function makeLog(id: number, over: Partial<AuditLogItem> = {}): AuditLogItem {
  return {
    id,
    action: 'create',
    actor_id: 7,
    target_kind: 'project',
    target_id: id,
    detail: `记录 ${id}`,
    run_id: null,
    iteration_id: null,
    created_at: '2026-11-16T08:00:00',
    ...over,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mocks.getLogs.mockResolvedValue({ data: { items: [makeLog(1), makeLog(2)], total: 42 } })
})

describe('useAuditLog — 选项常量', () => {
  it('目标类型与操作类型选项覆盖后端枚举', async () => {
    await mountHost()

    expect(targetKindOptions.map((item) => item.value)).toEqual([
      'project',
      'iteration',
      'pipeline',
      'test_case',
      'test_point',
      'test_task',
    ])
    expect(actionOptions.map((item) => item.value)).toEqual([
      'create',
      'update',
      'delete',
      'execute',
      'approve',
      'reject',
    ])
  })
})

describe('useAuditLog — 加载', () => {
  it('挂载后以默认分页参数拉取', async () => {
    await mountHost()

    expect(mocks.getLogs).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    expect(ctx.logs.value).toHaveLength(2)
    expect(ctx.pagination.total).toBe(42)
    expect(ctx.loading.value).toBe(false)
  })

  it('响应缺少 items/total 时兜底为空与 0', async () => {
    mocks.getLogs.mockResolvedValue({ data: {} })

    await mountHost()

    expect(ctx.logs.value).toEqual([])
    expect(ctx.pagination.total).toBe(0)
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('加载失败时提示错误信息', async () => {
    mocks.getLogs.mockRejectedValue(new Error('审计服务不可用'))

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('审计服务不可用')
    expect(ctx.loading.value).toBe(false)
  })

  it('加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getLogs.mockRejectedValue('boom')

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('获取审计日志失败')
  })
})

describe('useAuditLog — 筛选条件拼装', () => {
  it('动作、操作者、目标类型与时间范围全部透传', async () => {
    await mountHost()
    mocks.getLogs.mockClear()

    ctx.filters.action = 'delete'
    ctx.filters.actorId = '12'
    ctx.filters.targetKind = 'iteration'
    ctx.filters.dateRange = ['2026-11-01', '2026-11-16']
    await ctx.loadLogs()

    expect(mocks.getLogs).toHaveBeenCalledWith({
      page: 1,
      page_size: 20,
      action: 'delete',
      actor_id: 12,
      target_kind: 'iteration',
      since: '2026-11-01',
      until: '2026-11-16',
    })
  })

  it('空筛选不产生多余参数', async () => {
    await mountHost()
    mocks.getLogs.mockClear()

    await ctx.loadLogs()

    expect(mocks.getLogs).toHaveBeenCalledWith({ page: 1, page_size: 20 })
  })

  it('操作者非数字或非正数时忽略', async () => {
    await mountHost()
    mocks.getLogs.mockClear()

    ctx.filters.actorId = 'abc'
    await ctx.loadLogs()
    expect(mocks.getLogs).toHaveBeenLastCalledWith({ page: 1, page_size: 20 })

    ctx.filters.actorId = '0'
    await ctx.loadLogs()
    expect(mocks.getLogs).toHaveBeenLastCalledWith({ page: 1, page_size: 20 })
  })

  it('时间范围不完整时忽略', async () => {
    await mountHost()
    mocks.getLogs.mockClear()

    ctx.filters.dateRange = ['2026-11-01'] as unknown as [string, string]
    await ctx.loadLogs()

    expect(mocks.getLogs).toHaveBeenLastCalledWith({ page: 1, page_size: 20 })
  })
})

describe('useAuditLog — 分页与重置', () => {
  it('搜索重置到第一页', async () => {
    await mountHost()
    ctx.pagination.page = 5
    mocks.getLogs.mockClear()

    ctx.handleSearch()
    await flushPromises()

    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getLogs).toHaveBeenCalledWith({ page: 1, page_size: 20 })
  })

  it('重置清空全部筛选但保留分页大小', async () => {
    await mountHost()
    ctx.filters.action = 'create'
    ctx.filters.actorId = '3'
    ctx.filters.targetKind = 'project'
    ctx.filters.dateRange = ['2026-11-01', '2026-11-16']
    ctx.pagination.pageSize = 50
    ctx.pagination.page = 4
    mocks.getLogs.mockClear()

    ctx.handleReset()
    await flushPromises()

    expect(ctx.filters).toMatchObject({
      action: '',
      actorId: '',
      targetKind: '',
      dateRange: null,
    })
    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getLogs).toHaveBeenCalledWith({ page: 1, page_size: 50 })
  })

  it('修改分页大小回到第一页', async () => {
    await mountHost()
    ctx.pagination.page = 3
    mocks.getLogs.mockClear()

    ctx.handleSizeChange(100)
    await flushPromises()

    expect(ctx.pagination.pageSize).toBe(100)
    expect(ctx.pagination.page).toBe(1)
    expect(mocks.getLogs).toHaveBeenCalledWith({ page: 1, page_size: 100 })
  })

  it('切换页码保留分页大小', async () => {
    await mountHost()
    ctx.pagination.pageSize = 50
    mocks.getLogs.mockClear()

    ctx.handleCurrentChange(3)
    await flushPromises()

    expect(ctx.pagination.page).toBe(3)
    expect(mocks.getLogs).toHaveBeenCalledWith({ page: 3, page_size: 50 })
  })
})
