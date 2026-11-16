import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import CaseVersionDiff from '../CaseVersionDiff.vue'
import type { FieldDiff, StepDiff } from '@/api/case/types'

const ElDescriptionsStub = defineComponent({
  name: 'ElDescriptions',
  props: { title: { type: String, default: '' } },
  template: '<div class="el-descriptions"><h4 v-if="title">{{ title }}</h4><slot /></div>',
})

const ElDescriptionsItemStub = defineComponent({
  name: 'ElDescriptionsItem',
  props: {
    label: { type: String, default: '' },
    labelClassName: { type: String, default: '' },
  },
  template:
    '<div class="el-descriptions-item" :data-label="label" :data-label-class="labelClassName"><slot /></div>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: { type: { type: String, default: '' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElEmptyStub = defineComponent({
  name: 'ElEmpty',
  props: { description: { type: String, default: '' } },
  template: '<div class="el-empty">{{ description }}</div>',
})

const stubs = {
  ElDescriptions: ElDescriptionsStub,
  ElDescriptionsItem: ElDescriptionsItemStub,
  ElTag: ElTagStub,
  ElIcon: ElIconStub,
  ElEmpty: ElEmptyStub,
}

function fieldDiff(partial: Partial<FieldDiff>): FieldDiff {
  return { old: '', new: '', changeType: 'modified', ...partial } as FieldDiff
}

function mountDiff(diffData: Record<string, FieldDiff> = {}, stepsDiff: StepDiff[] = []) {
  return mount(CaseVersionDiff, {
    props: { diffData, stepsDiff },
    global: { stubs },
  })
}

describe('CaseVersionDiff — 字段变更', () => {
  it('渲染字段中文名、旧值与新值', () => {
    const wrapper = mountDiff({
      title: fieldDiff({ old: '旧标题', new: '新标题', changeType: 'modified' }),
    })

    const item = wrapper.find('.el-descriptions-item')
    expect(item.attributes('data-label')).toBe('标题')
    expect(item.find('.diff-old').text()).toBe('旧标题')
    expect(item.find('.diff-new').text()).toBe('新标题')
    expect(item.find('.el-tag').text()).toBe('修改')
    expect(item.find('.el-tag').attributes('data-type')).toBe('warning')
  })

  it('未知字段回退为原始字段名', () => {
    const wrapper = mountDiff({ unknown_field: fieldDiff({ old: 'a', new: 'b' }) })

    expect(wrapper.find('.el-descriptions-item').attributes('data-label')).toBe('unknown_field')
  })

  it.each([
    ['added', '新增', 'success'],
    ['deleted', '删除', 'danger'],
    ['modified', '修改', 'warning'],
  ] as const)('changeType=%s 对应标签与底色类', (changeType, label, tagType) => {
    const wrapper = mountDiff({ title: fieldDiff({ old: 'a', new: 'b', changeType }) })

    expect(wrapper.find('.el-tag').text()).toBe(label)
    expect(wrapper.find('.el-tag').attributes('data-type')).toBe(tagType)
    expect(wrapper.find('.diff-old').classes()).toContain(`value-${changeType}-bg`)
    expect(wrapper.find('.diff-new').classes()).toContain(`value-${changeType}-bg`)
    expect(wrapper.find('.el-descriptions-item').attributes('data-label-class')).toBe(
      `diff-label-${changeType}`
    )
  })

  it('空值统一展示为 -', () => {
    const wrapper = mountDiff({
      title: fieldDiff({ old: null, new: undefined as unknown as string }),
      module: fieldDiff({ old: '', new: '模块A' }),
    })

    const items = wrapper.findAll('.el-descriptions-item')
    expect(items[0].find('.diff-old').text()).toBe('-')
    expect(items[0].find('.diff-new').text()).toBe('-')
    expect(items[1].find('.diff-old').text()).toBe('-')
  })

  it('对象值格式化为 JSON，数值转为字符串', () => {
    const wrapper = mountDiff({
      exec_script: fieldDiff({ old: { a: 1 }, new: 42 }),
    })

    const item = wrapper.find('.el-descriptions-item')
    expect(item.find('.diff-old').text()).toContain('"a": 1')
    expect(item.find('.diff-new').text()).toBe('42')
  })
})

describe('CaseVersionDiff — 步骤变更', () => {
  it('渲染步骤卡片与字段中文名', () => {
    const wrapper = mountDiff({}, [
      {
        stepNumber: 2,
        fields: {
          action: fieldDiff({ old: '点击A', new: '点击B', changeType: 'modified' }),
          param: fieldDiff({ old: '', new: 'p=1', changeType: 'added' }),
        },
      },
    ] as unknown as StepDiff[])

    expect(wrapper.find('.section-title').text()).toBe('步骤变更')
    expect(wrapper.find('.step-diff-header .el-tag').text()).toBe('步骤 2')

    const items = wrapper.findAll('.step-diff-card .el-descriptions-item')
    expect(items.map((i) => i.attributes('data-label'))).toEqual(['操作', '参数'])
    expect(items[0].find('.diff-new').text()).toBe('点击B')
    expect(items[1].find('.el-tag').text()).toBe('新增')
  })

  it('仅步骤变更时不渲染字段变更区块', () => {
    const wrapper = mountDiff({}, [
      { stepNumber: 1, fields: { action: fieldDiff({ old: 'a', new: 'b' }) } },
    ] as unknown as StepDiff[])

    expect(wrapper.find('.el-descriptions h4').exists()).toBe(false)
    expect(wrapper.find('.step-diff-card').exists()).toBe(true)
  })
})

describe('CaseVersionDiff — 空态', () => {
  it('字段与步骤均无变更时展示空态', () => {
    const wrapper = mountDiff({}, [])

    expect(wrapper.find('.diff-section').exists()).toBe(false)
    expect(wrapper.find('.el-empty').text()).toBe('两个版本之间无差异')
  })

  it('仅有字段变更时不展示空态', () => {
    const wrapper = mountDiff({ priority: fieldDiff({ old: 1, new: 2, changeType: 'modified' }) })

    expect(wrapper.find('.el-empty').exists()).toBe(false)
    expect(wrapper.find('.el-descriptions h4').text()).toBe('字段变更')
  })
})
