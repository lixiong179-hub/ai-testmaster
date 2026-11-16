import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent } from 'vue'

vi.mock('@/api/case', () => ({
  caseApi: {
    getSupplementData: vi.fn(),
    supplementCase: vi.fn(),
  },
}))

import { caseApi } from '@/api/case'
import SupplementForm from '../SupplementForm.vue'

const getDataMock = vi.mocked(caseApi.getSupplementData)
const supplementMock = vi.mocked(caseApi.supplementCase)

const ElTabsStub = defineComponent({
  name: 'ElTabs',
  template: '<div class="el-tabs"><slot /></div>',
})

const ElTabPaneStub = defineComponent({
  name: 'ElTabPane',
  props: { label: { type: String, default: '' }, name: { type: String, default: '' } },
  template: '<div class="el-tab-pane" :data-name="name"><slot /></div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: {
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
  },
  emits: ['click'],
  template: `<button class="el-button" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
})

const ElInputStub = defineComponent({
  name: 'ElInput',
  props: { modelValue: { type: String, default: '' }, placeholder: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<input class="el-input" :value="modelValue" :placeholder="placeholder" @input="$emit('update:modelValue', $event.target.value)" />`,
})

const ElCheckboxStub = defineComponent({
  name: 'ElCheckbox',
  props: { modelValue: { type: Boolean, default: false } },
  emits: ['change'],
  template: `<input type="checkbox" class="el-checkbox" :checked="modelValue" @change="$emit('change', $event.target.checked)" />`,
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const ElTableStub = defineComponent({
  name: 'ElTable',
  props: { data: { type: Array, default: () => [] } },
  template: '<table class="el-table"><slot /></table>',
})

const ElTableColumnStub = defineComponent({
  name: 'ElTableColumn',
  props: { prop: { type: String, default: '' }, label: { type: String, default: '' } },
  template: '<col class="el-table-column" />',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const stubs = {
  ElTabs: ElTabsStub,
  ElTabPane: ElTabPaneStub,
  ElButton: ElButtonStub,
  ElInput: ElInputStub,
  ElCheckbox: ElCheckboxStub,
  ElEmpty: ElEmptyStub,
  ElTable: ElTableStub,
  ElTableColumn: ElTableColumnStub,
  ElIcon: ElIconStub,
}

function mountForm() {
  return mount(SupplementForm, {
    props: { caseId: 1, projectId: 2 },
    global: { stubs },
  })
}

async function mountWithData() {
  const wrapper = mountForm()
  await flushPromises()
  return wrapper
}

const buttonByText = (wrapper: ReturnType<typeof mountForm>, text: string) =>
  wrapper.findAll('button').find((b) => b.text() === text)

describe('SupplementForm — 推断能力', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getDataMock.mockResolvedValue({
      test_case: { id: 1 },
      inferred_capabilities: [
        { name: '登录能力', description: '支持账号密码登录' },
        { name: '支付能力', description: '支持扫码支付' },
      ],
      questions: [{ question: '是否需要多语言？' }],
    } as never)
  })

  it('加载后渲染能力条目与统计文案', async () => {
    const wrapper = await mountWithData()

    expect(getDataMock).toHaveBeenCalledWith(1)
    expect(wrapper.findAll('.capability-item')).toHaveLength(2)
    expect(wrapper.text()).toContain('登录能力')
    expect(wrapper.text()).toContain('支持扫码支付')
    expect(wrapper.find('.toolbar-stat').text()).toBe('共 2 项，已选 0 项')
  })

  it('全选与清空同步统计与选中样式', async () => {
    const wrapper = await mountWithData()

    await buttonByText(wrapper, '全选')!.trigger('click')
    expect(wrapper.find('.toolbar-stat').text()).toBe('共 2 项，已选 2 项')
    expect(wrapper.findAll('.capability-item.selected')).toHaveLength(2)

    await buttonByText(wrapper, '清空')!.trigger('click')
    expect(wrapper.find('.toolbar-stat').text()).toBe('共 2 项，已选 0 项')
    expect(wrapper.findAll('.capability-item.selected')).toHaveLength(0)
  })

  it('点击条目切换选中状态', async () => {
    const wrapper = await mountWithData()

    await wrapper.findAll('.capability-item')[1].trigger('click')
    expect(wrapper.findAll('.capability-item')[1].classes()).toContain('selected')

    await wrapper.findAll('.capability-item')[1].trigger('click')
    expect(wrapper.findAll('.capability-item')[1].classes()).not.toContain('selected')
  })

  it('无推断能力时展示空态', async () => {
    getDataMock.mockResolvedValue({
      test_case: { id: 1 },
      inferred_capabilities: [],
      questions: [],
    } as never)

    const wrapper = await mountWithData()

    expect(wrapper.find('.el-empty').text()).toBe('暂无推断能力')
  })
})

describe('SupplementForm — 自定义能力与问题', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getDataMock.mockResolvedValue({
      test_case: { id: 1 },
      inferred_capabilities: [],
      questions: [{ question: '是否需要多语言？' }],
    } as never)
  })

  it('添加与删除自定义能力', async () => {
    const wrapper = await mountWithData()

    await buttonByText(wrapper, '添加自定义能力')!.trigger('click')
    expect(wrapper.findAll('.custom-capability-item')).toHaveLength(1)

    const inputs = wrapper.findAll('.custom-capability-item .el-input')
    await inputs[0].setValue('导出能力')
    await inputs[1].setValue('支持导出 Excel')

    // 删除按钮无文字，使用选择器定位
    await wrapper.find('.custom-capability-item button').trigger('click')

    expect(wrapper.findAll('.custom-capability-item')).toHaveLength(0)
  })

  it('渲染补充问题序号与文本', async () => {
    const wrapper = await mountWithData()

    expect(wrapper.findAll('.question-item')).toHaveLength(1)
    expect(wrapper.find('.question-text').text()).toBe('1. 是否需要多语言？')
  })
})

describe('SupplementForm — 提交与结果', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getDataMock.mockResolvedValue({
      test_case: { id: 1 },
      inferred_capabilities: [{ name: '登录能力', description: '支持登录' }],
      questions: [{ question: '是否需要多语言？' }],
    } as never)
  })

  it('无任何补充内容时提交按钮禁用', async () => {
    const wrapper = await mountWithData()

    expect(buttonByText(wrapper, '提交补充')!.attributes('disabled')).toBeDefined()
  })

  it('选中能力后可提交，payload 只带已选项', async () => {
    supplementMock.mockResolvedValue({
      change_summary: [{ field: 'capabilities', old_value: '无', new_value: '登录能力' }],
    } as never)
    const wrapper = await mountWithData()

    await buttonByText(wrapper, '全选')!.trigger('click')
    await buttonByText(wrapper, '提交补充')!.trigger('click')
    await flushPromises()

    expect(supplementMock).toHaveBeenCalledWith(1, {
      project_id: 2,
      inferred_capabilities: [{ name: '登录能力', description: '支持登录' }],
      custom_capabilities: [],
      questions: [],
    })
  })

  it('提交后展示变更摘要', async () => {
    supplementMock.mockResolvedValue({
      change_summary: [{ field: '标题', old_value: '旧标题', new_value: '新标题' }],
    } as never)
    const wrapper = await mountWithData()

    await buttonByText(wrapper, '全选')!.trigger('click')
    await buttonByText(wrapper, '提交补充')!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.change-summary').exists()).toBe(true)
    expect(wrapper.find('.change-summary').text()).toContain('变更摘要')
    const table = wrapper.findComponent(ElTableStub)
    expect(table.props('data')).toEqual([
      { field: '标题', old_value: '旧标题', new_value: '新标题' },
    ])
  })

  it('取消按钮向外抛 cancel', async () => {
    const wrapper = await mountWithData()

    await buttonByText(wrapper, '取消')!.trigger('click')

    expect(wrapper.emitted('cancel')).toHaveLength(1)
  })
})
