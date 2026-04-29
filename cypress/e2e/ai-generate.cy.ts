describe('AI生成用例功能测试', () => {
  beforeEach(() => {
    cy.login()
    cy.navigateToAIGenerate()
  })

  it('查看AI生成用例页面', () => {
    cy.url().should('include', '/ai-generate')
    cy.contains('AI生成测试用例')
    cy.get('textarea[placeholder*="测试场景"]').should('exist')
  })

  it('生成测试用例', () => {
    cy.get('textarea[placeholder*="测试场景"]').type('测试用户登录功能')
    cy.get('.el-select').contains('请选择').click()
    cy.get('.el-select-dropdown__item').contains('功能测试').click()
    cy.get('button').contains('开始生成').click()
    cy.wait(5000)
    cy.contains('AI生成测试用例')
  })

  it('场景示例点击', () => {
    cy.get('.tip-tag').first().click()
    cy.get('textarea[placeholder*="测试场景"]').should('not.be.empty')
  })

  it('重置表单', () => {
    cy.get('textarea[placeholder*="测试场景"]').type('测试用户登录功能')
    cy.get('button').contains('重置').click()
    cy.get('textarea[placeholder*="测试场景"]').should('be.empty')
  })

  it('返回按钮', () => {
    cy.get('button').contains('返回').click()
    cy.url().should('include', '/case')
  })
})
