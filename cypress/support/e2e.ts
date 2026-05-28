// 导入Cypress命令
import './commands'

type RequestOptions = Partial<Cypress.RequestOptions>

let captchaRequestIndex = 0
const API_URL = Cypress.env('apiUrl') || 'http://127.0.0.1:8000'
const CAPTCHA_API_PATTERN = '**/api/v1/auth/captcha/generate'

const hashSpecName = () => {
  const name = Cypress.spec?.name || 'default-spec'
  let hash = 0
  for (let i = 0; i < name.length; i += 1) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  }
  return hash
}

const nextCaptchaIp = () => {
  captchaRequestIndex += 1
  const specHash = hashSpecName()
  const secondOctet = 64 + (specHash % 64)
  const thirdOctet = 1 + (Math.floor(specHash / 64) % 250)
  const fourthOctet = 1 + (captchaRequestIndex % 250)
  return `127.${secondOctet}.${thirdOctet}.${fourthOctet}`
}

const normalizeRequestArgs = (args: unknown[]): RequestOptions => {
  if (typeof args[0] === 'object' && args[0] !== null) {
    return { ...(args[0] as RequestOptions) }
  }

  if (typeof args[0] === 'string' && typeof args[1] === 'string') {
    return {
      method: args[0],
      url: args[1],
      body: args[2],
    } as RequestOptions
  }

  if (typeof args[0] === 'string') {
    return {
      url: args[0],
      body: args[1],
    } as RequestOptions
  }

  return {}
}

const shouldAttachCaptcha = (options: RequestOptions) => {
  const method = String(options.method || 'GET').toUpperCase()
  const url = String(options.url || '')
  const body = options.body
  return (
    method === 'POST' &&
    /\/api\/v1\/auth\/login$/.test(url) &&
    body !== null &&
    typeof body === 'object' &&
    !Array.isArray(body) &&
    !('captcha_id' in body) &&
    !('captcha_code' in body)
  )
}

const shouldIsolateCaptchaRequest = (options: RequestOptions) => {
  const method = String(options.method || 'GET').toUpperCase()
  const url = String(options.url || '')
  const headers = (options.headers || {}) as Record<string, unknown>
  return (
    method === 'GET' &&
    /\/api\/v1\/auth\/captcha\/generate$/.test(url) &&
    !headers['X-Forwarded-For']
  )
}

Cypress.Commands.overwrite('request', (originalFn, ...args) => {
  const options = normalizeRequestArgs(args)

  if (shouldIsolateCaptchaRequest(options)) {
    return originalFn({
      ...options,
      headers: {
        ...(options.headers as Record<string, unknown> | undefined),
        'X-Forwarded-For': nextCaptchaIp(),
      },
    })
  }

  if (!shouldAttachCaptcha(options)) {
    return originalFn(...args)
  }

  const url = String(options.url)
  const captchaUrl = url.replace(/\/auth\/login$/, '/auth/captcha/generate')
  const forwardedFor = nextCaptchaIp()

  return originalFn({
    method: 'GET',
    url: captchaUrl,
    headers: {
      'X-Forwarded-For': forwardedFor,
    },
  }).then((captchaResponse) => {
    const captcha = captchaResponse.body?.data || {}
    return originalFn({
      ...options,
      headers: {
        ...(options.headers as Record<string, unknown> | undefined),
        'X-Forwarded-For': forwardedFor,
      },
      body: {
        ...(options.body as Record<string, unknown>),
        captcha_id: captcha.captcha_id,
        captcha_code: captcha.code,
      },
    })
  })
})

Cypress.Commands.overwrite('login', (_originalFn, username, password) => {
  const credentials = {
    username: username || Cypress.env('adminUsername') || 'admin',
    password: password || Cypress.env('adminPassword') || 'admin123',
  }

  return cy
    .request({
      method: 'GET',
      url: `${API_URL}/api/v1/auth/captcha/generate`,
    })
    .then((captchaResponse) => {
      expect(captchaResponse.status).to.eq(200)
      const captcha = captchaResponse.body?.data || {}

      cy.intercept('GET', CAPTCHA_API_PATTERN, {
        statusCode: 200,
        body: {
          code: 200,
          data: {
            captcha_id: captcha.captcha_id,
            code: captcha.code,
          },
        },
      }).as('captchaForLogin')

      cy.visit('/login')
      cy.wait('@captchaForLogin')
      cy.get('.el-tabs__item').contains('账号登录').click()
      cy.get('input[placeholder*="账号"]')
        .filter(':visible')
        .first()
        .clear()
        .type(credentials.username)
      cy.get('input[placeholder*="密码"]')
        .filter(':visible')
        .first()
        .clear()
        .type(credentials.password)
      cy.get('input[placeholder*="验证码"]')
        .filter(':visible')
        .first()
        .clear()
        .type(String(captcha.code))
      cy.get('button').contains('登录').click()
      cy.url({ timeout: 10000 }).should('include', '/home')
    })
})
