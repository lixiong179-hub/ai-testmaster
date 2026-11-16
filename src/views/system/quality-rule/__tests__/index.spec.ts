import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, reactive, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useQualityRule', () => ({
  useQualityRule: () => state.current,
}))

import QualityRulePage from '../index.vue'

const actions = {
  handleProjectChange: vi.fn(),
  openEditDialog: vi.fn(),
  saveRule: vi.fn(),
}
const resetToDefault = vi.fn()

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
    <div class="el-dialog__footer"><slot name="footer" /></div>
  </div>`,
})

const stubs = { ElDialog: ElDialogStub }

function makeRule(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    rule_key: `rule.${id}`,
    default_value: '30',
    rule_value: '30',
    value_type: 'text',
    description: `规则 ${id}`,
    enum_options: null,
    ...over,
  }
}

const isDefaultValue = (row: { rule_value: unknown; default_value: unknown }) =>
  String(row.rule_value) === String(row.default_value)

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    loading: ref(false),
    rules: ref([
      makeRule(1),
      makeRule(2, { rule_value: '60', description: null }),
      makeRule(3, { value_type: 'boolean', default_value: false, rule_value: true }),
    ]),
    projects: ref([
      { id: 7, name: 'Alpha 项目' },
      { id: 8, name: 'Beta 项目' },
    ]),
    selectedProjectId: ref<number | undefined>(7),
    dialogVisible: ref(false),
    currentRule: ref<ReturnType<typeof makeRule> | null>(null),
    formRef: ref<unknown>(null),
    formData: reactive({
      rule_key: '',
      rule_value_str: '',
      rule_value_num: 0,
      rule_value_bool: false,
    }),
    formRules: {},
    formatRuleValue: (value: unknown) =>
      typeof value === 'boolean' ? (value ? '开启' : '关闭') : String(value ?? '-'),
    isDefaultValue,
    ...actions,
    resetToDefault,
    ...over,
  }
}

let ctx: Record<string, unknown>

async function mountPage(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  const wrapper = mount(QualityRulePage, { global: { stubs } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('质量规则页 — 列表', () => {
  it('渲染规则 key、默认值与当前值', async () => {
    const wrapper = await mountPage()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('rule.1')
    expect(rows[0].text()).toContain('30')
    // 布尔值走 formatRuleValue
    expect(rows[2].text()).toContain('开启')
    expect(rows[2].text()).toContain('关闭')
  })

  it('当前值非默认时高亮并展示已修改标签', async () => {
    const wrapper = await mountPage()

    const modifiedRow = wrapper.findAll('.el-table__row')[1]
    expect(modifiedRow.find('.value-modified').exists()).toBe(true)
    expect(modifiedRow.text()).toContain('已修改')

    const untouchedRow = wrapper.findAll('.el-table__row')[0]
    expect(untouchedRow.find('.value-modified').exists()).toBe(false)
    expect(untouchedRow.text()).not.toContain('已修改')
  })

  it('描述为空时展示占位符', async () => {
    const wrapper = await mountPage()

    expect(wrapper.findAll('.el-table__row')[1].text()).toContain('-')
  })

  it('点击编辑透传当前行', async () => {
    const wrapper = await mountPage()

    const editBtn = wrapper.findAll('.el-table__row')[1].findAll('.el-button')[0]
    await editBtn.trigger('click')

    expect(actions.openEditDialog).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }))
  })

  it('默认值行的恢复默认按钮禁用，已修改行可点击', async () => {
    const wrapper = await mountPage()

    const rows = wrapper.findAll('.el-table__row')
    const defaultBtn = rows[0].findAll('.el-button')[1]
    const modifiedBtn = rows[1].findAll('.el-button')[1]

    expect(defaultBtn.attributes('disabled')).toBeDefined()
    expect(modifiedBtn.attributes('disabled')).toBeUndefined()

    await modifiedBtn.trigger('click')
    expect(resetToDefault).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }))
  })

  it('未选择项目时提示先选项目', async () => {
    const wrapper = await mountPage({ selectedProjectId: ref<number | undefined>(undefined) })

    const texts = wrapper.findAll('.el-empty').map((node) => node.text())
    expect(texts.some((text) => text.includes('请先选择项目'))).toBe(true)
    expect(texts.some((text) => text.includes('暂无质量规则数据'))).toBe(false)
  })

  it('已选项目但无规则时展示暂无数据', async () => {
    const wrapper = await mountPage({ rules: ref([]) })

    const texts = wrapper.findAll('.el-empty').map((node) => node.text())
    expect(texts.some((text) => text.includes('暂无质量规则数据'))).toBe(true)
  })

  it('切换项目透传项目 ID', async () => {
    const wrapper = await mountPage()

    wrapper.findComponent({ name: 'ElSelect' }).vm.$emit('change', 8)

    expect(actions.handleProjectChange).toHaveBeenCalledWith(8)
  })
})

describe('质量规则页 — 编辑弹窗', () => {
  it('布尔类型渲染开关控件', async () => {
    const wrapper = await mountPage({
      dialogVisible: ref(true),
      currentRule: ref(makeRule(3, { value_type: 'boolean', default_value: false })),
    })

    expect(wrapper.findComponent({ name: 'ElSwitch' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ElInputNumber' }).exists()).toBe(false)
  })

  it('数字类型渲染数字输入框', async () => {
    const wrapper = await mountPage({
      dialogVisible: ref(true),
      currentRule: ref(makeRule(4, { value_type: 'number' })),
    })

    expect(wrapper.findComponent({ name: 'ElInputNumber' }).exists()).toBe(true)
  })

  it('枚举类型渲染下拉框', async () => {
    const wrapper = await mountPage({
      dialogVisible: ref(true),
      currentRule: ref(makeRule(5, { value_type: 'enum', enum_options: ['low', 'high'] })),
    })

    expect(wrapper.findComponent({ name: 'ElSelect' }).exists()).toBe(true)
  })

  it('文本类型渲染输入框并展示规则 key 与默认值', async () => {
    const wrapper = await mountPage({
      dialogVisible: ref(true),
      currentRule: ref(makeRule(1)),
      formData: reactive({
        rule_key: 'rule.1',
        rule_value_str: '30',
        rule_value_num: 0,
        rule_value_bool: false,
      }),
    })

    expect(wrapper.findComponent({ name: 'ElInputNumber' }).exists()).toBe(false)
    // 规则 key 与描述渲染在禁用输入框内，需读 value 而非文本
    const inputs = wrapper.findAll('.el-dialog__body input')
    expect((inputs[0].element as HTMLInputElement).value).toBe('rule.1')
    expect(wrapper.find('.el-dialog__body').text()).toContain('30')
  })

  it('表单实例通过 setFormRef 回写', async () => {
    await mountPage({ dialogVisible: ref(true), currentRule: ref(makeRule(1)) })

    expect((ctx.formRef as { value: unknown }).value).not.toBeNull()
  })

  it('保存与取消按钮分别触发保存、关闭弹窗', async () => {
    const wrapper = await mountPage({ dialogVisible: ref(true), currentRule: ref(makeRule(1)) })

    const footerButtons = wrapper.findAll('.dialog-footer .el-button')
    await footerButtons[0].trigger('click')
    expect((ctx.dialogVisible as { value: boolean }).value).toBe(false)

    ctx = makeCtx({ dialogVisible: ref(true), currentRule: ref(makeRule(1)) })
    state.current = ctx
    const reopened = mount(QualityRulePage, { global: { stubs } })
    await flushPromises()

    const saveBtn = reopened.findAll('.dialog-footer .el-button').find((n) => n.text() === '保存')!
    await saveBtn.trigger('click')
    expect(actions.saveRule).toHaveBeenCalledTimes(1)
  })
})
