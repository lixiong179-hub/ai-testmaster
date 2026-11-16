import { describe, it, expect, vi, beforeEach } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  route: { query: {} as Record<string, unknown> },
  push: vi.fn(),
  getUIScreenList: vi.fn(),
  getUIPrototypeProjectList: vi.fn(),
  parseUIScreens: vi.fn(),
  deleteUIScreen: vi.fn(),
  uploadUIScreens: vi.fn(),
  generatePageFlow: vi.fn(),
  getIteration: vi.fn(),
  getImageUrl: vi.fn(),
  cleanupImageCache: vi.fn(),
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  confirm: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/api/uiPrototype', () => ({
  uiPrototypeApi: {
    getUIScreenList: mocks.getUIScreenList,
    getUIPrototypeProjectList: mocks.getUIPrototypeProjectList,
    parseUIScreens: mocks.parseUIScreens,
    deleteUIScreen: mocks.deleteUIScreen,
    uploadUIScreens: mocks.uploadUIScreens,
  },
}))

vi.mock('@/api/uiPrototypeFlow', () => ({
  uiPrototypeFlowApi: { generatePageFlow: mocks.generatePageFlow },
}))

vi.mock('@/api/iteration', () => ({
  iterationApi: { getIteration: mocks.getIteration },
}))

vi.mock('@/composables/useScreenImageUrl', () => ({
  useScreenImageUrl: () => ({
    getImageUrl: mocks.getImageUrl,
    cleanupImageCache: mocks.cleanupImageCache,
  }),
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: mocks.success,
    warning: mocks.warning,
    error: mocks.error,
    info: mocks.info,
  },
  ElMessageBox: { confirm: mocks.confirm },
}))

import { useUIPrototype } from '../useUIPrototype'

type ScreenLike = Record<string, unknown>

let ctx: ReturnType<typeof useUIPrototype>

const TestHost = defineComponent({
  setup() {
    ctx = useUIPrototype()
    return () => h('div')
  },
})

const defaultQuery: Record<string, unknown> = {
  project_id: '7',
  prototype_project_id: '12',
  name: '洪恩UI原型',
}

function setScreens(items: ScreenLike[]) {
  mocks.getUIScreenList.mockResolvedValue({ data: { items } })
}

function setProjects(items: Record<string, unknown>[]) {
  mocks.getUIPrototypeProjectList.mockResolvedValue({ data: { items } })
}

async function mountHost(query: Record<string, unknown> = defaultQuery) {
  mocks.route.query = query
  const wrapper = mount(TestHost)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getImageUrl.mockResolvedValue('blob:mock')
  mocks.getUIScreenList.mockResolvedValue({ data: { items: [] } })
  mocks.getUIPrototypeProjectList.mockResolvedValue({ data: { items: [] } })
  mocks.parseUIScreens.mockResolvedValue({})
  mocks.deleteUIScreen.mockResolvedValue({})
  mocks.uploadUIScreens.mockResolvedValue({ total: 0 })
  mocks.generatePageFlow.mockResolvedValue({ success: true })
  mocks.getIteration.mockResolvedValue({ data: { id: 5, name: '接口迭代' } })
})

describe('useUIPrototype — 路由派生', () => {
  it('从 query 解析项目、原型与迭代信息', async () => {
    await mountHost({
      ...defaultQuery,
      iteration_id: '5',
      iteration_name: '迭代一期',
      iteration_version: 'v2.0',
    })

    expect(ctx.projectId.value).toBe(7)
    expect(ctx.prototypeProjectId.value).toBe(12)
    expect(ctx.prototypeName.value).toBe('洪恩UI原型')
    expect(ctx.iterationName.value).toBe('迭代一期')
    expect(ctx.currentIteration.value).toMatchObject({
      id: 5,
      project_id: 7,
      name: '迭代一期',
      version: 'v2.0',
    })
    expect(mocks.getIteration).not.toHaveBeenCalled()
  })

  it('原型名缺省回退为 UI原型图', async () => {
    await mountHost({ project_id: '7', prototype_project_id: '12' })

    expect(ctx.prototypeName.value).toBe('UI原型图')
    expect(ctx.iterationName.value).toBe('')
  })

  it('仅有序号无名称时回查迭代详情', async () => {
    await mountHost({ ...defaultQuery, iteration_id: '5' })

    expect(mocks.getIteration).toHaveBeenCalledWith(5)
    expect(ctx.currentIteration.value).toMatchObject({ id: 5, name: '接口迭代' })
  })

  it('迭代详情 404 时静默处理，其它错误告警', async () => {
    mocks.getIteration.mockRejectedValueOnce({ response: { status: 404 } })
    await mountHost({ ...defaultQuery, iteration_id: '5' })
    expect(mocks.warning).not.toHaveBeenCalled()

    mocks.getIteration.mockRejectedValueOnce({ response: { status: 500 } })
    await mountHost({ ...defaultQuery, iteration_id: '5' })
    expect(mocks.warning).toHaveBeenCalledWith('迭代信息加载失败')
  })
})

describe('useUIPrototype — 挂载校验', () => {
  it('缺少项目或原型 ID 时提示并返回需求页', async () => {
    const wrapper = await mountHost({ project_id: '7' })

    expect(mocks.error).toHaveBeenCalledWith('缺少项目ID或原型项目ID参数')
    expect(mocks.push).toHaveBeenCalledWith('/home/requirement')
    expect(mocks.getUIScreenList).not.toHaveBeenCalled()

    wrapper.unmount()
  })
})

describe('useUIPrototype — 截图加载', () => {
  it('按 data.items 解析截图并填充图片地址', async () => {
    setScreens([
      { id: 1, screen_name: '首页', parse_status: 'completed', original_file_path: '/a.png' },
      { id: 2, screen_name: '无图', parse_status: 'pending' },
    ])

    await mountHost()

    expect(ctx.screens.value).toHaveLength(2)
    expect(mocks.getImageUrl).toHaveBeenCalledTimes(1)
    expect(ctx.screenImageUrls.value[1]).toBe('blob:mock')
    expect(ctx.screenImageUrls.value[2]).toBeUndefined()
  })

  it('兼容顶层数组响应', async () => {
    mocks.getUIScreenList.mockResolvedValue([
      { id: 3, screen_name: '列表页', parse_status: 'failed' },
    ])

    await mountHost()

    expect(ctx.screens.value.map((s) => s.id)).toEqual([3])
    expect(ctx.failedScreenCount.value).toBe(1)
  })

  it('加载失败时提示并清空截图', async () => {
    mocks.getUIScreenList.mockRejectedValue(new Error('boom'))

    await mountHost()

    expect(mocks.error).toHaveBeenCalledWith('加载截图列表失败，请刷新重试')
    expect(ctx.screens.value).toEqual([])
    expect(ctx.loading.value).toBe(false)
  })

  it('按 id 匹配原型项目并读取流转摘要', async () => {
    setProjects([
      { id: 11, has_flow: false },
      { id: 12, has_flow: true, flow_summary: { node_count: 4, edge_count: 3 } },
    ])

    await mountHost()

    expect(mocks.getUIPrototypeProjectList).toHaveBeenCalledWith(7, 1, 100, undefined)
    expect(ctx.hasFlow.value).toBe(true)
    expect(ctx.flowSummary.value).toEqual({ node_count: 4, edge_count: 3 })
  })

  it('原型项目加载失败时仅告警不抛出', async () => {
    mocks.getUIPrototypeProjectList.mockRejectedValue(new Error('boom'))
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

    await mountHost()

    expect(warnSpy).toHaveBeenCalled()
    expect(ctx.prototypeProject.value).toBeNull()
    warnSpy.mockRestore()
  })
})

describe('useUIPrototype — 统计与主操作文案', () => {
  it('按解析状态统计已解析/失败/待处理', async () => {
    setScreens([
      { id: 1, parse_status: 'completed' },
      { id: 2, parse_status: 'completed' },
      { id: 3, parse_status: 'failed' },
      { id: 4, parse_status: 'running' },
      { id: 5 },
    ])

    await mountHost()

    expect(ctx.completedScreenCount.value).toBe(2)
    expect(ctx.failedScreenCount.value).toBe(1)
    expect(ctx.pendingScreenCount.value).toBe(2)
  })

  it.each([
    ['无截图', [], 'text', '上传截图'],
    ['有截图待解析', [{ id: 1, parse_status: 'pending' }], 'text', '解析页面'],
    ['视觉模式待解析', [{ id: 1, parse_status: 'pending' }], 'vision', 'AI视觉解析'],
    [
      '解析完成待流转',
      [
        { id: 1, parse_status: 'completed' },
        { id: 2, parse_status: 'completed' },
      ],
      'text',
      '分析页面流转',
    ],
  ])('主操作文案：%s', async (_label, screens, mode, expected) => {
    setScreens(screens as ScreenLike[])
    await mountHost()
    ctx.parseMode.value = mode as 'text' | 'vision'

    expect(ctx.primaryActionText.value).toBe(expected)
  })

  it('解析完成且已有流转时提示生成用例', async () => {
    setScreens([
      { id: 1, parse_status: 'completed' },
      { id: 2, parse_status: 'completed' },
    ])
    setProjects([{ id: 12, has_flow: true }])

    await mountHost()

    expect(ctx.primaryActionText.value).toBe('生成测试用例')
  })

  it('主操作按状态分发到上传/解析/流转/用例', async () => {
    await mountHost()
    await ctx.handlePrimaryAction()
    expect(ctx.uploadDialogVisible.value).toBe(true)

    await mountHost()
    ctx.screens.value = [{ id: 1, parse_status: 'pending' }] as never
    mocks.getUIScreenList.mockResolvedValue({
      data: { items: [{ id: 1, parse_status: 'completed' }] },
    })
    vi.useFakeTimers()
    const parsePromise = ctx.handlePrimaryAction()
    await vi.advanceTimersByTimeAsync(2000)
    await parsePromise
    vi.useRealTimers()
    expect(mocks.parseUIScreens).toHaveBeenCalledTimes(1)

    await mountHost()
    ctx.screens.value = [
      { id: 1, parse_status: 'completed' },
      { id: 2, parse_status: 'completed' },
    ] as never
    await ctx.handlePrimaryAction()
    expect(mocks.generatePageFlow).toHaveBeenCalledTimes(1)

    await mountHost()
    ctx.screens.value = [{ id: 1, parse_status: 'completed' }] as never
    setProjects([{ id: 12, has_flow: true }])
    ctx.prototypeProject.value = { id: 12, has_flow: true } as never
    await ctx.handlePrimaryAction()
    expect(mocks.push).toHaveBeenCalledWith(
      expect.objectContaining({ path: '/home/case/smart-generate' })
    )
  })
})

describe('useUIPrototype — 预览', () => {
  it('未缓存时取图并写入缓存', async () => {
    await mountHost()

    await ctx.handlePreviewScreen({ id: 9, screen_name: '详情页' } as never)

    expect(mocks.getImageUrl).toHaveBeenCalledTimes(1)
    expect(ctx.screenImageUrls.value[9]).toBe('blob:mock')
    expect(ctx.previewScreen.value?.id).toBe(9)
    expect(ctx.previewVisible.value).toBe(true)
  })

  it('已缓存时不再请求图片', async () => {
    await mountHost()
    ctx.screenImageUrls.value[9] = 'blob:cached'

    await ctx.handlePreviewScreen({ id: 9 } as never)

    expect(mocks.getImageUrl).not.toHaveBeenCalled()
    expect(ctx.previewVisible.value).toBe(true)
  })

  it('取图失败不影响预览打开', async () => {
    mocks.getImageUrl.mockResolvedValue('')
    await mountHost()

    await ctx.handlePreviewScreen({ id: 9 } as never)

    expect(ctx.screenImageUrls.value[9]).toBeUndefined()
    expect(ctx.previewVisible.value).toBe(true)
  })
})

describe('useUIPrototype — 解析', () => {
  it('单页解析提交后轮询至完成', async () => {
    await mountHost()
    mocks.getUIScreenList.mockResolvedValue({
      data: { items: [{ id: 1, parse_status: 'completed' }] },
    })

    vi.useFakeTimers()
    const promise = ctx.handleParseScreen({ id: 1 } as never)
    await vi.advanceTimersByTimeAsync(2000)
    await promise
    vi.useRealTimers()

    expect(mocks.parseUIScreens).toHaveBeenCalledWith([1], 12, 'text')
    expect(mocks.success).toHaveBeenCalledWith('解析任务已启动')
    expect(ctx.parsing.value).toBe(false)
    expect(ctx.pendingScreensCount.value).toBe(0)
  })

  it('解析进行中重复触发被忽略', async () => {
    await mountHost()
    ctx.parsing.value = true

    await ctx.handleParseScreen({ id: 1 } as never)

    expect(mocks.parseUIScreens).not.toHaveBeenCalled()
  })

  it('解析失败时展示后端 detail', async () => {
    await mountHost()
    mocks.parseUIScreens.mockRejectedValue({ response: { data: { detail: '模型超时' } } })

    await ctx.handleParseScreen({ id: 1 } as never)

    expect(mocks.error).toHaveBeenCalledWith('模型超时')
    expect(ctx.parsing.value).toBe(false)
  })

  it('批量解析只提交 pending/failed 的图片', async () => {
    await mountHost()
    ctx.screens.value = [
      { id: 1, parse_status: 'pending' },
      { id: 2, parse_status: 'completed' },
      { id: 3, parse_status: 'failed' },
    ] as never
    mocks.getUIScreenList.mockResolvedValue({
      data: {
        items: [
          { id: 1, parse_status: 'completed' },
          { id: 3, parse_status: 'completed' },
        ],
      },
    })

    vi.useFakeTimers()
    const promise = ctx.handleBatchParse()
    await vi.advanceTimersByTimeAsync(2000)
    await promise
    vi.useRealTimers()

    expect(mocks.parseUIScreens).toHaveBeenCalledWith([1, 3], 12, 'text')
    expect(mocks.success).toHaveBeenCalledWith('已启动 2 张图片的文本模型一键解析')
  })

  it('视觉批量解析使用对应文案', async () => {
    await mountHost()
    ctx.parseMode.value = 'vision'
    ctx.screens.value = [{ id: 1, parse_status: 'pending' }] as never
    mocks.getUIScreenList.mockResolvedValue({
      data: { items: [{ id: 1, parse_status: 'completed' }] },
    })

    vi.useFakeTimers()
    const promise = ctx.handleBatchParse()
    await vi.advanceTimersByTimeAsync(2000)
    await promise
    vi.useRealTimers()

    expect(mocks.parseUIScreens).toHaveBeenCalledWith([1], 12, 'vision')
    expect(mocks.success).toHaveBeenCalledWith('已启动 1 张图片的AI视觉解析')
  })

  it('无待解析图片时直接提示', async () => {
    await mountHost()
    ctx.screens.value = [{ id: 1, parse_status: 'completed' }] as never

    await ctx.handleBatchParse()

    expect(mocks.info).toHaveBeenCalledWith('所有图片已解析完成')
    expect(mocks.parseUIScreens).not.toHaveBeenCalled()
  })
})

describe('useUIPrototype — 流转与上传', () => {
  it('不足 2 张已解析页面时拒绝流转', async () => {
    await mountHost()
    ctx.screens.value = [{ id: 1, parse_status: 'completed' }] as never

    await ctx.handleGenerateFlow()

    expect(mocks.warning).toHaveBeenCalledWith('至少需要 2 张已解析页面才能分析页面流转')
    expect(mocks.generatePageFlow).not.toHaveBeenCalled()
  })

  it('流转成功提示并刷新截图与原型状态', async () => {
    await mountHost()
    ctx.screens.value = [
      { id: 1, parse_status: 'completed' },
      { id: 2, parse_status: 'completed' },
    ] as never
    const callsBefore = mocks.getUIScreenList.mock.calls.length

    await ctx.handleGenerateFlow()

    expect(mocks.generatePageFlow).toHaveBeenCalledWith(12)
    expect(mocks.success).toHaveBeenCalledWith('页面流转分析完成')
    expect(mocks.getUIScreenList.mock.calls.length).toBe(callsBefore + 1)
    expect(ctx.flowGenerating.value).toBe(false)
  })

  it('流转返回 success=false 时按提示处理', async () => {
    await mountHost()
    ctx.screens.value = [
      { id: 1, parse_status: 'completed' },
      { id: 2, parse_status: 'completed' },
    ] as never
    mocks.generatePageFlow.mockResolvedValue({ success: false, msg: '页面不足' })

    await ctx.handleGenerateFlow()

    expect(mocks.warning).toHaveBeenCalledWith('页面不足')
  })

  it('流转异常展示后端 detail', async () => {
    await mountHost()
    ctx.screens.value = [
      { id: 1, parse_status: 'completed' },
      { id: 2, parse_status: 'completed' },
    ] as never
    mocks.generatePageFlow.mockRejectedValue({ response: { data: { detail: '模型异常' } } })

    await ctx.handleGenerateFlow()

    expect(mocks.error).toHaveBeenCalledWith('模型异常')
    expect(ctx.flowGenerating.value).toBe(false)
  })

  it('上传成功提示数量并关闭弹层', async () => {
    await mountHost()
    mocks.uploadUIScreens.mockResolvedValue({ total: 3 })
    ctx.uploadDialogVisible.value = true

    await ctx.handleUploadSubmit([{ name: 'a.png' } as File])

    expect(mocks.uploadUIScreens).toHaveBeenCalledWith(
      7,
      [{ name: 'a.png' }],
      '洪恩UI原型',
      12,
      undefined
    )
    expect(mocks.success).toHaveBeenCalledWith('追加上传成功，共 3 张图片')
    expect(ctx.uploadDialogVisible.value).toBe(false)
    expect(ctx.uploading.value).toBe(false)
  })

  it('上传失败提示错误并复位状态', async () => {
    await mountHost()
    mocks.uploadUIScreens.mockRejectedValue({ response: { data: { detail: '格式不支持' } } })

    await ctx.handleUploadSubmit([])

    expect(mocks.error).toHaveBeenCalledWith('格式不支持')
    expect(ctx.uploading.value).toBe(false)
  })
})

describe('useUIPrototype — 删除与导航', () => {
  it('确认后删除并刷新', async () => {
    await mountHost()
    mocks.confirm.mockResolvedValue('confirm')
    const callsBefore = mocks.getUIScreenList.mock.calls.length

    await ctx.handleDeleteScreen({ id: 3, screen_name: '登录页' } as never)
    await nextTick()
    await flushPromises()

    expect(mocks.confirm).toHaveBeenCalledWith(
      '确定要删除图片 "登录页" 吗？',
      '删除确认',
      expect.objectContaining({ type: 'warning' })
    )
    expect(mocks.deleteUIScreen).toHaveBeenCalledWith(3)
    expect(mocks.success).toHaveBeenCalledWith('删除成功')
    expect(mocks.getUIScreenList.mock.calls.length).toBe(callsBefore + 1)
  })

  it('取消删除不调用接口也不报错', async () => {
    await mountHost()
    mocks.confirm.mockRejectedValue('cancel')

    await ctx.handleDeleteScreen({ id: 3, screen_name: '登录页' } as never)

    expect(mocks.deleteUIScreen).not.toHaveBeenCalled()
    expect(mocks.error).not.toHaveBeenCalled()
  })

  it('删除异常展示后端 detail', async () => {
    await mountHost()
    mocks.confirm.mockResolvedValue('confirm')
    mocks.deleteUIScreen.mockRejectedValue({ response: { data: { detail: '已被引用' } } })

    await ctx.handleDeleteScreen({ id: 3, screen_name: '登录页' } as never)

    expect(mocks.error).toHaveBeenCalledWith('已被引用')
  })

  it('返回、用例生成与回归分析跳转参数正确', async () => {
    await mountHost({ ...defaultQuery, iteration_id: '5' })

    ctx.goBack()
    expect(mocks.push).toHaveBeenCalledWith('/home/requirement')

    ctx.goToCaseGenerate()
    expect(mocks.push).toHaveBeenCalledWith({
      path: '/home/case/smart-generate',
      query: { project_id: 7, ui_project_id: 12 },
    })

    ctx.goToFlowEditor()
    expect(mocks.push).toHaveBeenLastCalledWith({
      path: '/home/case/smart-generate',
      query: { project_id: 7, ui_project_id: 12 },
    })

    ctx.goToScenario4()
    expect(mocks.push).toHaveBeenLastCalledWith({
      name: 'IterationRegressionGenerate',
      query: {
        project_id: 7,
        ui_project_id: 12,
        name: '洪恩UI原型',
        change_source: 'ui_flow',
      },
    })
  })

  it('取消解析终止轮询并清空待解析计数', async () => {
    await mountHost()
    ctx.parsing.value = true

    ctx.handleCancelParse()

    expect(mocks.info).toHaveBeenCalledWith('解析任务已取消')
    expect(ctx.parsing.value).toBe(false)
    expect(ctx.pendingScreensCount.value).toBe(0)
  })

  it('卸载时清理图片缓存', async () => {
    const wrapper = await mountHost()

    wrapper.unmount()

    expect(mocks.cleanupImageCache).toHaveBeenCalledTimes(1)
  })
})
