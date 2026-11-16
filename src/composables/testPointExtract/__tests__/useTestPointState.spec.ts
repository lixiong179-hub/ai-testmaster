import { describe, it, expect, vi, beforeEach } from 'vitest'
import { silenceConsole } from '@/test-utils'
import type { ExtractSharedState, TestPointItem } from '../types'

const mocks = vi.hoisted(() => ({
  getList: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} }),
}))

vi.mock('@/api/testPoint', () => ({
  testPointApi: { getList: mocks.getList },
}))

import { createSharedState } from '../createSharedState'
import { useTestPointState } from '../useTestPointState'

let state: ExtractSharedState
let tpState: ReturnType<typeof useTestPointState>

function makePoint(overrides: Partial<TestPointItem> = {}): TestPointItem {
  return { id: 1, module: '登录', point: '登录成功', priority: 2, ...overrides }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceConsole()
  state = createSharedState()
  tpState = useTestPointState(state)
})

describe('useTestPointState — 进度与分页计算属性', () => {
  it('进度 100 时为 success，有错误信息时为 exception，否则为空', () => {
    expect(tpState.progressStatus.value).toBe('')

    state.errorMessage.value = '提取失败'
    expect(tpState.progressStatus.value).toBe('exception')

    state.progress.value = 100
    expect(tpState.progressStatus.value).toBe('success')
  })

  it('未落库时按页码本地切片', () => {
    state.pageSize.value = 2
    state.testPoints.value = [makePoint({ id: 1 }), makePoint({ id: 2 }), makePoint({ id: 3 })]

    state.currentPage.value = 1
    expect(tpState.paginatedTestPoints.value.map((tp) => tp.id)).toEqual([1, 2])

    state.currentPage.value = 2
    expect(tpState.paginatedTestPoints.value.map((tp) => tp.id)).toEqual([3])
  })

  it('已落库时直接使用接口返回的分页数据', () => {
    state.pageSize.value = 1
    state.savedFromDb.value = true
    state.testPoints.value = [makePoint({ id: 1 }), makePoint({ id: 2 })]

    expect(tpState.paginatedTestPoints.value).toHaveLength(2)
  })

  it('模块数量统计包含「未分类」', () => {
    state.testPoints.value = [
      makePoint({ id: 1, module: '登录' }),
      makePoint({ id: 2, module: '登录' }),
      makePoint({ id: 3, module: '' }),
    ]

    expect(tpState.moduleCount.value).toBe(2)
  })

  it('总数在本地与落库模式下来源不同', () => {
    state.testPoints.value = [makePoint(), makePoint({ id: 2 })]
    expect(tpState.totalDisplayCount.value).toBe(2)

    state.savedFromDb.value = true
    state.dbTotal.value = 42
    expect(tpState.totalDisplayCount.value).toBe(42)
  })
})

describe('useTestPointState — 优先级与分布', () => {
  it.each([
    [1, 'danger', '高'],
    [2, 'warning', '中'],
    [3, 'info', '低'],
    ['1', 'danger', '高'],
  ])('优先级 %s 映射为 %s / %s', (priority, tagType, label) => {
    expect(tpState.getPriorityTagType(priority)).toBe(tagType)
    expect(tpState.getPriorityLabel(priority)).toBe(label)
  })

  it('未知优先级回退为低', () => {
    expect(tpState.getPriorityTagType(9)).toBe('info')
    expect(tpState.getPriorityLabel(9)).toBe('低')
  })

  it('按优先级统计数量', () => {
    state.testPoints.value = [
      makePoint({ id: 1, priority: 1 }),
      makePoint({ id: 2, priority: 1 }),
      makePoint({ id: 3, priority: 3 }),
    ]

    expect(tpState.getPriorityCount(1)).toBe(2)
    expect(tpState.getPriorityCount(2)).toBe(0)
  })

  it('模块分布统计空模块归入「未分类」', () => {
    state.testPoints.value = [
      makePoint({ id: 1, module: '登录' }),
      makePoint({ id: 2, module: '登录' }),
      makePoint({ id: 3, module: '' }),
    ]

    expect(tpState.getModuleDistribution()).toEqual({ 登录: 2, 未分类: 1 })
  })
})

describe('useTestPointState — 数据加载与分页交互', () => {
  it('从数据库加载测试点时写入列表、总数与页码', async () => {
    state.pageSize.value = 20
    mocks.getList.mockResolvedValue({ items: [makePoint()], total: 31 })

    await tpState.loadSavedTestPoints(9, 2)

    expect(mocks.getList).toHaveBeenCalledWith(9, { page: 2, page_size: 20 })
    expect(state.testPoints.value).toHaveLength(1)
    expect(state.dbTotal.value).toBe(31)
    expect(state.savedFromDb.value).toBe(true)
    expect(state.currentPage.value).toBe(2)
    expect(state.loadingTestPoints.value).toBe(false)
  })

  it('加载失败时保持原状并复位 loading', async () => {
    mocks.getList.mockRejectedValue(new Error('boom'))

    await tpState.loadSavedTestPoints(9)

    expect(state.loadingTestPoints.value).toBe(false)
    expect(state.savedFromDb.value).toBe(false)
  })

  it('落库模式下翻页会重新请求接口', async () => {
    state.savedFromDb.value = true
    state.formData.project_id = 9
    mocks.getList.mockResolvedValue({ items: [], total: 0 })

    tpState.handlePageChange(3)

    expect(mocks.getList).toHaveBeenCalledWith(9, { page: 3, page_size: 10 })
  })

  it('本地模式下翻页只更新页码', async () => {
    tpState.handlePageChange(2)

    expect(state.currentPage.value).toBe(2)
    expect(mocks.getList).not.toHaveBeenCalled()
  })

  it('落库但未选项目时不请求接口，退化为本地翻页', () => {
    state.savedFromDb.value = true

    tpState.handlePageChange(2)

    expect(mocks.getList).not.toHaveBeenCalled()
    expect(state.currentPage.value).toBe(2)
  })

  it('选择变化记录选中行', () => {
    const rows = [makePoint()]

    tpState.handleSelectionChange(rows)

    expect(state.selectedRows.value).toEqual(rows)
  })

  it('清空选择时同步清空表格选中态', () => {
    const clearSelection = vi.fn()
    state.selectedRows.value = [makePoint()]
    state.testPointTable.value = { clearSelection } as never

    tpState.clearSelection()

    expect(state.selectedRows.value).toEqual([])
    expect(clearSelection).toHaveBeenCalledTimes(1)
  })

  it('表格实例不存在时清空选择不报错', () => {
    state.selectedRows.value = [makePoint()]

    expect(() => tpState.clearSelection()).not.toThrow()
    expect(state.selectedRows.value).toEqual([])
  })
})
