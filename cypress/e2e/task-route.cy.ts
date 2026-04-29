describe('任务路由可达性', () => {
  it('访问 /home/task 会落到任务列表', () => {
    cy.visit('/home/task', {
      onBeforeLoad(win) {
        win.localStorage.setItem('token', 'e2e-token')
      },
    })
    cy.url().should('include', '/home/task')
  })
})
