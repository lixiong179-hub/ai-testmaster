describe('登录API测试', () => {
  it('测试登录API功能', () => {
    cy.request({
      method: 'POST',
      url: 'http://127.0.0.1:8000/api/v1/auth/login',
      body: {
        username: 'admin',
        password: 'admin123',
      },
      headers: {
        'Content-Type': 'application/json',
      },
    }).then((response) => {
      cy.log('登录API响应状态码:', response.status)
      cy.log('登录API响应数据:', response.body)

      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(200)
      expect(response.body.data).to.have.property('access_token')

      const token = response.body.data.access_token
      expect(token).to.not.be.empty
      cy.log('获取到的token:', token)
    })
  })

  it('测试登录API - 错误的密码', () => {
    cy.request({
      method: 'POST',
      url: 'http://127.0.0.1:8000/api/v1/auth/login',
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

      expect(response.status).to.be.oneOf([400, 401])
    })
  })
})
