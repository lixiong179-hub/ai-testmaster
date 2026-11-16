import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ProgressBar from '../ProgressBar.vue'

describe('ProgressBar — 展示', () => {
  it('默认标题与百分比', () => {
    const wrapper = mount(ProgressBar)

    expect(wrapper.find('.progress-title').text()).toBe('分析进度')
    expect(wrapper.find('.progress-percentage').text()).toBe('0%')
  })

  it('透传标题、进度与状态', () => {
    const wrapper = mount(ProgressBar, {
      props: { title: '用例生成进度', progress: 62, status: 'warning' },
    })

    expect(wrapper.find('.progress-title').text()).toBe('用例生成进度')
    expect(wrapper.find('.progress-percentage').text()).toBe('62%')

    const progress = wrapper.findComponent({ name: 'ElProgress' })
    expect(progress.props('percentage')).toBe(62)
    expect(progress.props('status')).toBe('warning')
    expect(progress.props('strokeWidth')).toBe(15)
  })

  it('有提示文案时才渲染消息区', () => {
    const withoutMessage = mount(ProgressBar)
    expect(withoutMessage.find('.progress-message').exists()).toBe(false)

    const withMessage = mount(ProgressBar, { props: { message: '正在解析需求文档…' } })
    expect(withMessage.find('.progress-message').text()).toBe('正在解析需求文档…')
  })

  it('进度变化后百分比同步更新', async () => {
    const wrapper = mount(ProgressBar, { props: { progress: 10 } })

    await wrapper.setProps({ progress: 100 })

    expect(wrapper.find('.progress-percentage').text()).toBe('100%')
  })
})
