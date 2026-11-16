import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'

const mocks = vi.hoisted(() => ({
  getProjects: vi.fn(),
  rollbackCaseVersion: vi.fn(),
  listRefreshSuggestions: vi.fn(),
  reviewRefreshSuggestion: vi.fn(),
  scanStaleCases: vi.fn(),
  autoRefreshCases: vi.fn(),
  getRefreshSuggestionsStats: vi.fn(),
}))

vi.mock('@/api/project', () => ({
  default: { getProjects: mocks.getProjects },
}))

vi.mock('@/api/case', () => ({
  caseApi: { rollbackCaseVersion: mocks.rollbackCaseVersion },
}))

vi.mock('@/api/caseRefresh', () => ({
  listRefreshSuggestions: mocks.listRefreshSuggestions,
  reviewRefreshSuggestion: mocks.reviewRefreshSuggestion,
  scanStaleCases: mocks.scanStaleCases,
  autoRefreshCases: mocks.autoRefreshCases,
  getRefreshSuggestionsStats: mocks.getRefreshSuggestionsStats,
}))

// 保留真实组件，仅替换消息与确认框，便于断言文案
vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  const message = Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    close: vi.fn(),
    closeAll: vi.fn(),
  })
  return {
    ...actual,
    ElMessage: message,
    ElMessageBox: { ...actual.ElMessageBox, confirm: vi.fn() },
  }
})

import { ElMessage, ElMessageBox } from 'element-plus'
import CaseRefresh from '../CaseRefresh.vue'

const messageMock = ElMessage as unknown as ReturnType<typeof vi.fn> & {
  success: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
  warning: ReturnType<typeof vi.fn>
  info: ReturnType<typeof vi.fn>
}
const confirmMock = ElMessageBox.confirm as unknown as ReturnType<typeof vi.fn>

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: {
    modelValue: { type: Boolean, default: false },
    title: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'close'],
  template: `
    <div v-if="modelValue" class="el-dialog">
      <div class="el-dialog__header">{{ title }}</div>
      <slot />
      <div class="el-dialog__footer"><slot name="footer" /></div>
    </div>
  `,
})

interface SuggestionFixture {
  id: number
  case_id: number
  requirement_id: number | null
  trigger_reason: string
  triggered_at: string | null
  suggestion_status: string
  suggested_title: string | null
  suggested_steps: Array<Record<string, unknown>> | null
  suggested_expected_result: string | null
  diff_description: string | null
  deprecation_reason: string | null
  review_status: string
  reviewer_name: string | null
  reviewed_at: string | null
  reject_reason: string | null
  model_version: string | null
  snapshot_version_id: number | null
  created_at: string | null
}

function makeSuggestion(overrides: Partial<SuggestionFixture> = {}): SuggestionFixture {
  return {
    id: 1,
    case_id: 101,
    requirement_id: null,
    trigger_reason: '需求变更',
    triggered_at: '2026-06-27T10:00:00',
    suggestion_status: 'pending',
    suggested_title: '新的用例标题',
    suggested_steps: [{ action: '打开首页' }],
    suggested_expected_result: '展示首页',
    diff_description: '标题与预期结果变更',
    deprecation_reason: null,
    review_status: 'pending',
    reviewer_name: null,
    reviewed_at: null,
    reject_reason: null,
    model_version: 'v2',
    snapshot_version_id: 9,
    created_at: '2026-06-27T09:00:00',
    ...overrides,
  }
}

function mountPage() {
  return mount(CaseRefresh, { global: { stubs: { ElDialog: ElDialogStub } } })
}

async function selectProject(wrapper: ReturnType<typeof mount>, projectId: number) {
  const select = wrapper.findComponent({ name: 'ElSelect' })
  select.vm.$emit('update:modelValue', projectId)
  select.vm.$emit('change', projectId)
  await flushPromises()
}

function rows(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('.workspace-card .el-table__row')
}

function buttonByText(
  scope: { findAll: (s: string) => Array<{ text: () => string }> },
  text: string
) {
  return scope.findAll('button').find((btn) => btn.text().includes(text)) as
    | { trigger: (e: string) => Promise<void> }
    | undefined
}

function dialogByTitle(wrapper: ReturnType<typeof mount>, title: string) {
  return wrapper.findAll('.el-dialog').find((el) => el.text().includes(title))
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getProjects.mockResolvedValue({
    data: {
      items: [
        { id: 5, name: '项目A' },
        { id: 6, name: '项目B' },
      ],
    },
  })
  mocks.listRefreshSuggestions.mockResolvedValue({
    data: { items: [makeSuggestion()], total: 1 },
  })
  mocks.getRefreshSuggestionsStats.mockResolvedValue({
    data: { pending: 1, applied: 2, rejected: 3, total: 6 },
  })
  mocks.scanStaleCases.mockResolvedValue({ data: { count: 4 } })
  mocks.autoRefreshCases.mockResolvedValue({ data: { total_scanned: 0, status: 'done' } })
  mocks.reviewRefreshSuggestion.mockResolvedValue({ data: {} })
  mocks.rollbackCaseVersion.mockResolvedValue({ data: {} })
  confirmMock.mockResolvedValue('confirm')
})

afterEach(() => {
  vi.useRealTimers()
})

describe('CaseRefresh — 页面初始化', () => {
  it('挂载后拉取项目列表', async () => {
    mountPage()
    await flushPromises()

    expect(mocks.getProjects).toHaveBeenCalledWith({ page: 1, page_size: 100 })
  })

  it('未选择项目时展示空态且不请求建议', async () => {
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('.workspace-card').exists()).toBe(false)
    expect(wrapper.find('.el-empty').text()).toContain('请选择项目后查看保鲜建议')
    expect(mocks.listRefreshSuggestions).not.toHaveBeenCalled()
  })

  it('未选择项目时两个扫描按钮禁用', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const buttons = wrapper.findAllComponents({ name: 'ElButton' })
    expect(buttons.find((b) => b.text().includes('AI保鲜扫描'))!.props('disabled')).toBe(true)
    expect(buttons.find((b) => b.text().includes('仅扫描过期'))!.props('disabled')).toBe(true)
  })

  it('项目加载失败时提示错误', async () => {
    mocks.getProjects.mockRejectedValue(new Error('项目接口异常'))
    mountPage()
    await flushPromises()

    expect(messageMock.error).toHaveBeenCalledWith('项目接口异常')
  })

  it('项目加载失败且非 Error 时使用兜底文案', async () => {
    mocks.getProjects.mockRejectedValue(undefined)
    mountPage()
    await flushPromises()

    expect(messageMock.error).toHaveBeenCalledWith('加载项目失败')
  })
})

describe('CaseRefresh — 建议列表', () => {
  it('选择项目后按第一页拉取建议与统计', async () => {
    const wrapper = mountPage()
    await flushPromises()

    await selectProject(wrapper, 5)

    expect(mocks.listRefreshSuggestions).toHaveBeenCalledWith(5, 1, 20)
    expect(mocks.getRefreshSuggestionsStats).toHaveBeenCalledWith(5)
    expect(wrapper.find('.workspace-card').exists()).toBe(true)
    expect(rows(wrapper)).toHaveLength(1)
  })

  it('统计卡片展示待审核/已应用/已驳回数量', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    const chips = wrapper.findAll('.stat-chip')
    expect(chips[0].text()).toContain('待审核')
    expect(chips[0].text()).toContain('1')
    expect(chips[1].text()).toContain('已应用')
    expect(chips[1].text()).toContain('2')
    expect(chips[2].text()).toContain('已驳回')
    expect(chips[2].text()).toContain('3')
  })

  it('统计接口失败时数量归零', async () => {
    mocks.getRefreshSuggestionsStats.mockRejectedValue(new Error('统计失败'))
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    const chips = wrapper.findAll('.stat-chip')
    expect(chips[0].find('.stat-value').text()).toBe('0')
    expect(chips[1].find('.stat-value').text()).toBe('0')
    expect(chips[2].find('.stat-value').text()).toBe('0')
  })

  it('建议接口失败时提示错误', async () => {
    mocks.listRefreshSuggestions.mockRejectedValue(new Error('建议接口异常'))
    const wrapper = mountPage()
    await flushPromises()

    await selectProject(wrapper, 5)

    expect(messageMock.error).toHaveBeenCalledWith('建议接口异常')
  })

  it('表格行展示建议标题、触发原因与状态标签', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    const row = rows(wrapper)[0]
    expect(row.text()).toContain('新的用例标题')
    expect(row.text()).toContain('需求变更')
    expect(row.text()).toContain('待处理')
    expect(row.text()).toContain('待审核')
    expect(row.text()).toContain('2026-06-27 10:00:00')
  })

  it('建议标题缺失时回退为「用例 #id」，触发时间为空展示 --', async () => {
    mocks.listRefreshSuggestions.mockResolvedValue({
      data: {
        items: [
          makeSuggestion({
            suggested_title: null,
            triggered_at: null,
            suggestion_status: 'expired',
            review_status: 'rejected',
          }),
        ],
        total: 1,
      },
    })
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    const row = rows(wrapper)[0]
    expect(row.text()).toContain('用例 #101')
    expect(row.text()).toContain('已过期')
    expect(row.text()).toContain('已驳回')
    expect(row.text()).toContain('--')
  })

  it('待审核行展示查看详情/通过/驳回三个操作', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    const texts = rows(wrapper)[0]
      .findAll('button')
      .map((b) => b.text())
    expect(texts).toEqual(['查看详情', '通过', '驳回'])
  })

  it('已通过行展示查看diff，有快照时额外展示回滚', async () => {
    mocks.listRefreshSuggestions.mockResolvedValue({
      data: { items: [makeSuggestion({ review_status: 'approved' })], total: 1 },
    })
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    const texts = rows(wrapper)[0]
      .findAll('button')
      .map((b) => b.text())
    expect(texts).toEqual(['查看diff', '回滚'])
  })

  it('已通过但无快照版本时不展示回滚', async () => {
    mocks.listRefreshSuggestions.mockResolvedValue({
      data: {
        items: [makeSuggestion({ review_status: 'approved', snapshot_version_id: null })],
        total: 1,
      },
    })
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    const texts = rows(wrapper)[0]
      .findAll('button')
      .map((b) => b.text())
    expect(texts).toEqual(['查看diff'])
  })

  it('已驳回行展示占位文案', async () => {
    mocks.listRefreshSuggestions.mockResolvedValue({
      data: { items: [makeSuggestion({ review_status: 'rejected' })], total: 1 },
    })
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    expect(rows(wrapper)[0].find('.text-muted').text()).toBe('--')
  })

  it('切换页码后按新页码重新拉取', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)
    mocks.listRefreshSuggestions.mockClear()

    const pagination = wrapper.findComponent({ name: 'ElPagination' })
    pagination.vm.$emit('update:current-page', 2)
    pagination.vm.$emit('current-change', 2)
    await flushPromises()

    expect(mocks.listRefreshSuggestions).toHaveBeenCalledWith(5, 2, 20)
  })

  it('调整每页条数后重置到第一页', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)
    mocks.listRefreshSuggestions.mockClear()

    const pagination = wrapper.findComponent({ name: 'ElPagination' })
    pagination.vm.$emit('update:page-size', 50)
    pagination.vm.$emit('size-change', 50)
    await flushPromises()

    expect(mocks.listRefreshSuggestions).toHaveBeenCalledWith(5, 1, 50)
  })
})

describe('CaseRefresh — 扫描动作', () => {
  it('仅扫描过期成功后提示发现数量', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    await buttonByText(wrapper, '仅扫描过期')!.trigger('click')
    await flushPromises()

    expect(mocks.scanStaleCases).toHaveBeenCalledWith(5)
    expect(messageMock.success).toHaveBeenCalledWith('扫描完成，发现 4 条过期用例')
  })

  it('仅扫描过期失败时提示错误', async () => {
    mocks.scanStaleCases.mockRejectedValue(new Error('扫描失败'))
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    await buttonByText(wrapper, '仅扫描过期')!.trigger('click')
    await flushPromises()

    expect(messageMock.error).toHaveBeenCalledWith('扫描失败')
  })

  it('AI 保鲜扫描无过期用例时给出 info 提示', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    await buttonByText(wrapper, 'AI保鲜扫描')!.trigger('click')
    await flushPromises()

    expect(mocks.autoRefreshCases).toHaveBeenCalledWith(5)
    expect(messageMock.info).toHaveBeenCalledWith('无过期用例')
  })

  it('AI 保鲜扫描提交后台处理时提示并 3 秒后自动刷新', async () => {
    mocks.autoRefreshCases.mockResolvedValue({
      data: { total_scanned: 3, status: 'processing' },
    })
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)
    mocks.listRefreshSuggestions.mockClear()

    vi.useFakeTimers()
    await buttonByText(wrapper, 'AI保鲜扫描')!.trigger('click')
    await vi.advanceTimersByTimeAsync(0)

    expect(messageMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'success',
        message: expect.stringContaining('已提交后台处理，共 3 条过期用例'),
      })
    )
    expect(mocks.listRefreshSuggestions).not.toHaveBeenCalled()

    await vi.advanceTimersByTimeAsync(3000)
    expect(mocks.listRefreshSuggestions).toHaveBeenCalledWith(5, 1, 20)
  })

  it('AI 保鲜扫描异常时提示错误', async () => {
    mocks.autoRefreshCases.mockRejectedValue(new Error('扫描服务不可用'))
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    await buttonByText(wrapper, 'AI保鲜扫描')!.trigger('click')
    await flushPromises()

    expect(messageMock.error).toHaveBeenCalledWith('扫描服务不可用')
  })
})

describe('CaseRefresh — 审核弹窗', () => {
  it('点击通过打开审核弹窗并展示建议详情', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    await buttonByText(rows(wrapper)[0], '通过')!.trigger('click')
    await nextTick()

    const dialog = dialogByTitle(wrapper, '通过保鲜建议')
    expect(dialog).toBeTruthy()
    expect(dialog!.text()).toContain('新的用例标题')
    expect(dialog!.text()).toContain('展示首页')
    expect(dialog!.text()).toContain('标题与预期结果变更')
    expect(dialog!.findAll('.step-list li')).toHaveLength(1)
  })

  it('确认通过后调用审核接口并刷新列表', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)
    await buttonByText(rows(wrapper)[0], '通过')!.trigger('click')
    await nextTick()
    mocks.listRefreshSuggestions.mockClear()

    await buttonByText(dialogByTitle(wrapper, '通过保鲜建议')!, '确认通过')!.trigger('click')
    await flushPromises()

    expect(mocks.reviewRefreshSuggestion).toHaveBeenCalledWith(1, 'approve', undefined)
    expect(messageMock.success).toHaveBeenCalledWith('已通过')
    expect(mocks.listRefreshSuggestions).toHaveBeenCalledTimes(1)
  })

  it('驳回弹窗要求填写原因，填写后携带 trim 后的原因提交', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    await buttonByText(rows(wrapper)[0], '驳回')!.trigger('click')
    await nextTick()

    const dialog = dialogByTitle(wrapper, '驳回保鲜建议')!
    expect(dialog.text()).toContain('驳回原因')
    expect(buttonByText(dialog, '确认驳回')).toBeTruthy()

    const input = dialog.findAllComponents({ name: 'ElInput' })[0]
    input.vm.$emit('update:modelValue', '  用例已废弃  ')
    await nextTick()

    await buttonByText(dialog, '确认驳回')!.trigger('click')
    await flushPromises()

    expect(mocks.reviewRefreshSuggestion).toHaveBeenCalledWith(1, 'reject', '用例已废弃')
    expect(messageMock.success).toHaveBeenCalledWith('已驳回')
  })

  it('驳回原因为空时确认按钮禁用', async () => {
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)
    await buttonByText(rows(wrapper)[0], '驳回')!.trigger('click')
    await nextTick()

    const dialog = dialogByTitle(wrapper, '驳回保鲜建议')!
    const confirmBtn = dialog
      .findAllComponents({ name: 'ElButton' })
      .find((btn: VueWrapper) => btn.text().includes('确认驳回'))
    expect(confirmBtn!.props('disabled')).toBe(true)
  })

  it('审核接口失败时提示错误', async () => {
    mocks.reviewRefreshSuggestion.mockRejectedValue(new Error('审核超时'))
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)
    await buttonByText(rows(wrapper)[0], '通过')!.trigger('click')
    await nextTick()

    await buttonByText(dialogByTitle(wrapper, '通过保鲜建议')!, '确认通过')!.trigger('click')
    await flushPromises()

    expect(messageMock.error).toHaveBeenCalledWith('审核超时')
  })
})

describe('CaseRefresh — 变更详情与回滚', () => {
  it('点击查看详情打开 diff 弹窗并展示模型与快照信息', async () => {
    mocks.listRefreshSuggestions.mockResolvedValue({
      data: { items: [makeSuggestion({ review_status: 'approved' })], total: 1 },
    })
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    await buttonByText(rows(wrapper)[0], '查看diff')!.trigger('click')
    await nextTick()

    const dialog = dialogByTitle(wrapper, '变更详情')!
    expect(dialog.text()).toContain('模型版本')
    expect(dialog.text()).toContain('v2')
    expect(dialog.text()).toContain('快照版本ID')
    expect(dialog.text()).toContain('#9')
    expect(buttonByText(dialog, '回滚到此版本')).toBeTruthy()
  })

  it('表格内回滚确认后调用版本回滚接口并刷新', async () => {
    mocks.listRefreshSuggestions.mockResolvedValue({
      data: { items: [makeSuggestion({ review_status: 'approved' })], total: 1 },
    })
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)
    mocks.listRefreshSuggestions.mockClear()

    await buttonByText(rows(wrapper)[0], '回滚')!.trigger('click')
    await flushPromises()

    expect(confirmMock).toHaveBeenCalled()
    expect(mocks.rollbackCaseVersion).toHaveBeenCalledWith(101, 9)
    expect(messageMock.success).toHaveBeenCalledWith('回滚成功')
    expect(mocks.listRefreshSuggestions).toHaveBeenCalledTimes(1)
  })

  it('取消回滚时不调用接口', async () => {
    mocks.listRefreshSuggestions.mockResolvedValue({
      data: { items: [makeSuggestion({ review_status: 'approved' })], total: 1 },
    })
    confirmMock.mockRejectedValue('cancel')
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    await buttonByText(rows(wrapper)[0], '回滚')!.trigger('click')
    await flushPromises()

    expect(mocks.rollbackCaseVersion).not.toHaveBeenCalled()
  })

  it('回滚接口失败时提示错误', async () => {
    mocks.listRefreshSuggestions.mockResolvedValue({
      data: { items: [makeSuggestion({ review_status: 'approved' })], total: 1 },
    })
    mocks.rollbackCaseVersion.mockRejectedValue(new Error('快照不存在'))
    const wrapper = mountPage()
    await flushPromises()
    await selectProject(wrapper, 5)

    await buttonByText(rows(wrapper)[0], '回滚')!.trigger('click')
    await flushPromises()

    expect(messageMock.error).toHaveBeenCalledWith('快照不存在')
  })
})
