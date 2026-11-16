import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, reactive } from 'vue'

const state = vi.hoisted(() => ({ current: null as Record<string, unknown> | null }))

vi.mock('@/composables/useTestPointExtract', () => ({
  useTestPointExtract: () => state.current,
}))

import Step1ProjectSelect from '../Step1ProjectSelect.vue'

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElSelectStub = defineComponent({
  name: 'ElSelect',
  props: {
    modelValue: { type: [Number, String], default: '' },
    placeholder: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'change'],
  template: `<select class="el-select" :data-placeholder="placeholder" :value="modelValue" @change="$emit('change', $event.target.value)"><slot /><slot name="prefix" /></select>`,
})

const ElOptionStub = defineComponent({
  name: 'ElOption',
  props: { label: { type: String, default: '' }, value: { type: [Number, String], default: '' } },
  template: '<option class="el-option" :value="value">{{ label }}</option>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { type: { type: String, default: '' } },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" @click="$emit('click')"><slot /></button>`,
})

const stubs = {
  ElIcon: ElIconStub,
  ElSelect: ElSelectStub,
  ElOption: ElOptionStub,
  ElTag: ElTagStub,
  ElButton: ElButtonStub,
}

function setup(projectId: number | '' = '', files: Array<Record<string, unknown>> = []) {
  const formData = reactive({ project_id: projectId })
  const ctx = {
    formData,
    projects: [
      { id: 1, name: '项目A' },
      { id: 2, name: '项目B' },
    ],
    files,
    selectedProjectInfo: projectId
      ? { id: projectId, name: projectId === 1 ? '项目A' : '项目B' }
      : null,
    handleProjectChange: vi.fn(),
    goToNextStep: vi.fn(),
    getResourceTypeCount: vi.fn(
      (type: string) => files.filter((f) => f.resource_type === type).length
    ),
  }
  state.current = ctx

  const wrapper = mount(Step1ProjectSelect, { global: { stubs } })
  return { ctx, formData, wrapper }
}

describe('Step1ProjectSelect — 未选择项目', () => {
  it('展示引导区、选择器与四步工作流', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.guide-title').text()).toBe('选择您的项目')
    expect(wrapper.find('.el-select').attributes('data-placeholder')).toBe('请搜索或选择项目')
    expect(wrapper.findAll('.wf-step').map((s) => s.text().replace(/\s+/g, ''))).toEqual([
      '1选择项目',
      '2上传需求',
      '3AI提取',
      '4校验结果',
    ])
    expect(wrapper.find('.project-selected-view').exists()).toBe(false)
  })

  it('按项目列表渲染可选项', () => {
    const { wrapper } = setup()

    expect(wrapper.findAll('.el-option').map((o) => o.text())).toEqual(['项目A', '项目B'])
  })

  it('切换项目触发 handleProjectChange', async () => {
    const { ctx, wrapper } = setup()

    await wrapper.find('.el-select').trigger('change')

    expect(ctx.handleProjectChange).toHaveBeenCalledTimes(1)
  })
})

describe('Step1ProjectSelect — 已选择项目', () => {
  const files = [
    { id: 1, resource_type: 'requirement' },
    { id: 2, resource_type: 'requirement' },
    { id: 3, resource_type: 'ui_mockup' },
    { id: 4, resource_type: 'api_doc' },
  ]

  it('展示项目名称、ID 与资源文件数', () => {
    const { wrapper } = setup(1, files)

    expect(wrapper.find('.project-name-large').text()).toBe('项目A')
    const tags = wrapper.findAll('.project-meta-tags .el-tag').map((t) => t.text())
    expect(tags).toEqual(['ID: 1', '4 个资源文件'])
  })

  it('按资源类型统计四类数量', () => {
    const { wrapper } = setup(1, files)

    const values = wrapper.findAll('.grid-value').map((v) => v.text())
    expect(values).toEqual(['4', '2', '1', '1'])
    expect(wrapper.findAll('.grid-label').map((l) => l.text())).toEqual([
      '资源文件',
      '需求文档',
      'UI原型',
      'API文档',
    ])
  })

  it('重新选择清空项目ID', async () => {
    const { formData, wrapper } = setup(1, files)

    await wrapper.findAll('.project-card-footer button')[0].trigger('click')

    expect(formData.project_id).toBe('')
    expect(wrapper.find('.project-selection-guide').exists()).toBe(true)
  })

  it('下一步触发 goToNextStep', async () => {
    const { ctx, wrapper } = setup(1, files)

    await wrapper.findAll('.project-card-footer button')[1].trigger('click')

    expect(ctx.goToNextStep).toHaveBeenCalledTimes(1)
    expect(wrapper.findAll('.project-card-footer button')[1].text()).toContain('下一步：选择需求')
  })
})
