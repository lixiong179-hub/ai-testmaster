import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const mocks = vi.hoisted(() => ({
  getProjectDetail: vi.fn(),
  getProjectConfig: vi.fn(),
}))

vi.mock('@/api/project', () => ({
  default: {
    getProjectDetail: mocks.getProjectDetail,
    getProjectConfig: mocks.getProjectConfig,
  },
}))

import QuickAssetsCard from '../QuickAssetsCard.vue'

function mountCard(props: Record<string, unknown> = {}) {
  return mount(QuickAssetsCard, {
    props: { projectId: 7, caseCount: 18, exploredPages: [], ...props },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.getProjectDetail.mockResolvedValue({ data: { name: 'Alpha 项目' } })
  mocks.getProjectConfig.mockResolvedValue({ data: {} })
})

describe('QuickAssetsCard — 资产概览', () => {
  it('展示项目名与项目 ID、已生成用例数', async () => {
    const wrapper = mountCard()
    await flushPromises()

    const values = wrapper.findAll('.asset-value').map((node) => node.text())
    expect(values[0]).toBe('Alpha 项目 (#7)')
    expect(values[1]).toBe('18 条')
  })

  it('项目详情失败时降级展示项目 ID', async () => {
    mocks.getProjectDetail.mockRejectedValue(new Error('boom'))

    const wrapper = mountCard()
    await flushPromises()

    expect(wrapper.findAll('.asset-value')[0].text()).toBe('项目 #7')
  })

  it('projectId 为空时不请求并展示占位符', async () => {
    const wrapper = mountCard({ projectId: null })
    await flushPromises()

    expect(mocks.getProjectDetail).not.toHaveBeenCalled()
    expect(mocks.getProjectConfig).not.toHaveBeenCalled()
    expect(wrapper.findAll('.asset-value')[0].text()).toBe('-')
  })
})

describe('QuickAssetsCard — 环境配置', () => {
  it('渲染三套环境与地址', async () => {
    mocks.getProjectDetail.mockResolvedValue({
      data: {
        name: 'Alpha 项目',
        web_env_configs: {
          test: { url: 'https://test.example.com' },
          staging: { url: 'https://staging.example.com' },
          prod: { url: '' },
        },
      },
    })

    const wrapper = mountCard()
    await flushPromises()

    const labels = wrapper.findAll('.env-item .el-tag').map((node) => node.text())
    expect(labels).toEqual(['测试', '灰度', '正式'])
    expect(wrapper.text()).toContain('https://test.example.com')
    expect(wrapper.text()).toContain('https://staging.example.com')
    // 未配置环境展示占位符
    expect(wrapper.text()).toContain('未配置')
  })

  it('配置接口返回的环境配置覆盖详情数据', async () => {
    mocks.getProjectDetail.mockResolvedValue({
      data: { name: 'Alpha 项目', web_env_configs: { test: { url: 'https://old.com' } } },
    })
    mocks.getProjectConfig.mockResolvedValue({
      data: { web_env_configs: { test: { url: 'https://new.com' } } },
    })

    const wrapper = mountCard()
    await flushPromises()

    expect(wrapper.text()).toContain('https://new.com')
    expect(wrapper.text()).not.toContain('https://old.com')
  })

  it('配置接口失败时保留详情中的环境配置', async () => {
    mocks.getProjectDetail.mockResolvedValue({
      data: { name: 'Alpha 项目', web_env_configs: { test: { url: 'https://keep.com' } } },
    })
    mocks.getProjectConfig.mockRejectedValue(new Error('boom'))

    const wrapper = mountCard()
    await flushPromises()

    expect(wrapper.text()).toContain('https://keep.com')
  })

  it('全部环境为空时不渲染环境区块', async () => {
    const wrapper = mountCard()
    await flushPromises()

    expect(wrapper.find('.env-section').exists()).toBe(false)
  })
})

describe('QuickAssetsCard — 探索页面', () => {
  it('按数量渲染可折叠清单与页面信息', async () => {
    const wrapper = mountCard({
      exploredPages: [
        { url: 'https://example.com/login', title: '登录页', screenshot: 'shot-1.png' },
        { url: 'https://example.com/search' },
      ],
    })
    await flushPromises()

    expect(wrapper.find('.el-collapse-item__header').text()).toContain('探索页面清单（2）')
    expect(wrapper.text()).toContain('登录页')
    expect(wrapper.text()).toContain('https://example.com/search')
    // 有截图时渲染缩略图
    expect(wrapper.findComponent({ name: 'ElImage' }).exists()).toBe(true)
  })

  it('无探索页面时不渲染折叠区', async () => {
    const wrapper = mountCard()
    await flushPromises()

    expect(wrapper.find('.el-collapse').exists()).toBe(false)
  })
})
