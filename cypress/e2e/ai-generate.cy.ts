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
      body: [mockPrototypeProject],
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
    cy.get('.vue-flow__node').should('have.length', mockScreens.length)
  }

  const connectFirstTwoFlowNodes = () => {
    cy.get('.flow-sort-editor').then(($editor) => {
      const instance = ($editor[0] as any).__vueParentComponent
      expect(instance).to.exist

      const vm = instance.setupState || instance.ctx
      expect(vm.onConnect).to.be.a('function')
      expect(vm.onEdgeConditionConfirm).to.be.a('function')

      vm.onConnect({ source: 'node_17', target: 'node_18' })
      vm.onEdgeConditionConfirm({
        edge_type: 'normal',
        condition: null,
        label: '正常流转',
      })
    })
  }

  const connectFirstTwoFlowNodesByDrag = () => {
    return cy.window().then((win) => {
      return cy
        .get('.vue-flow__node[data-id="node_17"] .vue-flow__handle.source')
        .should('exist')
        .then(($source) => {
          return cy
            .get('.vue-flow__node[data-id="node_18"] .vue-flow__handle.target')
            .should('exist')
            .then(($target) => {
              const sourceEl = $source[0] as HTMLElement
              const targetEl = $target[0] as HTMLElement
              const paneEl = win.document.querySelector('.vue-flow__pane') as HTMLElement

              expect(paneEl).to.exist

              const sourceRect = sourceEl.getBoundingClientRect()
              const targetRect = targetEl.getBoundingClientRect()
              const startX = sourceRect.left + sourceRect.width / 2
              const startY = sourceRect.top + sourceRect.height / 2
              const endX = targetRect.left + targetRect.width / 2
              const endY = targetRect.top + targetRect.height / 2
              const midX = Math.round((startX + endX) / 2)
              const midY = Math.round((startY + endY) / 2)

              const dispatchPointer = (
                element: Element | Document,
                type: string,
                x: number,
                y: number
              ) => {
                const target = element === win.document ? win.document : (element as Element)
                target.dispatchEvent(
                  new win.PointerEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    pointerId: 1,
                    pointerType: 'mouse',
                    isPrimary: true,
                    clientX: x,
                    clientY: y,
                    button: 0,
                    buttons: type === 'pointerup' ? 0 : 1,
                  })
                )
              }

              const dispatchMouse = (
                element: Element | Document,
                type: string,
                x: number,
                y: number
              ) => {
                const target = element === win.document ? win.document : (element as Element)
                target.dispatchEvent(
                  new win.MouseEvent(type, {
                    bubbles: true,
                    cancelable: true,
                    composed: true,
                    clientX: x,
                    clientY: y,
                    button: 0,
                    buttons: type === 'mouseup' ? 0 : 1,
                  })
                )
              }

              dispatchMouse(sourceEl, 'mousedown', startX, startY)
              dispatchPointer(sourceEl, 'pointerdown', startX, startY)
              dispatchMouse(paneEl, 'mousemove', midX, midY)
              dispatchPointer(paneEl, 'pointermove', midX, midY)
              dispatchPointer(targetEl, 'pointerover', endX, endY)
              dispatchPointer(targetEl, 'pointerenter', endX, endY)
              dispatchMouse(targetEl, 'mouseover', endX, endY)
              dispatchMouse(targetEl, 'mouseenter', endX, endY)
              dispatchMouse(targetEl, 'mousemove', endX, endY)
              dispatchPointer(targetEl, 'pointermove', endX, endY)
              dispatchPointer(win.document, 'pointermove', endX, endY)
              dispatchMouse(win.document, 'mousemove', endX, endY)
              dispatchPointer(targetEl, 'pointerup', endX, endY)
              dispatchMouse(targetEl, 'mouseup', endX, endY)
            })
        })
    })
  }

  const chooseEdgeTypeAndConfirm = (typeLabel: string, conditionText?: string) => {
    cy.contains('.el-dialog__title', '设置连线类型').should('be.visible')
    cy.get('.el-dialog .el-select').click()
    cy.get('.el-select-dropdown__item').contains(typeLabel).click()

    if (conditionText) {
      cy.get('.el-dialog textarea').clear().type(conditionText)
    }

    cy.contains('.el-dialog .el-button', '确认').click()
  }

  const assertEdgeStyle = (expectedStroke: string, expectedDash?: string) => {
    cy.get('.vue-flow__edge').should('have.length', 1)
    cy.get('.vue-flow__edge .vue-flow__edge-path').should(($path) => {
      const path = $path[0] as unknown as SVGPathElement
      const computedStyle = window.getComputedStyle(path)
      const inlineStyle = path.getAttribute('style') || ''

      expect(computedStyle.stroke).to.eq(expectedStroke)
      if (expectedDash) {
        const normalizedStyle = inlineStyle.replace(/\s+/g, ' ')
        const dashPattern = expectedDash.replace(/\s+/g, ', ')
        expect(normalizedStyle).to.include(`stroke-dasharray: ${dashPattern}`)
      } else {
        expect(inlineStyle).to.not.include('stroke-dasharray')
      }
    })
  }

  const changeNodeFlowType = (nodeId: number, flowTypeLabel: string, expectedClass: string) => {
    cy.get(`.vue-flow__node[data-id="node_${nodeId}"] .flow-type-tag`).click()
    cy.get('.el-dropdown__popper:visible .el-dropdown-menu__item').contains(flowTypeLabel).click({
      force: true,
    })
    cy.get(`.vue-flow__node[data-id="node_${nodeId}"] .flow-node-card`).should(
      'have.class',
      expectedClass
    )
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
    cy.contains('AI生成测试用例')
    cy.contains('选择需求来源')
    cy.contains('button', '下一步：配置测试参数').should('exist')
  })

  it('可进入参数配置步骤', () => {
    cy.contains('button', '下一步：配置测试参数').click()
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
    cy.contains('button', '下一步：配置测试参数').click()
    cy.contains('button', '开始生成').should('not.be.disabled').click()

    cy.wait('@generateContext')
    cy.wait('@aiGenerateEnhanced')
  })

  it('缩放按钮会真正改变画布视口', () => {
    openAiGenerateWithFlowData()

    cy.get('.flow-sort-editor .zoom-level')
      .invoke('text')
      .then((text) => {
        const initialZoom = Number.parseInt(text.trim(), 10)
        expect(initialZoom).to.be.greaterThan(0)

        getNodeRenderedWidth(17).then((initialWidth) => {
          cy.get('.flow-sort-editor .zoom-controls .el-button').eq(1).click()
          cy.wait(250)

          cy.get('.flow-sort-editor .zoom-level')
            .invoke('text')
            .then((zoomedText) => {
              const zoomedValue = Number.parseInt(zoomedText.trim(), 10)
              expect(zoomedValue).to.be.greaterThan(initialZoom)
            })

          getNodeRenderedWidth(17).then((zoomedWidth) => {
            expect(zoomedWidth).to.be.greaterThan(initialWidth + 10)
          })

          cy.get('.flow-sort-editor .zoom-controls .el-button').eq(0).click()
          cy.wait(250)

          cy.get('.flow-sort-editor .zoom-level')
            .invoke('text')
            .then((restoredText) => {
              const restoredZoom = Number.parseInt(restoredText.trim(), 10)
              expect(restoredZoom).to.eq(initialZoom)
            })

          getNodeRenderedWidth(17).then((restoredWidth) => {
            expect(Math.abs(restoredWidth - initialWidth)).to.be.lessThan(5)
          })
        })
      })
  })

  it('连线后仍然显示箭头标记', () => {
    openAiGenerateWithFlowData()
    connectFirstTwoFlowNodes()

    cy.get('.vue-flow__edge').should('have.length', 1)
    cy.get('.vue-flow__edge .vue-flow__edge-path')
      .should('have.attr', 'marker-end')
      .and('include', 'url(')
      .and('include', 'arrowclosed')
  })

  it('拖拽 handle 连线后显示箭头标记', () => {
    openAiGenerateWithFlowData()
    connectFirstTwoFlowNodesByDrag()

    chooseEdgeTypeAndConfirm('正常流转')

    cy.get('.vue-flow__edge').should('have.length', 1)
    cy.get('.vue-flow__edge .vue-flow__edge-path')
      .should('have.attr', 'marker-end')
      .and('include', 'url(')
      .and('include', 'arrowclosed')
  })

  it('拖拽连线后选择 branch 类型会显示绿色实线', () => {
    openAiGenerateWithFlowData()
    connectFirstTwoFlowNodesByDrag()
    chooseEdgeTypeAndConfirm('条件分支', '用户点击高级筛选')

    assertEdgeStyle('rgb(103, 194, 58)')
    cy.get('.vue-flow__edge .vue-flow__edge-path')
      .should('have.attr', 'marker-end')
      .and('include', '#67c23a')
  })

  it('拖拽连线后选择 exception 类型会显示红色虚线', () => {
    openAiGenerateWithFlowData()
    connectFirstTwoFlowNodesByDrag()
    chooseEdgeTypeAndConfirm('异常跳转', '接口超时')

    assertEdgeStyle('rgb(245, 108, 108)', '5 5')
    cy.get('.vue-flow__edge .vue-flow__edge-path')
      .should('have.attr', 'marker-end')
      .and('include', '#f56c6c')
  })

  it('撤销后边类型样式仍然正确恢复', () => {
    openAiGenerateWithFlowData()
    connectFirstTwoFlowNodesByDrag()
    chooseEdgeTypeAndConfirm('异常跳转', '接口超时')

    assertEdgeStyle('rgb(245, 108, 108)', '5 5')
    changeNodeFlowType(18, '分支流程', 'flow-type-branch')

    cy.get('.flow-sort-editor .toolbar-actions .action-group .el-button').eq(2).click()
    cy.contains('.el-message', '已撤销').should('exist')

    cy.get('.vue-flow__node[data-id="node_18"] .flow-node-card').should(
      'have.class',
      'flow-type-main'
    )
    assertEdgeStyle('rgb(245, 108, 108)', '5 5')
    cy.get('.vue-flow__edge .vue-flow__edge-path')
      .should('have.attr', 'marker-end')
      .and('include', '#f56c6c')
  })
})
