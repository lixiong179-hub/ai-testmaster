describe('全流程操作验证测试', () => {
  beforeEach(() => {
    cy.loginByApi()
  })

  it('登录系统', () => {
    cy.visit('/home/project')
    cy.url().should('include', '/home/project')
    cy.contains('.card-title', '项目列表').should('be.visible')
  })

  it('项目中心可访问并展示创建入口', () => {
    cy.visit('/home/project')
    cy.contains('button', '创建项目').should('be.visible')
    cy.get('.project-table').should('exist')
  })

  it('资源中心可访问', () => {
    cy.visit('/home/requirement')
    cy.url().should('include', '/home/requirement')
    cy.contains('资源中心').should('exist')
  })

  it('测试资产可访问', () => {
    cy.visit('/home/case')
    cy.url().should('include', '/home/case')
    cy.contains('测试用例列表').should('be.visible')
  })

  it('AI生成页面可访问', () => {
    cy.visit('/home/case/ai-generate')
    cy.url().should('include', '/home/case/ai-generate')
    cy.contains('新增用例生成').should('be.visible')
  })

  it('执行中心可访问', () => {
    cy.visit('/home/task')
    cy.url().should('include', '/home/task')
    cy.contains(/执行中心|测试任务列表/).should('be.visible')
  })

  it('报告中心可访问', () => {
    cy.visit('/home/report')
    cy.url().should('include', '/home/report')
    cy.contains('报告中心').should('exist')
  })

  it('验证导航菜单和权限退出', () => {
    cy.visit('/home/project')
    cy.get('.sidebar-menu').should('be.visible')
    cy.get('.user-info').click()
    cy.contains('.el-dropdown-menu__item', '退出登录').click()
    cy.url().should('include', '/login')
  })
})
