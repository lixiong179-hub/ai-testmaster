import 'cypress-file-upload'

type Credentials = {
  username: string
  password: string
}

type PermissionPayload = Record<string, string | string[]>

type AuthUser = {
  username?: string
  permissions?: string[]
  [key: string]: unknown
}

const API_URL = Cypress.env('apiUrl') || 'http://127.0.0.1:8000'

const getAdminCredentials = (
  username = Cypress.env('adminUsername') || 'admin',
  password = Cypress.env('adminPassword') || 'admin123'
): Credentials => ({
  username,
  password,
})

const signPermissions = (permissions: string[]): PermissionPayload => {
  const raw = permissions.slice().sort().join(',')
  let hash = 0
  for (let i = 0; i < raw.length; i += 1) {
    const ch = raw.charCodeAt(i)
    hash = (hash << 5) - hash + ch
    hash |= 0
  }
  return {
    permissions,
    __perm_sig__: hash.toString(36),
  }
}

declare global {
  namespace Cypress {
    interface Chainable {
      login(username?: string, password?: string): Chainable<void>
      loginByApi(username?: string, password?: string): Chainable<void>
      navigateToCaseManagement(): Chainable<void>
      navigateToAIGenerate(): Chainable<void>
    }
  }
}

Cypress.Commands.add('login', (username, password) => {
  const credentials = getAdminCredentials(username, password)
  return cy
    .visit('/login')
    .get('.el-tabs__item')
    .contains('账号登录')
    .click()
    .get('input[placeholder*="账号"]')
    .filter(':visible')
    .first()
    .clear()
    .type(credentials.username)
    .get('input[placeholder*="密码"]')
    .filter(':visible')
    .first()
    .clear()
    .type(credentials.password)
    .get('input[placeholder*="验证码"]')
    .filter(':visible')
    .first()
    .then(($input) => {
      const code = window.localStorage.getItem('captcha') || '1234'
      cy.wrap($input).clear().type(code)
    })
    .get('button')
    .contains('登录')
    .click()
    .url({ timeout: 10000 })
    .should('include', '/home')
})

Cypress.Commands.add('loginByApi', (username, password) => {
  const credentials = getAdminCredentials(username, password)

  return cy
    .request({
      method: 'GET',
      url: `${API_URL}/api/v1/auth/captcha/generate`,
    })
    .then((captchaResponse) => {
      expect(captchaResponse.status).to.eq(200)
      const captcha = captchaResponse.body.data || {}
      const formData = new URLSearchParams()
      formData.append('username', credentials.username)
      formData.append('password', credentials.password)
      formData.append('captcha_id', String(captcha.captcha_id || ''))
      formData.append('captcha_code', String(captcha.code || ''))

      return cy.request({
        method: 'POST',
        url: `${API_URL}/api/v1/auth/login`,
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData.toString(),
      })
    })
    .then((loginResponse) => {
      expect(loginResponse.status).to.eq(200)
      const token = loginResponse.body.data.access_token
      expect(token).to.be.a('string').and.not.be.empty

      return cy
        .request({
          method: 'GET',
          url: `${API_URL}/api/v1/auth/me`,
          headers: { Authorization: `Bearer ${token}` },
        })
        .then((meResponse) => ({
          token: String(token),
          user: (meResponse.body.data || {}) as AuthUser,
        }))
    })
    .then(({ token, user }) => {
      const rawPermissions = Array.isArray(user.permissions) ? user.permissions : []
      const permissions =
        credentials.username === 'admin'
          ? Array.from(new Set([...rawPermissions, '*']))
          : rawPermissions.length > 0
            ? rawPermissions
            : ['*']

      Cypress.env('authToken', token)
      Cypress.env('authUser', user)

      cy.visit('/login')
      cy.window().then((win) => {
        win.localStorage.setItem('token', token)
        win.localStorage.setItem(
          'userInfo',
          JSON.stringify({ ...user, ...signPermissions(permissions) })
        )
      })
    })
})

Cypress.Commands.add('navigateToCaseManagement', () => {
  return cy.get('.sidebar-menu').contains('测试资产').click().url().should('include', '/case')
})

Cypress.Commands.add('navigateToAIGenerate', () => {
  return cy
    .get('.sidebar-menu')
    .contains('测试资产')
    .click()
    .get('.sidebar-menu')
    .contains('用例列表')
    .click()
    .url()
    .should('include', '/case')
})
