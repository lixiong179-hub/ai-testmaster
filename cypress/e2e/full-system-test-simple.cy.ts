describe('AI TestMaster 全流程系统测试', () => {
  const timestamp = Date.now()
  const project1Name = `测试项目1_${timestamp}`
  const project2Name = `测试项目2_${timestamp}`
  const API_URL = Cypress.env('apiUrl') || 'http://127.0.0.1:8000'
  let authToken = ''
  let project1Id = 0
  let project2Id = 0

  const authHeaders = () => ({ Authorization: `Bearer ${authToken}` })
  const findProjectIdByName = (name: string) =>
    cy
      .request({
        method: 'GET',
        url: `${API_URL}/api/v1/project/list?page=1&page_size=1000`,
        headers: authHeaders(),
      })
      .then((response) => {
        expect(response.status).to.eq(200)
        const items = response.body.data?.items || []
        const project = items.find(
          (item: { id?: number; project_id?: number; name?: string }) => item.name === name
        )
        expect(project, `project ${name}`).to.exist
        return Number(project.id || project.project_id)
      })

  before(() => {
    cy.loginByApi().then(() => {
      authToken = String(Cypress.env('authToken') || '')
    })
  })

  after(() => {
    ;[project1Id, project2Id].forEach((projectId) => {
      if (!projectId || !authToken) return
      cy.request({
        method: 'DELETE',
        url: `${API_URL}/api/v1/project/${projectId}`,
        headers: authHeaders(),
        failOnStatusCode: false,
      })
    })
  })

  describe('步骤1: 登录系统', () => {
    it('应该成功登录并跳转到首页', () => {
      cy.login()
      cy.url().should('include', '/home')
    })
  })

  describe('步骤2: 创建项目1', () => {
    it('应该成功创建项目1', () => {
      cy.request({
        method: 'POST',
        url: `${API_URL}/api/v1/project`,
        headers: authHeaders(),
        body: {
          name: project1Name,
          description: '这是测试项目1的描述，用于全流程验证',
          project_type: 'web',
        },
      }).then((response) => {
        expect(response.status).to.eq(200)
        findProjectIdByName(project1Name).then((id) => {
          project1Id = id
          expect(project1Id).to.be.greaterThan(0)
          cy.request({
            method: 'GET',
            url: `${API_URL}/api/v1/project/${project1Id}`,
            headers: authHeaders(),
          }).then((detailResponse) => {
            expect(detailResponse.status).to.eq(200)
            expect(detailResponse.body.data.name).to.eq(project1Name)
          })
        })
      })
    })
  })

  describe('步骤3: 项目1 - 查看详情', () => {
    it('应该能够查看项目1详情', () => {
      cy.loginByApi()
      cy.visit(`/home/project/detail?id=${project1Id}`)
      cy.contains('项目详情').should('be.visible')
      cy.contains(project1Name).should('be.visible')
    })
  })

  describe('步骤4: 创建项目2', () => {
    it('应该成功创建项目2', () => {
      cy.request({
        method: 'POST',
        url: `${API_URL}/api/v1/project`,
        headers: authHeaders(),
        body: {
          name: project2Name,
          description: '这是测试项目2的描述，用于多项目隔离验证',
          project_type: 'web',
        },
      }).then((response) => {
        expect(response.status).to.eq(200)
        findProjectIdByName(project2Name).then((id) => {
          project2Id = id
          expect(project2Id).to.be.greaterThan(0)
          cy.request({
            method: 'GET',
            url: `${API_URL}/api/v1/project/${project2Id}`,
            headers: authHeaders(),
          }).then((detailResponse) => {
            expect(detailResponse.status).to.eq(200)
            expect(detailResponse.body.data.name).to.eq(project2Name)
          })
        })
      })
    })
  })

  describe('步骤5: 验证多项目隔离', () => {
    it('项目1和项目2应该独立存在', () => {
      cy.request({
        method: 'GET',
        url: `${API_URL}/api/v1/project/${project1Id}`,
        headers: authHeaders(),
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.data.name).to.eq(project1Name)
      })
      cy.request({
        method: 'GET',
        url: `${API_URL}/api/v1/project/${project2Id}`,
        headers: authHeaders(),
      }).then((response) => {
        expect(response.status).to.eq(200)
        expect(response.body.data.name).to.eq(project2Name)
      })
    })

    it('项目1详情应该显示正确的项目名称', () => {
      cy.loginByApi()
      cy.visit(`/home/project/detail?id=${project1Id}`)
      cy.contains(project1Name).should('be.visible')
      cy.contains(project2Name).should('not.exist')
    })

    it('项目2详情应该显示正确的项目名称', () => {
      cy.loginByApi()
      cy.visit(`/home/project/detail?id=${project2Id}`)
      cy.contains(project2Name).should('be.visible')
      cy.contains(project1Name).should('not.exist')
    })
  })

  describe('步骤6: 验证权限控制', () => {
    it('清除token后应该无法访问项目页面', () => {
      cy.visit('/home/project')
      cy.url().should('include', '/login')
    })

    it('未登录时访问API应该返回401', () => {
      cy.request({
        method: 'GET',
        url: `${API_URL}/api/v1/project/list`,
        headers: { Authorization: 'Bearer invalid_token' },
        failOnStatusCode: false,
      }).then((response) => {
        expect(response.status).to.be.oneOf([401, 422])
      })
    })
  })

  describe('步骤7: 重新登录并清理', () => {
    it('应该能够重新登录', () => {
      cy.login()
      cy.url().should('include', '/home')
    })

    it('应该能够删除测试项目', () => {
      cy.request({
        method: 'DELETE',
        url: `${API_URL}/api/v1/project/${project1Id}`,
        headers: authHeaders(),
        failOnStatusCode: false,
      })
        .its('status')
        .should('be.oneOf', [200, 404])
      cy.request({
        method: 'DELETE',
        url: `${API_URL}/api/v1/project/${project2Id}`,
        headers: authHeaders(),
        failOnStatusCode: false,
      })
        .its('status')
        .should('be.oneOf', [200, 404])
    })
  })
})
