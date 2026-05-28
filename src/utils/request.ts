import axios, {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios'
import { debounce, throttle } from './debounce'
import { useFlowSortStore } from '@/store/flowSort'

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
  (error) => {
    // 处理401错误，跳转到登录页面
    if (error.response && error.response.status === 401) {
      localStorage.removeItem('token')
      try {
        const flowSortStore = useFlowSortStore()
        flowSortStore.reset()
      } catch {
        // flowSortStore 可能未初始化，忽略错误
      }
      if (!window.location.pathname.includes('/login')) {
        window.location.href = '/login'
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
