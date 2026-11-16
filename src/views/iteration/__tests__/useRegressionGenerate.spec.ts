import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createComposableHost,
  deferred,
  mockCancel,
  mockConfirm,
  silenceElMessage,
} from '@/test-utils'

const mocks = vi.hoisted(() => ({
  back: vi.fn(),
  push: vi.fn(),
  getIterations: vi.fn(),
  getIteration: vi.fn(),
  createIteration: vi.fn(),
  updateIteration: vi.fn(),
  deleteIteration: vi.fn(),
  addIterationInput: vi.fn(),
  getTestPoints: vi.fn(),
  precheckScenario4: vi.fn(),
  runPipeline: vi.fn(),
}))

const route = vi.hoisted(() => ({ query: {} as Record<string, string | undefined> }))

vi.mock('vue-router', () => ({
  useRouter: () => ({ back: mocks.back, push: mocks.push }),
  useRoute: () => route,
}))

vi.mock('@/api/iteration', () => ({
  iterationApi: {
    getIterations: mocks.getIterations,
    getIteration: mocks.getIteration,
    createIteration: mocks.createIteration,
    updateIteration: mocks.updateIteration,
    deleteIteration: mocks.deleteIteration,
    addIterationInput: mocks.addIterationInput,
  },
}))

vi.mock('@/api/pipeline', () => ({
  pipelineApi: {
    precheckScenario4: mocks.precheckScenario4,
    runPipeline: mocks.runPipeline,
  },
}))

vi.mock('@/api/testPoint', () => ({
  testPointApi: { getList: mocks.getTestPoints },
}))

import { useRegressionGenerate } from '../useRegressionGenerate'

type Ctx = ReturnType<typeof useRegressionGenerate>

const host = createComposableHost<Ctx>(() => useRegressionGenerate())
let ctx: Ctx

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

function makeIteration(id: number, name: string, over: Record<string, unknown> = {}) {
  return {
    id,
    project_id: 7,
    name,
    version: 'v1',
    description: `${name}描述`,
    status: 'draft',
    ...over,
  }
}

function makePrecheck(over: Record<string, unknown> = {}) {
  return {
    project_id: 7,
    history_cases: {
      total: 3,
      included: 2,
      active: 2,
      draft: 0,
      pending_review: 0,
      archived: 0,
      deleted: 1,
    },
    test_points: { total: 1, selected: 0 },
    ui: {
      selected_screen_count: 1,
      parsed_screen_count: 1,
      unparsed_screen_count: 0,
      parse_failed_count: 0,
      usable_screen_ids: [101, 102],
    },
    can_run: true,
    blocking_reasons: [],
    warnings: [],
    ...over,
  }
}

/** 8 位十六进制哈希（computeHash 输出格式） */
const HASH = expect.stringMatching(/^[0-9a-f]{8}$/)

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mockConfirm()
  route.query = { project_id: '7', ui_project_id: '9', name: '原型A' }
  mocks.getIterations.mockResolvedValue({
    data: { items: [makeIteration(1, '迭代一'), makeIteration(2, '迭代二')] },
  })
  mocks.getIteration.mockResolvedValue({ data: { id: 1, pipeline_runs: [] } })
  mocks.getTestPoints.mockResolvedValue({ items: [{ id: 11, title: '测试点A' }], total: 1 })
  mocks.precheckScenario4.mockResolvedValue({ data: makePrecheck() })
  mocks.createIteration.mockResolvedValue({ data: makeIteration(3, '迭代三') })
  mocks.updateIteration.mockResolvedValue({ data: makeIteration(1, '迭代一改') })
  mocks.deleteIteration.mockResolvedValue({ code: 200, message: 'ok', data: {} })
  mocks.addIterationInput.mockResolvedValue({ code: 200, message: 'ok', data: {} })
  mocks.runPipeline.mockResolvedValue({ data: { run_id: 88, pipeline_run_id: 99 } })
})

describe('useRegressionGenerate — URL 派生状态', () => {
  it('解析项目、原型名称与变更来源', async () => {
    route.query = {
      project_id: '7',
      ui_project_id: '9',
      name: '原型A',
      change_source: 'requirement',
    }

    await mountHost()

    expect(ctx.projectId.value).toBe(7)
    expect(ctx.prototypeName.value).toBe('原型A')
    expect(ctx.changeSource.value).toBe('requirement')
    expect(ctx.changeSourceText.value).toBe('需求/测试点变化')
  })

  it('缺失参数时回退默认值', async () => {
    route.query = {}

    await mountHost()

    expect(ctx.projectId.value).toBe(0)
    expect(ctx.prototypeName.value).toBe('UI原型')
    expect(ctx.changeSource.value).toBe('ui_flow')
    expect(ctx.changeSourceText.value).toBe('UI/流程变化')
  })

  it('mixed 来源展示混合变化文案', async () => {
    route.query = { project_id: '7', change_source: 'mixed' }

    await mountHost()

    expect(ctx.changeSourceText.value).toBe('混合变化')
  })

  it('非法来源回退为 UI/流程变化', async () => {
    route.query = { project_id: '7', change_source: 'unknown' }

    await mountHost()

    expect(ctx.changeSource.value).toBe('ui_flow')
  })

  it('canStart 需要同时具备迭代与可运行预检', async () => {
    await mountHost()
    expect(ctx.canStart.value).toBeFalsy()

    ctx.selectedIterationId.value = 1
    expect(ctx.canStart.value).toBe(true)

    mocks.precheckScenario4.mockResolvedValue({ data: makePrecheck({ can_run: false }) })
    await ctx.loadPrecheck()
    expect(ctx.canStart.value).toBeFalsy()
  })

  it('recommendedScenario 默认 4，可由预检覆盖', async () => {
    await mountHost()
    expect(ctx.recommendedScenario.value).toBe(4)

    mocks.precheckScenario4.mockResolvedValue({
      data: makePrecheck({ recommended_pipeline_scenario: 5 }),
    })
    await ctx.loadPrecheck()

    expect(ctx.recommendedScenario.value).toBe(5)
  })
})

describe('useRegressionGenerate — 首屏加载', () => {
  it('挂载后并行加载迭代、测试点与预检', async () => {
    await mountHost()

    expect(mocks.getIterations).toHaveBeenCalledWith(7)
    expect(mocks.getTestPoints).toHaveBeenCalledWith(7, { page: 1, page_size: 100 })
    expect(mocks.precheckScenario4).toHaveBeenCalledWith({
      project_id: 7,
      ui_project_id: 9,
      test_point_ids: undefined,
      change_source: 'ui_flow',
    })
    expect(ctx.iterations.value).toHaveLength(2)
    expect(ctx.testPoints.value).toHaveLength(1)
    expect(ctx.precheckData.value?.can_run).toBe(true)
    expect(ctx.precheckLoading.value).toBe(false)
  })

  it('无项目 ID 时不发起任何请求', async () => {
    route.query = {}

    await mountHost()

    expect(mocks.getIterations).not.toHaveBeenCalled()
    expect(mocks.getTestPoints).not.toHaveBeenCalled()
    expect(mocks.precheckScenario4).not.toHaveBeenCalled()
  })

  it('迭代列表缺失 items 时兜底为空数组', async () => {
    mocks.getIterations.mockResolvedValue({ data: {} })

    await mountHost()

    expect(ctx.iterations.value).toEqual([])
  })

  it('迭代列表失败时给出警告', async () => {
    mocks.getIterations.mockRejectedValue(new Error('boom'))

    await mountHost()

    expect(ElMessage.warning).toHaveBeenCalledWith('加载迭代列表失败')
  })

  it('测试点加载失败时静默处理', async () => {
    mocks.getTestPoints.mockRejectedValue(new Error('boom'))

    await mountHost()

    expect(ElMessage.error).not.toHaveBeenCalled()
    expect(ElMessage.warning).not.toHaveBeenCalled()
    expect(ctx.testPoints.value).toEqual([])
  })

  it('预检失败时提示后端 detail', async () => {
    mocks.precheckScenario4.mockRejectedValue({
      response: { data: { detail: '缺少 UI 原型' } },
    })

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('缺少 UI 原型')
    expect(ctx.precheckLoading.value).toBe(false)
  })

  it('预检失败且无 detail 时使用兜底文案', async () => {
    mocks.precheckScenario4.mockRejectedValue(null)

    await mountHost()

    expect(ElMessage.error).toHaveBeenCalledWith('预检失败')
  })

  it('已选测试点参与预检请求', async () => {
    await mountHost()
    ctx.selectedTestPointIds.value = [11, 12]
    mocks.precheckScenario4.mockClear()

    await ctx.loadPrecheck()

    expect(mocks.precheckScenario4).toHaveBeenCalledWith(
      expect.objectContaining({ test_point_ids: [11, 12] })
    )
  })
})

describe('useRegressionGenerate — 新建迭代', () => {
  it('名称为空时提示且不请求', async () => {
    await mountHost()
    ctx.newIterationForm.value.name = '   '

    await ctx.handleCreateIteration()

    expect(ElMessage.warning).toHaveBeenCalledWith('请输入迭代名称')
    expect(mocks.createIteration).not.toHaveBeenCalled()
  })

  it('创建成功后加入列表、选中并重置表单', async () => {
    await mountHost()
    ctx.newIterationForm.value = { name: ' 迭代三 ', version: 'v2', description: '说明' }
    ctx.showCreateIteration.value = true

    await ctx.handleCreateIteration()

    expect(mocks.createIteration).toHaveBeenCalledWith({
      project_id: 7,
      name: '迭代三',
      version: 'v2',
      description: '说明',
    })
    expect(ctx.iterations.value).toHaveLength(3)
    expect(ctx.selectedIterationId.value).toBe(3)
    expect(ctx.showCreateIteration.value).toBe(false)
    expect(ctx.newIterationForm.value).toEqual({ name: '', version: '', description: '' })
    expect(ElMessage.success).toHaveBeenCalledWith('迭代创建成功')
    expect(ctx.creatingIteration.value).toBe(false)
  })

  it('可选字段为空时不提交', async () => {
    await mountHost()
    ctx.newIterationForm.value.name = '迭代三'

    await ctx.handleCreateIteration()

    expect(mocks.createIteration).toHaveBeenCalledWith({
      project_id: 7,
      name: '迭代三',
      version: undefined,
      description: undefined,
    })
  })

  it('创建失败时提示且不复位创建中标记', async () => {
    mocks.createIteration.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.newIterationForm.value.name = '迭代三'

    await ctx.handleCreateIteration()

    expect(ElMessage.error).toHaveBeenCalledWith('创建迭代失败')
    expect(ctx.iterations.value).toHaveLength(2)
    expect(ctx.creatingIteration.value).toBe(false)
  })

  it('请求期间 creatingIteration 为 true', async () => {
    const pending = deferred<unknown>()
    mocks.createIteration.mockReturnValueOnce(pending.promise)
    await mountHost()
    ctx.newIterationForm.value.name = '迭代三'

    const task = ctx.handleCreateIteration()
    expect(ctx.creatingIteration.value).toBe(true)

    pending.resolve({ data: makeIteration(3, '迭代三') })
    await task
    expect(ctx.creatingIteration.value).toBe(false)
  })
})

describe('useRegressionGenerate — 编辑迭代', () => {
  it('未选择迭代时提示', async () => {
    await mountHost()

    await ctx.handleEditIteration()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择一个迭代')
    expect(ctx.showEditIteration.value).toBe(false)
  })

  it('选中项不在列表时不打开弹窗', async () => {
    await mountHost()
    ctx.selectedIterationId.value = 999

    await ctx.handleEditIteration()

    expect(ctx.showEditIteration.value).toBe(false)
  })

  it('打开弹窗并回填表单', async () => {
    await mountHost()
    ctx.selectedIterationId.value = 2

    await ctx.handleEditIteration()

    expect(ctx.showEditIteration.value).toBe(true)
    expect(ctx.editIterationForm.value).toEqual({
      name: '迭代二',
      version: 'v1',
      description: '迭代二描述',
    })
  })

  it('名称为空时不保存', async () => {
    await mountHost()
    ctx.selectedIterationId.value = 1
    await ctx.handleEditIteration()
    ctx.editIterationForm.value.name = '  '

    await ctx.handleSaveEditIteration()

    expect(ElMessage.warning).toHaveBeenCalledWith('请输入迭代名称')
    expect(mocks.updateIteration).not.toHaveBeenCalled()
  })

  it('未持有编辑目标时不保存', async () => {
    await mountHost()

    await ctx.handleSaveEditIteration()

    expect(mocks.updateIteration).not.toHaveBeenCalled()
  })

  it('保存成功后替换列表项并关闭弹窗', async () => {
    await mountHost()
    ctx.selectedIterationId.value = 1
    await ctx.handleEditIteration()
    ctx.editIterationForm.value = { name: ' 迭代一改 ', version: '', description: '' }

    await ctx.handleSaveEditIteration()

    expect(mocks.updateIteration).toHaveBeenCalledWith(1, {
      name: '迭代一改',
      version: undefined,
      description: undefined,
    })
    expect(ctx.iterations.value[0].name).toBe('迭代一改')
    expect(ctx.showEditIteration.value).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('迭代更新成功')
    expect(ctx.editingIteration.value).toBe(false)
  })

  it('保存失败时提示', async () => {
    mocks.updateIteration.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.selectedIterationId.value = 1
    await ctx.handleEditIteration()
    ctx.editIterationForm.value.name = '迭代一改'

    await ctx.handleSaveEditIteration()

    expect(ElMessage.error).toHaveBeenCalledWith('更新迭代失败')
    expect(ctx.editingIteration.value).toBe(false)
  })
})

describe('useRegressionGenerate — 删除迭代', () => {
  it('未选择迭代时提示', async () => {
    await mountHost()

    await ctx.handleDeleteIteration()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先选择一个迭代')
    expect(mocks.deleteIteration).not.toHaveBeenCalled()
  })

  it('选中项不在列表时不发请求', async () => {
    await mountHost()
    ctx.selectedIterationId.value = 999

    await ctx.handleDeleteIteration()

    expect(mocks.deleteIteration).not.toHaveBeenCalled()
  })

  it('确认后删除并从列表移除、清空选中', async () => {
    await mountHost()
    ctx.selectedIterationId.value = 2
    await ctx.handleEditIteration()

    await ctx.handleDeleteIteration()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mocks.deleteIteration).toHaveBeenCalledWith(2)
    expect(ctx.iterations.value.map((it) => it.id)).toEqual([1])
    expect(ctx.selectedIterationId.value).toBe('')
    expect(ElMessage.success).toHaveBeenCalledWith('迭代已删除')
  })

  it('取消删除时不调用接口', async () => {
    mockCancel()
    await mountHost()
    ctx.selectedIterationId.value = 2

    await ctx.handleDeleteIteration()

    expect(mocks.deleteIteration).not.toHaveBeenCalled()
    expect(ctx.iterations.value).toHaveLength(2)
  })

  it('删除失败时提示', async () => {
    mocks.deleteIteration.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.selectedIterationId.value = 2

    await ctx.handleDeleteIteration()

    expect(ElMessage.error).toHaveBeenCalledWith('删除迭代失败')
    expect(ctx.iterations.value).toHaveLength(2)
  })
})

describe('useRegressionGenerate — 启动回归分析', () => {
  it('未选择迭代时直接返回', async () => {
    await mountHost()

    await ctx.handleStart()

    expect(mocks.getIteration).not.toHaveBeenCalled()
    expect(mocks.runPipeline).not.toHaveBeenCalled()
  })

  it('预检数据缺失时直接返回', async () => {
    mocks.precheckScenario4.mockResolvedValue({ data: null })
    await mountHost()
    ctx.selectedIterationId.value = 1

    await ctx.handleStart()

    expect(mocks.runPipeline).not.toHaveBeenCalled()
  })

  it('已运行过的迭代需二次确认，取消则中止', async () => {
    mocks.getIteration.mockResolvedValue({ data: { id: 1, pipeline_runs: [{ id: 5 }] } })
    mockCancel()
    await mountHost()
    ctx.selectedIterationId.value = 1

    await ctx.handleStart()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(mocks.addIterationInput).not.toHaveBeenCalled()
    expect(mocks.runPipeline).not.toHaveBeenCalled()
  })

  it('确认后写入原型/测试点/变更说明并启动预检推荐场景', async () => {
    mocks.getIteration.mockResolvedValue({ data: { id: 1, pipeline_runs: [{ id: 5 }] } })
    await mountHost()
    ctx.selectedIterationId.value = 1
    ctx.selectedTestPointIds.value = [11]
    ctx.changeNotes.value = ' 本次仅改文案 '
    mocks.addIterationInput.mockClear()

    await ctx.handleStart()

    expect(mocks.addIterationInput).toHaveBeenNthCalledWith(1, 1, {
      kind: 'prototype',
      payload: { screen_ids: [101, 102] },
      hash: HASH,
    })
    expect(mocks.addIterationInput).toHaveBeenNthCalledWith(2, 1, {
      kind: 'testpoint',
      payload: { test_point_ids: [11] },
      hash: HASH,
    })
    expect(mocks.addIterationInput).toHaveBeenNthCalledWith(3, 1, {
      kind: 'change_notes',
      payload: { notes: '本次仅改文案' },
      hash: HASH,
    })
    expect(mocks.runPipeline).toHaveBeenCalledWith(1, { scenario: 4 })
    expect(mocks.push).toHaveBeenCalledWith({
      name: 'IterationPipelineProgress',
      params: { runId: 88 },
    })
    expect(ElMessage.success).toHaveBeenCalledWith('回归变更分析已启动')
    expect(ctx.starting.value).toBe(false)
  })

  it('无测试点与变更说明时只写入原型输入', async () => {
    await mountHost()
    ctx.selectedIterationId.value = 1
    mocks.addIterationInput.mockClear()

    await ctx.handleStart()

    expect(mocks.addIterationInput).toHaveBeenCalledTimes(1)
    expect(mocks.addIterationInput).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ kind: 'prototype' })
    )
  })

  it('run_id 缺失时回退 pipeline_run_id', async () => {
    mocks.runPipeline.mockResolvedValue({ data: { pipeline_run_id: 99 } })
    await mountHost()
    ctx.selectedIterationId.value = 1

    await ctx.handleStart()

    expect(mocks.push).toHaveBeenCalledWith({
      name: 'IterationPipelineProgress',
      params: { runId: 99 },
    })
  })

  it('预检推荐场景为 5 时按 5 启动', async () => {
    mocks.precheckScenario4.mockResolvedValue({
      data: makePrecheck({ recommended_pipeline_scenario: 5 }),
    })
    await mountHost()
    ctx.selectedIterationId.value = 1

    await ctx.handleStart()

    expect(mocks.runPipeline).toHaveBeenCalledWith(1, { scenario: 5 })
  })

  it('读取迭代详情失败不阻断启动', async () => {
    mocks.getIteration.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.selectedIterationId.value = 1

    await ctx.handleStart()

    expect(mocks.runPipeline).toHaveBeenCalledTimes(1)
  })

  it('启动失败时提示后端 detail 并复位标记', async () => {
    mocks.runPipeline.mockRejectedValue({ response: { data: { detail: '模型额度不足' } } })
    await mountHost()
    ctx.selectedIterationId.value = 1

    await ctx.handleStart()

    expect(ElMessage.error).toHaveBeenCalledWith('模型额度不足')
    expect(ctx.starting.value).toBe(false)
    expect(mocks.push).not.toHaveBeenCalled()
  })

  it('启动失败且无 detail 时使用兜底文案', async () => {
    mocks.runPipeline.mockRejectedValue(null)
    await mountHost()
    ctx.selectedIterationId.value = 1

    await ctx.handleStart()

    expect(ElMessage.error).toHaveBeenCalledWith('启动场景 4 失败')
  })

  it('返回上一页', async () => {
    await mountHost()

    ctx.goBack()

    expect(mocks.back).toHaveBeenCalledTimes(1)
  })
})

describe('useRegressionGenerate — 异步竞态', () => {
  it('预检进行中 precheckLoading 为 true', async () => {
    const pending = deferred<{ data: ReturnType<typeof makePrecheck> }>()
    mocks.precheckScenario4.mockReturnValueOnce(pending.promise)
    await mountHost()

    const task = ctx.loadPrecheck()
    expect(ctx.precheckLoading.value).toBe(true)

    pending.resolve({ data: makePrecheck() })
    await task
    await flushPromises()

    expect(ctx.precheckLoading.value).toBe(false)
  })
})
