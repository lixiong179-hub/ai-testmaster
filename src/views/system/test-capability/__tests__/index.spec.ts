import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('../useTestCapability', () => ({
  useTestCapability: () => state.current,
}))

import TestCapabilityPage from '../index.vue'

const actions = {
  handleProjectChange: vi.fn(),
  openAddDialog: vi.fn(),
  saveCapability: vi.fn(),
}

const openEditDialog = vi.fn()
const deleteCapability = vi.fn()

const STATUS_OPTIONS = [
  { label: '启用', value: 'active' },
  { label: '停用', value: 'disabled' },
]

/** el-dialog 在 happy-dom 下不会渲染内容（依赖 teleport 与过渡），改用按 modelValue 渲染插槽的桩 */
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

function makeCapability(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    key: `cap-${id}`,
    title: `能力 ${id}`,
    description: null,
    status: 'active',
    created_at: '2026-11-16 08:00:00',
    ...over,
  }
}

function makeCtx(over: Record<string, unknown> = {}) {
  return {
    loading: ref(false),
    capabilities: ref([
      makeCapability(1),
      makeCapability(2, { description: '支付能力', status: 'disabled' }),
    ]),
    projects: ref([{ id: 7, name: 'Alpha 项目' }]),
    selectedProjectId: ref<number | undefined>(7),
    dialogVisible: ref(false),
    dialogTitle: ref('新增测试能力'),
    formRef: ref<unknown>(null),
    formData: ref({ key: '', title: '', description: '', status: 'active' }),
    formRules: { key: [{ required: true }] },
    STATUS_OPTIONS,
    getStatusTagType: (status: string) => (status === 'active' ? 'success' : 'info'),
    getStatusLabel: (status: string) => (status === 'active' ? '启用' : '停用'),
    ...actions,
    openEditDialog,
    deleteCapability,
    ...over,
  }
}

let ctx: Record<string, unknown>

function mountPage(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  return mount(TestCapabilityPage, { global: { stubs } })
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('测试能力管理页 — 列表渲染', () => {
  it('渲染能力列表：描述空值占位与状态标签', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('cap-1')
    expect(rows[0].text()).toContain('能力 1')
    expect(rows[0].text()).toContain('-')
    expect(rows[0].text()).toContain('启用')
    expect(rows[1].text()).toContain('支付能力')
    expect(rows[1].text()).toContain('停用')
  })

  it('未选择项目时提示先选项目，不提示无数据', async () => {
    const wrapper = mountPage({
      selectedProjectId: ref<number | undefined>(undefined),
      capabilities: ref([]),
    })
    await flushPromises()

    const emptyTexts = wrapper.findAll('.el-empty').map((node) => node.text())
    expect(emptyTexts.some((text) => text.includes('请先选择项目'))).toBe(true)
    expect(emptyTexts.some((text) => text.includes('暂无测试能力数据'))).toBe(false)
  })

  it('已选项目且无数据时展示暂无数据空态', async () => {
    const wrapper = mountPage({ capabilities: ref([]) })
    await flushPromises()

    const emptyTexts = wrapper.findAll('.el-empty').map((node) => node.text())
    expect(emptyTexts.some((text) => text.includes('暂无测试能力数据'))).toBe(true)
  })

  it('弹窗打开后表单实例完成 ref 绑定', () => {
    mountPage({ dialogVisible: ref(true) })

    expect((ctx.formRef as { value: unknown }).value).not.toBeNull()
  })
})

describe('测试能力管理页 — 交互', () => {
  it('点击新增触发 openAddDialog', async () => {
    const wrapper = mountPage()

    const addBtn = wrapper
      .findAll('.header-actions .el-button')
      .find((node) => node.text().includes('新增能力'))!
    await addBtn.trigger('click')

    expect(actions.openAddDialog).toHaveBeenCalledTimes(1)
  })

  it('行内编辑与删除透传当前行', async () => {
    const wrapper = mountPage()
    await flushPromises()

    const firstRow = wrapper.findAll('.el-table__row')[0]
    const buttons = firstRow.findAll('.el-button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    expect(openEditDialog).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
    expect(deleteCapability).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }))
  })

  it('切换项目透传项目 ID', () => {
    const wrapper = mountPage()

    wrapper.findComponent({ name: 'ElSelect' }).vm.$emit('change', 9)

    expect(actions.handleProjectChange).toHaveBeenCalledWith(9)
  })

  it('弹窗可见时渲染标题并支持保存', async () => {
    const wrapper = mountPage({ dialogVisible: ref(true), dialogTitle: ref('编辑测试能力') })
    await flushPromises()

    expect(wrapper.find('.el-dialog').attributes('data-title')).toBe('编辑测试能力')

    const saveBtn = wrapper.findAll('.el-button').find((node) => node.text().includes('保存'))!
    await saveBtn.trigger('click')

    expect(actions.saveCapability).toHaveBeenCalledTimes(1)
  })
})
