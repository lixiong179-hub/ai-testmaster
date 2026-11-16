import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import ErrorState from '../ErrorState.vue'

const ElIconStub = defineComponent({
  name: 'ElIcon',
  template: '<i class="el-icon"><slot /></i>',
})

const ElButtonStub = defineComponent({
  name: 'ElButton',
  props: { type: { type: String, default: '' } },
  emits: ['click'],
  template: `<button class="el-button" :data-type="type" @click="$emit('click')"><slot /></button>`,
})

const stubs = { ElIcon: ElIconStub, ElButton: ElButtonStub }

function mountState(props: Record<string, unknown> = {}) {
  return mount(ErrorState, {
    props: { title: '生成失败', ...props },
    global: { stubs },
  })
}

describe('ErrorState — 结构', () => {
  it('以 alert 语义渲染标题与图标', () => {
    const wrapper = mountState()

    const root = wrapper.find('.error-state')
    expect(root.attributes('role')).toBe('alert')
    expect(root.attributes('aria-live')).toBe('assertive')
    expect(wrapper.find('.error-title').text()).toBe('生成失败')
    expect(wrapper.find('.error-icon').exists()).toBe(true)
  })

  it('无原因时不渲染原因段落', () => {
    const wrapper = mountState()

    expect(wrapper.find('.error-reason').exists()).toBe(false)
  })

  it('有原因时展示后端原文', () => {
    const wrapper = mountState({ reason: '模型返回超时（timeout=30s）' })

    expect(wrapper.find('.error-reason').text()).toBe('模型返回超时（timeout=30s）')
  })
})

describe('ErrorState — 重试与扩展操作', () => {
  it('不可重试时不渲染重试按钮', () => {
    const wrapper = mountState()

    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('可重试时渲染主按钮并抛 retry', async () => {
    const wrapper = mountState({ retryable: true })

    const button = wrapper.find('.error-actions button')
    expect(button.attributes('data-type')).toBe('primary')
    expect(button.text()).toContain('重试')

    await button.trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('extra-actions 插槽内容渲染在操作区', () => {
    const wrapper = mount(ErrorState, {
      props: { title: '保存失败', retryable: true },
      slots: { 'extra-actions': '<button class="extra">返回列表</button>' },
      global: { stubs },
    })

    expect(wrapper.find('.error-actions .extra').text()).toBe('返回列表')
  })
})
