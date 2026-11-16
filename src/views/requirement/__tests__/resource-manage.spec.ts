import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, reactive, ref } from 'vue'

const mockCtx = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/requirement/useResourceManage', async () => {
  const constants =
    await vi.importActual<typeof import('@/constants/resource')>('@/constants/resource')
  return {
    provideResourceManage: () => mockCtx.current,
    RESOURCE_TYPE_OPTIONS: constants.RESOURCE_TYPE_OPTIONS,
  }
})

import ResourceManagePage from '../resource-manage.vue'

const ElCardStub = defineComponent({
  name: 'ElCard',
  template: '<div class="el-card"><slot /></div>',
})

const ElFormStub = defineComponent({
  name: 'ElForm',
  props: {
    inline: { type: Boolean, default: false },
    model: { type: Object, default: () => ({}) },
  },
  template: '<form class="el-form" :data-inline="inline"><slot /></form>',
})

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' } },
  template: '<div class="el-form-item" :data-label="label"><slot /></div>',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: [Number, String], default: '' },
    placeholder: { type: String, default: '' },
    clearable: { type: Boolean, default: false },
    filterable: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'change'],
  template: `<div class="el-select" :data-placeholder="placeholder" :data-filterable="filterable" @click="$emit('change', 'x')"><slot /></div>`,
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<div class="el-option" :data-value="value">{{ label }}</div>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { type: { type: String, default: '' } },
  emits: ['click'],
  template:
    '<button class="el-button" :data-type="type" @click="$emit(\'click\')"><slot /></button>',
})

const IterationPanelStub = defineComponent({
  name: 'IterationPanel',
  template: '<div class="iteration-panel-stub"></div>',
})

const ResourceTableStub = defineComponent({
  name: 'ResourceTable',
  template: '<div class="resource-table-stub"></div>',
})

const stubs = {
  ElCard: ElCardStub,
  ElForm: ElFormStub,
  ElFormItem: ElFormItemStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElButton: ElButtonStub,
  IterationPanel: IterationPanelStub,
  ResourceTable: ResourceTableStub,
}

function createCtx(projectId: number | '' = 1) {
  const resourceList = reactive({
    filterForm: reactive({ project_id: projectId, resource_type: '' }),
    handleSearch: vi.fn(),
    handleReset: vi.fn(),
  })
  const ctx = {
    resourceList,
    projects: ref([
      { id: 1, name: '项目A' },
      { id: 2, name: '项目B' },
    ]),
    handleReset: vi.fn(),
    init: vi.fn(),
    cleanup: vi.fn(),
  }
  mockCtx.current = ctx
  return ctx
}

function setup(projectId: number | '' = 1) {
  const ctx = createCtx(projectId)
  const wrapper = mount(ResourceManagePage, { global: { stubs } })
  return { ctx, wrapper }
}

describe('resource-manage — 筛选表单', () => {
  it('项目与类型下拉分别展示占位文案', () => {
    const { wrapper } = setup()

    const selects = wrapper.findAll('.el-select')
    expect(selects).toHaveLength(2)
    expect(selects[0].attributes('data-placeholder')).toBe('请先选择项目')
    expect(selects[0].attributes('data-filterable')).toBe('true')
    expect(selects[1].attributes('data-placeholder')).toBe('全部')
  })

  it('按项目列表渲染选项', () => {
    const { wrapper } = setup()

    const projectItem = wrapper.findAll('.el-form-item')[0]
    expect(projectItem.findAll('.el-option').map((o) => o.text())).toEqual(['项目A', '项目B'])
  })

  it('类型下拉按常量渲染 5 个选项', () => {
    const { wrapper } = setup()

    const typeItem = wrapper.findAll('.el-form-item')[1]
    expect(typeItem.findAll('.el-option').map((o) => o.text())).toEqual([
      '需求文档',
      'UI原型图',
      'API文档',
      '测试数据',
      '其他文件',
    ])
  })

  it('切换类型立即触发查询', async () => {
    const { ctx, wrapper } = setup()

    await wrapper.findAll('.el-select')[1].trigger('click')

    expect(ctx.resourceList.handleSearch).toHaveBeenCalledTimes(1)
  })
})

describe('resource-manage — 操作按钮', () => {
  it('查询按钮调用 handleSearch，重置按钮调用页面级 handleReset', async () => {
    const { ctx, wrapper } = setup()

    const formItems = wrapper.findAll('.el-form-item')
    const buttons = formItems[formItems.length - 1].findAll('.el-button')
    expect(buttons.map((b) => b.text())).toEqual(['查询', '重置'])
    expect(buttons[0].attributes('data-type')).toBe('primary')

    await buttons[0].trigger('click')
    await buttons[1].trigger('click')

    expect(ctx.resourceList.handleSearch).toHaveBeenCalledTimes(1)
    expect(ctx.handleReset).toHaveBeenCalledTimes(1)
    expect(ctx.resourceList.handleReset).not.toHaveBeenCalled()
  })
})

describe('resource-manage — 布局与生命周期', () => {
  it('渲染迭代面板与资源表格两个子区块', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.iteration-panel-stub').exists()).toBe(true)
    expect(wrapper.find('.resource-table-stub').exists()).toBe(true)
    expect(wrapper.find('.main-content').exists()).toBe(true)
  })

  it('挂载时初始化、卸载时清理', () => {
    const { ctx, wrapper } = setup()

    expect(ctx.init).toHaveBeenCalledTimes(1)
    expect(ctx.cleanup).not.toHaveBeenCalled()

    wrapper.unmount()

    expect(ctx.cleanup).toHaveBeenCalledTimes(1)
  })
})
