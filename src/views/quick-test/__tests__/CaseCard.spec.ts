import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import CaseCard from '../components/CaseCard.vue'
import type { CaseData } from '../quickTestTypes'

function makeCase(overrides: Partial<CaseData> = {}): CaseData {
    return {
        id: 1,
        title: '登录功能验证',
        status: 'passed',
        steps: [],
        ...overrides,
    }
}

function mountCard(caseData: CaseData = makeCase()) {
    return mount(CaseCard, { props: { caseData } })
}

describe('CaseCard', () => {
    describe('状态标签渲染', () => {
        it('passed 渲染 ✓ 通过 且 success tag', () => {
            const wrapper = mountCard(makeCase({ status: 'passed' }))
            const tag = wrapper.find('.case-status-tag')
            expect(tag.text()).toContain('通过')
            expect(tag.classes().join(' ')).toMatch(/success/)
        })

        it('failed 渲染 ✗ 失败 且 danger tag', () => {
            const wrapper = mountCard(makeCase({ status: 'failed' }))
            const tag = wrapper.find('.case-status-tag')
            expect(tag.text()).toContain('失败')
            expect(tag.classes().join(' ')).toMatch(/danger/)
        })

        it('running 渲染 ⏳ 进行中 且 warning tag', () => {
            const wrapper = mountCard(makeCase({ status: 'running' }))
            const tag = wrapper.find('.case-status-tag')
            expect(tag.text()).toContain('进行中')
            expect(tag.classes().join(' ')).toMatch(/warning/)
        })

        it('pending 渲染 ○ 待执行 且 info tag', () => {
            const wrapper = mountCard(makeCase({ status: 'pending' }))
            const tag = wrapper.find('.case-status-tag')
            expect(tag.text()).toContain('待执行')
            expect(tag.classes().join(' ')).toMatch(/info/)
        })
    })

    describe('卡片样式随状态变化', () => {
        it('failed 卡片有 is-failed 类与红色边框背景', () => {
            const wrapper = mountCard(makeCase({ status: 'failed' }))
            expect(wrapper.find('.case-card').classes()).toContain('is-failed')
        })

        it('passed 卡片有 is-passed 类', () => {
            const wrapper = mountCard(makeCase({ status: 'passed' }))
            expect(wrapper.find('.case-card').classes()).toContain('is-passed')
        })
    })

    describe('耗时展示', () => {
        it('duration_sec 存在时展示耗时文案', () => {
            const wrapper = mountCard(makeCase({ duration_sec: 90 }))
            expect(wrapper.find('.case-duration').text()).toContain('1分30秒')
        })

        it('duration_sec 缺失时不渲染耗时节点', () => {
            const wrapper = mountCard(makeCase({ duration_sec: undefined }))
            expect(wrapper.find('.case-duration').exists()).toBe(false)
        })

        it('耗时不足 1 分钟展示秒数', () => {
            const wrapper = mountCard(makeCase({ duration_sec: 45 }))
            expect(wrapper.find('.case-duration').text()).toContain('45s')
        })
    })

    describe('步骤与元素验证图标', () => {
        it('步骤 element_verified=true 渲染 ok 图标', () => {
            const wrapper = mountCard(
                makeCase({
                    status: 'passed',
                    steps: [
                        {
                            step: 1,
                            description: '输入账号',
                            action: 'click',
                            target_element: '#username',
                            expected_result: '输入框获取焦点',
                            element_verified: true,
                        },
                    ],
                })
            )
            const verified = wrapper.find('.step-verified.ok')
            expect(verified.exists()).toBe(true)
        })

        it('步骤 element_verified=false 渲染 warn 图标', () => {
            const wrapper = mountCard(
                makeCase({
                    status: 'failed',
                    steps: [
                        {
                            step: 1,
                            description: '点击登录按钮',
                            action: 'click',
                            target_element: '#submit',
                            expected_result: '跳转主页',
                            element_verified: false,
                        },
                    ],
                })
            )
            expect(wrapper.find('.step-verified.warn').exists()).toBe(true)
        })

        it('步骤 element_verified 缺失时不渲染验证图标', () => {
            const wrapper = mountCard(
                makeCase({
                    status: 'passed',
                    steps: [
                        {
                            step: 1,
                            description: '步骤无验证状态',
                            action: 'navigate',
                            target_element: '',
                            expected_result: '',
                        },
                    ],
                })
            )
            expect(wrapper.find('.step-verified').exists()).toBe(false)
        })

        it('步骤 target_element 渲染为 tag', () => {
            const wrapper = mountCard(
                makeCase({
                    status: 'passed',
                    steps: [
                        {
                            step: 1,
                            description: '点击搜索',
                            action: 'click',
                            target_element: '#search-btn',
                            expected_result: '弹出搜索框',
                            element_verified: true,
                        },
                    ],
                })
            )
            expect(wrapper.find('.step-target').text()).toBe('#search-btn')
        })

        it('步骤为空时展示预期/实际区块', () => {
            const wrapper = mountCard(
                makeCase({
                    status: 'failed',
                    steps: [],
                    expected_result: '应跳转主页',
                    actual_result: '停留在登录页',
                })
            )
            expect(wrapper.find('.case-result').exists()).toBe(true)
            expect(wrapper.find('.result-row.is-fail').exists()).toBe(true)
        })
    })

    describe('失败截图与放大预览', () => {
        it('失败用例有失败步骤截图时渲染 el-image 并支持 preview-src-list', () => {
            const wrapper = mountCard(
                makeCase({
                    status: 'failed',
                    steps: [
                        {
                            step: 1,
                            description: '失败步骤',
                            action: 'click',
                            target_element: '#btn',
                            expected_result: '应成功',
                            element_verified: false,
                            screenshot: 'data:image/png;base64,abc',
                        },
                    ],
                })
            )
            const img = wrapper.findComponent({ name: 'ElImage' })
            expect(img.exists()).toBe(true)
            expect(img.props('src')).toBe('data:image/png;base64,abc')
            const preview = img.props('previewSrcList') as unknown
            expect(preview).toBeTruthy()
            expect(JSON.stringify(preview)).toContain('data:image/png;base64,abc')
        })

        it('成功用例不渲染失败截图', () => {
            const wrapper = mountCard(
                makeCase({
                    status: 'passed',
                    steps: [
                        {
                            step: 1,
                            description: '通过步骤',
                            action: 'click',
                            target_element: '#btn',
                            expected_result: '应成功',
                            element_verified: true,
                            screenshot: 'data:image/png;base64,xyz',
                        },
                    ],
                })
            )
            expect(wrapper.find('.case-screenshot').exists()).toBe(false)
        })

        it('失败步骤无截图时不渲染截图区', () => {
            const wrapper = mountCard(
                makeCase({
                    status: 'failed',
                    steps: [
                        {
                            step: 1,
                            description: '无截图失败',
                            action: 'click',
                            target_element: '#btn',
                            expected_result: '应成功',
                            element_verified: false,
                        },
                    ],
                    failure_reason: '元素未找到',
                })
            )
            expect(wrapper.find('.case-screenshot').exists()).toBe(false)
            // 失败原因仍应展示
            expect(wrapper.find('.case-failure-reason').text()).toContain('元素未找到')
        })
    })
})
