import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import FlowLayoutPanel from '../FlowLayoutPanel.vue'

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
  props: { type: { type: String, default: 'primary' }, size: { type: String, default: 'default' } },
  template: '<span class="el-tag" :data-type="type"><slot /></span>',
})

const ElAlertStub = defineComponent({
  name: 'ElAlert',
  props: { title: { type: String, default: '' }, type: { type: String, default: 'info' } },
  template: '<div class="el-alert" :data-type="type">{{ title }}</div>',
})

const stubs = {
  ElCollapseItem: ElCollapseItemStub,
  ElIcon: ElIconStub,
  ElTag: ElTagStub,
  ElAlert: ElAlertStub,
}

type PanelProps = {
  flows?: Array<{ from: string; to: string; trigger?: string }>
  navigation?: Array<{ screen: string; actions?: string[] }>
  layoutConstraints?: Array<{ priority: string; constraint: string; target?: string }>
  visualStyle?: Record<string, string>
  warnings?: string[]
}

function setup(props: PanelProps = {}) {
  const wrapper = mount(FlowLayoutPanel, { props: props as never, global: { stubs } })
  return { wrapper }
}

function blockNames(wrapper: ReturnType<typeof setup>['wrapper']) {
  return wrapper.findAll('.el-collapse-item').map((n) => n.attributes('data-name'))
}

describe('FlowLayoutPanel — 跳转流程', () => {
  it('无 flows 与 navigation 时不渲染该分组', () => {
    const { wrapper } = setup({
      layoutConstraints: [{ priority: 'high', constraint: '固定宽度' }],
    })

    expect(blockNames(wrapper)).toEqual(['layout'])
  })

  it('仅 navigation 有数据时同样渲染分组', () => {
    const { wrapper } = setup({ navigation: [{ screen: '首页' }] })

    expect(blockNames(wrapper)).toEqual(['flows'])
  })

  it('按条目渲染 from/to 与触发方式', () => {
    const { wrapper } = setup({
      flows: [
        { from: '首页', to: '登录页', trigger: '点击登录' },
        { from: '登录页', to: '工作台' },
      ],
    })

    const items = wrapper.findAll('.flow-item')
    expect(items).toHaveLength(2)
    expect(items[0].find('.flow-from').text()).toBe('首页')
    expect(items[0].find('.flow-to').text()).toBe('登录页')
    expect(items[0].find('.el-tag').text()).toBe('点击登录')
    expect(items[1].find('.el-tag').exists()).toBe(false)
  })

  it('navigation 展示页面与操作列表，无操作时不渲染操作区', () => {
    const { wrapper } = setup({
      navigation: [{ screen: '首页', actions: ['点击搜索', '下拉刷新'] }, { screen: '设置页' }],
    })

    const navs = wrapper.findAll('.nav-item')
    expect(navs[0].find('.nav-screen').text()).toBe('首页')
    expect(navs[0].find('.nav-actions').text()).toBe('操作: 点击搜索, 下拉刷新')
    expect(navs[1].find('.nav-actions').exists()).toBe(false)
  })
})

describe('FlowLayoutPanel — 布局约束', () => {
  it('按优先级映射标签颜色并展示目标', () => {
    const { wrapper } = setup({
      layoutConstraints: [
        { priority: 'high', constraint: '卡片等宽', target: '商品卡' },
        { priority: 'medium', constraint: '间距 8px' },
        { priority: 'low', constraint: '圆角 4px' },
        { priority: 'unknown', constraint: '其他' },
      ],
    })

    const items = wrapper.findAll('.constraint-item')
    expect(items.map((i) => i.find('.priority-tag').attributes('data-type'))).toEqual([
      'danger',
      'warning',
      'info',
      'info',
    ])
    expect(items[0].find('.constraint-text').text()).toBe('卡片等宽')
    expect(items[0].find('.constraint-target').text()).toBe('目标: 商品卡')
    expect(items[1].find('.constraint-target').exists()).toBe(false)
  })

  it('无约束时不渲染分组', () => {
    const { wrapper } = setup({ flows: [{ from: 'A', to: 'B' }] })

    expect(blockNames(wrapper)).toEqual(['flows'])
  })
})

describe('FlowLayoutPanel — 视觉风格', () => {
  it('展示颜色色块与文案', () => {
    const { wrapper } = setup({
      visualStyle: {
        background_color: '#ffffff',
        theme_color: '#2563eb',
        border_radius_style: '大圆角',
        shadow_style: '轻阴影',
      },
    })

    const items = wrapper.findAll('.style-item')
    expect(items.map((i) => i.find('.style-label').text())).toEqual([
      '背景色',
      '主题色',
      '圆角风格',
      '阴影风格',
    ])
    expect(items[0].find('.style-value').text()).toBe('#ffffff')
    expect(items[0].find('.color-swatch').attributes('style')).toContain(
      'background-color: #ffffff'
    )
    expect(items[1].find('.color-swatch').attributes('style')).toContain(
      'background-color: #2563eb'
    )
    expect(items[2].find('.style-value').text()).toBe('大圆角')
    expect(items[3].find('.style-value').text()).toBe('轻阴影')
  })

  it('仅展示已提供的字段', () => {
    const { wrapper } = setup({ visualStyle: { theme_color: '#ff0000' } })

    const items = wrapper.findAll('.style-item')
    expect(items).toHaveLength(1)
    expect(items[0].find('.style-label').text()).toBe('主题色')
  })

  it('未提供 visualStyle 时不渲染分组', () => {
    const { wrapper } = setup({ flows: [{ from: 'A', to: 'B' }] })

    expect(blockNames(wrapper)).toEqual(['flows'])
  })
})

describe('FlowLayoutPanel — 警告信息', () => {
  it('渲染条数标签与全部警告文案', () => {
    const { wrapper } = setup({ warnings: ['页面缺少标题', '存在重复元素'] })

    const block = wrapper.find('[data-name="warnings"]')
    expect(block.find('.collapse-title').text()).toBe('警告信息2条')
    expect(block.findAll('.el-alert').map((a) => a.text())).toEqual([
      '页面缺少标题',
      '存在重复元素',
    ])
  })

  it('空数组不渲染分组', () => {
    const { wrapper } = setup({ warnings: [] })

    expect(blockNames(wrapper)).toEqual([])
  })
})
