import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ElMessage, ElMessageBox } from 'element-plus'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  deleteFile: vi.fn(),
  deleteUIPrototypeProject: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/api/file', () => {
  const api = { deleteFile: mocks.deleteFile }
  return { fileApi: api, default: api }
})

vi.mock('@/api/uiPrototype', () => {
  const api = { deleteUIPrototypeProject: mocks.deleteUIPrototypeProject }
  return { uiPrototypeApi: api, default: api }
})

import { mockCancel, mockConfirm, silenceElMessage } from '@/test-utils'
import { useResourceOperations } from '../useResourceOperations'

function makeManager(overrides: Record<string, unknown> = {}) {
  return {
    iterations: [{ id: 1, name: '迭代A' }],
    selectedIterationId: null as number | null,
    getIterationNameById: vi.fn((id: number) => (id === 1 ? '迭代A' : '未分类')),
    showError: vi.fn(),
    ...overrides,
  } as never
}

function makeRow(overrides: Record<string, unknown> = {}) {
  return {
    id: 11,
    project_id: 7,
    name: '需求文档.pdf',
    resource_type: 'requirement',
    source_type: 'file',
    iteration_id: null,
    ...overrides,
  } as never
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
  mocks.deleteFile.mockResolvedValue({ code: 200 })
  mocks.deleteUIPrototypeProject.mockResolvedValue({ code: 200 })
})

describe('useResourceOperations — AI 分析跳转', () => {
  it('文件资源携带 file_id 跳转测试点管理', () => {
    const refresh = vi.fn()
    const { handleAnalyze } = useResourceOperations(makeManager(), refresh)

    handleAnalyze(makeRow())

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/test-point-management',
      query: {
        projectId: '7',
        file_id: '11',
        openExtract: '1',
        filename: '需求文档.pdf',
      },
    })
  })

  it('UI 原型资源不携带 file_id', () => {
    const { handleAnalyze } = useResourceOperations(makeManager(), vi.fn())

    handleAnalyze(
      makeRow({ resource_type: 'ui_mockup', source_type: 'ui_prototype', prototype_project_id: 21 })
    )

    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/test-point-management',
      query: {
        projectId: '7',
        openExtract: '1',
        filename: '需求文档.pdf',
      },
    })
  })

  it('行内迭代 ID 为空时使用当前选中迭代', () => {
    const manager = makeManager({ selectedIterationId: 1 })
    const { handleAnalyze } = useResourceOperations(manager, vi.fn())

    handleAnalyze(makeRow())

    expect(mocks.push).toHaveBeenCalled()
  })
})

describe('useResourceOperations — 删除', () => {
  it('删除 UI 原型项目使用 prototype_project_id', async () => {
    const refresh = vi.fn()
    const { handleDelete } = useResourceOperations(makeManager(), refresh)
    const row = makeRow({
      resource_type: 'ui_mockup',
      source_type: 'ui_prototype',
      prototype_project_id: 21,
      screen_count: 8,
    })

    await handleDelete(row)

    const confirmArg = (ElMessageBox.confirm as unknown as { mock: { calls: unknown[][] } }).mock
      .calls[0][0] as string
    expect(confirmArg).toContain('确定要删除UI原型项目 "需求文档.pdf" 吗？')
    expect(confirmArg).toContain('其下所有 8 张图片')
    expect(mocks.deleteUIPrototypeProject).toHaveBeenCalledWith(21)
    expect(ElMessage.success).toHaveBeenCalledWith('UI原型项目 "需求文档.pdf" 已删除')
    expect(refresh).toHaveBeenCalled()
  })

  it('原型项目无 prototype_project_id 时回退行 id', async () => {
    const { handleDelete } = useResourceOperations(makeManager(), vi.fn())

    await handleDelete(makeRow({ resource_type: 'ui_mockup', source_type: 'ui_prototype' }))

    expect(mocks.deleteUIPrototypeProject).toHaveBeenCalledWith(11)
  })

  it('删除文件时提示所属迭代', async () => {
    const refresh = vi.fn()
    const { handleDelete } = useResourceOperations(makeManager(), refresh)

    await handleDelete(makeRow({ iteration_id: 1 }))

    const confirmArg = (ElMessageBox.confirm as unknown as { mock: { calls: unknown[][] } }).mock
      .calls[0][0] as string
    expect(confirmArg).toContain('所属迭代：迭代A')
    expect(mocks.deleteFile).toHaveBeenCalledWith(11, 7)
    expect(ElMessage.success).toHaveBeenCalledWith('文件 "需求文档.pdf" 已删除')
    expect(refresh).toHaveBeenCalled()
  })

  it('迭代名未知时不追加所属迭代信息', async () => {
    const { handleDelete } = useResourceOperations(makeManager(), vi.fn())

    await handleDelete(makeRow({ iteration_id: 99 }))

    const confirmArg = (ElMessageBox.confirm as unknown as { mock: { calls: unknown[][] } }).mock
      .calls[0][0] as string
    expect(confirmArg).not.toContain('所属迭代')
  })

  it('取消删除时不提示错误', async () => {
    mockCancel()
    const manager = makeManager()
    const refresh = vi.fn()
    const { handleDelete } = useResourceOperations(manager, refresh)

    await handleDelete(makeRow())

    expect(mocks.deleteFile).not.toHaveBeenCalled()
    expect((manager as { showError: unknown }).showError).not.toHaveBeenCalled()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('删除异常交由 showError 处理', async () => {
    mocks.deleteFile.mockRejectedValue(new Error('boom'))
    const manager = makeManager()
    const { handleDelete } = useResourceOperations(manager, vi.fn())

    await handleDelete(makeRow())

    expect((manager as { showError: unknown }).showError).toHaveBeenCalledWith(
      '删除',
      expect.any(Error)
    )
  })
})

describe('useResourceOperations — 编辑导航', () => {
  it('UI 原型资源跳转原型页并返回 false', () => {
    const manager = makeManager({ selectedIterationId: 1 })
    const { handleEditNavigation } = useResourceOperations(manager, vi.fn())

    const result = handleEditNavigation(
      makeRow({ resource_type: 'ui_mockup', source_type: 'ui_prototype', prototype_project_id: 21 })
    )

    expect(result).toBe(false)
    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/requirement/ui-prototype',
      query: {
        project_id: '7',
        prototype_project_id: '21',
        name: '需求文档.pdf',
        iteration_id: '1',
        iteration_name: '迭代A',
      },
    })
  })

  it('未选中迭代时不携带迭代信息', () => {
    const { handleEditNavigation } = useResourceOperations(makeManager(), vi.fn())

    handleEditNavigation(makeRow({ resource_type: 'ui_mockup', source_type: 'ui_prototype' }))

    const arg = (mocks.push as unknown as { mock: { calls: { query: unknown }[][] } }).mock
      .calls[0][0]
    expect(arg.query).not.toHaveProperty('iteration_id')
  })

  it('文件资源交由弹窗编辑', () => {
    const { handleEditNavigation } = useResourceOperations(makeManager(), vi.fn())

    expect(handleEditNavigation(makeRow())).toBe(true)
    expect(mocks.push).not.toHaveBeenCalled()
  })
})
