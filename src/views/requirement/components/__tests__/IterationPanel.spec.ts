import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, inject, provide, reactive, ref } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/requirement/useResourceManage', () => ({
  useResourceManage: () => state.current,
  ITERATION_STATUS_OPTIONS: [
    { label: '草稿', value: 'draft' },
    { label: '进行中', value: 'in_progress' },
  ],
}))

import IterationPanel from '../IterationPanel.vue'

const actions = {
  handleAddIterationWrapper: vi.fn(),
  handleSelectIterationAndRefresh: vi.fn(),
  handleIterationCommandWrapper: vi.fn(),
  handleIterationSubmitWrapper: vi.fn(),
}

/** 复刻 el-dropdown 的 command 机制：item 点击后由父级 dropdown 派发 command 事件 */
const CommandKey = Symbol('dropdown-command')

const ElDropdownStub = defineComponent({
  name: 'ElDropdown',
  emits: ['command'],
  setup(_props, { slots, emit }) {
    provide(CommandKey, (command: string) => emit('command', command))
    return () => h('div', { class: 'el-dropdown' }, [slots.default?.(), slots.dropdown?.()])
  },
})
const ElDropdownMenuStub = defineComponent({
  name: 'ElDropdownMenu',
  template: '<div class="el-dropdown-menu"><slot /></div>',
})
const ElDropdownItemStub = defineComponent({
  name: 'ElDropdownItem',
  props: { command: { type: String, default: '' } },
  setup(props, { slots }) {
    const runCommand = inject<(command: string) => void>(CommandKey, () => {})
    return () =>
      h(
        'div',
        { class: 'el-dropdown-item', onClick: () => runCommand(props.command) },
        slots.default?.()
      )
  },
})

const ElDialogStub = defineComponent({
  name: 'ElDialog',
  props: { modelValue: { type: Boolean, default: false }, title: { type: String, default: '' } },
  emits: ['update:modelValue'],
  template: `<div class="el-dialog" v-if="modelValue" :data-title="title">
    <div class="el-dialog__body"><slot /></div>
    <div class="el-dialog__footer"><slot name="footer" /></div>
  </div>`,
})

const stubs = {
  ElDropdown: ElDropdownStub,
  ElDropdownMenu: ElDropdownMenuStub,
  ElDropdownItem: ElDropdownItemStub,
  ElDialog: ElDialogStub,
}

function makeIteration(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    name: `迭代 ${id}`,
    version: `v${id}.0`,
    status: 'draft',
    project_id: 7,
    ...over,
  }
}

function makeCtx(over: Record<string, unknown> = {}) {
  const iterations = over.iterations ?? [makeIteration(1), makeIteration(2)]
  return {
    resourceList: reactive({ filterForm: { project_id: over.projectId ?? 7 } }),
    safeIterationsArray: ref(iterations),
    iterationFormLocalRef: ref<unknown>(null),
    getIterationStats: (id: number) => ({
      files: id === 1 ? 2 : 0,
      prototypes: id === 1 ? 1 : 0,
    }),
    iterationManager: reactive({
      selectedIterationId: over.selectedIterationId ?? null,
      iterationDialogVisible: over.dialogVisible ?? false,
      iterationDialogMode: over.dialogMode ?? 'add',
      isSubmitting: over.isSubmitting ?? false,
      iterationFormData: { name: '', version: '', description: '', status: 'draft' },
      iterationFormRules: {},
      getIterationStatusType: () => 'info',
      getIterationStatusText: (status?: string) => (status === 'in_progress' ? '进行中' : '草稿'),
    }),
    ...actions,
    ...over,
  }
}

let ctx: Record<string, unknown>

async function mountPanel(over: Record<string, unknown> = {}) {
  ctx = makeCtx(over)
  state.current = ctx
  const wrapper = mount(IterationPanel, { global: { stubs } })
  await flushPromises()
  return wrapper
}

function cards(wrapper: Awaited<ReturnType<typeof mountPanel>>) {
  return wrapper.findAll('.iteration-card')
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('IterationPanel — 未选择项目', () => {
  it('新建按钮禁用并展示引导空态', async () => {
    const wrapper = await mountPanel({ projectId: 0, iterations: [] })

    const addBtn = wrapper.findAll('.el-button')[0]
    expect(addBtn.attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('请先选择一个项目')
    expect(wrapper.find('.iteration-list').exists()).toBe(false)
  })
})

describe('IterationPanel — 迭代列表', () => {
  it('渲染全部/未分类与迭代卡片', async () => {
    const wrapper = await mountPanel()

    const list = cards(wrapper)
    expect(list).toHaveLength(4)
    expect(list[0].text()).toContain('全部')
    expect(list[1].text()).toContain('迭代 1')
    expect(list[1].text()).toContain('v1.0')
    expect(list[1].text()).toContain('草稿')
    expect(list[3].text()).toContain('未分类')
    expect(list[3].text()).toContain('无迭代')
  })

  it('有文档与原型时展示统计，为 0 时隐藏', async () => {
    const wrapper = await mountPanel()

    const first = cards(wrapper)[1]
    expect(first.text()).toContain('2 个文档')
    expect(first.text()).toContain('1 个原型')

    const second = cards(wrapper)[2]
    expect(second.text()).not.toContain('个文档')
    expect(second.text()).not.toContain('个原型')
  })

  it('选中项与全部/未分类的高亮状态', async () => {
    const selected = await mountPanel({ selectedIterationId: 2 })
    const selectedCards = cards(selected)
    expect(selectedCards[0].classes()).not.toContain('active')
    expect(selectedCards[2].classes()).toContain('active')

    const allSelected = await mountPanel({ selectedIterationId: null })
    expect(cards(allSelected)[0].classes()).toContain('active')

    const noneCategory = await mountPanel({ selectedIterationId: 0 })
    expect(cards(noneCategory)[3].classes()).toContain('active')
  })

  it('点击卡片切换迭代（含全部与未分类）', async () => {
    const wrapper = await mountPanel()
    const list = cards(wrapper)

    await list[0].trigger('click')
    await list[1].trigger('click')
    await list[3].trigger('click')

    expect(actions.handleSelectIterationAndRefresh).toHaveBeenNthCalledWith(1, null)
    expect(actions.handleSelectIterationAndRefresh).toHaveBeenNthCalledWith(2, 1)
    expect(actions.handleSelectIterationAndRefresh).toHaveBeenNthCalledWith(3, 0)
  })

  it('新建迭代按钮在已选项目时可用', async () => {
    const wrapper = await mountPanel()

    await wrapper.findAll('.el-button')[0].trigger('click')

    expect(actions.handleAddIterationWrapper).toHaveBeenCalledTimes(1)
  })

  it('无迭代时展示引导并提供创建入口', async () => {
    const wrapper = await mountPanel({ iterations: [] })

    expect(wrapper.text()).toContain('该项目暂无迭代')
    const createBtn = wrapper
      .findAll('.el-button')
      .find((n) => n.text().includes('创建第一个迭代'))!
    await createBtn.trigger('click')

    expect(actions.handleAddIterationWrapper).toHaveBeenCalledTimes(1)
  })

  it('下拉命令透传操作类型与迭代', async () => {
    const wrapper = await mountPanel()

    const items = wrapper.findAll('.el-dropdown')[0].findAll('.el-dropdown-item')
    expect(items.map((node) => node.text())).toEqual(['编辑', '删除'])

    await items[0].trigger('click')

    expect(actions.handleIterationCommandWrapper).toHaveBeenCalledTimes(1)
    const [cmd, iteration] = actions.handleIterationCommandWrapper.mock.calls[0]
    expect(cmd).toBe('edit')
    expect(iteration).toMatchObject({ id: 1 })
  })
})

describe('IterationPanel — 迭代弹窗', () => {
  it('新建模式标题与表单 ref 回写', async () => {
    const wrapper = await mountPanel({ dialogVisible: true, dialogMode: 'add' })

    expect(wrapper.find('.el-dialog').attributes('data-title')).toBe('新建迭代')
    expect((ctx.iterationFormLocalRef as { value: unknown }).value).not.toBeNull()
  })

  it('编辑模式标题为编辑迭代', async () => {
    const wrapper = await mountPanel({ dialogVisible: true, dialogMode: 'edit' })

    expect(wrapper.find('.el-dialog').attributes('data-title')).toBe('编辑迭代')
  })

  it('提交中按钮进入 loading 态', async () => {
    const wrapper = await mountPanel({ dialogVisible: true, isSubmitting: true })

    const submitBtn = wrapper
      .findAll('.el-dialog__footer .el-button')
      .find((n) => n.text() === '确定')!
    expect(submitBtn.classes()).toContain('is-loading')
  })

  it('点击确定触发保存', async () => {
    const wrapper = await mountPanel({ dialogVisible: true })

    const submitBtn = wrapper
      .findAllComponents({ name: 'ElButton' })
      .find((btn) => btn.text() === '确定')!
    // ElButton 的 click 事件带 MouseEvent 校验，直接 emit 空参会被丢弃
    submitBtn.vm.$emit('click', new MouseEvent('click'))
    await flushPromises()

    expect(actions.handleIterationSubmitWrapper).toHaveBeenCalledTimes(1)
  })

  it('取消关闭弹窗', async () => {
    const wrapper = await mountPanel({ dialogVisible: true })

    const cancelBtn = wrapper
      .findAll('.el-dialog__footer .el-button')
      .find((n) => n.text() === '取消')!
    await cancelBtn.trigger('click')

    expect(
      (ctx.iterationManager as { iterationDialogVisible: boolean }).iterationDialogVisible
    ).toBe(false)
  })
})
