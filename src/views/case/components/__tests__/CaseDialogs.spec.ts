import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount, type DOMWrapper, type VueWrapper } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'

const mockCtx = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))
const batchLocatorOpen = vi.hoisted(() => ({ fn: null as unknown as ReturnType<typeof vi.fn> }))

vi.mock('@/composables/case/useCaseDetail', () => ({
  useCaseDetail: () => mockCtx.current,
}))

vi.mock('@/api/case', () => ({
  testCaseApi: { compareCaseVersions: vi.fn() },
}))

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
  return { ...actual, ElMessage: message }
})

import { ElMessage } from 'element-plus'
import { testCaseApi } from '@/api/case'
import CaseDialogs from '../CaseDialogs.vue'

batchLocatorOpen.fn = vi.fn()

const messageMock = ElMessage as unknown as {
  success: ReturnType<typeof vi.fn>
  error: ReturnType<typeof vi.fn>
  warning: ReturnType<typeof vi.fn>
}

const compareMock = testCaseApi.compareCaseVersions as unknown as ReturnType<typeof vi.fn>

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: {
    modelValue: { type: Boolean, default: false },
    title: { type: String, default: '' },
    width: { type: String, default: '' },
    appendToBody: { type: Boolean, default: false },
    destroyOnClose: { type: Boolean, default: false },
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

const CaseVersionDiffStub = defineComponent({
  name: 'CaseVersionDiff',
  props: {
    diffData: { type: Array, default: () => [] },
    stepsDiff: { type: [Array, Object], default: () => [] },
  },
  setup() {
    return () => h('div', { class: 'case-version-diff-stub' })
  },
})

const BatchLocatorDialogStub = defineComponent({
  name: 'BatchLocatorDialog',
  props: { projectId: { type: Number, default: 0 } },
  setup(_props, { expose }) {
    expose({ open: batchLocatorOpen.fn })
    return () => h('div', { class: 'batch-locator-stub' })
  },
})

interface TechnicalStep {
  step_number: number
  display_action?: string | null
  description?: string | null
  action?: string | null
}

interface VersionRow {
  id: number
  version_number: number
  change_type: string
  change_description: string | null
  operator_name: string | null
  created_at: string | null
}

function makeVersion(overrides: Partial<VersionRow> = {}): VersionRow {
  return {
    id: 1,
    version_number: 1,
    change_type: 'update',
    change_description: '调整步骤',
    operator_name: '张三',
    created_at: '2026-01-02T03:04:05Z',
    ...overrides,
  }
}

function makeCtx() {
  return {
    quickVerifyVisible: ref(false),
    quickVerifyLoading: ref(false),
    selectedVerifySteps: ref<number[]>([]),
    technicalViewData: ref<{ steps: TechnicalStep[] } | null>(null),
    executeQuickVerify: vi.fn(),

    versionHistoryVisible: ref(false),
    versionLoading: ref(false),
    versionList: ref<VersionRow[]>([]),
    versionTotal: ref(0),
    versionPage: ref(1),
    rollbackLoading: ref(false),
    fetchVersionHistory: vi.fn(),
    handleRollback: vi.fn(),

    addLocatorVisible: ref(false),
    addLocatorLoading: ref(false),
    addLocatorForm: ref({
      css_selector: '',
      xpath: '',
      ai_coordinate: '',
      locator_type: 'css',
    }),
    saveAddLocator: vi.fn(),

    batchLocatorVisible: ref(false),
    caseItem: ref<{ project_id: number } | null>({ project_id: 7 }),
    caseId: ref<number | null>(12),
  }
}

type Ctx = ReturnType<typeof makeCtx>

function mountDialogs(ctx: Ctx) {
  mockCtx.current = ctx as unknown as Record<string, unknown>
  return mount(CaseDialogs, {
    global: {
      stubs: {
        ElDialog: ElDialogStub,
        CaseVersionDiff: CaseVersionDiffStub,
        BatchLocatorDialog: BatchLocatorDialogStub,
      },
    },
  })
}

function findButton(scope: VueWrapper | DOMWrapper<Element>, text: string) {
  const buttons = (
    scope as unknown as { findAll: (selector: string) => DOMWrapper<HTMLButtonElement>[] }
  ).findAll('button')
  const hit = buttons.find((btn) => btn.text().includes(text))
  if (!hit) throw new Error(`未找到按钮：${text}`)
  return hit
}

function elButtons(wrapper: VueWrapper) {
  return wrapper.findAllComponents({ name: 'ElButton' })
}

function dialogByTitle(wrapper: VueWrapper, title: string) {
  return wrapper
    .findAll('.el-dialog')
    .find((el) => el.find('.el-dialog__header').text().includes(title))
}

beforeEach(() => {
  vi.clearAllMocks()
  batchLocatorOpen.fn.mockClear()
  compareMock.mockReset()
})

describe('CaseDialogs — 快速验证弹窗', () => {
  it('未打开时不渲染弹窗', () => {
    const wrapper = mountDialogs(makeCtx())

    expect(wrapper.findAll('.el-dialog')).toHaveLength(0)
  })

  it('按 display_action / description / action 优先级渲染步骤文案', () => {
    const ctx = makeCtx()
    ctx.quickVerifyVisible.value = true
    ctx.technicalViewData.value = {
      steps: [
        { step_number: 1, display_action: '点击登录', description: '描述一', action: '原始动作' },
        { step_number: 2, display_action: null, description: '填写用户名', action: '原始动作' },
        { step_number: 3, display_action: '', description: null, action: '输入密码' },
      ],
    }
    const wrapper = mountDialogs(ctx)

    const text = dialogByTitle(wrapper, '快速验证')!.text()
    expect(text).toContain('步骤 1:')
    expect(text).toContain('点击登录')
    expect(text).toContain('填写用户名')
    expect(text).toContain('输入密码')
    expect(text).not.toContain('原始动作')
  })

  it('超长动作截断为 50 字并追加省略号', () => {
    const longAction = 'A'.repeat(60)
    const ctx = makeCtx()
    ctx.quickVerifyVisible.value = true
    ctx.technicalViewData.value = { steps: [{ step_number: 1, action: longAction }] }
    const wrapper = mountDialogs(ctx)

    const text = dialogByTitle(wrapper, '快速验证')!.text()
    expect(text).toContain(`${'A'.repeat(50)}...`)
    expect(text).not.toContain(longAction)
  })

  it('全部文案缺失时展示占位符且不追加省略号', () => {
    const ctx = makeCtx()
    ctx.quickVerifyVisible.value = true
    ctx.technicalViewData.value = {
      steps: [{ step_number: 9, display_action: null, description: null, action: null }],
    }
    const wrapper = mountDialogs(ctx)

    const text = dialogByTitle(wrapper, '快速验证')!.text()
    expect(text).toContain('步骤 9:')
    expect(text).toContain('-')
    expect(text).not.toContain('...')
  })

  it('取消直接关闭弹窗', async () => {
    const ctx = makeCtx()
    ctx.quickVerifyVisible.value = true
    const wrapper = mountDialogs(ctx)

    await findButton(dialogByTitle(wrapper, '快速验证')!, '取消').trigger('click')

    expect(ctx.quickVerifyVisible.value).toBe(false)
  })

  it('开始验证触发执行并透传 loading 状态', async () => {
    const ctx = makeCtx()
    ctx.quickVerifyVisible.value = true
    ctx.quickVerifyLoading.value = true
    const wrapper = mountDialogs(ctx)

    expect(
      elButtons(wrapper)
        .find((btn) => btn.text().includes('开始验证'))!
        .props('loading')
    ).toBe(true)

    ctx.quickVerifyLoading.value = false
    await nextTick()
    await findButton(dialogByTitle(wrapper, '快速验证')!, '开始验证').trigger('click')

    expect(ctx.executeQuickVerify).toHaveBeenCalledTimes(1)
  })
})

describe('CaseDialogs — 版本历史列表', () => {
  it('加载中展示骨架屏而非表格', () => {
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionLoading.value = true
    const wrapper = mountDialogs(ctx)

    const dialog = dialogByTitle(wrapper, '版本历史')!
    expect(dialog.find('.loading-container').exists()).toBe(true)
    expect(dialog.findAll('.el-table__row')).toHaveLength(0)
  })

  it('渲染版本号、修改类型标签与空值占位', async () => {
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [
      makeVersion({
        id: 1,
        version_number: 3,
        change_type: 'correction',
        change_description: null,
        operator_name: null,
        created_at: null,
      }),
      makeVersion({ id: 2, version_number: 4, change_type: 'rollback' }),
      makeVersion({ id: 3, version_number: 5, change_type: 'create' }),
      makeVersion({ id: 4, version_number: 6, change_type: 'custom' }),
    ]
    const wrapper = mountDialogs(ctx)
    await flushPromises()

    const rows = dialogByTitle(wrapper, '版本历史')!.findAll('.el-table__row')
    expect(rows).toHaveLength(4)
    expect(rows[0].text()).toContain('v3')
    expect(rows[0].text()).toContain('纠正')
    expect(rows[0].text()).toContain('-')
    expect(rows[1].text()).toContain('回滚')
    expect(rows[2].text()).toContain('创建')
    expect(rows[3].text()).toContain('custom')
  })

  it('修改时间按本地化格式展示', async () => {
    const created = '2026-03-04T05:06:07Z'
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [makeVersion({ created_at: created })]
    const wrapper = mountDialogs(ctx)
    await flushPromises()

    const row = dialogByTitle(wrapper, '版本历史')!.find('.el-table__row')
    expect(row.text()).toContain(new Date(created).toLocaleString())
  })

  it('未选满两个版本时对比按钮禁用并展示计数', () => {
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [makeVersion({ id: 1 }), makeVersion({ id: 2, version_number: 2 })]
    const wrapper = mountDialogs(ctx)

    const compareBtn = elButtons(wrapper).find((btn) => btn.text() === '对比')!
    expect(compareBtn.props('disabled')).toBe(true)
    expect(dialogByTitle(wrapper, '版本历史')!.text()).toContain('已选择 0/2 个版本进行对比')
  })

  it('选中两行后启用对比按钮', async () => {
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [makeVersion({ id: 1 }), makeVersion({ id: 2, version_number: 2 })]
    const wrapper = mountDialogs(ctx)

    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [
      { id: 1, version_number: 1 },
      { id: 2, version_number: 2 },
    ])
    await nextTick()

    expect(dialogByTitle(wrapper, '版本历史')!.text()).toContain('已选择 2/2 个版本进行对比')
    const compareBtn = elButtons(wrapper).find((btn) => btn.text() === '对比')!
    expect(compareBtn.props('disabled')).toBe(false)
  })

  it('选择超过两行时只保留最后两条', async () => {
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [
      makeVersion({ id: 1, version_number: 1 }),
      makeVersion({ id: 2, version_number: 2 }),
      makeVersion({ id: 3, version_number: 3 }),
    ]
    const wrapper = mountDialogs(ctx)

    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [
      { id: 1, version_number: 1 },
      { id: 2, version_number: 2 },
      { id: 3, version_number: 3 },
    ])
    await nextTick()

    expect(dialogByTitle(wrapper, '版本历史')!.text()).toContain('已选择 2/2 个版本进行对比')
  })

  it('完成对比后打开对比弹窗并透传差异数据', async () => {
    compareMock.mockResolvedValue({
      from_version: { version_number: 2 },
      to_version: { version_number: 5 },
      diff: [{ field: 'title' }],
      stepsDiff: { added: [], removed: [] },
    })
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [
      makeVersion({ id: 10, version_number: 5 }),
      makeVersion({ id: 11, version_number: 2 }),
    ]
    const wrapper = mountDialogs(ctx)

    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [
      { id: 10, version_number: 5 },
      { id: 11, version_number: 2 },
    ])
    await nextTick()
    await findButton(dialogByTitle(wrapper, '版本历史')!, '对比').trigger('click')
    await flushPromises()

    expect(compareMock).toHaveBeenCalledWith(12, 11, 10)
    const compareDialog = dialogByTitle(wrapper, '版本对比')!
    expect(compareDialog.text()).toContain('v2')
    expect(compareDialog.text()).toContain('v5')
    expect(wrapper.findComponent(CaseVersionDiffStub).props('diffData')).toEqual([
      { field: 'title' },
    ])
    expect(wrapper.findComponent(CaseVersionDiffStub).props('stepsDiff')).toEqual({
      added: [],
      removed: [],
    })
  })

  it('对比失败时提示错误并关闭对比弹窗', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    compareMock.mockRejectedValue(new Error('对比服务异常'))
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [makeVersion({ id: 1 }), makeVersion({ id: 2, version_number: 2 })]
    const wrapper = mountDialogs(ctx)

    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [
      { id: 1, version_number: 1 },
      { id: 2, version_number: 2 },
    ])
    await nextTick()
    await findButton(dialogByTitle(wrapper, '版本历史')!, '对比').trigger('click')
    await flushPromises()

    expect(messageMock.error).toHaveBeenCalledWith('对比服务异常')
    expect(dialogByTitle(wrapper, '版本对比')).toBeUndefined()
    expect(wrapper.findAll('.el-dialog')).toHaveLength(1)
    expect(errorSpy).toHaveBeenCalled()
    errorSpy.mockRestore()
  })

  it('非 Error 异常降级为默认提示文案', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    compareMock.mockRejectedValue('boom')
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [makeVersion({ id: 1 }), makeVersion({ id: 2, version_number: 2 })]
    const wrapper = mountDialogs(ctx)

    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [
      { id: 1, version_number: 1 },
      { id: 2, version_number: 2 },
    ])
    await nextTick()
    await findButton(dialogByTitle(wrapper, '版本历史')!, '对比').trigger('click')
    await flushPromises()

    expect(messageMock.error).toHaveBeenCalledWith('版本对比失败')
    errorSpy.mockRestore()
  })

  it('选中不足两个版本时点击对比给出警告且不发请求', async () => {
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [makeVersion({ id: 1 })]
    const wrapper = mountDialogs(ctx)

    wrapper
      .findComponent({ name: 'ElTable' })
      .vm.$emit('selection-change', [{ id: 1, version_number: 1 }])
    await nextTick()

    elButtons(wrapper)
      .find((btn) => btn.text() === '对比')!
      .vm.$emit('click', new MouseEvent('click'))
    await flushPromises()

    expect(messageMock.warning).toHaveBeenCalledWith('请选择两个版本进行对比')
    expect(compareMock).not.toHaveBeenCalled()
  })

  it('缺少 caseId 时直接返回且不发请求', async () => {
    const ctx = makeCtx()
    ctx.caseId.value = 0
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [makeVersion({ id: 1 }), makeVersion({ id: 2, version_number: 2 })]
    const wrapper = mountDialogs(ctx)

    wrapper.findComponent({ name: 'ElTable' }).vm.$emit('selection-change', [
      { id: 1, version_number: 1 },
      { id: 2, version_number: 2 },
    ])
    await nextTick()
    await findButton(dialogByTitle(wrapper, '版本历史')!, '对比').trigger('click')
    await flushPromises()

    expect(compareMock).not.toHaveBeenCalled()
    expect(dialogByTitle(wrapper, '版本对比')).toBeUndefined()
  })

  it('翻页触发重新拉取版本历史', async () => {
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [makeVersion()]
    ctx.versionTotal.value = 45
    const wrapper = mountDialogs(ctx)

    wrapper.findComponent({ name: 'ElPagination' }).vm.$emit('current-change', 3)
    await nextTick()

    expect(ctx.fetchVersionHistory).toHaveBeenCalledWith(3)
  })

  it('确认回滚把当前行交给处理器', async () => {
    const ctx = makeCtx()
    ctx.versionHistoryVisible.value = true
    ctx.versionList.value = [makeVersion({ id: 21, version_number: 7 })]
    const wrapper = mountDialogs(ctx)
    await flushPromises()

    wrapper
      .findAllComponents({ name: 'ElPopconfirm' })[0]
      .vm.$emit('confirm', new MouseEvent('click'))

    expect(ctx.handleRollback).toHaveBeenCalledWith(expect.objectContaining({ id: 21 }))
  })
})

describe('CaseDialogs — 添加元素定位', () => {
  it('输入框与单选组写回表单状态', async () => {
    const ctx = makeCtx()
    ctx.addLocatorVisible.value = true
    const wrapper = mountDialogs(ctx)

    const dialog = dialogByTitle(wrapper, '添加元素定位')!
    const inputs = dialog.findAll('input')
    await inputs[0].setValue('#username')
    await inputs[1].setValue('//input[@name="username"]')
    await inputs[2].setValue('100,200')
    dialog.findComponent({ name: 'ElRadioGroup' }).vm.$emit('update:modelValue', 'xpath')
    await nextTick()

    expect(ctx.addLocatorForm.value).toEqual({
      css_selector: '#username',
      xpath: '//input[@name="username"]',
      ai_coordinate: '100,200',
      locator_type: 'xpath',
    })
  })

  it('保存调用保存动作，取消直接关闭', async () => {
    const ctx = makeCtx()
    ctx.addLocatorVisible.value = true
    const wrapper = mountDialogs(ctx)

    await findButton(dialogByTitle(wrapper, '添加元素定位')!, '保存').trigger('click')
    expect(ctx.saveAddLocator).toHaveBeenCalledTimes(1)

    await findButton(dialogByTitle(wrapper, '添加元素定位')!, '取消').trigger('click')
    expect(ctx.addLocatorVisible.value).toBe(false)
  })
})

describe('CaseDialogs — 批量定位联动', () => {
  it('批量定位标志置位时打开子弹窗并复位', async () => {
    const ctx = makeCtx()
    const wrapper = mountDialogs(ctx)

    ctx.batchLocatorVisible.value = true
    await nextTick()

    const stub = wrapper.findComponent({ name: 'BatchLocatorDialog' })
    expect(stub.props('projectId')).toBe(7)
    expect(batchLocatorOpen.fn).toHaveBeenCalledWith([])
    expect(ctx.batchLocatorVisible.value).toBe(false)
  })

  it('无当前用例时项目号回退为 0 且不主动打开', () => {
    const ctx = makeCtx()
    ctx.caseItem.value = null
    const wrapper = mountDialogs(ctx)

    expect(wrapper.findComponent({ name: 'BatchLocatorDialog' }).props('projectId')).toBe(0)
    expect(batchLocatorOpen.fn).not.toHaveBeenCalled()
  })
})
