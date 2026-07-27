describe('项目功能测试', () => {
  it('应该能够访问项目列表页面（带认证）', () => {
    cy.request({
      method: 'POST',
      url: 'http://127.0.0.1:8000/api/v1/auth/login',
      body: {
        username: 'admin',
        password: 'admin123',
      },
    }).then((response) => {
      cy.log('登录响应:', JSON.stringify(response.body))
      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(200)
      const token = response.body.data.access_token
      cy.log('获取到token:', token)

      cy.window().then((win) => {
        win.localStorage.setItem('token', token)
        cy.log('已设置token到localStorage')
      })
    })

    cy.visit('/home/project')
    cy.wait(3000)

    cy.url().then((url) => {
      cy.log('当前URL:', url)
    })

    cy.contains('项目列表').should('be.visible')
  })
})
