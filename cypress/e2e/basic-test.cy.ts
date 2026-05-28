describe('基本功能测试', () => {
  it('应该能够访问登录页面', () => {
    cy.visit('/login')
    cy.wait(2000)
    cy.url().should('include', '/login')
    cy.contains('登录').should('be.visible')
  })

  it('应该能够访问首页', () => {
    cy.visit('/')
    cy.wait(2000)
    cy.url().should('include', '/login')
  })
})
