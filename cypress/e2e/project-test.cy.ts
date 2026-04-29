describe('项目功能测试', () => {
  it('应该能够访问项目列表页面（带认证）', () => {
    // 先通过API登录获取token
    cy.request({
      method: 'POST',
      url: 'http://localhost:8001/api/v1/auth/login',
      body: {
        username: 'admin',
        password: 'password123',
      },
    }).then((response) => {
      cy.log('登录响应:', JSON.stringify(response.body))
      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(200)
      const token = response.body.data.access_token
      cy.log('获取到token:', token)

      // 设置token到localStorage
      cy.window().then((win) => {
        win.localStorage.setItem('token', token)
        cy.log('已设置token到localStorage')
      })
    })

    // 访问项目页面
    cy.visit('/home/project')
    cy.wait(3000)

    // 检查当前URL
    cy.url().then((url) => {
      cy.log('当前URL:', url)
    })

    // 验证页面加载成功
    cy.contains('项目列表').should('be.visible')
  })
})
