import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'

const store = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/store/useGenerateStore', () => ({
  useGenerateStore: () => store.current,
}))

import GenerateCaseResultCard from '../GenerateCaseResultCard.vue'

const ElCardStub = defineComponent({
  name: 'ElCard',
  props: { shadow: { type: String, default: 'always' } },
  template:
    '<div class="el-card"><div class="el-card__header"><slot name="header" /></div><slot /></div>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: 'primary' }, size: { type: String, default: 'default' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    type: { type: String, default: '' },
    size: { type: String, default: 'default' },
    plain: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
  },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" :data-loading="loading" @click="$emit(\'click\', $event)"><slot /></button>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: { title: { type: String, default: '' }, type: { type: String, default: 'info' } },
  template:
    '<div class="el-alert" :data-type="type"><span class="alert-title">{{ title }}</span></div>',
})

const ElDescriptionsStub = defineComponent({
  name: 'ElDescriptions',
  props: { column: { type: Number, default: 1 }, border: { type: Boolean, default: false } },
  template: '<div class="el-descriptions"><slot /></div>',
})

const ElDescriptionsItemStub = defineComponent({
  name: 'ElDescriptionsItem',
  props: { label: { type: String, default: '' }, span: { type: Number, default: 1 } },
  template: '<div class="desc-item" :data-label="label"><slot /></div>',
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: {
    modelValue: { type: String, default: '' },
    type: { type: String, default: 'text' },
    rows: { type: Number, default: 2 },
    placeholder: { type: String, default: '' },
  },
  template:
    '<input class="el-input" :data-type="type" :value="modelValue" :placeholder="placeholder" />',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: { modelValue: { type: [Number, String], default: undefined } },
  template: '<div class="el-select"><slot /></div>',
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<div class="el-option" :data-value="value">{{ label }}</div>',
})

const ElRowStub = defineComponent({
  name: 'ElRow',
  props: { gutter: { type: Number, default: 0 } },
  template: '<div class="el-row"><slot /></div>',
})

const ElColStub = defineComponent({
  name: 'ElCol',
  props: { span: { type: Number, default: 24 } },
  template: '<div class="el-col"><slot /></div>',
})

const GenerateCaseNavBarStub = defineComponent({
  name: 'GenerateCaseNavBar',
  template: '<div class="nav-bar-stub"></div>',
})

const GenerateCaseStepSectionStub = defineComponent({
  name: 'GenerateCaseStepSection',
  template: '<div class="step-section-stub"></div>',
})

const stubs = {
  ElCard: ElCardStub,
  ElTag: ElTagStub,
  ElButton: ElButtonStub,
  ElIcon: ElIconStub,
  ElAlert: ElAlertStub,
  ElDescriptions: ElDescriptionsStub,
  ElDescriptionsItem: ElDescriptionsItemStub,
  ElInput: ElInputStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElRow: ElRowStub,
  ElCol: ElColStub,
  GenerateCaseNavBar: GenerateCaseNavBarStub,
  GenerateCaseStepSection: GenerateCaseStepSectionStub,
}

type CaseData = Record<string, unknown>

const baseCase: CaseData = {
  title: '登录失败锁定',
  test_point_label: '登录/账号锁定',
  case_type: 'ui_automation',
  priority: 1,
  module: '登录',
  precondition: '用户已注册',
  expected_result: '  账号被锁定  ',
  test_data: {
    account: { username: 'test', password: '123456' },
    invalid: { username: 'x' },
  },
}

type StoreOverrides = {
  cases?: CaseData[]
  generating?: boolean
  index?: number
  editing?: boolean
  saving?: boolean
  viewingCase?: CaseData | null
  editingCase?: Record<string, unknown>
}

function createStore(overrides: StoreOverrides = {}) {
  const cases = overrides.cases ?? [baseCase]
  return {
    generatedCases: cases,
    generating: overrides.generating ?? false,
    currentCaseIndex: overrides.index ?? 0,
    isEditingResult: overrides.editing ?? false,
    saving: overrides.saving ?? false,
    viewingCase: overrides.viewingCase === undefined ? cases[0] : overrides.viewingCase,
    editingCase: reactive(
      overrides.editingCase ?? {
        title: '登录失败锁定',
        module: '登录',
        case_type: 'ui_automation',
        priority: 1,
        precondition: '用户已注册',
        expected_result: '账号被锁定',
      }
    ),
    currentStep: 2,
    startEditResult: vi.fn(),
    handleSaveCase: vi.fn(),
    cancelEditResult: vi.fn(),
    handleDeleteCase: vi.fn(),
    handleRegenerateCase: vi.fn(),
    getTypeTagType: () => 'primary',
    getTypeLabel: (type: string) =>
      ({ ui_automation: 'UI自动化', manual: '手工测试' })[type] ?? type,
    getPriorityTagType: () => 'danger',
    getPriorityLabel: (priority: number) => ({ 1: '高', 2: '中', 3: '低' })[priority] ?? '低',
    getDataTypeLabel: (key: string) => ({ account: '正常账号', invalid: '异常账号' })[key] ?? key,
    cleanExpectedResult: (text: string) => text.trim(),
  }
}

function setup(overrides: StoreOverrides = {}) {
  const fake = createStore(overrides)
  store.current = fake

  const wrapper = mount(GenerateCaseResultCard, { global: { stubs } })
  return { fake, wrapper }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('GenerateCaseResultCard — 展示条件与头部', () => {
  it('无生成结果或生成中不渲染', () => {
    expect(setup({ cases: [] }).wrapper.find('.result-card').exists()).toBe(false)
    expect(setup({ generating: true }).wrapper.find('.result-card').exists()).toBe(false)
  })

  it('展示当前序号与总数', () => {
    const { wrapper } = setup({ cases: [baseCase, baseCase, baseCase], index: 1 })

    expect(wrapper.find('.el-card__header .el-tag').text()).toBe('2/3')
  })

  it('操作按钮分别转发编辑、删除与重新生成', async () => {
    const { fake, wrapper } = setup({ index: 2 })
    const buttons = wrapper.findAll('.result-actions .el-button')

    expect(buttons.map((b) => b.text())).toEqual(['编辑', '删除', '重新生成'])

    for (const button of buttons) {
      await button.trigger('click')
    }

    expect(fake.startEditResult).toHaveBeenCalledTimes(1)
    expect(fake.handleDeleteCase).toHaveBeenCalledWith(2)
    expect(fake.handleRegenerateCase).toHaveBeenCalledWith(2)
  })

  it('编辑态展示保存与取消并隐藏其余按钮', async () => {
    const { fake, wrapper } = setup({ editing: true, saving: true })
    const buttons = wrapper.findAll('.result-actions .el-button')

    expect(buttons.map((b) => b.text())).toEqual(['保存修改', '取消'])
    expect(buttons[0].attributes('data-loading')).toBe('true')

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    expect(fake.handleSaveCase).toHaveBeenCalledTimes(1)
    expect(fake.cancelEditResult).toHaveBeenCalledTimes(1)
  })
})

describe('GenerateCaseResultCard — 只读详情', () => {
  it('渲染概述信息与用例字段', () => {
    const { wrapper } = setup()

    const labels = wrapper.findAll('.desc-item').map((i) => i.attributes('data-label'))
    expect(labels).toEqual(['用例名称', '关联测试点', '用例类型', '优先级', '模块', '前置条件'])

    const nameItem = wrapper.findAll('.desc-item')[0]
    expect(nameItem.text()).toBe('登录失败锁定')
    const typeTag = wrapper.findAll('.desc-item')[2].find('.el-tag')
    expect(typeTag.text()).toBe('UI自动化')
    expect(typeTag.attributes('data-type')).toBe('primary')
    const priorityTag = wrapper.findAll('.desc-item')[3].find('.el-tag')
    expect(priorityTag.text()).toBe('高')
  })

  it('缺失字段回退为占位符', () => {
    const { wrapper } = setup({
      cases: [{ title: '仅标题' }],
      viewingCase: { title: '仅标题' },
    })

    const items = wrapper.findAll('.desc-item')
    expect(items[1].text()).toBe('-')
    expect(items[4].text()).toBe('-')
    expect(items[5].text()).toBe('-')
  })

  it('错误结果时展示失败提示', () => {
    const { wrapper } = setup({ viewingCase: { ...baseCase, _error: '模型超时' } })

    const alert = wrapper.find('.el-alert')
    expect(alert.attributes('data-type')).toBe('error')
    expect(alert.find('.alert-title').text()).toBe('生成失败: 模型超时')
  })

  it.each([
    ['added', 'success', '查漏·新增'],
    ['modified', 'warning', '补缺·修正'],
    ['deprecated', 'danger', '去冗·废弃'],
  ])('评审结果 %s 展示 %s/%s', (changeType, tagType, label) => {
    const { wrapper } = setup({
      viewingCase: { ...baseCase, ai_change_type: changeType, parent_case_id: 88 },
    })

    const item = wrapper
      .findAll('.desc-item')
      .find((i) => i.attributes('data-label') === '评审结果')!
    expect(item.find('.el-tag').text()).toBe(label)
    expect(item.find('.el-tag').attributes('data-type')).toBe(tagType)
    expect(item.text()).toContain('源用例 #88')
  })

  it('无评审结果时不渲染该字段', () => {
    const { wrapper } = setup()

    expect(
      wrapper.findAll('.desc-item').some((i) => i.attributes('data-label') === '评审结果')
    ).toBe(false)
  })

  it('测试数据按分组渲染卡片', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.test-data-section').exists()).toBe(true)
    expect(wrapper.findAll('.test-data-title').map((t) => t.text())).toEqual([
      '正常账号',
      '异常账号',
    ])
    expect(wrapper.findAll('.test-data-item').map((i) => i.text())).toEqual([
      'username: test',
      'password: 123456',
      'username: x',
    ])
  })

  it('无测试数据时不渲染数据区', () => {
    const { wrapper } = setup({ viewingCase: { ...baseCase, test_data: {} } })

    expect(wrapper.find('.test-data-section').exists()).toBe(false)
  })

  it('总体预期结果展示清洗后的文本', () => {
    const { wrapper } = setup()

    const alerts = wrapper.findAll('.el-alert')
    const alert = alerts[alerts.length - 1]
    expect(alert.find('.alert-title').text()).toBe('账号被锁定')
    expect(alert.attributes('data-type')).toBe('success')
  })
})

describe('GenerateCaseResultCard — 编辑态与底部操作', () => {
  it('编辑态渲染可编辑字段', () => {
    const { wrapper } = setup({ editing: true })

    const fields = wrapper.findAll('.edit-field label').map((l) => l.text())
    expect(fields).toEqual(['用例名称 *', '模块', '用例类型', '优先级', '前置条件'])

    const inputs = wrapper.findAll('.edit-field .el-input')
    expect(inputs[0].attributes('value')).toBe('登录失败锁定')
    expect(wrapper.findAll('.edit-field .el-option').map((o) => o.text())).toEqual([
      'UI自动化',
      '手工测试',
      'API自动化',
      '性能测试',
      '安全测试',
      'P0-高',
      'P2-中',
      'P3-低',
    ])
  })

  it('编辑态展示预期结果输入框且隐藏只读区', () => {
    const { wrapper } = setup({ editing: true })

    const textarea = wrapper.find('.expected-result-section .el-input')
    expect(textarea.attributes('data-type')).toBe('textarea')
    expect(wrapper.find('.el-descriptions').exists()).toBe(false)
    expect(wrapper.find('.test-data-section').exists()).toBe(false)
  })

  it('底部按钮支持调整配置与完成', async () => {
    const { fake, wrapper } = setup()
    const buttons = wrapper.findAll('.result-actions-bottom .el-button')

    expect(buttons.map((b) => b.text())).toEqual(['调整配置重新生成', '完成'])

    await buttons[0].trigger('click')
    expect(fake.currentStep).toBe(1)

    await buttons[1].trigger('click')
    expect(wrapper.emitted('finish')).toHaveLength(1)
  })

  it('编辑态隐藏底部操作区但仍渲染导航与步骤区块', () => {
    const { wrapper } = setup({ editing: true })

    expect(wrapper.find('.result-actions-bottom').exists()).toBe(false)
    expect(wrapper.find('.nav-bar-stub').exists()).toBe(true)
    expect(wrapper.find('.step-section-stub').exists()).toBe(true)
  })
})
