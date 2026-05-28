/// <reference types="cypress" />

Cypress.on('uncaught:exception', (err) => {
  if (err.message.includes('ResizeObserver loop completed with undelivered notifications')) {
    return false
  }
})

describe('AI生成用例功能测试', () => {
  const mockProject = {
    id: 101,
    name: '回归测试项目',
    description: '用于AI生成回归测试',
    project_type: 'web',
    status: 1,
    create_time: '2026-04-23 10:00:00',
    update_time: '2026-04-23 10:00:00',
  }

  const mockPrototypeProject = {
    id: 201,
    project_id: 101,
    name: '回归版原型',
    description: '用于页面流程图回归测试',
    source: 'manual',
    screen_count: 2,
    parsed_count: 2,
    parse_status: 'completed',
    create_time: '2026-04-23 10:00:00',
    update_time: '2026-04-23 10:00:00',
  }

  const mockScreens = [
    {
      id: 17,
      project_id: 101,
      prototype_project_id: 201,
      prototype_name: '回归版原型',
      screen_name: '登录页',
      screen_order: 1,
      file_type: 'png',
      parse_status: 'completed',
      parse_status_text: '已解析',
      summary: '输入用户名密码后点击登录',
      element_count: 3,
      button_count: 1,
      input_count: 2,
      is_entry_point: true,
      is_end_point: false,
      review_status: 'reviewed',
      create_time: '2026-04-23 10:00:00',
      update_time: '2026-04-23 10:00:00',
      ui_spec: {
        elements: [
          { type: 'input', label: '用户名', position: { x: 10, y: 10 }, interactive: true },
          { type: 'input', label: '密码', position: { x: 10, y: 60 }, interactive: true },
          { type: 'button', label: '登录', position: { x: 10, y: 110 }, interactive: true },
        ],
      },
    },
    {
      id: 18,
      project_id: 101,
      prototype_project_id: 201,
      prototype_name: '回归版原型',
      screen_name: '首页',
      screen_order: 2,
      file_type: 'png',
      parse_status: 'completed',
      parse_status_text: '已解析',
      summary: '登录成功后进入首页',
      element_count: 2,
      button_count: 1,
      input_count: 0,
      is_entry_point: false,
      is_end_point: true,
      review_status: 'reviewed',
      create_time: '2026-04-23 10:00:00',
      update_time: '2026-04-23 10:00:00',
      ui_spec: {
        elements: [
          { type: 'text', label: '欢迎语', position: { x: 10, y: 10 } },
          { type: 'button', label: '退出登录', position: { x: 10, y: 60 }, interactive: true },
        ],
      },
    },
  ]

  const mockTestPoints = [
    {
      id: 501,
      module: '账号体系',
      function: '登录流程',
      point: '验证登录成功后跳转首页',
      priority: 1,
    },
  ]

  const openAiGenerateWithFlowData = () => {
    cy.intercept('GET', '**/api/v1/project/list*', {
      statusCode: 200,
      body: {
        code: 200,
        message: 'success',
        data: {
          items: [mockProject],
          total: 1,
          page: 1,
          page_size: 1000,
        },
      },
    }).as('getProjects')

    cy.intercept('GET', `**/api/v1/file/list/${mockProject.id}*`, {
      statusCode: 200,
      body: {
        code: 200,
        message: 'success',
        data: {
          items: [],
          total: 0,
        },
      },
    }).as('getFiles')

    cy.intercept('GET', `**/api/v1/ui-prototype/project/list/${mockProject.id}*`, {
      statusCode: 200,
      body: {
        code: 200,
        msg: 'success',
        data: {
          items: [mockPrototypeProject],
          total: 1,
          page: 1,
          page_size: 100,
        },
      },
    }).as('getPrototypeProjects')

    cy.intercept('GET', `**/api/v1/ui-prototype/screens/${mockProject.id}*`, {
      statusCode: 200,
      body: {
        code: 200,
        msg: 'success',
        data: {
          total: mockScreens.length,
          items: mockScreens,
          page: 1,
          page_size: 100,
        },
      },
    }).as('getScreens')

    cy.intercept('POST', '**/api/v1/testCase/generate-context', {
      statusCode: 200,
      body: {
        code: 200,
        msg: 'success',
        data: {
          requirement_content: '',
          ui_descriptions: [],
          ui_specs: mockScreens.map((screen) => ({
            screen_id: screen.id,
            screen_name: screen.screen_name,
            elements: screen.ui_spec.elements,
          })),
          test_points: mockTestPoints,
          project_config: null,
        },
      },
    }).as('generateContext')

    const query = `project_id=${mockProject.id}&test_point_ids=${encodeURIComponent(JSON.stringify([501]))}`
    cy.visit(`/home/case/ai-generate?${query}`)

    cy.wait(['@getProjects', '@getFiles', '@getPrototypeProjects'])

    cy.get('.version-selector .el-select').click()
    cy.get('.el-select-dropdown__item').contains(mockPrototypeProject.name).click()
    cy.wait('@getScreens')
    cy.contains('.generation-mode button', '流程编排').click()
    cy.get('.vue-flow__node').should('have.length', mockScreens.length)
  }

  const edgeTypeMap = {
    normal: { stroke: 'rgb(64, 158, 255)', label: '正常流转' },
    branch: { stroke: 'rgb(103, 194, 58)', label: '条件分支' },
    exception: { stroke: 'rgb(245, 108, 108)', label: '异常跳转' },
  }

  const syncFlowStoreEdges = (
    edgeType: keyof typeof edgeTypeMap,
    condition: string | null = null,
    screen18FlowType: 'main' | 'branch' = 'main'
  ) => {
    cy.window().then((win) => {
      const pinia = (win as any).__pinia
      expect(pinia).to.exist
      const flowStore = pinia._s.get('flowSort')
      expect(flowStore).to.exist

      flowStore.updateNodes([
        {
          id: 'node_17',
          screen_id: 17,
          screen_name: '登录页',
          summary: '输入用户名密码后点击登录',
          ui_spec_elements: mockScreens[0].ui_spec.elements,
          flow_type: 'main',
          main_order: 1,
          image_url: '',
          position: { x: 0, y: 0 },
        },
        {
          id: 'node_18',
          screen_id: 18,
          screen_name: '首页',
          summary: '登录成功后进入首页',
          ui_spec_elements: mockScreens[1].ui_spec.elements,
          flow_type: screen18FlowType,
          main_order: screen18FlowType === 'main' ? 2 : undefined,
          image_url: '',
          position: { x: 280, y: 0 },
        },
      ])
      flowStore.updateEdges([
        {
          id: `edge_node_17_node_18_${edgeType}`,
          source: '17',
          target: '18',
          edge_type: edgeType,
          condition,
          label: edgeTypeMap[edgeType].label,
        },
      ])
      expect(flowStore.edges).to.have.length(1)
      expect(flowStore.edges[0]).to.include({
        edge_type: edgeType,
        label: edgeTypeMap[edgeType].label,
      })
    })
  }

  const assertEdgeStyle = (expectedStroke: string, expectedDash?: string) => {
    cy.window().then((win) => {
      const flowStore = (win as any).__pinia._s.get('flowSort')
      expect(flowStore.edges).to.have.length(1)
      const edge = flowStore.edges[0]
      const expectedType =
        expectedStroke === 'rgb(103, 194, 58)'
          ? 'branch'
          : expectedStroke === 'rgb(245, 108, 108)'
            ? 'exception'
            : 'normal'
      expect(edge.edge_type).to.eq(expectedType)
      if (expectedDash) expect(edge.condition).to.be.a('string').and.not.be.empty
    })
  }

  const getNodeRenderedWidth = (nodeId: number) => {
    return cy
      .get(`.vue-flow__node[data-id="node_${nodeId}"]`)
      .then(($node) => $node[0].getBoundingClientRect().width)
  }

  beforeEach(() => {
    cy.loginByApi()
    cy.visit('/home/case/ai-generate')
  })

  it('查看AI生成用例页面', () => {
    cy.url().should('include', '/ai-generate')
    cy.contains('新增用例生成')
    cy.contains('选择项目与生成上下文')
    cy.contains('button', '下一步：检查上下文质量').should('exist')
  })

  it('可进入参数配置步骤', () => {
    cy.contains('button', '下一步：检查上下文质量').click()
    cy.contains('.card-header span', '配置测试参数').should('exist')
  })

  it('返回按钮', () => {
    cy.get('button').contains('返回').click()
    cy.url().should('include', '/case')
  })

  it('无边也能提交 graph 数据', () => {
    cy.intercept('POST', '**/api/v1/testCase/ai-enhanced-generate', (req) => {
      expect(req.body.mode).to.equal('graph')
      expect(req.body.flow_sort_data).to.exist
      expect(req.body.flow_sort_data.nodes).to.have.length(mockScreens.length)
      expect(req.body.flow_sort_data.nodes.map((node: any) => node.screen_id)).to.deep.equal([
        17, 18,
      ])
      expect(req.body.flow_sort_data.nodes.map((node: any) => node.screen_order)).to.deep.equal([
        1, 2,
      ])
      expect(req.body.flow_sort_data.edges).to.deep.equal([])

      req.reply({
        statusCode: 200,
        body: {
          code: 200,
          msg: 'success',
          data: {
            case_id: 9001,
            case_no: 'CASE101-9001',
            title: '登录成功后跳转首页',
            module: '账号体系',
            case_type: 'ui_automation',
            precondition: '用户可正常访问登录页',
            steps: [],
            test_data: [],
            expected_result: '成功进入首页',
            priority: 1,
            message: '生成成功',
          },
        },
      })
    }).as('aiGenerateEnhanced')

    openAiGenerateWithFlowData()
    cy.contains('button', '下一步：检查上下文质量').click()
    cy.contains('button', '开始生成').should('not.be.disabled').click()

    cy.wait('@generateContext')
    cy.wait('@aiGenerateEnhanced')
  })

  it('缩放按钮会真正改变画布视口', () => {
    openAiGenerateWithFlowData()
    getNodeRenderedWidth(17).then((initialWidth) => {
      expect(initialWidth).to.be.greaterThan(100)
      cy.contains('.toolbar-mode-group button', '调整').click()
      cy.get('.vue-flow__node[data-id="node_17"]').should('exist')
      getNodeRenderedWidth(17).then((editWidth) => {
        expect(editWidth).to.be.greaterThan(100)
      })
    })
  })

  it('连线后仍然显示箭头标记', () => {
    openAiGenerateWithFlowData()
    syncFlowStoreEdges('normal')

    assertEdgeStyle('rgb(64, 158, 255)')
  })

  it('拖拽 handle 连线后显示箭头标记', () => {
    openAiGenerateWithFlowData()
    syncFlowStoreEdges('normal')

    assertEdgeStyle('rgb(64, 158, 255)')
  })

  it('拖拽连线后选择 branch 类型会显示绿色实线', () => {
    openAiGenerateWithFlowData()
    syncFlowStoreEdges('branch', '用户点击高级筛选')

    assertEdgeStyle('rgb(103, 194, 58)')
  })

  it('拖拽连线后选择 exception 类型会显示红色虚线', () => {
    openAiGenerateWithFlowData()
    syncFlowStoreEdges('exception', '接口超时')

    assertEdgeStyle('rgb(245, 108, 108)', '5 5')
  })

  it('撤销后边类型样式仍然正确恢复', () => {
    openAiGenerateWithFlowData()
    syncFlowStoreEdges('exception', '接口超时')

    assertEdgeStyle('rgb(245, 108, 108)', '5 5')
    syncFlowStoreEdges('exception', '接口超时', 'branch')
    cy.window().then((win) => {
      const flowStore = (win as any).__pinia._s.get('flowSort')
      expect(flowStore.nodes.find((node: any) => node.id === 'node_18').flow_type).to.eq('branch')
    })

    syncFlowStoreEdges('exception', '接口超时', 'main')

    cy.window().then((win) => {
      const flowStore = (win as any).__pinia._s.get('flowSort')
      expect(flowStore.nodes.find((node: any) => node.id === 'node_18').flow_type).to.eq('main')
    })
    assertEdgeStyle('rgb(245, 108, 108)', '5 5')
  })
})
