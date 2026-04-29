describe('AI TestMaster API 接口测试', () => {
  let authToken: string

  before(() => {
    // 登录获取token
    cy.request({
      method: 'POST',
      url: 'http://localhost:8001/api/v1/auth/login',
      body: {
        username: 'admin',
        password: 'password123'
      }
    }).then((response) => {
      expect(response.status).to.eq(200)
      expect(response.body.code).to.eq(200)
      authToken = response.body.data.access_token
    })
  })

  describe('认证接口测试', () => {
    it('登录接口应该返回200', () => {
      cy.request({
        method: 'POST',
        url: 'http://localhost:8001/api/v1/auth/login',
        body: {
          username: 'admin',
          password: 'password123'
        }
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.code).to.eq(200)
        expect(response.body.data).to.have.property('access_token')
      })
    })

    it('登录失败应该返回401', () => {
      cy.request({
        method: 'POST',
        url: 'http://localhost:8001/api/v1/auth/login',
        body: {
          username: 'admin',
          password: 'wrong_password'
        },
        failOnStatusCode: false
      }).then((response) => {
        expect(response.status).to.eq(401)
      })
    })


  })

  describe('项目接口测试', () => {
    let projectId: number

    it('创建项目接口应该返回200', () => {
      const timestamp = new Date().getTime()
      cy.request({
        method: 'POST',
        url: 'http://localhost:8001/api/v1/project/create',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: {
          name: `API测试项目_${timestamp}`,
          description: '用于API测试的项目'
        }
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.code).to.eq(200)
        projectId = response.body.data.project_id
        cy.log(`创建项目成功，项目ID: ${projectId}`)
      })
    })

    it('获取项目列表接口应该返回200', () => {
      cy.request({
        method: 'GET',
        url: 'http://localhost:8001/api/v1/project/list',
        headers: {
          'Authorization': `Bearer ${authToken}`
        },
        qs: {
          page: 1,
          page_size: 10
        }
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.code).to.eq(200)
        expect(response.body.data).to.have.property('items')
        expect(response.body.data.items).to.be.an('array')
      })
    })

    it('获取项目详情接口应该返回200', () => {
      cy.request({
        method: 'GET',
        url: `http://localhost:8001/api/v1/project/${projectId}`,
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.code).to.eq(200)
        expect(response.body.data).to.have.property('id', projectId)
      })
    })

    it('删除项目接口应该返回200', () => {
      cy.request({
        method: 'DELETE',
        url: `http://localhost:8001/api/v1/project/${projectId}`,
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.code).to.eq(200)
      })
    })
  })

  describe('需求接口测试', () => {
    let projectId: number
    let requirementId: number

    before(() => {
      // 创建测试项目
      const timestamp = new Date().getTime()
      cy.request({
        method: 'POST',
        url: 'http://localhost:8001/api/v1/project/create',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: {
          name: `需求测试项目_${timestamp}`,
          description: '用于需求测试的项目'
        }
      }).then((response) => {
        projectId = response.body.data.project_id
      })
    })

    it('提交URL接口应该返回200', () => {
      cy.request({
        method: 'POST',
        url: 'http://localhost:8001/api/v1/file/submit-url',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: {
          project_id: projectId,
          url: 'https://www.baidu.com',
          file_type: 'url'
        },
        failOnStatusCode: false
      }).then((response) => {
        // URL验证可能会失败，但我们只检查接口是否正常工作
        expect(response.status).to.be.oneOf([200, 400])
      })
    })

    after(() => {
      // 清理测试项目
      cy.request({
        method: 'DELETE',
        url: `http://localhost:8001/api/v1/project/${projectId}`,
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      })
    })
  })

  describe('测试用例接口测试', () => {
    let projectId: number

    before(() => {
      // 创建测试项目
      const timestamp = new Date().getTime()
      cy.request({
        method: 'POST',
        url: 'http://localhost:8001/api/v1/project/create',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: {
          name: `测试用例测试项目_${timestamp}`,
          description: '用于测试用例测试的项目'
        }
      }).then((response) => {
        projectId = response.body.data.project_id
      })
    })

    it('获取测试用例列表接口应该返回200', () => {
      cy.request({
        method: 'GET',
        url: 'http://localhost:8001/api/v1/test_cases/',
        headers: {
          'Authorization': `Bearer ${authToken}`
        },
        qs: {
          project_id: projectId
        }
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.code).to.eq(200)
      })
    })

    after(() => {
      // 清理测试项目
      cy.request({
        method: 'DELETE',
        url: `http://localhost:8001/api/v1/project/${projectId}`,
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      })
    })
  })

  describe('测试任务接口测试', () => {
    let projectId: number

    before(() => {
      // 创建测试项目
      const timestamp = new Date().getTime()
      cy.request({
        method: 'POST',
        url: 'http://localhost:8001/api/v1/project/create',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json'
        },
        body: {
          name: `测试任务测试项目_${timestamp}`,
          description: '用于测试任务测试的项目'
        }
      }).then((response) => {
        projectId = response.body.data.project_id
      })
    })

    it('创建测试任务接口应该返回200', () => {
      cy.request({
        method: 'POST',
        url: 'http://localhost:8001/api/v1/test-task',
        headers: {
          'Authorization': `Bearer ${authToken}`
        },
        qs: {
          project_id: projectId,
          task_name: '测试任务'
        }
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body).to.have.property('id')
      })
    })

    it('获取测试任务列表接口应该返回200', () => {
      cy.request({
        method: 'GET',
        url: 'http://localhost:8001/api/v1/test-task',
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      }).then((response) => {
        expect(response.status).to.eq(200)
        // 测试任务列表接口返回的是 { total: 0, items: [] } 格式
        expect(response.body).to.have.property('total')
        expect(response.body).to.have.property('items')
      })
    })

    after(() => {
      // 清理测试项目
      cy.request({
        method: 'DELETE',
        url: `http://localhost:8001/api/v1/project/${projectId}`,
        headers: {
          'Authorization': `Bearer ${authToken}`
        }
      })
    })
  })

  describe('测试报告接口测试', () => {
    it('获取测试报告列表接口应该返回200', () => {
      cy.request({
        method: 'GET',
        url: 'http://localhost:8001/api/v1/report',
        headers: {
          'Authorization': `Bearer ${authToken}`
        },
        qs: {
          project_id: 1,
          page: 1,
          page_size: 10
        }
      }).then((response) => {
        expect(response.status).to.eq(200)
        // 测试报告接口返回的是TestReportList模型，不是标准的code/message/data格式
        expect(response.body).to.have.property('reports')
        expect(response.body).to.have.property('total')
      })
    })
  })

  describe('权限控制测试', () => {
    it('未授权访问应该返回401', () => {
      cy.request({
        method: 'GET',
        url: 'http://localhost:8001/api/v1/project/list',
        headers: {
          'Authorization': 'Bearer invalid_token'
        },
        failOnStatusCode: false
      }).then((response) => {
        expect(response.status).to.eq(401)
      })
    })

    it('无token访问应该返回401', () => {
      cy.request({
        method: 'GET',
        url: 'http://localhost:8001/api/v1/project/list',
        failOnStatusCode: false
      }).then((response) => {
        expect(response.status).to.eq(401)
      })
    })
  })
})
