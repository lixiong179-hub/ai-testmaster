import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '@/api/auth'
import type { ApiResponse } from '@/utils/request'
import type { LoginForm as LoginFormType } from '@/types/user'
import { signPermissions } from '@/directives/permission'

export function useLogin() {
  const router = useRouter()
  const activeTab = ref('account')
  const loading = ref(false)
  const phoneLoading = ref(false)
  const phoneCountdown = ref(0)
  const isMobile = ref(false)
  const captchaId = ref('')
  const captchaCode = ref('')
  const captchaImage = ref('')
  const captchaCanvas = ref<HTMLCanvasElement>()
  const loginFormRef = ref()
  const phoneFormRef = ref()

  const loginForm = reactive<LoginFormType>({
    username: '',
    password: '',
    code: '',
    remember: false,
  })
  const phoneForm = reactive({ phone: '', code: '', remember: false })

  const loginRules = {
    username: [{ required: true, message: '请输入账号或手机号', trigger: 'blur' }],
    password: [
      { required: true, message: '请输入密码', trigger: 'blur' },
      { min: 6, message: '密码长度至少6位', trigger: 'blur' },
    ],
    code: [
      { required: true, message: '请输入验证码', trigger: 'blur' },
      { min: 4, max: 4, message: '验证码为4位数字', trigger: 'blur' },
    ],
  }
  const phoneRules = {
    phone: [
      { required: true, message: '请输入手机号', trigger: 'blur' },
      { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' },
    ],
    code: [
      { required: true, message: '请输入验证码', trigger: 'blur' },
      { min: 4, max: 4, message: '验证码为4位数字', trigger: 'blur' },
    ],
  }

  const checkMobile = () => {
    isMobile.value = window.innerWidth <= 768
  }

  const encryptStorage = (key: string, value: unknown): void => {
    try {
      const d = new TextEncoder().encode(JSON.stringify(value))
      localStorage.setItem(key, btoa(String.fromCharCode(...d)))
    } catch {
      /* ignore */
    }
  }
  const decryptStorage = (key: string): unknown => {
    try {
      const e = localStorage.getItem(key)
      if (e) {
        const b = atob(e)
        return JSON.parse(new TextDecoder().decode(Uint8Array.from(b, (c) => c.charCodeAt(0))))
      }
    } catch {
      /* ignore */
    }
    return null
  }

  const drawCaptchaOnCanvas = (code: string) => {
    const canvas = captchaCanvas.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.fillStyle = '#f5f7fa'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    for (let i = 0; i < 5; i++) {
      ctx.strokeStyle = `rgb(${Math.random() * 255},${Math.random() * 255},${Math.random() * 255})`
      ctx.beginPath()
      ctx.moveTo(Math.random() * canvas.width, Math.random() * canvas.height)
      ctx.lineTo(Math.random() * canvas.width, Math.random() * canvas.height)
      ctx.stroke()
    }
    ctx.font = '24px Arial'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    for (let i = 0; i < code.length; i++) {
      ctx.fillStyle = `rgb(${Math.random() * 100 + 50},${Math.random() * 100 + 50},${Math.random() * 100 + 50})`
      ctx.fillText(
        code[i],
        (i + 0.5) * (canvas.width / code.length),
        canvas.height / 2 + (Math.random() - 0.5) * 10
      )
    }
  }

  const fallbackCaptcha = () => {
    const canvas = captchaCanvas.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const code = Math.floor(1000 + Math.random() * 9000).toString()
    captchaCode.value = code
    captchaImage.value = ''
    captchaId.value = ''
    drawCaptchaOnCanvas(code)
  }

  const refreshCaptcha = async () => {
    try {
      const response = await authApi.generateCaptcha()
      if (response?.code === 200 && response.data) {
        captchaId.value = response.data.captcha_id
        if (response.data.image) {
          captchaImage.value = response.data.image
          captchaCode.value = ''
        } else if (response.data.code) {
          captchaImage.value = ''
          captchaCode.value = response.data.code
          drawCaptchaOnCanvas(response.data.code)
        } else {
          fallbackCaptcha()
        }
      } else {
        fallbackCaptcha()
      }
    } catch {
      fallbackCaptcha()
    }
  }

  const loadRememberedPassword = () => {
    const r = localStorage.getItem('rememberedUsername')
    if (r) {
      loginForm.username = r
      loginForm.remember = true
    }
  }
  const loadRememberedPhone = () => {
    const r = decryptStorage('rememberedPhone') as { phone?: string } | null
    if (r?.phone) {
      phoneForm.phone = r.phone
      phoneForm.remember = true
    }
  }
  const getPhoneCode = (): void => {
    ElMessage.warning('手机验证码功能已停用，请使用账号登录')
  }

  async function saveUserInfo(): Promise<void> {
    try {
      const r = (await authApi.getCurrentUser()) as any
      const d = r?.data || r
      if (d) {
        localStorage.setItem(
          'userInfo',
          JSON.stringify(
            signPermissions(
              d.permissions || d.roles?.flatMap((r: any) => r.permissions || []) || []
            )
          )
        )
      }
    } catch {
      localStorage.setItem('userInfo', JSON.stringify(signPermissions([])))
    }
  }

  const handleLogin = async () => {
    if (!loginFormRef.value) return
    await loginFormRef.value.validate(async (valid: boolean) => {
      if (!valid) return
      loading.value = true
      try {
        const fd = new URLSearchParams()
        fd.append('username', loginForm.username)
        fd.append('password', loginForm.password)
        if (captchaId.value) {
          fd.append('captcha_id', captchaId.value)
          fd.append('captcha_code', loginForm.code)
        }
        const response = (await authApi.login(fd)) as unknown as ApiResponse
        if (!response) throw new Error('服务器无响应')
        const lr = response as {
          code: number
          data: { access_token: string }
          msg?: string
          message?: string
        }
        if (lr.code === 200 && lr.data?.access_token) {
          localStorage.setItem('token', lr.data.access_token)
          await saveUserInfo()
          if (loginForm.remember) localStorage.setItem('rememberedUsername', loginForm.username)
          else localStorage.removeItem('rememberedUsername')
          ElMessage.success('登录成功')
          await router.push('/home/project')
        } else if (lr.code === 401) throw new Error(lr.msg || lr.message || '用户名或密码错误')
        else if (lr.code === 400) throw new Error(lr.msg || lr.message || '请求参数错误')
        else throw new Error(lr.msg || lr.message || `登录失败（状态码: ${lr.code || '未知'}）`)
      } catch (error: any) {
        let msg = '登录失败，请稍后重试'
        if (error.message) msg = error.message
        else if (error.response?.data?.detail) msg = error.response.data.detail
        else if (error.response?.data?.message) msg = error.response.data.message
        else if (error.response?.status === 401) msg = '用户名或密码错误'
        else if (error.response?.status === 403) msg = '账号已被禁用'
        else if (error.response?.status === 429) msg = '操作太频繁，请稍后再试'
        else if (error.code === 'ERR_NETWORK') msg = '网络连接失败'
        else if (error.code === 'ECONNABORTED') msg = '请求超时'
        ElMessage.error(msg)
        refreshCaptcha()
      } finally {
        loading.value = false
      }
    })
  }

  const handlePhoneLogin = async () => {
    if (!phoneFormRef.value) return
    await phoneFormRef.value.validate(async (valid: boolean) => {
      if (!valid) return
      phoneLoading.value = true
      try {
        const fd = new URLSearchParams()
        fd.append('username', phoneForm.phone)
        fd.append('password', 'phone-login')
        const response = (await authApi.login(fd)) as unknown as ApiResponse
        const fr = response as { code: number; data: { access_token: string } }
        if (fr?.code === 200 && fr.data?.access_token) {
          localStorage.setItem('token', fr.data.access_token)
          await saveUserInfo()
          if (phoneForm.remember) encryptStorage('rememberedPhone', { phone: phoneForm.phone })
          else localStorage.removeItem('rememberedPhone')
          ElMessage.success('登录成功')
          router.push('/home/project')
        } else {
          ElMessage.error('登录失败，返回数据格式错误')
        }
      } catch (error: any) {
        ElMessage.error(error.response?.data?.message || '登录失败')
      } finally {
        phoneLoading.value = false
      }
    })
  }

  onMounted(() => {
    checkMobile()
    window.addEventListener('resize', checkMobile)
    loadRememberedPassword()
    loadRememberedPhone()
    setTimeout(refreshCaptcha, 100)
  })

  return {
    activeTab,
    loading,
    phoneLoading,
    phoneCountdown,
    isMobile,
    captchaImage,
    captchaCanvas,
    loginFormRef,
    phoneFormRef,
    loginForm,
    phoneForm,
    loginRules,
    phoneRules,
    refreshCaptcha,
    getPhoneCode,
    handleLogin,
    handlePhoneLogin,
  }
}
