import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import ElementDetailPanel from '../ElementDetailPanel.vue'

const ElCollapseItemStub = defineComponent({
  name: 'ElCollapseItem',
  props: { name: { type: String, default: '' } },
  template: `<div class="el-collapse-item" :data-name="name">
    <div class="collapse-item-title"><slot name="title" /></div>
    <div class="collapse-item-body"><slot /></div>
  </div>`,
})

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: {
    type: { type: String, default: 'primary' },
    size: { type: String, default: 'default' },
  },
  template: '<span class="el-tag" :data-type="type" :data-size="size"><slot /></span>',
})

const stubs = {
  ElCollapseItem: ElCollapseItemStub,
  ElIcon: ElIconStub,
  ElTag: ElTagStub,
}

type ElementData = {
  type: string
  label: string
  description?: string
  semantic_hint?: string
  interactive?: boolean
  state?: string
  position?: { x: number; y: number; width?: number; height?: number }
}

function setup(elements: ElementData[] = []) {
  const wrapper = mount(ElementDetailPanel, {
    props: { elements: elements as never },
    global: { stubs },
  })
  return { wrapper }
}

describe('ElementDetailPanel — 折叠标题', () => {
  it('展示标题文案与元素总数', () => {
    const { wrapper } = setup([{ type: 'button', label: '提交' }])

    expect(wrapper.find('.el-collapse-item').attributes('data-name')).toBe('elements')
    expect(wrapper.find('.collapse-title').text()).toBe('元素详情1项')
  })

  it('无元素时计数为 0 且列表为空', () => {
    const { wrapper } = setup()

    expect(wrapper.find('.collapse-title').text()).toBe('元素详情0项')
    expect(wrapper.findAll('.element-item')).toHaveLength(0)
  })
})

describe('ElementDetailPanel — 排序', () => {
  it('按 y 升序、同 y 再按 x 升序排列', () => {
    const { wrapper } = setup([
      { type: 'button', label: 'C', position: { x: 10, y: 100 } },
      { type: 'button', label: 'B', position: { x: 200, y: 10 } },
      { type: 'button', label: 'A', position: { x: 100, y: 10 } },
    ])

    expect(wrapper.findAll('.element-label').map((n) => n.text())).toEqual(['A', 'B', 'C'])
  })

  it('缺失 position 的元素按 (0,0) 处理排在最前', () => {
    const { wrapper } = setup([
      { type: 'text', label: '有坐标', position: { x: 0, y: 5 } },
      { type: 'text', label: '无坐标' },
    ])

    expect(wrapper.findAll('.element-label').map((n) => n.text())).toEqual(['无坐标', '有坐标'])
  })

  it('排序不修改传入数组顺序', () => {
    const elements: ElementData[] = [
      { type: 'button', label: '后', position: { x: 0, y: 20 } },
      { type: 'button', label: '前', position: { x: 0, y: 10 } },
    ]
    const { wrapper } = setup(elements)

    expect(wrapper.findAll('.element-label').map((n) => n.text())).toEqual(['前', '后'])
    expect(elements.map((e) => e.label)).toEqual(['后', '前'])
  })
})

describe('ElementDetailPanel — 类型标签', () => {
  it.each([
    ['button', 'primary'],
    ['input', 'warning'],
    ['text', 'info'],
    ['image', 'success'],
    ['video', 'danger'],
    ['form', 'primary'],
  ])('类型 %s 使用 %s 色', (type, color) => {
    const { wrapper } = setup([{ type, label: type }])

    expect(wrapper.find('.element-type-tag').attributes('data-type')).toBe(color)
    expect(wrapper.find('.element-type-tag').text()).toBe(type)
  })

  it('未知类型回退为 info', () => {
    const { wrapper } = setup([{ type: 'unknown_widget', label: 'x' }])

    expect(wrapper.find('.element-type-tag').attributes('data-type')).toBe('info')
  })

  it('语义提示作为独立标签展示', () => {
    const { wrapper } = setup([{ type: 'button', label: '登录', semantic_hint: '提交登录表单' }])

    const tags = wrapper.findAll('.element-main .el-tag')
    expect(tags).toHaveLength(2)
    expect(tags[1].text()).toBe('提交登录表单')
  })
})

describe('ElementDetailPanel — 元信息', () => {
  it('描述、位置、尺寸、可交互与状态一并展示', () => {
    const { wrapper } = setup([
      {
        type: 'button',
        label: '登录',
        description: '主按钮',
        position: { x: 12, y: 34, width: 120, height: 40 },
        interactive: true,
        state: 'disabled',
      },
    ])

    const meta = wrapper.find('.element-meta')
    expect(meta.find('.element-desc').text()).toBe('主按钮')
    expect(meta.find('.element-position').text().replace(/\s+/g, ' ').trim()).toBe(
      '位置: (12, 34) 尺寸: 120x40'
    )
    expect(meta.findAll('.el-tag').map((t) => t.text())).toEqual(['可交互', 'disabled'])
    expect(meta.findAll('.el-tag').map((t) => t.attributes('data-type'))).toEqual([
      'success',
      'warning',
    ])
  })

  it('缺少 width 时不展示尺寸片段', () => {
    const { wrapper } = setup([
      { type: 'text', label: 'x', description: '说明', position: { x: 1, y: 2 } },
    ])

    expect(wrapper.find('.element-position').text().replace(/\s+/g, ' ').trim()).toBe(
      '位置: (1, 2)'
    )
  })

  it('仅当存在描述时才渲染元信息行', () => {
    const { wrapper } = setup([
      { type: 'button', label: '无描述', position: { x: 1, y: 1 }, interactive: true },
    ])

    expect(wrapper.find('.element-meta').exists()).toBe(false)
  })
})
