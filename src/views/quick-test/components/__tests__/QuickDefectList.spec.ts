import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import { silenceElMessage } from '@/test-utils'
import { SEVERITY_LABELS } from '../../quickTestTypes'
import type { DefectData } from '../../quickTestTypes'
import QuickDefectList from '../QuickDefectList.vue'

function makeDefect(bugNo: string, over: Record<string, unknown> = {}): DefectData {
  return {
    bug_no: bugNo,
    title: `缺陷 ${bugNo}`,
    severity: 2,
    module: '订单',
    ux_category: '交互体验',
    status: 'open',
    reproduction_steps: '1. 打开页面 2. 点击提交',
    evidence: null,
    screenshot: undefined,
    fix_suggestion: '补充校验',
    case_id: 100,
    ...over,
  } as unknown as DefectData
}

function mountList(defects: DefectData[] = []) {
  return mount(QuickDefectList, { props: { defects } })
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
})

describe('QuickDefectList — 空态', () => {
  it('无缺陷时展示空态且不显示数量标签', () => {
    const wrapper = mountList()

    expect(wrapper.find('.el-empty').text()).toContain('暂无缺陷')
    expect(wrapper.find('.count-tag').exists()).toBe(false)
  })
})

describe('QuickDefectList — 列表', () => {
  it('按严重度升序排列并展示数量标签', () => {
    const wrapper = mountList([
      makeDefect('BUG-3', { severity: 3 }),
      makeDefect('BUG-1', { severity: 1 }),
    ])

    const items = wrapper.findAll('.defect-item')
    expect(items).toHaveLength(2)
    expect(items[0].classes()).toContain('sev-1')
    expect(items[0].text()).toContain('BUG-1')
    expect(items[1].classes()).toContain('sev-3')
    expect(wrapper.find('.count-tag').text()).toBe('2')
  })

  it('严重度标签文案取常量映射', () => {
    const wrapper = mountList([makeDefect('BUG-1', { severity: 1 })])
    const tag = wrapper.find('.defect-head .el-tag')

    expect(tag.text()).toBe(SEVERITY_LABELS[1])
  })

  it('渲染模块、分类、复现步骤与修复建议', () => {
    const wrapper = mountList([makeDefect('BUG-1')])
    const text = wrapper.find('.defect-item').text()

    expect(text).toContain('模块：订单')
    expect(text).toContain('分类：交互体验')
    expect(text).toContain('复现步骤：')
    expect(text).toContain('1. 打开页面 2. 点击提交')
    expect(text).toContain('修复建议：')
  })

  it('缺失可选字段时不渲染对应区块', () => {
    const wrapper = mountList([
      makeDefect('BUG-2', {
        module: null,
        ux_category: null,
        reproduction_steps: null,
        fix_suggestion: null,
        screenshot: null,
      }),
    ])

    expect(wrapper.find('.defect-meta').text()).toBe('')
    expect(wrapper.find('.defect-steps').exists()).toBe(false)
    expect(wrapper.find('.defect-fix').exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'ElImage' }).exists()).toBe(false)
  })

  it('有截图时渲染预览图', () => {
    const wrapper = mountList([makeDefect('BUG-1', { screenshot: 'shot.png' })])

    expect(wrapper.findComponent({ name: 'ElImage' }).exists()).toBe(true)
  })
})

describe('QuickDefectList — 创建 Bug', () => {
  it('点击创建 Bug 时通知父组件并给出兜底提示', async () => {
    const wrapper = mountList([makeDefect('BUG-1')])

    await wrapper.find('.defect-actions .el-button').trigger('click')

    expect(wrapper.emitted('create-bug')?.[0]).toEqual([
      expect.objectContaining({ bug_no: 'BUG-1' }),
    ])
    expect(ElMessage.info).toHaveBeenCalledWith('Bug 创建入口即将上线')
  })
})
