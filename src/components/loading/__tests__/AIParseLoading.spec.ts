import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AIParseLoading from '../AIParseLoading.vue'

describe('AIParseLoading.vue', () => {
  it('visible 为 false 时不渲染', () => {
    const wrapper = mount(AIParseLoading, { props: { visible: false } })
    expect(wrapper.find('.ai-parse-loading').exists()).toBe(false)
  })

  it('visible 为 true 时渲染加载卡片', () => {
    const wrapper = mount(AIParseLoading, { props: { visible: true } })
    expect(wrapper.find('.ai-parse-loading').exists()).toBe(true)
    expect(wrapper.find('.loading-card').exists()).toBe(true)
  })

  it('默认 parseMode 为 text', () => {
    const wrapper = mount(AIParseLoading, { props: { visible: true } })
    expect(wrapper.find('.detail-value').text()).toBe('文本模型')
  })

  it('parseMode 为 vision 时显示 AI视觉', () => {
    const wrapper = mount(AIParseLoading, { props: { visible: true, parseMode: 'vision' } })
    expect(wrapper.find('.detail-value').text()).toBe('AI视觉')
  })

  it('点击取消按钮触发 cancel 事件', async () => {
    const wrapper = mount(AIParseLoading, { props: { visible: true, showCancelButton: true } })
    await wrapper.find('.loading-actions .el-button').trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
  })
})
