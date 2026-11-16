import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { ElMessage } from 'element-plus'
import { silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  getLoginLogs: vi.fn(),
  changePassword: vi.fn(),
  /** 表单校验结果开关，由用例控制 */
  formValid: { value: true },
}))

vi.mock('@/api/user', () => ({
  userApi: {
    getCurrentUser: mocks.getCurrentUser,
    getLoginLogs: mocks.getLoginLogs,
    changePassword: mocks.changePassword,
  },
}))

import ProfilePage from '../index.vue'

/**
 * 真实 el-form 校验依赖异步校验器与字段注册，在 happy-dom 下不稳定；
 * 视图层只需验证「校验通过/不通过 → 是否提交」的接线，故用受控表单桩。
 */
const ElFormStub = defineComponent({
  name: 'ElForm',
  props: {
    model: { type: Object, default: () => ({}) },
    rules: { type: Object, default: () => ({}) },
  },
  setup(_props, { slots, expose }) {
    const validate = async (callback?: (valid: boolean) => void) => {
      callback?.(mocks.formValid.value)
      return mocks.formValid.value
    }
    expose({ validate, clearValidate: vi.fn(), resetFields: vi.fn() })
    return () => h('form', { class: 'el-form' }, slots.default?.())
  },
})

const ElFormItemStub = defineComponent({
  name: 'ElFormItem',
  props: { label: { type: String, default: '' }, prop: { type: String, default: '' } },
  setup(_props, { slots }) {
    return () => h('div', { class: 'el-form-item' }, slots.default?.())
  },
})

const stubs = { ElForm: ElFormStub, ElFormItem: ElFormItemStub }

function makeUser(over: Record<string, unknown> = {}) {
  return {
    id: 1,
    username: 'admin',
    email: 'admin@example.com',
    phone: '13800000000',
    status: true,
    last_login_time: '2026-11-16 08:00:00',
    created_at: '2026-01-01 00:00:00',
    roles: [
      { id: 1, name: '管理员' },
      { id: 2, name: '测试工程师' },
    ],
    ...over,
  }
}

function makeLog(id: number, over: Record<string, unknown> = {}) {
  return {
    id,
    username: 'admin',
    ip: '127.0.0.1',
    user_agent: 'Chrome',
    login_time: '2026-11-16 08:00:00',
    status: true,
    ...over,
  }
}

async function mountPage() {
  const wrapper = mount(ProfilePage, { global: { stubs } })
  await flushPromises()
  return wrapper
}

function buttonByText(wrapper: VueWrapper, text: string) {
  return wrapper.findAll('.el-button').find((node) => node.text().includes(text))
}

/** 表单桩会渲染所有 tab-pane 内容，密码输入框固定为 3 个 */
async function fillPasswordForm(
  wrapper: VueWrapper,
  values: { oldPassword: string; newPassword: string; confirmPassword: string }
) {
  const inputs = wrapper.findAll('.el-tab-pane input[type="password"]')
  expect(inputs).toHaveLength(3)
  await inputs[0].setValue(values.oldPassword)
  await inputs[1].setValue(values.newPassword)
  await inputs[2].setValue(values.confirmPassword)
}

function inputValue(wrapper: VueWrapper, index: number) {
  const inputs = wrapper.findAll('.el-tab-pane input[type="password"]')
  return (inputs[index].element as HTMLInputElement).value
}

beforeEach(() => {
  vi.clearAllMocks()
  silenceElMessage()
  mocks.formValid.value = true
  mocks.getCurrentUser.mockResolvedValue({ data: makeUser() })
  mocks.getLoginLogs.mockResolvedValue({
    data: [makeLog(1), makeLog(2, { status: false })],
    headers: { 'x-total-count': '42' },
  })
  mocks.changePassword.mockResolvedValue({ code: 200 })
})

describe('个人中心 — 数据加载', () => {
  it('挂载后填充用户信息与角色标签', async () => {
    const wrapper = await mountPage()

    expect(mocks.getCurrentUser).toHaveBeenCalledTimes(1)
    const inputs = wrapper.findAll('.el-tab-pane input')
    const values = inputs.map((node) => (node.element as HTMLInputElement).value)
    expect(values).toContain('admin')
    expect(values).toContain('admin@example.com')
    expect(values).toContain('13800000000')
    expect(wrapper.findAll('.role-tag').map((node) => node.text())).toEqual([
      '管理员',
      '测试工程师',
    ])
  })

  it('登录日志渲染用户名、IP 与状态', async () => {
    const wrapper = await mountPage()

    const rows = wrapper.findAll('.el-table__row')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('127.0.0.1')
    expect(rows[0].text()).toContain('成功')
    expect(rows[1].text()).toContain('失败')
  })

  it('登录日志总数取响应头并转为数字', async () => {
    const wrapper = await mountPage()

    // 响应头为字符串 '42'，分页组件必须拿到 number
    expect(wrapper.find('.el-pagination__total').text()).toContain('42')
  })

  it('响应头缺失时以当前页条数作为总数', async () => {
    mocks.getLoginLogs.mockResolvedValue({ data: [makeLog(1)], headers: {} })

    const wrapper = await mountPage()

    expect(wrapper.find('.el-pagination__total').text()).toContain('1')
  })

  it('用户信息加载失败时提示', async () => {
    mocks.getCurrentUser.mockRejectedValue(new Error('boom'))

    await mountPage()

    expect(ElMessage.error).toHaveBeenCalledWith('获取用户信息失败')
  })

  it('登录日志加载失败时提示', async () => {
    mocks.getLoginLogs.mockRejectedValue(new Error('boom'))

    await mountPage()

    expect(ElMessage.error).toHaveBeenCalledWith('获取登录日志失败')
  })

  it('分页大小变更后按新尺寸重新拉取', async () => {
    const wrapper = await mountPage()
    mocks.getLoginLogs.mockClear()

    wrapper.findComponent({ name: 'ElPagination' }).vm.$emit('size-change', 20)
    await flushPromises()

    expect(mocks.getLoginLogs).toHaveBeenCalledWith(expect.objectContaining({ skip: 0, limit: 20 }))
  })

  it('翻页时按新页码计算 skip', async () => {
    const wrapper = await mountPage()
    mocks.getLoginLogs.mockClear()

    wrapper.findComponent({ name: 'ElPagination' }).vm.$emit('current-change', 3)
    await flushPromises()

    expect(mocks.getLoginLogs).toHaveBeenCalledWith(
      expect.objectContaining({ skip: 20, limit: 10 })
    )
  })
})

describe('个人中心 — 修改密码', () => {
  it('校验未通过时不调用接口', async () => {
    mocks.formValid.value = false
    const wrapper = await mountPage()

    await buttonByText(wrapper, '确认修改')!.trigger('click')
    await flushPromises()

    expect(mocks.changePassword).not.toHaveBeenCalled()
    expect(ElMessage.success).not.toHaveBeenCalled()
  })

  it('校验通过后提交并清空表单', async () => {
    const wrapper = await mountPage()
    await fillPasswordForm(wrapper, {
      oldPassword: 'oldpwd',
      newPassword: 'abcdef',
      confirmPassword: 'abcdef',
    })

    await buttonByText(wrapper, '确认修改')!.trigger('click')
    await flushPromises()

    expect(mocks.changePassword).toHaveBeenCalledWith({
      old_password: 'oldpwd',
      new_password: 'abcdef',
    })
    expect(ElMessage.success).toHaveBeenCalledWith('密码修改成功，请重新登录')
    expect(inputValue(wrapper, 0)).toBe('')
    expect(inputValue(wrapper, 1)).toBe('')
    expect(inputValue(wrapper, 2)).toBe('')
  })

  it('提交失败时展示后端提示', async () => {
    mocks.changePassword.mockRejectedValue({ response: { data: { message: '旧密码错误' } } })
    const wrapper = await mountPage()

    await buttonByText(wrapper, '确认修改')!.trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('旧密码错误')
  })

  it('失败且无后端提示时使用兜底文案', async () => {
    mocks.changePassword.mockRejectedValue(new Error('network'))
    const wrapper = await mountPage()

    await buttonByText(wrapper, '确认修改')!.trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('密码修改失败')
  })

  it('提交期间按钮展示 loading 态', async () => {
    let resolveChange: (value: unknown) => void = () => {}
    mocks.changePassword.mockReturnValue(
      new Promise((resolve) => {
        resolveChange = resolve
      })
    )
    const wrapper = await mountPage()

    await buttonByText(wrapper, '确认修改')!.trigger('click')
    await flushPromises()

    expect(buttonByText(wrapper, '确认修改')!.classes()).toContain('is-loading')

    resolveChange({ code: 200 })
    await flushPromises()

    expect(buttonByText(wrapper, '确认修改')!.classes()).not.toContain('is-loading')
  })
})
