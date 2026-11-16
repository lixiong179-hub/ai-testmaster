import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage, ElMessageBox } from 'element-plus'

const mocks = vi.hoisted(() => ({
  getIterations: vi.fn(),
  createIteration: vi.fn(),
  updateIteration: vi.fn(),
  deleteIteration: vi.fn(),
  getFileList: vi.fn(),
  getUIPrototypeProjectList: vi.fn(),
}))

vi.mock('@/api/iteration', () => {
  const api = {
    getIterations: mocks.getIterations,
    createIteration: mocks.createIteration,
    updateIteration: mocks.updateIteration,
    deleteIteration: mocks.deleteIteration,
  }
  return { iterationApi: api, default: api }
})

vi.mock('@/api/file', () => {
  const api = { getFileList: mocks.getFileList }
  return { fileApi: api, default: api }
})

vi.mock('@/api/uiPrototype', () => {
  const api = { getUIPrototypeProjectList: mocks.getUIPrototypeProjectList }
  return { uiPrototypeApi: api, default: api }
})

import { mockCancel, mockConfirm, silenceConsole, silenceElMessage } from '@/test-utils'
import { useIterationManager } from '../useIterationManager'

function makeIteration(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    project_id: 7,
    name: '迭代A',
    version: 'v1.0',
    description: 'desc',
    status: 'active',
    start_date: '2026-11-01',
    end_date: '2026-12-01',
    create_time: '2026-11-01T00:00:00',
    update_time: '2026-11-02T00:00:00',
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
  silenceConsole('error', 'warn')

  mocks.getIterations.mockResolvedValue({ items: [makeIteration()] })
  mocks.getFileList.mockResolvedValue({ data: { total: 3 } })
  mocks.getUIPrototypeProjectList.mockResolvedValue({ data: { total: 2 } })
  mocks.deleteIteration.mockResolvedValue({ code: 200 })
})

describe('useIterationManager — 列表加载', () => {
  it('项目 ID 为空时清空数据且不发请求', async () => {
    const mgr = useIterationManager()
    mgr.iterations = [makeIteration()] as never
    mgr.iterationStats = { 1: { files: 1, prototypes: 1 } }

    await mgr.loadIterations(0)

    expect(mocks.getIterations).not.toHaveBeenCalled()
    expect(mgr.iterations).toEqual([])
    expect(mgr.iterationStats).toEqual({})
  })

  it('加载迭代列表并汇总文件与原型数量', async () => {
    const mgr = useIterationManager()

    await mgr.loadIterations(7)

    expect(mocks.getIterations).toHaveBeenCalledWith(7)
    expect(mgr.iterations).toHaveLength(1)
    expect(mocks.getFileList).toHaveBeenCalledWith(7, 1, 1, 1)
    expect(mocks.getUIPrototypeProjectList).toHaveBeenCalledWith(7, 1, 1, 1)
    expect(mgr.iterationStats[1]).toEqual({ files: 3, prototypes: 2 })
  })

  it('响应直接为数组时也能解析', async () => {
    mocks.getIterations.mockResolvedValue([makeIteration({ id: 2 })])

    const mgr = useIterationManager()
    await mgr.loadIterations(7)

    expect(mgr.iterations).toHaveLength(1)
    expect(mgr.iterationStats[2]).toEqual({ files: 3, prototypes: 2 })
  })

  it('响应嵌套 data.items 时也能解析', async () => {
    mocks.getIterations.mockResolvedValue({ data: { items: [makeIteration({ id: 3 })] } })

    const mgr = useIterationManager()
    await mgr.loadIterations(7)

    expect(mgr.iterations).toHaveLength(1)
    expect(mgr.iterationStats[3]).toEqual({ files: 3, prototypes: 2 })
  })

  it('单个迭代统计失败时置零并告警', async () => {
    mocks.getFileList.mockRejectedValue(new Error('boom'))

    const mgr = useIterationManager()
    await mgr.loadIterations(7)

    expect(mgr.iterationStats[1]).toEqual({ files: 0, prototypes: 0 })
    expect(console.warn).toHaveBeenCalled()
  })

  it('列表请求失败时清空数据', async () => {
    mocks.getIterations.mockRejectedValue(new Error('boom'))

    const mgr = useIterationManager()
    await mgr.loadIterations(7)

    expect(console.error).toHaveBeenCalled()
    expect(mgr.iterations).toEqual([])
    expect(mgr.iterationStats).toEqual({})
  })

  it('无 total 时按列表长度兜底为 0', async () => {
    mocks.getFileList.mockResolvedValue({ data: { items: [] } })
    mocks.getUIPrototypeProjectList.mockResolvedValue({ data: {} })

    const mgr = useIterationManager()
    await mgr.loadIterations(7)

    expect(mgr.iterationStats[1]).toEqual({ files: 0, prototypes: 0 })
  })
})

describe('useIterationManager — 派生数据', () => {
  it('safeIterations 过滤非法项并补默认值', () => {
    const mgr = useIterationManager()
    mgr.iterations = [
      { id: 1 },
      { id: null },
      { id: 1.5 },
      null,
      { id: 2, name: 'B', version: 'v2.0', status: 'active' },
    ] as never

    const list = mgr.safeIterations

    expect(list).toHaveLength(2)
    expect(list[0].name).toBe('未命名迭代')
    expect(list[0].version).toBe('v1.0')
    expect(list[0].status).toBe('planning')
    expect(list[0].start_date).toBeNull()
    expect(list[0].create_time).toBeTruthy()
    expect(list[1].name).toBe('B')
  })

  it('validIterationsForSelect 过滤 id 为 0 的项', () => {
    const mgr = useIterationManager()
    mgr.iterations = [{ id: 0 }, { id: 5 }] as never

    expect(mgr.validIterationsForSelect).toHaveLength(1)
    expect(mgr.validIterationsForSelect[0].id).toBe(5)
  })

  it('getIterationIdParam 区分未选择与未分类', () => {
    const mgr = useIterationManager()

    expect(mgr.getIterationIdParam()).toBeUndefined()

    mgr.handleSelectIteration(0)
    expect(mgr.getIterationIdParam()).toBe(0)

    mgr.handleSelectIteration(5)
    expect(mgr.getIterationIdParam()).toBe(5)
  })

  it('状态类型与文案映射', () => {
    const mgr = useIterationManager()

    expect(mgr.getIterationStatusType('draft')).toBe('info')
    expect(mgr.getIterationStatusType('in_pipeline')).toBe('success')
    expect(mgr.getIterationStatusType('in_review')).toBe('warning')
    expect(mgr.getIterationStatusType('finalized')).toBe('primary')
    expect(mgr.getIterationStatusType('unknown')).toBe('info')

    expect(mgr.getIterationStatusText('draft')).toBe('草稿')
    expect(mgr.getIterationStatusText('active')).toBe('进行中')
    expect(mgr.getIterationStatusText('completed')).toBe('已完成')
    expect(mgr.getIterationStatusText('unknown')).toBe('未知状态')
  })

  it('标题按选择状态派生', () => {
    const mgr = useIterationManager()
    mgr.iterations = [makeIteration()] as never

    expect(mgr.getCurrentIterationTitle()).toBe('全部资源')

    mgr.handleSelectIteration(0)
    expect(mgr.getCurrentIterationTitle()).toBe('未分类资源')

    mgr.handleSelectIteration(1)
    expect(mgr.getCurrentIterationTitle()).toBe('迭代A (v1.0)')

    mgr.handleSelectIteration(99)
    expect(mgr.getCurrentIterationTitle()).toBe('资源列表')
  })

  it('按 ID 取名与统计', () => {
    const mgr = useIterationManager()
    mgr.iterations = [makeIteration()] as never
    mgr.iterationStats = { 1: { files: 4, prototypes: 5 } }

    expect(mgr.getIterationNameById(0)).toBe('未分类')
    expect(mgr.getIterationNameById(1)).toBe('迭代A')
    expect(mgr.getIterationNameById(99)).toBe('未知迭代')

    expect(mgr.getIterationStatsById(1)).toEqual({ files: 4, prototypes: 5 })
    expect(mgr.getIterationStatsById(99)).toEqual({ files: 0, prototypes: 0 })
  })
})

describe('useIterationManager — 删除与命令', () => {
  it('确认后删除迭代并清理选中项', async () => {
    const mgr = useIterationManager()
    mgr.handleSelectIteration(1)

    const result = await mgr.handleDeleteIteration(makeIteration() as never)

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mocks.deleteIteration).toHaveBeenCalledWith(1)
    expect(ElMessage.success).toHaveBeenCalledWith('迭代 "迭代A" 及其下的所有资源已删除')
    expect(mgr.selectedIterationId).toBeNull()
    expect(result).toBe(true)
  })

  it('删除非当前选中的迭代不影响选中项', async () => {
    const mgr = useIterationManager()
    mgr.handleSelectIteration(9)

    const result = await mgr.handleDeleteIteration(makeIteration() as never)

    expect(result).toBe(true)
    expect(mgr.selectedIterationId).toBe(9)
  })

  it('取消删除时静默返回', async () => {
    mockCancel()
    const mgr = useIterationManager()

    const result = await mgr.handleDeleteIteration(makeIteration() as never)

    expect(result).toBe(false)
    expect(mocks.deleteIteration).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('删除失败提示错误', async () => {
    mocks.deleteIteration.mockRejectedValue(new Error('boom'))
    const mgr = useIterationManager()

    const result = await mgr.handleDeleteIteration(makeIteration() as never)

    expect(result).toBe(false)
    expect(ElMessage.error).toHaveBeenCalledWith('删除迭代失败')
  })

  it('edit 命令打开编辑弹窗', async () => {
    const mgr = useIterationManager()

    const result = await mgr.handleIterationCommand('edit', makeIteration() as never)

    expect(result).toBe(false)
    expect(mgr.iterationDialogVisible).toBe(true)
    expect(mgr.iterationDialogMode).toBe('edit')
    expect(mgr.iterationFormData.id).toBe(1)
  })

  it('delete 命令走删除流程', async () => {
    const mgr = useIterationManager()

    const result = await mgr.handleIterationCommand('delete', makeIteration() as never)

    expect(result).toBe(true)
    expect(mocks.deleteIteration).toHaveBeenCalledWith(1)
  })

  it('未知命令直接返回 false', async () => {
    const mgr = useIterationManager()

    const result = await mgr.handleIterationCommand('other', makeIteration() as never)

    expect(result).toBe(false)
    expect(mocks.deleteIteration).not.toHaveBeenCalled()
  })

  it('新增迭代透传到表单模块', () => {
    const mgr = useIterationManager()

    mgr.handleAddIteration(7)

    expect(mgr.iterationDialogVisible).toBe(true)
    expect(mgr.iterationFormData.project_id).toBe(7)
  })

  it('isSubmitting 反映提交中状态', () => {
    const mgr = useIterationManager()

    expect(mgr.isSubmitting).toBe(false)
    mgr.submitting = true
    expect(mgr.isSubmitting).toBe(true)
  })
})
