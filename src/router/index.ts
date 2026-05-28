import { createRouter, createWebHistory } from 'vue-router'
import { routes } from './routes'
import { hasPermission } from '@/directives/permission'

const router = createRouter({
  history: createWebHistory(),
  routes,
})

function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return true
    const payload = JSON.parse(atob(parts[1]))
    if (!payload.exp) return false
    return Date.now() >= payload.exp * 1000
  } catch {
    return true
  }
}

router.beforeEach((to, _from, next) => {
  document.title = `${to.meta.title || 'AI TestMaster'} - AI自动化测试平台`
  if (to.meta.requireAuth) {
    const token = localStorage.getItem('token')
    if (!token || isTokenExpired(token)) {
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      next('/login')
      return
    }
    if (to.meta.permission && !hasPermission(to.meta.permission as string)) {
      next('/home/project')
      return
    }
    next()
  } else {
    next()
  }
})

export default router
