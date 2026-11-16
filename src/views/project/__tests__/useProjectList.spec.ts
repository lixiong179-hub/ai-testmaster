import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reactive } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { ElMessageBox } from 'element-plus'
import {
  createComposableHost,
  createFormInstanceMock,
  mockCancel,
  mockConfirm,
  silenceElMessage,
} from '@/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  store: {} as Record<string, unknown>,
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/store/project', () => ({
  useProjectStore: () => mocks.store,
}))

import { useProjectList } from '../useProjectList'

type Ctx = ReturnType<typeof useProjectList>

function createStore(overrides: Record<string, unknown> = {}) {
  return reactive({
    projects: [
      { id: 1, name: 'Alpha 项目', status: 1, source: 'manual' },
      { id: 2, name: 'beta 项目', status: 0, source: 'url_quick_test' },
      { id: 3, name: 'Gamma', status: 9 },
    ],
    currentPage: 1,
    pageSize: 10,
    loading: false,
    fetchProjects: vi.fn().mockResolvedValue(undefined),
    createProject: vi.fn().mockResolvedValue(11),
    deleteProject: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  })
}

const host = createComposableHost(() => useProjectList())
let ctx: Ctx

async function mountHost(storePatch: Record<string, unknown> = {}) {
  mocks.store = createStore(storePatch)
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
})

describe('useProjectList — 派生数据', () => {
  it('关键词过滤忽略大小写', async () => {
    await mountHost()
    ctx.searchKeyword.value = 'beta'

    expect(ctx.filteredProjects.value).toHaveLength(1)
    expect(ctx.filteredProjects.value[0].id).toBe(2)
  })

  it('来源过滤把缺失来源视为手动创建', async () => {
    await mountHost()

    ctx.sourceFilter.value = 'manual'
    expect(ctx.filteredProjects.value.map((p) => p.id)).toEqual([1, 3])

    ctx.sourceFilter.value = 'url_quick_test'
    expect(ctx.filteredProjects.value.map((p) => p.id)).toEqual([2])
  })

  it('来源与状态标签映射', async () => {
    await mountHost()

    expect(ctx.getSourceTagType('url_quick_test')).toBe('primary')
    expect(ctx.getSourceTagType('manual')).toBe('info')
    expect(ctx.getSourceText('url_quick_test')).toBe('快速测试')
    expect(ctx.getSourceText(undefined)).toBe('手动创建')

    expect(ctx.getStatusType(0)).toBe('info')
    expect(ctx.getStatusType(1)).toBe('success')
    expect(ctx.getStatusType(2)).toBe('warning')
    expect(ctx.getStatusType(9)).toBe('info')
    expect(ctx.getStatusText(1)).toBe('正常')
    expect(ctx.getStatusText(2)).toBe('归档')
    expect(ctx.getStatusText(9)).toBe('未知')
  })
})

describe('useProjectList — 查询与分页', () => {
  it('挂载时拉取项目列表', async () => {
    await mountHost()

    expect((mocks.store as { fetchProjects: unknown }).fetchProjects).toHaveBeenCalled()
  })

  it('搜索与翻页都触发重新拉取', async () => {
    await mountHost()
    const fetchProjects = (mocks.store as { fetchProjects: ReturnType<typeof vi.fn> }).fetchProjects
    fetchProjects.mockClear()

    ctx.handleSearch()
    expect(fetchProjects).toHaveBeenCalledTimes(1)

    ctx.handleCurrentChange(3)
    expect(mocks.store.currentPage).toBe(3)
    expect(fetchProjects).toHaveBeenCalledTimes(2)

    ctx.handleSizeChange(20)
    expect(mocks.store.pageSize).toBe(20)
    expect(mocks.store.currentPage).toBe(1)
    expect(fetchProjects).toHaveBeenCalledTimes(3)
  })
})

describe('useProjectList — 新建项目', () => {
  it('打开弹窗时重置表单', async () => {
    await mountHost()
    ctx.projectForm.value.name = '旧值'
    ctx.projectForm.value.project_type = 'app'

    ctx.openCreateDialog()

    expect(ctx.dialogVisible.value).toBe(true)
    expect(ctx.projectForm.value.name).toBe('')
    expect(ctx.projectForm.value.project_type).toBe('web')
    expect(ctx.projectForm.value.web_env_configs.test.url).toBe('')
  })

  it('表单未挂载时不做任何事', async () => {
    await mountHost()

    await ctx.createProject()

    expect((mocks.store as { createProject: unknown }).createProject).not.toHaveBeenCalled()
  })

  it('web 项目创建成功并跳转详情', async () => {
    await mountHost()
    ctx.projectFormRef.value = createFormInstanceMock({ withCallback: true }) as never
    ctx.projectForm.value.name = '新项目'
    ctx.projectForm.value.description = '说明'

    await ctx.createProject()

    expect((mocks.store as { createProject: unknown }).createProject).toHaveBeenCalledWith({
      name: '新项目',
      description: '说明',
      project_type: 'web',
      web_env_configs: expect.objectContaining({ test: expect.any(Object) }),
    })
    expect(ctx.dialogVisible.value).toBe(false)
    expect(mocks.push).toHaveBeenCalledWith('/home/project/detail?id=11')
  })

  it('app 项目不提交环境配置', async () => {
    await mountHost()
    ctx.projectFormRef.value = createFormInstanceMock({ withCallback: true }) as never
    ctx.projectForm.value.project_type = 'app'

    await ctx.createProject()

    expect((mocks.store as { createProject: unknown }).createProject).toHaveBeenCalledWith(
      expect.objectContaining({ web_env_configs: undefined })
    )
  })

  it('校验失败时不创建', async () => {
    await mountHost()
    ctx.projectFormRef.value = createFormInstanceMock({ valid: false, withCallback: true }) as never

    await ctx.createProject()

    expect((mocks.store as { createProject: unknown }).createProject).not.toHaveBeenCalled()
  })

  it('接口未返回 ID 时不跳转也不关闭弹窗', async () => {
    await mountHost({ createProject: vi.fn().mockResolvedValue(0) })
    ctx.projectFormRef.value = createFormInstanceMock({ withCallback: true }) as never
    ctx.dialogVisible.value = true

    await ctx.createProject()

    expect(mocks.push).not.toHaveBeenCalled()
    expect(ctx.dialogVisible.value).toBe(true)
  })
})

describe('useProjectList — 导航与删除', () => {
  it('三种跳转路径', async () => {
    await mountHost()

    ctx.goToDetail(5)
    expect(mocks.push).toHaveBeenCalledWith('/home/project/detail?id=5')

    ctx.goToTaskList(6)
    expect(mocks.push).toHaveBeenCalledWith('/home/task/list/6')

    ctx.goToTestPointManagement(7)
    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/test-point-management',
      query: { projectId: '7' },
    })
  })

  it('确认删除后调用删除接口', async () => {
    await mountHost()

    ctx.confirmDelete(3)
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect((mocks.store as { deleteProject: unknown }).deleteProject).toHaveBeenCalledWith(3)
  })

  it('取消删除不调用接口', async () => {
    mockCancel()
    await mountHost()

    ctx.confirmDelete(3)
    await flushPromises()

    expect((mocks.store as { deleteProject: unknown }).deleteProject).not.toHaveBeenCalled()
  })
})
