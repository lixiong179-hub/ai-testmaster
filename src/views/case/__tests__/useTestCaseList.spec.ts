import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const routeMock = vi.hoisted(() => ({ query: {} as Record<string, unknown> }))
const routerMock = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock('vue-router', () => ({
  useRoute: () => routeMock,
  useRouter: () => routerMock,
}))

vi.mock('@/api/case', () => ({
  caseApi: {
    getList: vi.fn(),
    delete: vi.fn(),
    batchDelete: vi.fn(),
  },
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: vi.fn() },
}))

vi.mock('@/composables/useCaseExport', () => ({
  useCaseExport: () => ({
    exporting: ref(false),
    handleExportAll: vi.fn(),
    handleExportSelected: vi.fn(),
  }),
}))

import { caseApi } from '@/api/case'
import projectApi from '@/api/project'
import { useTestCaseList } from '../useTestCaseList'

const getListMock = vi.mocked(caseApi.getList)
const deleteMock = vi.mocked(caseApi.delete)
const batchDeleteMock = vi.mocked(caseApi.batchDelete)
const getProjectsMock = vi.mocked(projectApi.getProjects)

function setup() {
  let api!: ReturnType<typeof useTestCaseList>
  const Host = defineComponent({
    setup() {
      api = useTestCaseList()
      return () => h('div')
    },
  })
  const wrapper = mount(Host)
  return { api, wrapper }
}

async function mountReady(query: Record<string, unknown> = {}) {
  routeMock.query = query
  const ctx = setup()
  await flushPromises()
  return ctx
}

describe('useTestCaseList — 初始化', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeMock.query = {}
    getProjectsMock.mockResolvedValue({
      data: { items: [{ id: 3, name: '项目C' }] },
    } as never)
    getListMock.mockResolvedValue({
      items: [{ id: 1, title: '用例A' }],
      total: 1,
      stats: { total: 9, automated: 4, manual: 5, high_priority: 2 },
    } as never)
    vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
    vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
    vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)
  })

  it('挂载时加载项目列表，无项目不拉用例', async () => {
    const { api } = await mountReady()

    expect(getProjectsMock).toHaveBeenCalledWith({ page: 1, page_size: 100 })
    expect(api.projects.value).toEqual([{ id: 3, name: '项目C' }])
    expect(getListMock).not.toHaveBeenCalled()
  })

  it('路由 query 带 projectId 时自动拉取用例并写入统计', async () => {
    const { api } = await mountReady({ projectId: '3' })

    expect(api.selectedProjectId.value).toBe(3)
    expect(getListMock).toHaveBeenCalledTimes(1)
    expect(api.testCases.value).toHaveLength(1)
    expect(api.total.value).toBe(1)
    expect(api.stats).toEqual({ total: 9, automated: 4, manual: 5, highPriority: 2 })
    expect(api.selectedProjectName.value).toBe('项目C')
  })

  it('项目加载失败时提示错误', async () => {
    getProjectsMock.mockRejectedValue(new Error('网络错误'))
    await mountReady()

    expect(ElMessage.error).toHaveBeenCalledWith('网络错误')
  })
})

describe('useTestCaseList — 取数口径', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeMock.query = { projectId: '3' }
    getProjectsMock.mockResolvedValue({ data: { items: [] } } as never)
    getListMock.mockResolvedValue({ items: [], total: 0 } as never)
    vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
  })

  it('请求携带筛选条件与分页参数', async () => {
    const { api } = await mountReady({ projectId: '3' })
    api.filters.keyword = '登录'
    api.filters.priority = 1
    api.page.value = 2

    await api.fetchTestCases()

    expect(getListMock).toHaveBeenLastCalledWith(
      3,
      expect.objectContaining({
        keyword: '登录',
        priority: 1,
        page: 2,
        page_size: 20,
        sort_by: 'create_time',
        sort_order: 'desc',
      })
    )
  })

  it('target_device 为 undefined 时从请求中剔除', async () => {
    const { api } = await mountReady({ projectId: '3' })
    api.filters.target_device = undefined

    await api.fetchTestCases()

    const lastCall = getListMock.mock.calls[getListMock.mock.calls.length - 1]
    const params = lastCall[1] as Record<string, unknown>
    expect('target_device' in params).toBe(false)
  })

  it('指定 target_device 时保留', async () => {
    const { api } = await mountReady({ projectId: '3' })
    api.filters.target_device = 'general'

    await api.fetchTestCases()

    expect(getListMock.mock.calls[getListMock.mock.calls.length - 1][1]).toMatchObject({
      target_device: 'general',
    })
  })

  it('未选项目时清空列表且不请求', async () => {
    const { api } = await mountReady()
    api.testCases.value = [{ id: 1 } as never]
    api.total.value = 5

    await api.fetchTestCases()

    expect(api.testCases.value).toEqual([])
    expect(api.total.value).toBe(0)
    expect(getListMock).not.toHaveBeenCalled()
  })

  it('请求失败时提示并清空列表', async () => {
    getListMock.mockRejectedValue(new Error('服务异常'))
    const { api } = await mountReady({ projectId: '3' })

    await api.fetchTestCases()

    expect(ElMessage.error).toHaveBeenCalledWith('服务异常')
    expect(api.testCases.value).toEqual([])
    expect(api.loading.value).toBe(false)
  })
})

describe('useTestCaseList — 交互', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeMock.query = { projectId: '3' }
    getProjectsMock.mockResolvedValue({ data: { items: [] } } as never)
    getListMock.mockResolvedValue({ items: [], total: 0 } as never)
    vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
    vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
    vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)
  })

  it('切换项目重置分页与选择并重新拉取', async () => {
    const { api } = await mountReady({ projectId: '3' })
    getListMock.mockClear()
    api.page.value = 3
    api.selectedRows.value = [{ id: 1 } as never]

    await api.handleProjectChange()

    expect(api.page.value).toBe(1)
    expect(api.selectedRows.value).toEqual([])
    expect(getListMock).toHaveBeenCalledTimes(1)
  })

  it('排序变更映射字段与方向并刷新', async () => {
    const { api } = await mountReady({ projectId: '3' })
    getListMock.mockClear()

    api.handleSortChange({ prop: 'title', order: 'ascending' })
    expect(api.filters.sort_by).toBe('title')
    expect(api.filters.sort_order).toBe('asc')

    api.handleSortChange({ prop: '', order: null })
    expect(api.filters.sort_by).toBe('create_time')
    expect(api.filters.sort_order).toBe('desc')
    expect(getListMock).toHaveBeenCalledTimes(2)
  })

  it('改变每页条数回到第一页', async () => {
    const { api } = await mountReady({ projectId: '3' })
    api.page.value = 4

    api.handlePageSizeChange(50)

    expect(api.pageSize.value).toBe(50)
    expect(api.page.value).toBe(1)
  })

  it('重置筛选清空全部条件并刷新', async () => {
    const { api } = await mountReady({ projectId: '3' })
    Object.assign(api.filters, {
      keyword: 'k',
      module: 'm',
      priority: 1,
      case_type: 'manual',
      status: 'active',
      created_by: 'u',
      target_device: 'general',
      sort_by: 'title',
      sort_order: 'asc',
    })
    api.page.value = 2

    api.resetFilters()

    expect(api.filters).toEqual({
      keyword: '',
      module: '',
      priority: undefined,
      case_type: undefined,
      status: undefined,
      created_by: '',
      target_device: undefined,
      sort_by: 'create_time',
      sort_order: 'desc',
    })
    expect(api.page.value).toBe(1)
  })
})

describe('useTestCaseList — 删除', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeMock.query = { projectId: '3' }
    getProjectsMock.mockResolvedValue({ data: { items: [] } } as never)
    getListMock.mockResolvedValue({ items: [], total: 0 } as never)
    vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
    vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
  })

  it('确认后删除单条并刷新', async () => {
    const { api } = await mountReady({ projectId: '3' })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)

    await api.handleDelete({ id: 11, project_id: 3, title: '登录用例' } as never)

    expect(ElMessageBox.confirm).toHaveBeenCalledWith('确定删除用例"登录用例"吗？', '提示', {
      type: 'warning',
    })
    expect(deleteMock).toHaveBeenCalledWith(11, 3)
    expect(ElMessage.success).toHaveBeenCalledWith('删除成功')
  })

  it('取消确认时不删除也不报错', async () => {
    const { api } = await mountReady({ projectId: '3' })
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel' as never)

    await api.handleDelete({ id: 11, project_id: 3, title: 'x' } as never)

    expect(deleteMock).not.toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('删除失败时透出错误信息', async () => {
    const { api } = await mountReady({ projectId: '3' })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    deleteMock.mockRejectedValue(new Error('用例已锁定'))

    await api.handleDelete({ id: 11, project_id: 3, title: 'x' } as never)

    expect(ElMessage.error).toHaveBeenCalledWith('用例已锁定')
  })

  it('批量删除按选中 ID 提交并清空选择', async () => {
    const { api } = await mountReady({ projectId: '3' })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
    api.selectedRows.value = [{ id: 1 }, { id: 2 }] as never

    await api.handleBatchDelete()

    expect(batchDeleteMock).toHaveBeenCalledWith(3, [1, 2])
    expect(api.selectedRows.value).toEqual([])
    expect(ElMessage.success).toHaveBeenCalledWith('批量删除成功')
  })

  it('未选项目时批量删除直接返回', async () => {
    const { api } = await mountReady()
    api.selectedProjectId.value = undefined

    await api.handleBatchDelete()

    expect(batchDeleteMock).not.toHaveBeenCalled()
  })
})

describe('useTestCaseList — 映射与跳转', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    routeMock.query = { projectId: '3' }
    getProjectsMock.mockResolvedValue({ data: { items: [] } } as never)
    getListMock.mockResolvedValue({ items: [], total: 0 } as never)
    vi.spyOn(ElMessage, 'warning').mockImplementation(() => undefined as never)
  })

  it('优先级与类型的标签映射', async () => {
    const { api } = await mountReady({ projectId: '3' })

    expect([api.getPriorityType(1), api.getPriorityType(2), api.getPriorityType(3)]).toEqual([
      'danger',
      'warning',
      'success',
    ])
    expect([api.getPriorityLabel(1), api.getPriorityLabel(2), api.getPriorityLabel(3)]).toEqual([
      '高',
      '中',
      '低',
    ])
    expect(api.getTypeLabel('ui_automation')).toBe('UI自动化')
    expect(api.getTypeLabel('unknown')).toBe('unknown')
    expect(api.getTypeTagType('api_automation')).toBe('success')
    expect(api.getTypeTagType('unknown')).toBe('info')
  })

  it('质量分析跳转，缺 ID 时提示', async () => {
    const { api } = await mountReady({ projectId: '3' })

    api.handleQualityAnalysis({ id: 0 } as never)
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择具体用例再进入质量分析')

    api.handleQualityAnalysis({ id: 5 } as never)
    expect(routerMock.push).toHaveBeenCalledWith('/home/case/quality/5')
  })

  it('批量建任务校验项目与选择后跳转', async () => {
    const { api } = await mountReady({ projectId: '3' })

    api.selectedProjectId.value = undefined
    api.handleBatchCreateTask()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')

    api.selectedProjectId.value = 3
    api.handleBatchCreateTask()
    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择用例')

    api.selectedRows.value = [{ id: 7 }, { id: 8 }] as never
    api.handleBatchCreateTask()
    expect(routerMock.push).toHaveBeenCalledWith({
      path: '/home/task/create/3',
      query: { case_ids: '7,8' },
    })
  })

  it('批量定位校验组件就绪并调用 open', async () => {
    const { api } = await mountReady({ projectId: '3' })
    api.selectedRows.value = [{ id: 7 }] as never

    api.handleBatchLocate()
    expect(ElMessage.warning).toHaveBeenCalledWith('批量定位组件未就绪')

    const open = vi.fn()
    api.setBatchLocatorRef({ open } as never)
    api.handleBatchLocate()
    expect(open).toHaveBeenCalledWith([7])
  })
})
