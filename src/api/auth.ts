import request from '@/utils/request'

export interface CaptchaResponse {
  captcha_id: string
  image?: string
  code?: string
}

export interface LoginResponse {
  access_token: string
}

export interface UserInfo {
  id: number
  username: string
  permissions: string[]
  roles?: { permissions?: string[] }[]
  [key: string]: unknown
}

export const authApi = {
  generateCaptcha: () =>
    request.get('/api/v1/auth/captcha/generate') as Promise<{
      code: number
      data: CaptchaResponse
    }>,

  login: (formData: URLSearchParams) =>
    request.post('/api/v1/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    }),

  getCurrentUser: () => request.get('/api/v1/auth/me'),
}
