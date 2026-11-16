import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import type { TestCase } from '@/types/testCase'
import CaseItem from '../CaseItem.vue'

function makeCase(overrides: Partial<TestCase> = {}): TestCase {
  return {
    id: 101,
    case_no: 'CASE-001',
    project_id: 1,
    module: '登录模块',
    title: '账号密码登录成功',
    priority: 1,
    case_type: 'manual',
    create_time: '2026-06-27T10:00:00',
    generate_status: 1,
    ...overrides,
  }
}

function mountItem(overrides: Partial<TestCase> = {}) {
  const caseItem = makeCase(overrides)
  const wrapper = mount(CaseItem, { props: { caseItem } })
  return { wrapper, caseItem }
}

function findButton(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper.findAll('button').find((btn) => btn.text().includes(text))
}

describe('CaseItem — 基础信息', () => {
  it('渲染用例编号、标题、模块与状态文案', () => {
    const { wrapper } = mountItem()

    expect(wrapper.find('.case-no').text()).toBe('CASE-001')
    expect(wrapper.find('.case-title').text()).toBe('账号密码登录成功')
    expect(wrapper.text()).toContain('登录模块')
    expect(wrapper.find('.case-status').text()).toBe('生成成功')
    expect(wrapper.find('.case-status').classes()).toContain('status-success')
  })

  it('按优先级渲染文案与样式类', () => {
    const high = mountItem({ priority: 1 }).wrapper.find('.case-priority')
    expect(high.text()).toBe('高')
    expect(high.classes()).toContain('high')

    const medium = mountItem({ priority: 2 }).wrapper.find('.case-priority')
    expect(medium.text()).toBe('中')
    expect(medium.classes()).toContain('medium')

    const low = mountItem({ priority: 3 }).wrapper.find('.case-priority')
    expect(low.text()).toBe('低')
    expect(low.classes()).toContain('low')
  })

  it('渲染用例类型标签与创建时间', () => {
    const { wrapper } = mountItem({ case_type: 'ui_automation' })

    expect(wrapper.find('.case-type-tag').text()).toBe('UI自动化')
    expect(wrapper.text()).toContain(new Date('2026-06-27T10:00:00').toLocaleString())
  })

  it('生命周期状态非 active 时展示徽标，active 时隐藏', () => {
    const draft = mountItem({ lifecycle_status: 'draft' }).wrapper
    expect(draft.find('.lifecycle-badge').text()).toBe('草稿')

    const active = mountItem({ lifecycle_status: 'active' }).wrapper
    expect(active.find('.lifecycle-badge').exists()).toBe(false)
  })
})

describe('CaseItem — 生成失败态', () => {
  it('生成失败时卡片标记 failed 并展示重试生成按钮', () => {
    const { wrapper } = mountItem({ generate_status: 2 })

    expect(wrapper.find('.case-card').classes()).toContain('failed')
    expect(wrapper.find('.case-status').text()).toBe('生成失败')
    expect(wrapper.find('.case-status').classes()).toContain('status-failed')
    expect(findButton(wrapper, '重试生成')).toBeTruthy()
  })

  it('生成成功时不展示重试生成按钮', () => {
    const { wrapper } = mountItem({ generate_status: 1 })

    expect(findButton(wrapper, '重试生成')).toBeFalsy()
  })
})

describe('CaseItem — 详情区块', () => {
  it('前置条件、步骤、预期结果齐全时渲染三个区块', () => {
    const { wrapper } = mountItem({
      precondition: '系统已启动',
      steps: [{ step_number: 1, display_action: '输入账号', param: 'admin' }],
      expected_result: '登录成功',
    })

    const sections = wrapper.findAll('.case-section')
    expect(sections).toHaveLength(3)
    expect(wrapper.text()).toContain('前置条件')
    expect(wrapper.text()).toContain('系统已启动')
    expect(wrapper.text()).toContain('测试步骤')
    expect(wrapper.text()).toContain('预期结果')
    expect(wrapper.text()).toContain('登录成功')
  })

  it('字段缺失时不渲染对应区块', () => {
    const { wrapper } = mountItem({ precondition: '', steps: [], expected_result: undefined })

    expect(wrapper.findAll('.case-section')).toHaveLength(0)
  })

  it('步骤按 step_number / display_action / param / expected 组合展示', () => {
    const { wrapper } = mountItem({
      steps: [
        {
          step_number: 2,
          display_action: '点击登录',
          param: '#submit',
          expected: '进入首页',
        } as never,
      ],
    })

    expect(wrapper.find('.step-number').text()).toBe('2')
    expect(wrapper.find('.step-content').text()).toBe('点击登录 (#submit)')
    expect(wrapper.find('.step-expected').text()).toBe('→ 进入首页')
  })

  it('步骤缺少结构化字段时回退到 description/action 与下标序号', () => {
    const { wrapper } = mountItem({
      steps: [{ description: '打开页面' }, { action: '提交表单' }],
    })

    const numbers = wrapper.findAll('.step-number').map((el) => el.text())
    expect(numbers).toEqual(['1', '2'])

    const contents = wrapper.findAll('.step-content').map((el) => el.text())
    expect(contents).toEqual(['打开页面', '提交表单'])
  })
})

describe('CaseItem — 事件派发', () => {
  it('点击查看详情抛出 viewDetail 并携带用例 ID', async () => {
    const { wrapper } = mountItem({ id: 555 })

    await findButton(wrapper, '查看详情')!.trigger('click')

    expect(wrapper.emitted('viewDetail')).toEqual([[555]])
  })

  it('点击复制用例抛出 copyCase 并携带整个用例对象', async () => {
    const { wrapper, caseItem } = mountItem()

    await findButton(wrapper, '复制用例')!.trigger('click')

    expect(wrapper.emitted('copyCase')).toEqual([[caseItem]])
  })

  it('点击重试生成抛出 retryGenerate 并携带用例 ID', async () => {
    const { wrapper } = mountItem({ id: 777, generate_status: 2 })

    await findButton(wrapper, '重试生成')!.trigger('click')

    expect(wrapper.emitted('retryGenerate')).toEqual([[777]])
  })

  it('点击删除抛出 deleteCase 并携带用例 ID', async () => {
    const { wrapper } = mountItem({ id: 888 })

    await findButton(wrapper, '删除')!.trigger('click')

    expect(wrapper.emitted('deleteCase')).toEqual([[888]])
  })

  it('未触发点击时不派发任何事件', () => {
    const { wrapper } = mountItem()

    expect(wrapper.emitted()).toEqual({})
  })
})
