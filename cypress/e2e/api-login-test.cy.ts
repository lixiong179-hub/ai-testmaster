describe('登录API测试', () => {
  it('测试登录API功能', () => {
    // 直接调用登录API
    cy.request({
      method: 'POST',
      url: 'http://localhost:8000/api/v1/auth/login',
      body: {
        username: 'admin',
        password: 'password123',
      },
      headers: {
        'Content-Type': 'application/json',
      },
    }).then((response) => {
      cy.log('登录API响应状态码:', response.status)
      cy.log('登录API响应数据:', response.body)

      // 验证登录成功
      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(200)
      expect(response.body.data).to.have.property('access_token')

      // 验证token不为空
      const token = response.body.data.access_token
      expect(token).to.not.be.empty
      cy.log('获取到的token:', token)
    })
  })

  it('测试登录API - 错误的密码', () => {
    // 直接调用登录API，使用错误的密码
    cy.request({
      method: 'POST',
      url: 'http://localhost:8000/api/v1/auth/login',
      body: {
        username: 'admin',
        password: 'wrongpassword',
      },
      headers: {
        'Content-Type': 'application/json',
      },
      failOnStatusCode: false,
    }).then((response) => {
      cy.log('登录API响应状态码:', response.status)
      cy.log('登录API响应数据:', response.body)

      // 验证登录失败
      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(401)
    })
  })
})
