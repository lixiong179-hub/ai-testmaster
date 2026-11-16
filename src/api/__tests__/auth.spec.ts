import { describe, it, expect, vi, beforeEach } from 'vitest'

const mocks = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))

vi.mock('@/utils/request', () => ({
  default: { get: mocks.get, post: mocks.post },
}))

import { authApi } from '../auth'

beforeEach(() => {
  vi.clearAllMocks()
})

describe('authApi — 端点契约', () => {
  it('generateCaptcha 走 GET /api/v1/auth/captcha/generate', async () => {
    mocks.get.mockResolvedValue({ code: 200, data: { captcha_id: 'cid', image: 'data:image' } })

    const res = await authApi.generateCaptcha()

    expect(mocks.get).toHaveBeenCalledWith('/api/v1/auth/captcha/generate')
    expect(res.data.captcha_id).toBe('cid')
  })

  it('login 以 form-urlencoded 提交', async () => {
    const formData = new URLSearchParams({ username: 'admin', password: 'pwd' })
    mocks.post.mockResolvedValue({ code: 200, data: { access_token: 'token-1' } })

    const res = await authApi.login(formData)

    expect(mocks.post).toHaveBeenCalledWith('/api/v1/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    expect(res.data.access_token).toBe('token-1')
  })

  it('getCurrentUser 走 GET /api/v1/auth/me', async () => {
    mocks.get.mockResolvedValue({ data: { id: 1, username: 'admin', permissions: ['a'] } })

    const res = await authApi.getCurrentUser()

    expect(mocks.get).toHaveBeenCalledWith('/api/v1/auth/me')
    expect(res.data.username).toBe('admin')
  })

  it('请求异常向上抛出，由调用方兜底', async () => {
    mocks.post.mockRejectedValue(new Error('bad credentials'))

    await expect(authApi.login(new URLSearchParams())).rejects.toThrow('bad credentials')
  })
})
