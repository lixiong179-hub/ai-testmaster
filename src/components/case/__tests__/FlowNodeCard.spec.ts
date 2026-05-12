import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import FlowNodeCard from '../FlowNodeCard.vue'

const ElTagStub = defineComponent({
  name: 'ElTag',
  props: ['type', 'size', 'effect', 'disabled'],
  template: `<span class="el-tag" :class="[type, { disabled }]"><slot /></span>`,
})

const ElDropdownStub = defineComponent({
  name: 'ElDropdown',
  props: ['trigger', 'disabled'],
  emits: ['command'],
  template: `<div class="el-dropdown" :class="{ disabled }"><slot /><slot name="dropdown" /></div>`,
})

const ElDropdownMenuStub = {
  name: 'ElDropdownMenu',
  template: '<div class="el-dropdown-menu"><slot /></div>',
}

const ElDropdownItemStub = {
  name: 'ElDropdownItem',
  props: ['command'],
  template: '<div class="el-dropdown-item"><slot /></div>',
}

const ElIconStub = {
  name: 'ElIcon',
  template: '<span class="el-icon"><slot /></span>',
}

const ElTooltipStub = {
  name: 'ElTooltip',
  props: ['content', 'placement', 'showAfter'],
  template: '<span class="el-tooltip"><slot /></span>',
}

const HandleStub = defineComponent({
  name: 'Handle',
  props: ['type', 'position'],
  template: '<div class="handle" />',
})

const stubs = {
  ElTag: ElTagStub,
  ElDropdown: ElDropdownStub,
  ElDropdownMenu: ElDropdownMenuStub,
  ElDropdownItem: ElDropdownItemStub,
  ElIcon: ElIconStub,
  ElTooltip: ElTooltipStub,
  Handle: HandleStub,
}

const baseData = {
  screen_id: 1,
  screen_name: '登录页',
  summary: '用户登录入口',
  flow_type: 'main' as const,
  image_url: '',
  element_count: 5,
}

describe('FlowNodeCard', () => {
  const mountCard = (props: Record<string, unknown> = {}) =>
    mount(FlowNodeCard, {
      props: {
        data: baseData,
        ...props,
      },
      global: { stubs },
    })

  describe('display mode', () => {
    it('should render full card with image in edit mode (default)', () => {
      const wrapper = mountCard()
      expect(wrapper.find('.node-image').exists()).toBe(true)
      expect(wrapper.find('.node-footer').exists()).toBe(true)
      expect(wrapper.find('.node-compact-body').exists()).toBe(false)
    })

    it('should render compact card in overview mode', () => {
      const wrapper = mountCard({ displayMode: 'overview' })
      expect(wrapper.find('.node-image--overview').exists()).toBe(true)
      expect(wrapper.find('.screen-name--overview').exists()).toBe(true)
      expect(wrapper.find('.node-footer--overview').exists()).toBe(true)
    })

    it('should show screen name in compact body', () => {
      const wrapper = mountCard({ displayMode: 'overview' })
      expect(wrapper.find('.screen-name--overview').text()).toBe('登录页')
    })

    it('should not show summary in overview mode', () => {
      const wrapper = mountCard({ displayMode: 'overview' })
      expect(wrapper.find('.screen-summary').exists()).toBe(false)
      expect(wrapper.find('.screen-name--overview').exists()).toBe(true)
    })

    it('should apply display-overview class in overview mode', () => {
      const wrapper = mountCard({ displayMode: 'overview' })
      expect(wrapper.find('.flow-node-card').classes()).toContain('display-overview')
    })

    it('should apply display-edit class in edit mode', () => {
      const wrapper = mountCard({ displayMode: 'edit' })
      expect(wrapper.find('.flow-node-card').classes()).toContain('display-edit')
    })
  })

  describe('search match highlight', () => {
    it('should apply is-search-match class when isSearchMatch is true', () => {
      const wrapper = mountCard({ isSearchMatch: true })
      expect(wrapper.find('.flow-node-card').classes()).toContain('is-search-match')
    })

    it('should not apply is-search-match class by default', () => {
      const wrapper = mountCard()
      expect(wrapper.find('.flow-node-card').classes()).not.toContain('is-search-match')
    })
  })

  describe('flow type', () => {
    it('should apply flow-type-main class for main type', () => {
      const wrapper = mountCard()
      expect(wrapper.find('.flow-node-card').classes()).toContain('flow-type-main')
    })

    it('should apply flow-type-branch class for branch type', () => {
      const wrapper = mountCard({ data: { ...baseData, flow_type: 'branch' } })
      expect(wrapper.find('.flow-node-card').classes()).toContain('flow-type-branch')
    })

    it('should apply flow-type-exception class for exception type', () => {
      const wrapper = mountCard({ data: { ...baseData, flow_type: 'exception' } })
      expect(wrapper.find('.flow-node-card').classes()).toContain('flow-type-exception')
    })

    it('should apply flow-type-bypass class for bypass type', () => {
      const wrapper = mountCard({ data: { ...baseData, flow_type: 'bypass' } })
      expect(wrapper.find('.flow-node-card').classes()).toContain('flow-type-bypass')
    })
  })

  describe('dropdown disabled in overview mode', () => {
    it('should disable dropdown in overview mode', () => {
      const wrapper = mountCard({ displayMode: 'overview' })
      const dropdown = wrapper.findComponent(ElDropdownStub)
      expect(dropdown.props('disabled')).toBe(true)
    })

    it('should enable dropdown in edit mode', () => {
      const wrapper = mountCard({ displayMode: 'edit' })
      const dropdown = wrapper.findComponent(ElDropdownStub)
      expect(dropdown.props('disabled')).toBe(false)
    })
  })

  describe('preview event', () => {
    it('should emit preview when clicking overview image', async () => {
      const wrapper = mountCard({ displayMode: 'overview' })
      await wrapper.find('.node-image--overview').trigger('click')
      expect(wrapper.emitted('preview')).toBeTruthy()
    })
  })
})
