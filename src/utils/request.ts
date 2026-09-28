import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios'
import { debounce, throttle } from './debounce'
import { useFlowSortStore } from '@/store/flowSort'
import { ElMessage } from 'element-plus'

// 接口类型超时配置（毫秒）
const TIMEOUT_CONFIG = {
  default: 30000, // 普通接口 30秒
  ai: 180000, // AI接口 3分钟（含重试）
  aiXmindImport: 300000, // XMind AI增强导入 5分钟
  upload: 60000, // 文件上传 60秒
  export: 60000, // 数据导出 60秒
}

// 根据URL判断接口类型并返回对应超时时间
function getTimeoutByUrl(url?: string): number {
  if (!url) return TIMEOUT_CONFIG.default

  const lowerUrl = url.toLowerCase()

  if (lowerUrl.includes('/test-point/import-xmind')) {
    return TIMEOUT_CONFIG.aiXmindImport
  }

  // AI相关接口
  if (
    lowerUrl.includes('/ai/') ||
    lowerUrl.includes('/ai-') ||
    lowerUrl.includes('/analyze') ||
    lowerUrl.includes('/generate') ||
    lowerUrl.includes('/extract') ||
    lowerUrl.includes('/test-point') ||
    lowerUrl.includes('/test-case') ||
    lowerUrl.includes('/testcase') ||
    lowerUrl.includes('/parse')
  ) {
    return TIMEOUT_CONFIG.ai
  }

  // 流程数据保存接口（节点/边数据量较大）
  if (lowerUrl.includes('/ui-prototype/flow/')) {
    return TIMEOUT_CONFIG.upload
  }

  // 文件上传/导出接口
  if (
    lowerUrl.includes('/upload') ||
    lowerUrl.includes('/export') ||
    lowerUrl.includes('/import')
  ) {
    return TIMEOUT_CONFIG.upload
  }

  return TIMEOUT_CONFIG.default
}

// API响应数据结构
export interface ValidationErrorDetail {
  msg?: string
  [key: string]: unknown
}

export interface CustomApiError extends Error {
  response?: AxiosResponse
  code?: string
}

export interface ApiResponse<T = unknown> {
  code: number
  msg: string
  message: string
  data: T
  timestamp?: number
}

// 创建axios实例
const service: AxiosInstance = axios.create({
  baseURL: import.meta.env?.VITE_API_BASE_URL || '',
  timeout: TIMEOUT_CONFIG.default,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 根据接口URL动态调整超时时间（如果未显式指定）
    if (!config.timeout || config.timeout === TIMEOUT_CONFIG.default) {
      config.timeout = getTimeoutByUrl(config.url)
    }

    // 添加token
    const token = localStorage.getItem('token')
    if (token) {
      config.headers = config.headers || {}
      config.headers.Authorization = `Bearer ${token}`
    }

    // FormData上传时删除默认Content-Type，让浏览器自动设置multipart/form-data + boundary
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }

    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// ========== 401 未授权处理（Task A-03） ==========
// 认证端点自身返回 401 属业务语义（如登录失败、刷新失败），不走「登录已过期」提示
const AUTH_ENDPOINTS = ['/auth/login', '/auth/refresh', '/auth/logout']
// 提示与跳转之间的延迟，保证用户能看清提示
const UNAUTHORIZED_REDIRECT_DELAY = 1500

/** 清理本地凭据（token / refresh_token / userInfo） */
function clearLocalCredentials(): void {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('userInfo')
}

/** 路由对象的最小结构（避免在 utils 层静态依赖 vue-router 类型） */
interface RouterLike {
  currentRoute?: { value?: { path?: string; fullPath?: string } }
  push: (to: { path: string; query?: Record<string, string> }) => unknown
}

// 按需解析 router：若在模块顶层静态 `import router from '@/router'`，会形成
// 「router → routes → views/api → utils/request → router」的初始化环，
// 导致部分单测在收集阶段即失败（0 test）、应用冷启动偶发 TDZ 错误。
let routerRef: RouterLike | null = null

async function resolveRouter(): Promise<RouterLike | null> {
  if (routerRef) {
    return routerRef
  }
  try {
    const mod = await import('@/router')
    routerRef = (mod.default || mod) as RouterLike
    return routerRef
  } catch {
    return null
  }
}

/**
 * 处理未授权（401 刷新令牌失败）：
 * 1. 登录页自身不发提示、不跳转（避免干扰用户输入）
 * 2. 清理本地凭据并重置流程排序缓存
 * 3. 弹出「登录已过期，请重新登录」
 * 4. 延迟 1500ms 后跳转登录页，非根路径带上 redirect 便于登录后回跳
 *    （router 不可用时退化为整页跳转，保证任何环境下都能回到登录页）
 */
async function handleUnauthorized(): Promise<void> {
  const router = await resolveRouter()
  const current = router?.currentRoute?.value
  const currentPath = current?.path || (typeof window !== 'undefined' ? window.location.pathname : '/')

  if (currentPath.includes('/login')) {
    return
  }

  clearLocalCredentials()
  try {
    const flowSortStore = useFlowSortStore()
    flowSortStore.reset()
  } catch {
    // flowSortStore 可能未初始化（如非组件上下文），忽略错误
  }

  ElMessage.warning('登录已过期，请重新登录')

  const target = {
    path: '/login',
    query: currentPath === '/' ? undefined : { redirect: current?.fullPath || currentPath },
  }

  window.setTimeout(() => {
    if (router) {
      router.push(target)
    } else if (typeof window !== 'undefined') {
      window.location.href = '/login'
    }
  }, UNAUTHORIZED_REDIRECT_DELAY)
}

/**
 * 尝试用 refresh_token 换取新的 access_token。
 *
 * @returns 新 token；无 refresh_token 或刷新失败/未返回 token 时返回 null
 */
async function tryRefreshToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) {
    return null
  }
  try {
    const res = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
    const payload = (res as { data?: Record<string, unknown> })?.data ?? {}
    const body = (payload as { data?: Record<string, unknown> }).data ?? payload
    const newToken = (body as { access_token?: string; token?: string })?.access_token
      || (body as { token?: string })?.token
      || null
    if (newToken) {
      localStorage.setItem('token', newToken)
      const rotated = (body as { refresh_token?: string })?.refresh_token
      if (rotated) {
        localStorage.setItem('refresh_token', rotated)
      }
    }
    return newToken
  } catch {
    return null
  }
}

// 响应拦截器
service.interceptors.response.use(
  ((response: AxiosResponse) => {
    if (response.config.responseType === 'blob') {
      return response
    }
    const res = response.data as ApiResponse
    if (res && typeof res === 'object' && ('code' in res || 'data' in res)) {
      return res
    }
    return { code: 0, msg: 'success', message: 'success', data: res } as ApiResponse
  }) as unknown as Parameters<typeof service.interceptors.response.use>[0],
  async (error) => {
    // 处理401错误：优先尝试刷新令牌，刷新失败再走「登录已过期」处理
    if (error.response && error.response.status === 401) {
      const requestUrl: string = error.config?.url || ''
      const isAuthEndpoint = AUTH_ENDPOINTS.some((path) => requestUrl.includes(path))

      if (!isAuthEndpoint) {
        const newToken = await tryRefreshToken()
        if (newToken) {
          // 用新令牌重放原请求（保留原配置的其余部分）
          error.config.headers = error.config.headers || {}
          error.config.headers.Authorization = `Bearer ${newToken}`
          return service(error.config)
        }
        await handleUnauthorized()
      }
    }

    // 返回更有用的错误信息
    const detail = error.response?.data?.detail
    let errorDetail = ''
    if (typeof detail === 'string') {
      errorDetail = detail
    } else if (Array.isArray(detail)) {
      errorDetail = detail.map((d: ValidationErrorDetail) => d.msg || String(d)).join('; ')
    }
    const customError = new Error(
      errorDetail || error.response?.data?.message || error.message
    ) as CustomApiError
    customError.response = error.response
    customError.code = error.code

    return Promise.reject(customError)
  }
)

// 类型化的请求方法
export const typedRequest = {
  get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return service.get(url, config) as unknown as Promise<ApiResponse<T>>
  },

  post<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    return service.post(url, data, config) as unknown as Promise<ApiResponse<T>>
  },

  put<T = unknown>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
  ): Promise<ApiResponse<T>> {
    return service.put(url, data, config) as unknown as Promise<ApiResponse<T>>
  },

  delete<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    return service.delete(url, config) as unknown as Promise<ApiResponse<T>>
  },
}

// 防抖处理的请求方法
export const debouncedRequest = debounce((config: AxiosRequestConfig) => {
  return service(config)
}, 300)

// 节流处理的请求方法
export const throttledRequest = throttle((config: AxiosRequestConfig) => {
  return service(config)
}, 1000)

export default service
