import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { ElMessage } from 'element-plus'

const mocks = vi.hoisted(() => ({
  getProjects: vi.fn(),
  iterationManager: {} as Record<string, unknown>,
  resourceList: {} as Record<string, unknown>,
  resourceUpload: {} as Record<string, unknown>,
  resourceOperations: {} as Record<string, unknown>,
}))

vi.mock('@/api/project', () => ({ default: { getProjects: mocks.getProjects } }))
vi.mock('@/composables/useIterationManager', () => ({
  useIterationManager: () => mocks.iterationManager,
}))
vi.mock('@/composables/useResourceList', () => ({
  useResourceList: () => mocks.resourceList,
}))
vi.mock('@/composables/useResourceUpload', () => ({
  useResourceUpload: () => mocks.resourceUpload,
}))
vi.mock('@/composables/useResourceOperations', () => ({
  useResourceOperations: () => mocks.resourceOperations,
}))

import { provideResourceManage, useResourceManage } from '../useResourceManage'
import { silenceElMessage } from '@/test-utils'

type ManageCtx = ReturnType<typeof provideResourceManage>

function createFakes(projectId: number | '' = 1) {
  const iterationManager = reactive({
    safeIterations: [{ id: 10, name: '迭代一期' }],
    validIterationsForSelect: [{ id: 10, name: '迭代一期', version: 'v1.0' }],
    selectedIterationId: null as number | null,
    iterationDialogVisible: false,
    getIterationStatsById: vi.fn(() => ({ total: 1 })),
    handleSelectIteration: vi.fn(),
    handleAddIteration: vi.fn(),
    loadIterations: vi.fn().mockResolvedValue(undefined),
    handleIterationCommand: vi.fn().mockResolvedValue(false),
    handleIterationSubmit: vi.fn().mockResolvedValue(false),
  })

  const resourceList = reactive({
    pagination: reactive({ page: 3, pageSize: 10 }),
    filterForm: reactive({ project_id: projectId as number | '', resource_type: '' }),
    resources: [],
    total: 0,
    isLoading: false,
    getResources: vi.fn().mockResolvedValue(undefined),
    handleReset: vi.fn(),
  })

  const resourceUpload = reactive({
    fileDialogMode: 'add' as 'add' | 'edit',
    isSubmitting: false,
    fileDialogVisible: false,
    fileFormData: reactive({
      project_id: 0 as number | '',
      iteration_id: null as number | null,
      name: '',
      resource_type: '',
      description: '',
      is_active: true,
    }),
    resetFileForm: vi.fn(),
    handleFileSubmit: vi.fn().mockResolvedValue(undefined),
    handleEdit: vi.fn(),
  })

  const resourceOperations = {
    handleEditNavigation: vi.fn(() => false),
    handleAnalyze: vi.fn(),
    handleDelete: vi.fn(),
  }

  mocks.iterationManager = iterationManager
  mocks.resourceList = resourceList
  mocks.resourceUpload = resourceUpload
  mocks.resourceOperations = resourceOperations

  return { iterationManager, resourceList, resourceUpload, resourceOperations }
}

let ctx: ManageCtx

const Host = defineComponent({
  setup() {
    ctx = provideResourceManage()
    return () => h('div')
  },
})

async function mountHost(projectId: number | '' = 1) {
  const fakes = createFakes(projectId)
  const wrapper = mount(Host)
  await flushPromises()
  return { ...fakes, wrapper }
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage('warning')
  silenceElMessage('error')
  silenceElMessage('success')
  mocks.getProjects.mockResolvedValue({
    data: {
      items: [
        { id: 1, name: '项目A' },
        { id: 2, name: '默认项目' },
      ],
    },
  })
})

describe('useResourceManage — 上下文与初始化', () => {
  it('useResourceManage 在已 provide 的组件树中可取到同一上下文', async () => {
    await mountHost()
    let injected: ManageCtx | undefined
    const Child = defineComponent({
      setup() {
        injected = useResourceManage()
        return () => h('span')
      },
    })
    const Parent = defineComponent({
      setup() {
        provideResourceManage()
        return () => h(Child)
      },
    })
    mount(Parent)

    expect(injected).toBeDefined()
    expect(typeof injected!.handleReset).toBe('function')
  })

  it('init 过滤默认项目并自动选中首个项目', async () => {
    const { wrapper, iterationManager, resourceList } = await mountHost('')

    await ctx.init()

    expect(ctx.projects.value).toEqual([{ id: 1, name: '项目A' }])
    expect(resourceList.filterForm.project_id).toBe(1)
    expect(iterationManager.loadIterations).toHaveBeenCalledWith(1)
    expect(resourceList.getResources).toHaveBeenCalled()
    expect(iterationManager.iterationDialogVisible).toBe(false)
    wrapper.unmount()
  })

  it('init 保留已选项目', async () => {
    const { iterationManager, resourceList } = await mountHost(2)

    await ctx.init()

    expect(resourceList.filterForm.project_id).toBe(2)
    expect(iterationManager.loadIterations).toHaveBeenCalledWith(2)
  })

  it('init 无项目时不触发资源加载', async () => {
    mocks.getProjects.mockResolvedValue({ data: { items: [{ id: 2, name: '默认项目' }] } })
    const { resourceList } = await mountHost('')

    await ctx.init()

    expect(ctx.projects.value).toEqual([])
    expect(resourceList.getResources).not.toHaveBeenCalled()
  })

  it('init 加载迭代异常时提示初始化失败', async () => {
    const { iterationManager } = await mountHost()
    iterationManager.loadIterations.mockRejectedValue(new Error('boom'))
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await ctx.init()

    expect(ElMessage.error).toHaveBeenCalledWith('页面初始化失败，请刷新重试')
    expect(errorSpy).toHaveBeenCalled()
    errorSpy.mockRestore()
  })

  it('初始化窗口期内会强制关闭弹窗，窗口期结束后不再拦截', async () => {
    vi.useFakeTimers()
    await mountHost()
    const initPromise = ctx.init()
    await vi.advanceTimersByTimeAsync(0)
    await initPromise

    ctx.iterationManager.iterationDialogVisible = true
    await nextTick()
    await nextTick()
    expect(ctx.iterationManager.iterationDialogVisible).toBe(false)

    await vi.advanceTimersByTimeAsync(600)
    ctx.iterationManager.iterationDialogVisible = true
    await nextTick()
    await nextTick()
    expect(ctx.iterationManager.iterationDialogVisible).toBe(true)

    ctx.cleanup()
    vi.useRealTimers()
  })
})

describe('useResourceManage — 新增资源弹窗', () => {
  it('未选择项目时提示并阻止打开', () => {
    const { resourceUpload } = createFakes('')
    mount(Host)

    ctx.handleAddFileWrapper()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择项目')
    expect(resourceUpload.fileDialogVisible).toBe(false)
  })

  it('已选迭代时带入迭代 ID 并清空上传组件', async () => {
    const { iterationManager, resourceList, resourceUpload } = await mountHost()
    iterationManager.selectedIterationId = 10
    const clearFiles = vi.fn()
    ctx.uploaderRef.value = { clearFiles } as never

    ctx.handleAddFileWrapper()
    await nextTick()

    expect(resourceUpload.resetFileForm).toHaveBeenCalledTimes(1)
    expect(resourceUpload.fileDialogMode).toBe('add')
    expect(resourceUpload.fileFormData.project_id).toBe(resourceList.filterForm.project_id)
    expect(resourceUpload.fileFormData.iteration_id).toBe(10)
    expect(resourceUpload.fileDialogVisible).toBe(true)
    expect(clearFiles).toHaveBeenCalledTimes(1)
  })

  it('未分类/全部迭代时迭代 ID 置空', async () => {
    const { iterationManager, resourceUpload } = await mountHost()
    iterationManager.selectedIterationId = 0

    ctx.handleAddFileWrapper()

    expect(resourceUpload.fileFormData.iteration_id).toBeNull()
  })

  it('编辑模式缺少表单引用时提示', async () => {
    await mountHost()
    ctx.resourceUpload.fileDialogMode = 'edit'
    ctx.fileFormLocalRef.value = null

    await ctx.handleFileSubmitWrapper()

    expect(ElMessage.error).toHaveBeenCalledWith('表单初始化失败，请刷新页面重试')
  })

  it('编辑模式转交表单提交', async () => {
    await mountHost()
    const formRef = { validate: vi.fn() }
    ctx.resourceUpload.fileDialogMode = 'edit'
    ctx.fileFormLocalRef.value = formRef as never

    await ctx.handleFileSubmitWrapper()

    expect(ctx.resourceUpload.handleFileSubmit).toHaveBeenCalledWith(formRef)
  })

  it('新增模式缺少上传组件或未选文件时给出提示', async () => {
    await mountHost()
    ctx.resourceUpload.fileDialogMode = 'add'
    ctx.uploaderRef.value = null

    await ctx.handleFileSubmitWrapper()
    expect(ElMessage.error).toHaveBeenCalledWith('上传组件初始化失败，请刷新页面重试')

    ctx.uploaderRef.value = { fileCount: 0 } as never
    await ctx.handleFileSubmitWrapper()
    expect(ElMessage.warning).toHaveBeenCalledWith('请选择文件')
  })

  it('新增模式触发上传组件 upload', async () => {
    await mountHost()
    const upload = vi.fn().mockResolvedValue(undefined)
    ctx.uploaderRef.value = { fileCount: 2, upload } as never

    await ctx.handleFileSubmitWrapper()

    expect(upload).toHaveBeenCalledTimes(1)
  })

  it('批量上传成功回到第一页并刷新', () => {
    const { resourceList, resourceUpload } = createFakes()
    mount(Host)
    resourceUpload.fileDialogVisible = true
    resourceList.pagination.page = 4

    ctx.handleBatchUploadSuccess()

    expect(resourceUpload.fileDialogVisible).toBe(false)
    expect(resourceList.pagination.page).toBe(1)
    expect(resourceList.getResources).toHaveBeenCalledTimes(1)
  })

  it('批量上传失败保持静默', () => {
    mount(Host)

    expect(() => ctx.handleBatchUploadError()).not.toThrow()
  })
})

describe('useResourceManage — 编辑与提交', () => {
  it('handleEditWrapper 仅在需要弹窗时打开编辑', async () => {
    const { resourceUpload, resourceOperations } = await mountHost()
    const row = { id: 1, name: '需求' }

    ctx.handleEditWrapper(row as never)
    expect(resourceUpload.handleEdit).not.toHaveBeenCalled()

    resourceOperations.handleEditNavigation.mockReturnValue(true)
    ctx.handleEditWrapper(row as never)
    expect(resourceUpload.handleEdit).toHaveBeenCalledWith(row)
  })

  it('切换迭代后回到第一页并刷新', async () => {
    const { iterationManager, resourceList } = await mountHost()
    resourceList.pagination.page = 5

    await ctx.handleSelectIterationAndRefresh(10)

    expect(iterationManager.handleSelectIteration).toHaveBeenCalledWith(10)
    expect(resourceList.pagination.page).toBe(1)
    expect(resourceList.getResources).toHaveBeenCalledTimes(1)
  })

  it('切换迭代异常时提示', async () => {
    const { iterationManager } = await mountHost()
    iterationManager.handleSelectIteration.mockImplementation(() => {
      throw new Error('boom')
    })
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    await ctx.handleSelectIterationAndRefresh(10)

    expect(ElMessage.error).toHaveBeenCalledWith('切换迭代失败，请重试')
    errorSpy.mockRestore()
  })

  it('迭代命令需要刷新时重载迭代与资源', async () => {
    const { iterationManager, resourceList } = await mountHost()
    iterationManager.handleIterationCommand.mockResolvedValue(true)

    await ctx.handleIterationCommandWrapper('archive', { id: 10 } as never)

    expect(iterationManager.loadIterations).toHaveBeenCalledWith(
      Number(resourceList.filterForm.project_id)
    )
    expect(resourceList.getResources).toHaveBeenCalledTimes(1)
  })

  it('迭代命令无需刷新时不动列表', async () => {
    const { iterationManager, resourceList } = await mountHost()

    await ctx.handleIterationCommandWrapper('edit', { id: 10 } as never)

    expect(iterationManager.loadIterations).not.toHaveBeenCalled()
    expect(resourceList.getResources).not.toHaveBeenCalled()
  })

  it('迭代表单未就绪或校验失败时不提交', async () => {
    const { iterationManager } = await mountHost()
    ctx.iterationFormLocalRef.value = null

    await ctx.handleIterationSubmitWrapper()
    expect(ElMessage.error).toHaveBeenCalledWith('表单初始化失败，请刷新页面重试')

    ctx.iterationFormLocalRef.value = { validate: vi.fn().mockRejectedValue(new Error('bad')) }
    await ctx.handleIterationSubmitWrapper()
    expect(iterationManager.handleIterationSubmit).not.toHaveBeenCalled()
  })

  it('迭代表单提交且需要刷新时重载数据', async () => {
    const { iterationManager, resourceList } = await mountHost()
    const formRef = { validate: vi.fn().mockResolvedValue(true) }
    ctx.iterationFormLocalRef.value = formRef
    iterationManager.handleIterationSubmit.mockResolvedValue(true)

    await ctx.handleIterationSubmitWrapper()

    expect(iterationManager.handleIterationSubmit).toHaveBeenCalledWith(formRef)
    expect(resourceList.pagination.page).toBe(1)
    expect(resourceList.getResources).toHaveBeenCalledTimes(1)
  })

  it('handleAddIterationWrapper 传入数字项目 ID', () => {
    const { iterationManager } = createFakes(7)
    mount(Host)

    ctx.handleAddIterationWrapper()

    expect(iterationManager.handleAddIteration).toHaveBeenCalledWith(7)
  })
})

describe('useResourceManage — 重置、联动与派生状态', () => {
  it('handleReset 清空资源并在无项目时重载空迭代列表', async () => {
    const { iterationManager, resourceList } = await mountHost('')
    resourceList.filterForm.project_id = ''

    await ctx.handleReset()

    expect(resourceList.handleReset).toHaveBeenCalledTimes(1)
    expect(iterationManager.loadIterations).toHaveBeenCalledWith(0)
  })

  it('项目变化时重置迭代并刷新资源', async () => {
    const { iterationManager, resourceList } = await mountHost()
    iterationManager.selectedIterationId = 10

    resourceList.filterForm.project_id = 2
    await flushPromises()

    expect(resourceList.pagination.page).toBe(1)
    expect(iterationManager.selectedIterationId).toBeNull()
    expect(iterationManager.loadIterations).toHaveBeenCalledWith(2)
    expect(resourceList.getResources).toHaveBeenCalled()
  })

  it('isFileSubmitting 依模式读取不同来源', async () => {
    const { resourceUpload } = await mountHost()

    resourceUpload.fileDialogMode = 'edit'
    resourceUpload.isSubmitting = true
    expect(ctx.isFileSubmitting.value).toBe(true)

    resourceUpload.fileDialogMode = 'add'
    ctx.uploaderRef.value = { uploading: true } as never
    expect(ctx.isFileSubmitting.value).toBe(true)

    ctx.uploaderRef.value = null
    expect(ctx.isFileSubmitting.value).toBe(false)
  })

  it('暴露迭代数据与统计查询', async () => {
    const { iterationManager } = await mountHost()

    expect(ctx.safeIterationsArray.value).toEqual(iterationManager.safeIterations)
    expect(ctx.validIterationsForSelectArray.value).toEqual(
      iterationManager.validIterationsForSelect
    )
    ctx.getIterationStats(10)
    expect(iterationManager.getIterationStatsById).toHaveBeenCalledWith(10)
  })

  it('cleanup 清理初始化定时器', async () => {
    await mountHost()
    const initPromise = ctx.init()
    await flushPromises()

    expect(() => ctx.cleanup()).not.toThrow()
    await initPromise
  })
})
