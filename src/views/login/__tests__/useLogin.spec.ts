import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ElMessage } from 'element-plus'
import { createComposableHost, createFormInstanceMock, silenceElMessage } from '@/test-utils'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  generateCaptcha: vi.fn(),
  login: vi.fn(),
  getCurrentUser: vi.fn(),
  signPermissions: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
}))

vi.mock('@/api/auth', () => ({
  authApi: {
    generateCaptcha: mocks.generateCaptcha,
    login: mocks.login,
    getCurrentUser: mocks.getCurrentUser,
  },
}))

vi.mock('@/directives/permission', () => ({
  signPermissions: mocks.signPermissions,
}))

import { useLogin } from '../useLogin'

type Ctx = ReturnType<typeof useLogin>

const host = createComposableHost(() => useLogin())
let ctx: Ctx

async function mountHost() {
  const pending = host.mount()
  await vi.advanceTimersByTimeAsync(100)
  const wrapper = await pending
  ctx = host.ctx
  return wrapper
}

function encode(value: unknown): string {
  return btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(value))))
}

/** 构造 2d 画布桩，用于观察验证码兜底的绘制行为 */
function createCanvasStub() {
  const context2d = {
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    fillText: vi.fn(),
    fillStyle: '',
    strokeStyle: '',
    font: '',
    textAlign: '',
    textBaseline: '',
  }
  const canvas = { width: 120, height: 40, getContext: () => context2d }
  return { canvas: canvas as never, context2d }
}

/**
 * 排空微任务队列。
 *
 * `validate(callback)` 形式下回调内的异步逻辑不会被 `validate()` 返回的
 * Promise 等待，因此 `await handleLogin()` 之后仍需让回调流程跑完。
 */
async function settle(): Promise<void> {
  await vi.advanceTimersByTimeAsync(0)
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
  localStorage.clear()
  silenceElMessage()
  mocks.signPermissions.mockImplementation((perms: unknown) => ({ signed: perms }))
  mocks.generateCaptcha.mockResolvedValue({
    code: 200,
    data: { captcha_id: 'c1', image: 'data:image/png;base64,xx' },
  })
  mocks.login.mockResolvedValue({ code: 200, data: { access_token: 'tk' } })
  mocks.getCurrentUser.mockResolvedValue({ data: { permissions: ['case:read'] } })
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useLogin — 初始化', () => {
  it('按窗口宽度判断移动端', async () => {
    Object.defineProperty(window, 'innerWidth', { value: 375, configurable: true })
    await mountHost()

    expect(ctx.isMobile.value).toBe(true)

    Object.defineProperty(window, 'innerWidth', { value: 1280, configurable: true })
    window.dispatchEvent(new Event('resize'))
    expect(ctx.isMobile.value).toBe(false)
  })

  it('回填记住的账号', async () => {
    localStorage.setItem('rememberedUsername', 'admin')
    await mountHost()

    expect(ctx.loginForm.username).toBe('admin')
    expect(ctx.loginForm.remember).toBe(true)
  })

  it('回填记住的手机号', async () => {
    localStorage.setItem('rememberedPhone', encode({ phone: '13800138000' }))
    await mountHost()

    expect(ctx.phoneForm.phone).toBe('13800138000')
    expect(ctx.phoneForm.remember).toBe(true)
  })

  it('挂载后延迟加载验证码', async () => {
    await mountHost()

    expect(mocks.generateCaptcha).toHaveBeenCalled()
    expect(ctx.captchaImage.value).toBe('data:image/png;base64,xx')
  })

  it('表单规则覆盖账号、密码与验证码', async () => {
    await mountHost()

    expect(ctx.loginRules.username[0].required).toBe(true)
    expect(ctx.loginRules.password).toHaveLength(2)
    expect(ctx.loginRules.code[1].min).toBe(4)
    expect(ctx.phoneRules.phone[1].pattern).toBeInstanceOf(RegExp)
  })
})

describe('useLogin — 验证码', () => {
  it('图片模式写入图片并透传 captcha_id', async () => {
    await mountHost()

    expect(ctx.captchaImage.value).toBe('data:image/png;base64,xx')

    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })
    await ctx.handleLogin()

    const formData = mocks.login.mock.calls[0][0] as URLSearchParams
    expect(formData.get('captcha_id')).toBe('c1')
  })

  it('文本模式绘制到画布', async () => {
    const { canvas, context2d } = createCanvasStub()
    mocks.generateCaptcha.mockResolvedValue({ code: 200, data: { captcha_id: 'c2', code: '5678' } })
    await mountHost()
    ctx.captchaCanvas.value = canvas

    await ctx.refreshCaptcha()

    expect(ctx.captchaImage.value).toBe('')
    expect(context2d.fillText).toHaveBeenCalledTimes(4)
  })

  it('响应缺少图片与文本时回退本地验证码', async () => {
    const { canvas, context2d } = createCanvasStub()
    mocks.generateCaptcha.mockResolvedValue({ code: 200, data: { captcha_id: 'c3' } })
    await mountHost()
    ctx.captchaCanvas.value = canvas

    await ctx.refreshCaptcha()

    expect(ctx.captchaImage.value).toBe('')
    expect(context2d.fillText).toHaveBeenCalledTimes(4)
  })

  it('接口返回非 200 时回退', async () => {
    const { canvas, context2d } = createCanvasStub()
    mocks.generateCaptcha.mockResolvedValue({ code: 500 })
    await mountHost()
    ctx.captchaCanvas.value = canvas

    await ctx.refreshCaptcha()

    expect(context2d.fillText).toHaveBeenCalledTimes(4)
  })

  it('接口异常时回退', async () => {
    const { canvas, context2d } = createCanvasStub()
    await mountHost()
    ctx.captchaCanvas.value = canvas
    mocks.generateCaptcha.mockRejectedValue(new Error('boom'))

    await ctx.refreshCaptcha()

    expect(ctx.captchaImage.value).toBe('')
    expect(context2d.fillText).toHaveBeenCalledTimes(4)
  })

  it('无画布时回退不抛错', async () => {
    mocks.generateCaptcha.mockRejectedValue(new Error('boom'))
    await mountHost()

    await expect(ctx.refreshCaptcha()).resolves.toBeUndefined()
  })

  it('手机验证码入口提示已停用', async () => {
    await mountHost()

    ctx.getPhoneCode()

    expect(ElMessage.warning).toHaveBeenCalledWith('手机验证码功能已停用，请使用账号登录')
  })
})

describe('useLogin — 账号登录', () => {
  it('表单未挂载时不发起请求', async () => {
    await mountHost()

    await ctx.handleLogin()

    expect(mocks.login).not.toHaveBeenCalled()
  })

  it('校验失败时不发起请求', async () => {
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ valid: false, withCallback: true })

    await ctx.handleLogin()

    expect(mocks.login).not.toHaveBeenCalled()
  })

  it('登录成功写入令牌与权限并跳转', async () => {
    mocks.generateCaptcha.mockResolvedValue({ code: 500 })
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })
    ctx.loginForm.username = 'admin'
    ctx.loginForm.password = '123456'
    ctx.loginForm.remember = true

    await ctx.handleLogin()
    await settle()

    const formData = mocks.login.mock.calls[0][0] as URLSearchParams
    expect(formData.get('username')).toBe('admin')
    expect(formData.get('password')).toBe('123456')
    expect(formData.get('captcha_id')).toBeNull()
    expect(localStorage.getItem('token')).toBe('tk')
    expect(localStorage.getItem('userInfo')).toBe(JSON.stringify({ signed: ['case:read'] }))
    expect(localStorage.getItem('rememberedUsername')).toBe('admin')
    expect(ElMessage.success).toHaveBeenCalledWith('登录成功')
    expect(mocks.push).toHaveBeenCalledWith('/home/project')
    expect(ctx.loading.value).toBe(false)
  })

  it('携带验证码时附带 captcha 参数', async () => {
    mocks.generateCaptcha.mockResolvedValue({
      code: 200,
      data: { captcha_id: 'c9', image: 'data:image/png;base64,xx' },
    })
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })
    ctx.loginForm.code = '1234'

    await ctx.handleLogin()
    await settle()

    const formData = mocks.login.mock.calls[0][0] as URLSearchParams
    expect(formData.get('captcha_id')).toBe('c9')
    expect(formData.get('captcha_code')).toBe('1234')
  })

  it('未勾选记住账号时清除本地缓存', async () => {
    localStorage.setItem('rememberedUsername', 'old')
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })
    ctx.loginForm.remember = false

    await ctx.handleLogin()
    await settle()

    expect(localStorage.getItem('rememberedUsername')).toBeNull()
  })

  it('401 使用接口 msg 提示', async () => {
    mocks.login.mockResolvedValue({ code: 401, data: {}, msg: '账号不存在' })
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handleLogin()

    expect(ElMessage.error).toHaveBeenCalledWith('账号不存在')
    expect(ctx.loading.value).toBe(false)
  })

  it('401 无 msg 时使用默认文案', async () => {
    mocks.login.mockResolvedValue({ code: 401, data: {} })
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handleLogin()

    expect(ElMessage.error).toHaveBeenCalledWith('用户名或密码错误')
  })

  it('400 提示参数错误', async () => {
    mocks.login.mockResolvedValue({ code: 400, data: {}, message: '缺少参数' })
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handleLogin()

    expect(ElMessage.error).toHaveBeenCalledWith('缺少参数')
  })

  it('其他状态码拼接状态码文案', async () => {
    mocks.login.mockResolvedValue({ code: 500, data: {} })
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handleLogin()

    expect(ElMessage.error).toHaveBeenCalledWith('登录失败（状态码: 500）')
  })

  it('响应为空时提示服务器无响应', async () => {
    mocks.login.mockResolvedValue(null)
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handleLogin()

    expect(ElMessage.error).toHaveBeenCalledWith('服务器无响应')
  })

  it.each([
    ['401', { response: { status: 401 } }, '用户名或密码错误'],
    ['403', { response: { status: 403 } }, '账号已被禁用'],
    ['429', { response: { status: 429 } }, '操作太频繁，请稍后再试'],
    ['网络错误', { code: 'ERR_NETWORK' }, '网络连接失败'],
    ['超时', { code: 'ECONNABORTED' }, '请求超时'],
    ['接口 detail', { response: { data: { detail: '服务异常' } } }, '服务异常'],
  ])('异常 %s 时给出对应文案', async (_, error, expected) => {
    mocks.login.mockRejectedValue(error)
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })
    mocks.generateCaptcha.mockClear()

    await ctx.handleLogin()

    expect(ElMessage.error).toHaveBeenCalledWith(expected)
    expect(mocks.generateCaptcha).toHaveBeenCalled()
  })

  it('未知异常使用兜底文案', async () => {
    mocks.login.mockRejectedValue({})
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handleLogin()

    expect(ElMessage.error).toHaveBeenCalledWith('登录失败，请稍后重试')
  })

  it('获取用户信息失败时写入空权限', async () => {
    mocks.getCurrentUser.mockRejectedValue(new Error('boom'))
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handleLogin()
    await settle()

    expect(localStorage.getItem('userInfo')).toBe(JSON.stringify({ signed: [] }))
  })

  it('用户信息平铺返回时从顶层取权限', async () => {
    mocks.getCurrentUser.mockResolvedValue({ permissions: ['a'] })
    await mountHost()
    ctx.loginFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handleLogin()
    await settle()

    expect(mocks.signPermissions).toHaveBeenCalledWith(['a'])
  })
})

describe('useLogin — 手机号登录', () => {
  it('成功登录并记住手机号', async () => {
    await mountHost()
    ctx.phoneFormRef.value = createFormInstanceMock({ withCallback: true })
    ctx.phoneForm.phone = '13800138000'
    ctx.phoneForm.remember = true

    await ctx.handlePhoneLogin()
    await settle()

    const formData = mocks.login.mock.calls[0][0] as URLSearchParams
    expect(formData.get('username')).toBe('13800138000')
    expect(formData.get('password')).toBe('phone-login')
    expect(localStorage.getItem('token')).toBe('tk')
    expect(localStorage.getItem('rememberedPhone')).toBeTruthy()
    expect(ElMessage.success).toHaveBeenCalledWith('登录成功')
    expect(ctx.phoneLoading.value).toBe(false)
  })

  it('未勾选记住时清除手机号缓存', async () => {
    await mountHost()
    ctx.phoneFormRef.value = createFormInstanceMock({ withCallback: true })
    ctx.phoneForm.remember = false
    localStorage.setItem('rememberedPhone', 'x')

    await ctx.handlePhoneLogin()
    await settle()

    expect(localStorage.getItem('rememberedPhone')).toBeNull()
  })

  it('返回格式异常时提示', async () => {
    mocks.login.mockResolvedValue({ code: 500 })
    await mountHost()
    ctx.phoneFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handlePhoneLogin()

    expect(ElMessage.error).toHaveBeenCalledWith('登录失败，返回数据格式错误')
  })

  it('登录异常时优先使用接口 message', async () => {
    mocks.login.mockRejectedValue({ response: { data: { message: '手机号未注册' } } })
    await mountHost()
    ctx.phoneFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handlePhoneLogin()

    expect(ElMessage.error).toHaveBeenCalledWith('手机号未注册')
  })

  it('登录异常无 message 时使用兜底文案', async () => {
    mocks.login.mockRejectedValue({})
    await mountHost()
    ctx.phoneFormRef.value = createFormInstanceMock({ withCallback: true })

    await ctx.handlePhoneLogin()

    expect(ElMessage.error).toHaveBeenCalledWith('登录失败')
  })

  it('表单未挂载或校验失败时不提交', async () => {
    await mountHost()

    await ctx.handlePhoneLogin()
    expect(mocks.login).not.toHaveBeenCalled()

    ctx.phoneFormRef.value = createFormInstanceMock({ valid: false, withCallback: true })
    await ctx.handlePhoneLogin()
    expect(mocks.login).not.toHaveBeenCalled()
  })
})
