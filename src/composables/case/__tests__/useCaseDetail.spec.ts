import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'

const mocks = vi.hoisted(() => ({
  route: { params: {} as Record<string, string>, query: {} as Record<string, string> },
  push: vi.fn(),
  getCase: vi.fn(),
  startCorrection: vi.fn(),
  submitVerification: vi.fn(),
  getCaseVersions: vi.fn(),
  rollbackCaseVersion: vi.fn(),
  updateStepLocator: vi.fn(),
  exportToExcel: vi.fn(),
  parsePrecondition: vi.fn(),
  batchSavePreconditionSteps: vi.fn(),
  downloadFromResponse: vi.fn(),
  parseBlobError: vi.fn(),
  createQuickVerify: vi.fn(),
  initEditForm: vi.fn(),
  toggleEdit: vi.fn(),
  cancelEdit: vi.fn(),
  saveEdit: vi.fn(),
  fetchTechnicalView: vi.fn(),
  handleViewChange: vi.fn(),
  startCellEdit: vi.fn(),
  cancelCellEdit: vi.fn(),
  saveCellEdit: vi.fn(),
  isEditing: { value: false },
  saving: { value: false },
  editForm: { value: { steps: [] as Record<string, unknown>[] } },
  currentView: { value: 'business' },
  viewLoading: { value: false },
  technicalViewData: { value: null as Record<string, unknown> | null },
  editingCell: { value: null },
  editingValue: { value: '' },
  cellSaving: { value: false },
}))

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/api/case', () => {
  const api = {
    getCase: mocks.getCase,
    startCorrection: mocks.startCorrection,
    submitVerification: mocks.submitVerification,
    getCaseVersions: mocks.getCaseVersions,
    rollbackCaseVersion: mocks.rollbackCaseVersion,
    updateStepLocator: mocks.updateStepLocator,
  }
  return { testCaseApi: api, caseApi: api, default: api }
})

vi.mock('@/api/testCaseView', () => {
  const api = {
    exportToExcel: mocks.exportToExcel,
    parsePrecondition: mocks.parsePrecondition,
    batchSavePreconditionSteps: mocks.batchSavePreconditionSteps,
  }
  return { testCaseViewApi: api, default: api }
})

vi.mock('@/api/testExecution', () => ({
  createQuickVerify: mocks.createQuickVerify,
}))

vi.mock('@/utils/download', () => ({
  downloadFromResponse: mocks.downloadFromResponse,
  parseBlobError: mocks.parseBlobError,
}))

vi.mock('@/composables/useCaseEdit', () => ({
  useCaseEdit: () => ({
    isEditing: mocks.isEditing,
    saving: mocks.saving,
    editForm: mocks.editForm,
    initEditForm: mocks.initEditForm,
    toggleEdit: mocks.toggleEdit,
    cancelEdit: mocks.cancelEdit,
    saveEdit: mocks.saveEdit,
  }),
}))

vi.mock('@/composables/useTechnicalView', () => ({
  VIEW_TYPES: { BUSINESS: 'business', TECHNICAL: 'technical' },
  useTechnicalView: () => ({
    currentView: mocks.currentView,
    viewLoading: mocks.viewLoading,
    technicalViewData: mocks.technicalViewData,
    fetchTechnicalView: mocks.fetchTechnicalView,
    handleViewChange: mocks.handleViewChange,
    getLocatorStatusType: (status: string) => `type-${status}`,
    getLocatorStatusLabel: (status: string) => `label-${status}`,
    formatLocatorCoverage: (v: unknown) => `coverage-${String(v)}`,
  }),
}))

vi.mock('@/composables/useCellEdit', () => ({
  useCellEdit: () => ({
    editingCell: mocks.editingCell,
    editingValue: mocks.editingValue,
    cellSaving: mocks.cellSaving,
    startCellEdit: mocks.startCellEdit,
    cancelCellEdit: mocks.cancelCellEdit,
    saveCellEdit: mocks.saveCellEdit,
  }),
}))

import {
  createComposableHost,
  installBrowserStubs,
  silenceConsole,
  silenceElMessage,
} from '@/test-utils'
import { provideCaseDetail, VIEW_TYPES } from '../useCaseDetail'

type Ctx = ReturnType<typeof provideCaseDetail>

let ctx: Ctx

const host = createComposableHost(() => provideCaseDetail())

async function mountHost() {
  const wrapper = await host.mount()
  ctx = host.ctx
  return wrapper
}

function makeCase(overrides: Record<string, unknown> = {}) {
  return {
    id: 42,
    case_no: 'TC-1',
    title: '标题',
    module: '模块',
    precondition: '前置',
    priority: 1,
    case_type: 'ui_automation',
    steps: [{ action: 'click', expected_result: 'ok' }],
    expected_result: '总体预期',
    ...overrides,
  }
}

beforeEach(() => {
  vi.clearAllMocks()
  installBrowserStubs()
  mocks.route.params = { caseId: '42' }
  mocks.route.query = {}
  mocks.isEditing.value = false
  mocks.saving.value = false
  mocks.editForm.value = { steps: [{ action: 'a', expected_result: 'b' }] }
  mocks.currentView.value = 'business'
  mocks.viewLoading.value = false
  mocks.technicalViewData.value = null
  mocks.editingCell.value = null
  mocks.editingValue.value = ''
  mocks.cellSaving.value = false

  silenceElMessage()
  silenceConsole('error')

  mocks.getCase.mockResolvedValue(makeCase())
  mocks.getCaseVersions.mockResolvedValue({
    items: [{ id: 9, version_number: 3 }],
    total: 5,
  })
  mocks.exportToExcel.mockResolvedValue({ data: new Blob(['x']) })
  mocks.parsePrecondition.mockResolvedValue({
    data: [{ step_number: 1, action: '打开页面', expected_result: '' }],
  })
  mocks.batchSavePreconditionSteps.mockResolvedValue({ code: 200 })
  mocks.parseBlobError.mockResolvedValue('导出Excel失败')
  mocks.createQuickVerify.mockResolvedValue({ code: 200 })
  mocks.submitVerification.mockResolvedValue({ code: 200 })
  mocks.startCorrection.mockResolvedValue({ code: 200 })
  mocks.rollbackCaseVersion.mockResolvedValue({ code: 200 })
  mocks.updateStepLocator.mockResolvedValue({ code: 200 })
})

describe('useCaseDetail — 路由派生与展示映射', () => {
  it('caseId 取自路由，非法值回退 0', async () => {
    await mountHost()
    expect(ctx.caseId.value).toBe(42)

    mocks.route.params = { caseId: 'abc' }
    await mountHost()
    expect(ctx.caseId.value).toBe(0)
  })

  it('businessSteps 跟随用例详情', async () => {
    await mountHost()
    expect(ctx.businessSteps.value).toEqual([])

    ctx.caseItem.value = makeCase() as never
    expect(ctx.businessSteps.value).toHaveLength(1)
  })

  it('优先级与用例类型映射', async () => {
    await mountHost()

    expect(ctx.getPriorityType(1)).toBe('danger')
    expect(ctx.getPriorityType(2)).toBe('warning')
    expect(ctx.getPriorityType(3)).toBe('success')
    expect(ctx.getPriorityType(9)).toBe('info')
    expect(ctx.getPriorityLabel(1)).toBe('高(P1)')
    expect(ctx.getPriorityLabel(9)).toBe('中(P2)')

    expect(ctx.getCaseTypeLabel('ui_automation')).toBe('UI自动化')
    expect(ctx.getCaseTypeLabel('API')).toBe('API自动化')
    expect(ctx.getCaseTypeLabel('功能测试')).toBe('手工测试')
    expect(ctx.getCaseTypeLabel('custom')).toBe('custom')
    expect(ctx.getCaseTypeLabel()).toBe('-')
    expect(ctx.getTestCategoryLabel('functional')).toBe('手工测试')
  })

  it('formatTime 与动作类型标签', async () => {
    await mountHost()

    expect(ctx.formatTime()).toBe('-')
    expect(typeof ctx.formatTime('2026-11-13T10:00:00Z')).toBe('string')
    expect(ctx.formatTime('2026-11-13T10:00:00Z')).not.toBe('-')

    expect(ctx.getActionTypeTagType('click')).toBe('primary')
    expect(ctx.getActionTypeTagType('input')).toBe('success')
    expect(ctx.getActionTypeTagType('navigate')).toBe('warning')
    expect(ctx.getActionTypeTagType('unknown')).toBe('info')
  })

  it('定位类型工具函数透出', async () => {
    await mountHost()
    expect(ctx.getLocatorTypeLabel('css')).toBe('CSS选择器')
    expect(ctx.getLocatorTypeTagType('css')).toBe('primary')
    expect(ctx.VIEW_TYPES).toEqual({ BUSINESS: 'business', TECHNICAL: 'technical' })
  })

  it('步骤高亮仅在纠正模式命中行时生效', async () => {
    await mountHost()
    expect(ctx.getStepRowClass({ row: {}, rowIndex: 1 })).toBe('')

    ctx.isCorrectionMode.value = true
    ctx.correctionStepIndex.value = 1
    expect(ctx.getStepRowClass({ row: {}, rowIndex: 1 })).toBe('highlighted-step')
    expect(ctx.getStepRowClass({ row: {}, rowIndex: 2 })).toBe('')
  })

  it('goBack 返回用例列表', async () => {
    await mountHost()
    ctx.goBack()
    expect(mocks.push).toHaveBeenCalledWith('/home/case')
  })
})

describe('useCaseDetail — 详情加载与编辑', () => {
  it('加载详情后补空步骤并初始化编辑表单', async () => {
    mocks.getCase.mockResolvedValue(makeCase({ steps: undefined }))
    await mountHost()

    await ctx.init()

    expect(mocks.getCase).toHaveBeenCalledWith(42)
    expect(ctx.caseItem.value?.steps).toEqual([])
    expect(mocks.initEditForm).toHaveBeenCalled()
    expect(ctx.loading.value).toBe(false)
  })

  it('无 caseId 时不请求详情', async () => {
    mocks.route.params = {}
    await mountHost()

    await ctx.init()

    expect(mocks.getCase).not.toHaveBeenCalled()
  })

  it('详情加载失败优先使用接口 detail', async () => {
    mocks.getCase.mockRejectedValue({ response: { data: { detail: '用例不存在' } } })
    await mountHost()

    await ctx.init()

    expect(ElMessage.error).toHaveBeenCalledWith('用例不存在')
    expect(ctx.loading.value).toBe(false)
  })

  it('详情加载失败无 detail 时用 message，再兜底默认文案', async () => {
    mocks.getCase.mockRejectedValueOnce(new Error('网络异常'))
    await mountHost()
    await ctx.init()
    expect(ElMessage.error).toHaveBeenCalledWith('网络异常')

    mocks.getCase.mockRejectedValueOnce({})
    await ctx.init()
    expect(ElMessage.error).toHaveBeenCalledWith('获取用例详情失败')
  })

  it('新增与删除步骤', async () => {
    await mountHost()

    ctx.addStep()
    expect(mocks.editForm.value.steps).toHaveLength(2)

    ctx.removeStep(1)
    expect(mocks.editForm.value.steps).toHaveLength(1)

    ctx.removeStep(0)
    expect(mocks.editForm.value.steps).toHaveLength(1)
  })

  it('编辑相关能力由 useCaseEdit 透出', async () => {
    await mountHost()

    expect(ctx.isEditing).toBe(mocks.isEditing)
    expect(ctx.saving).toBe(mocks.saving)
    expect(ctx.editForm).toBe(mocks.editForm)
    expect(ctx.toggleEdit).toBe(mocks.toggleEdit)
    expect(ctx.cancelEdit).toBe(mocks.cancelEdit)
    expect(ctx.saveEdit).toBe(mocks.saveEdit)
  })

  it('技术视图与单元格编辑能力透出', async () => {
    await mountHost()

    expect(ctx.currentView).toBe(mocks.currentView)
    expect(ctx.technicalViewData).toBe(mocks.technicalViewData)
    expect(ctx.fetchTechnicalView).toBe(mocks.fetchTechnicalView)
    expect(ctx.handleViewChange).toBe(mocks.handleViewChange)
    expect(ctx.startCellEdit).toBe(mocks.startCellEdit)
    expect(ctx.saveCellEdit).toBe(mocks.saveCellEdit)
    expect(ctx.getLocatorStatusType('recorded')).toBe('type-recorded')
    expect(ctx.getLocatorStatusLabel('recorded')).toBe('label-recorded')
    expect(ctx.formatLocatorCoverage(1)).toBe('coverage-1')
  })
})

describe('useCaseDetail — 复制与导出', () => {
  it('无详情时复制直接返回', async () => {
    await mountHost()
    await ctx.copyCase()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('安全上下文下使用剪贴板复制', async () => {
    const writeText = vi.mocked(navigator.clipboard.writeText)
    Object.defineProperty(window, 'isSecureContext', { value: true, configurable: true })
    await mountHost()
    ctx.caseItem.value = makeCase() as never

    await ctx.copyCase()

    expect(writeText).toHaveBeenCalledTimes(1)
    expect(writeText.mock.calls[0][0]).toContain('用例编号: TC-1')
    expect(ElMessage.success).toHaveBeenCalledWith('用例已复制到剪贴板')
  })

  it('非安全上下文回退 execCommand', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    const execCommand = vi.mocked(document.execCommand)
    execCommand.mockReturnValue(true)
    await mountHost()
    ctx.caseItem.value = makeCase() as never

    await ctx.copyCase()

    expect(execCommand).toHaveBeenCalledWith('copy')
    expect(ElMessage.success).toHaveBeenCalledWith('用例已复制到剪贴板')
  })

  it('execCommand 失败提示手动复制', async () => {
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    vi.mocked(document.execCommand).mockReturnValue(false)
    await mountHost()
    ctx.caseItem.value = makeCase() as never

    await ctx.copyCase()

    expect(ElMessage.error).toHaveBeenCalledWith('复制失败，请手动复制')
  })

  it('导出 Excel 使用 case_no 作为兜底文件名', async () => {
    await mountHost()
    ctx.caseItem.value = makeCase() as never

    await ctx.handleExportExcel()

    expect(mocks.exportToExcel).toHaveBeenCalledWith(42)
    expect(mocks.downloadFromResponse).toHaveBeenCalledWith(expect.anything(), 'TC-1.xlsx')
    expect(ElMessage.success).toHaveBeenCalledWith('导出成功')
    expect(ctx.exportingExcel.value).toBe(false)
  })

  it('无 case_no 时兜底文件名使用 case_ 前缀', async () => {
    mocks.getCase.mockResolvedValue(makeCase({ case_no: undefined }))
    await mountHost()
    await ctx.init()

    await ctx.handleExportExcel()

    expect(mocks.downloadFromResponse).toHaveBeenCalledWith(expect.anything(), 'case_42.xlsx')
  })

  it('导出失败展示解析后的错误信息', async () => {
    mocks.exportToExcel.mockRejectedValue(new Error('bad'))
    mocks.parseBlobError.mockResolvedValue('文件损坏')
    await mountHost()

    await ctx.handleExportExcel()

    expect(ElMessage.error).toHaveBeenCalledWith('文件损坏')
    expect(ctx.exportingExcel.value).toBe(false)
  })

  it('无 caseId 时不触发导出', async () => {
    mocks.route.params = {}
    await mountHost()

    await ctx.handleExportExcel()

    expect(mocks.exportToExcel).not.toHaveBeenCalled()
  })
})

describe('useCaseDetail — 前置条件步骤', () => {
  it('解析前置条件成功写入技术视图', async () => {
    await mountHost()
    ctx.technicalViewData.value = { steps: [], precondition_steps: [] } as never

    await ctx.parsePrecondition()

    expect(mocks.parsePrecondition).toHaveBeenCalledWith(42)
    expect(ElMessage.success).toHaveBeenCalledWith('AI解析成功，生成 1 个步骤')
    expect(mocks.technicalViewData.value?.precondition_steps).toHaveLength(1)
    expect(ctx.parsePreconditionLoading.value).toBe(false)
  })

  it('解析结果为空时提示未解析出步骤', async () => {
    mocks.parsePrecondition.mockResolvedValue({ data: [] })
    await mountHost()

    await ctx.parsePrecondition()

    expect(ElMessage.info).toHaveBeenCalledWith('AI未解析出可执行步骤')
  })

  it('解析失败优先使用 detail', async () => {
    mocks.parsePrecondition.mockRejectedValue({ response: { data: { detail: '模型超时' } } })
    await mountHost()

    await ctx.parsePrecondition()

    expect(ElMessage.error).toHaveBeenCalledWith('模型超时')
    expect(ctx.parsePreconditionLoading.value).toBe(false)
  })

  it('解析失败无 detail 时兜底默认文案', async () => {
    mocks.parsePrecondition.mockRejectedValue(new Error('x'))
    await mountHost()

    await ctx.parsePrecondition()

    expect(ElMessage.error).toHaveBeenCalledWith('AI解析失败')
  })

  it('新增前置条件步骤自动编号并保存', async () => {
    await mountHost()
    ctx.technicalViewData.value = {
      steps: [],
      precondition_steps: [{ step_number: 1, action: 'a' }],
    } as never

    ctx.addPreconditionStep()
    await flushPromises()

    const steps = mocks.technicalViewData.value?.precondition_steps as Record<string, unknown>[]
    expect(steps).toHaveLength(2)
    expect(steps[1].step_number).toBe(2)
    expect(mocks.batchSavePreconditionSteps).toHaveBeenCalledWith(42, { steps })
  })

  it('无技术视图时新增直接返回', async () => {
    await mountHost()

    ctx.addPreconditionStep()

    expect(mocks.batchSavePreconditionSteps).not.toHaveBeenCalled()
  })

  it('删除前置条件步骤后重排序号', async () => {
    await mountHost()
    ctx.technicalViewData.value = {
      steps: [],
      precondition_steps: [
        { step_number: 1, action: 'a' },
        { step_number: 2, action: 'b' },
      ],
    } as never

    await ctx.deletePreconditionStep(0)

    const steps = mocks.technicalViewData.value?.precondition_steps as Record<string, unknown>[]
    expect(steps).toHaveLength(1)
    expect(steps[0].step_number).toBe(1)
  })

  it('保存前置条件失败提示错误', async () => {
    mocks.batchSavePreconditionSteps.mockRejectedValue(new Error('x'))
    await mountHost()
    ctx.technicalViewData.value = { steps: [], precondition_steps: [] } as never

    ctx.addPreconditionStep()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('保存前置条件步骤失败')
  })
})

describe('useCaseDetail — 快速验证与版本', () => {
  it('打开快速验证默认选中全部步骤', async () => {
    await mountHost()
    ctx.technicalViewData.value = {
      steps: [{ step_number: 1 }, { step_number: 2 }],
    } as never

    ctx.openQuickVerify()

    expect(ctx.selectedVerifySteps.value).toEqual([1, 2])
    expect(ctx.quickVerifyVisible.value).toBe(true)
  })

  it('无技术视图时不打开快速验证', async () => {
    await mountHost()

    ctx.openQuickVerify()

    expect(ctx.quickVerifyVisible.value).toBe(false)
  })

  it('未选步骤时阻止提交', async () => {
    await mountHost()
    ctx.selectedVerifySteps.value = []

    await ctx.executeQuickVerify()

    expect(ElMessage.warning).toHaveBeenCalledWith('请至少选择一个步骤')
    expect(mocks.createQuickVerify).not.toHaveBeenCalled()
  })

  it('提交快速验证成功后跳转执行页', async () => {
    await mountHost()
    ctx.selectedVerifySteps.value = [1, 2]

    await ctx.executeQuickVerify()

    expect(mocks.createQuickVerify).toHaveBeenCalledWith(42, [1, 2])
    expect(mocks.submitVerification).toHaveBeenCalledWith(42)
    expect(ctx.quickVerifyVisible.value).toBe(false)
    expect(mocks.push).toHaveBeenCalledWith('/home/task/execution/42')
    expect(ctx.quickVerifyLoading.value).toBe(false)
  })

  it('提交快速验证失败提示错误', async () => {
    mocks.createQuickVerify.mockRejectedValue({ response: { data: { detail: '额度不足' } } })
    await mountHost()
    ctx.selectedVerifySteps.value = [1]

    await ctx.executeQuickVerify()

    expect(ElMessage.error).toHaveBeenCalledWith('额度不足')
    expect(ctx.quickVerifyLoading.value).toBe(false)
  })

  it('打开版本历史拉取第一页', async () => {
    await mountHost()
    ctx.versionPage.value = 3

    ctx.openVersionHistory()
    await flushPromises()

    expect(ctx.versionHistoryVisible.value).toBe(true)
    expect(ctx.versionPage.value).toBe(1)
    expect(mocks.getCaseVersions).toHaveBeenCalledWith(42, 1, 20)
    expect(ctx.versionList.value).toHaveLength(1)
    expect(ctx.versionTotal.value).toBe(5)
    expect(ctx.versionLoading.value).toBe(false)
  })

  it('版本总量缺失时用列表长度兜底', async () => {
    mocks.getCaseVersions.mockResolvedValue({ items: [{ id: 1 }, { id: 2 }] })
    await mountHost()

    await ctx.fetchVersionHistory()

    expect(ctx.versionTotal.value).toBe(2)
  })

  it('版本拉取失败提示错误', async () => {
    mocks.getCaseVersions.mockRejectedValue({ response: { data: { detail: '无权限' } } })
    await mountHost()

    await ctx.fetchVersionHistory()

    expect(ElMessage.error).toHaveBeenCalledWith('无权限')
    expect(ctx.versionLoading.value).toBe(false)
  })

  it('回滚成功刷新详情并在技术视图下重新拉取', async () => {
    await mountHost()
    mocks.currentView.value = VIEW_TYPES.TECHNICAL

    await ctx.handleRollback({ id: 9, version_number: 3 } as never)

    expect(mocks.rollbackCaseVersion).toHaveBeenCalledWith(42, 9)
    expect(ElMessage.success).toHaveBeenCalledWith('已回滚到版本 v3')
    expect(ctx.versionHistoryVisible.value).toBe(false)
    expect(mocks.getCase).toHaveBeenCalled()
    expect(mocks.fetchTechnicalView).toHaveBeenCalled()
    expect(ctx.rollbackLoading.value).toBe(false)
  })

  it('回滚成功后业务视图不重拉技术视图', async () => {
    await mountHost()
    mocks.currentView.value = VIEW_TYPES.BUSINESS

    await ctx.handleRollback({ id: 9, version_number: 3 } as never)

    expect(mocks.fetchTechnicalView).not.toHaveBeenCalled()
  })

  it('回滚失败提示错误', async () => {
    mocks.rollbackCaseVersion.mockRejectedValue({ response: { data: { detail: '版本不存在' } } })
    await mountHost()

    await ctx.handleRollback({ id: 9, version_number: 3 } as never)

    expect(ElMessage.error).toHaveBeenCalledWith('版本不存在')
    expect(ctx.rollbackLoading.value).toBe(false)
  })
})

describe('useCaseDetail — 定位信息维护', () => {
  function setupView() {
    mocks.technicalViewData.value = {
      steps: [{ step_number: 1, locator_status: 'pending' }],
    }
  }

  it('打开定位弹窗重置表单', async () => {
    await mountHost()
    setupView()
    ctx.addLocatorForm.value.css_selector = 'x'

    ctx.openAddLocator(0, {})

    expect(ctx.addLocatorVisible.value).toBe(true)
    expect(ctx.addLocatorStepIndex.value).toBe(0)
    expect(ctx.addLocatorForm.value).toEqual({
      css_selector: '',
      xpath: '',
      ai_coordinate: '',
      locator_type: 'css',
    })
  })

  it('未填写任何定位信息时提示', async () => {
    await mountHost()
    setupView()
    ctx.openAddLocator(0, {})

    await ctx.saveAddLocator()

    expect(ElMessage.warning).toHaveBeenCalledWith('请至少填写一种定位信息')
    expect(mocks.updateStepLocator).not.toHaveBeenCalled()
  })

  it('保存定位成功后写回步骤', async () => {
    await mountHost()
    setupView()
    ctx.openAddLocator(0, {})
    ctx.addLocatorForm.value.css_selector = '#app'
    ctx.addLocatorForm.value.xpath = '//div'

    await ctx.saveAddLocator()

    const steps = mocks.technicalViewData.value?.steps as unknown as Record<string, unknown>[]
    const step = steps[0]
    expect(mocks.updateStepLocator).toHaveBeenCalledWith(42, 1, {
      css_selector: '#app',
      xpath: '//div',
      ai_coordinate: '',
    })
    expect(step.locator).toMatchObject({ css_selector: '#app', xpath: '//div' })
    expect(step.locator_status).toBe('recorded')
    expect(ElMessage.success).toHaveBeenCalledWith('定位信息添加成功')
    expect(ctx.addLocatorVisible.value).toBe(false)
    expect(ctx.addLocatorLoading.value).toBe(false)
  })

  it('保存定位失败提示错误', async () => {
    mocks.updateStepLocator.mockRejectedValue({ response: { data: { detail: '元素冲突' } } })
    await mountHost()
    setupView()
    ctx.openAddLocator(0, {})
    ctx.addLocatorForm.value.css_selector = '#app'

    await ctx.saveAddLocator()

    expect(ElMessage.error).toHaveBeenCalledWith('元素冲突')
    expect(ctx.addLocatorLoading.value).toBe(false)
  })

  it('步骤索引越界时直接返回', async () => {
    await mountHost()
    setupView()
    ctx.openAddLocator(5, {})
    ctx.addLocatorForm.value.css_selector = '#app'

    await ctx.saveAddLocator()

    expect(mocks.updateStepLocator).not.toHaveBeenCalled()
  })
})

describe('useCaseDetail — 纠正参数与初始化', () => {
  it('无纠正参数时不做处理', async () => {
    await mountHost()

    await ctx.handleCorrectionParams()

    expect(ctx.isCorrectionMode.value).toBe(false)
    expect(mocks.fetchTechnicalView).not.toHaveBeenCalled()
  })

  it('纠正参数写入状态并切到技术视图', async () => {
    mocks.route.query = {
      correction: 'true',
      stepIndex: '2',
      issueType: 'case_issue',
      failureReason: encodeURIComponent('点击失败'),
      aiAnalysis: encodeURIComponent('定位器失效'),
    }
    await mountHost()

    await ctx.handleCorrectionParams()

    expect(ctx.isCorrectionMode.value).toBe(true)
    expect(ctx.correctionStepIndex.value).toBe(2)
    expect(ctx.issueType.value).toBe('case_issue')
    expect(ctx.failureReason.value).toBe('点击失败')
    expect(ctx.aiAnalysisText.value).toBe('定位器失效')
    expect(ctx.currentView.value).toBe(VIEW_TYPES.TECHNICAL)
    expect(mocks.fetchTechnicalView).toHaveBeenCalled()
    expect(mocks.startCorrection).toHaveBeenCalledWith(42)
  })

  it('产品缺陷场景关闭编辑态且不改纠正状态', async () => {
    mocks.route.query = { correction: 'true', issueType: 'product_bug' }
    await mountHost()
    mocks.isEditing.value = true

    await ctx.handleCorrectionParams()

    expect(ctx.issueType.value).toBe('product_bug')
    expect(mocks.isEditing.value).toBe(false)
    expect(ctx.correctionStepIndex.value).toBe(-1)
    expect(mocks.startCorrection).not.toHaveBeenCalled()
  })

  it('设置纠正状态失败只记录日志', async () => {
    mocks.route.query = { correction: 'true', issueType: 'needs_review' }
    mocks.startCorrection.mockRejectedValue(new Error('x'))
    await mountHost()

    await ctx.handleCorrectionParams()

    expect(console.error).toHaveBeenCalled()
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('init 在无 caseId 时跳过', async () => {
    mocks.route.params = {}
    await mountHost()

    await ctx.init()

    expect(mocks.getCase).not.toHaveBeenCalled()
  })

  it('init 串联详情加载与纠正参数处理', async () => {
    mocks.route.query = { correction: 'true', issueType: 'case_issue' }
    await mountHost()

    await ctx.init()

    expect(mocks.getCase).toHaveBeenCalledWith(42)
    expect(ctx.isCorrectionMode.value).toBe(true)
  })
})
