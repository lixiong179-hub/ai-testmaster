import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import App from '@/App.vue'

const RouterViewStub = defineComponent({
  name: 'RouterView',
  setup() {
    return () => h('div', { class: 'router-view-stub' })
  },
})

function mountApp() {
  return mount(App, { global: { stubs: { RouterView: RouterViewStub } } })
}

describe('App — 根壳渲染', () => {
  it('只输出 router-view 出口，不包裹额外容器', () => {
    const wrapper = mountApp()

    expect(wrapper.find('.router-view-stub').exists()).toBe(true)
    expect(wrapper.html()).toBe('<div class="router-view-stub"></div>')
  })

  it('渲染结果不含业务节点与文本', () => {
    const wrapper = mountApp()

    expect(wrapper.text()).toBe('')
    expect(wrapper.findAll('button, form, table')).toHaveLength(0)
  })

  it('重复挂载结构稳定，卸载不抛错', () => {
    const first = mountApp()
    const second = mountApp()

    expect(first.html()).toBe(second.html())
    expect(() => {
      first.unmount()
      second.unmount()
    }).not.toThrow()
  })
})
