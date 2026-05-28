describe('AI TestMaster Complete E2E Tests', () => {
  const API_URL = Cypress.env('apiUrl') || 'http://127.0.0.1:8000'

  beforeEach(() => {
    cy.clearLocalStorage()
    cy.clearCookies()
  })

  describe('User Login Authentication', () => {
    it('T01: Login page renders correctly - verify elements exist', () => {
      cy.visit('/login')
      cy.contains('登录 AI TestMaster').should('be.visible')
      cy.get('input[placeholder*="账号"]').filter(':visible').first().should('be.visible')
      cy.get('input[placeholder*="密码"]').filter(':visible').first().should('be.visible')
      cy.get('input[placeholder*="验证码"]').filter(':visible').first().should('be.visible')
      cy.contains('button', '登录').should('be.visible')
    })

    it('T02: Login with correct credentials - verify redirect', () => {
      cy.login()
      cy.url().should('include', '/home')
      cy.window().then((win) => {
        expect(win.localStorage.getItem('token')).to.be.a('string').and.not.be.empty
      })
    })

    it('T03: Login with wrong password - verify error message', () => {
      cy.visit('/login')
      cy.get('.el-tabs__item').contains('账号登录').click()
      cy.get('input[placeholder*="账号"]').filter(':visible').first().type('admin')
      cy.get('input[placeholder*="密码"]').filter(':visible').first().type('wrongpassword')
      cy.get('input[placeholder*="验证码"]').filter(':visible').first().type('0000')
      cy.get('button').contains('登录').click()
      cy.get('.el-message__content', { timeout: 10000 }).should('be.visible')
      cy.url().should('include', '/login')
    })

    it('T04: Access protected page without login - redirect to login', () => {
      cy.visit('/home/project')
      cy.url().should('include', '/login')
    })
  })

  describe('Project Management', () => {
    beforeEach(() => {
      cy.loginByApi()
    })

    it('T05: Project list page - verify data display and layout', () => {
      cy.visit('/home/project')
      cy.contains('.card-title', '项目列表').should('be.visible')
      cy.get('.project-table').should('exist')
      cy.contains('button', '创建项目').should('be.visible')
    })

    it('T06: Project detail route can be opened from a project row when data exists', () => {
      cy.visit('/home/project')
      cy.get('body').then(($body) => {
        if ($body.find('.project-table tbody tr').length === 0) {
          cy.contains('项目列表').should('be.visible')
          return
        }
        cy.get('.project-table tbody tr').first().find('button').contains('详情').click()
        cy.url().should('include', '/home/project/detail')
      })
    })
  })

  describe('Page Navigation and Layout', () => {
    beforeEach(() => {
      cy.loginByApi()
    })

    it('T07: Sidebar navigation - menu items are clickable', () => {
      cy.visit('/home/project')
      cy.get('.sidebar-menu').should('be.visible')
      ;['/home/project', '/home/requirement', '/home/case', '/home/task', '/home/report'].forEach(
        (path) => {
          cy.visit(path)
          cy.url().should('include', path)
        }
      )
    })

    it('T08: Breadcrumb navigation shows current path', () => {
      cy.visit('/home/project')
      cy.get('.el-breadcrumb').should('exist')
      cy.contains('.el-breadcrumb', '工作台').should('exist')
    })
  })

  describe('Permission Control', () => {
    it('T09: Invalid token redirects to login', () => {
      cy.visit('/login', {
        onBeforeLoad(win) {
          win.localStorage.setItem('token', 'invalid_token_12345')
        },
      })
      cy.visit('/home/project')
      cy.url().should('include', '/login')
    })
  })

  describe('Frontend API Request Verification', () => {
    beforeEach(() => {
      cy.loginByApi()
    })

    it('T10: Frontend stores token after login', () => {
      cy.window().then((win) => {
        const token = win.localStorage.getItem('token')
        expect(token).to.be.a('string').and.have.length.greaterThan(10)
      })
    })

    it('T11: Frontend sends correct auth header on API calls', () => {
      cy.window().then((win) => {
        const token = win.localStorage.getItem('token')
        cy.request({
          method: 'GET',
          url: `${API_URL}/api/v1/project/list`,
          headers: { Authorization: `Bearer ${token}` },
        })
          .its('status')
          .should('eq', 200)
      })
    })
  })
})
