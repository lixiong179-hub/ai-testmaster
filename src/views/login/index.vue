<template>
  <div class="login-container">
    <div class="login-form-wrapper">
      <h2 class="login-title">AI TestMaster 登录</h2>
      
      <!-- 登录方式切换 -->
      <div class="login-tabs">
        <el-tabs v-model="activeTab" class="login-tabs">
          <el-tab-pane label="账号登录" name="account">
            <el-form
              ref="loginFormRef"
              :model="loginForm"
              :rules="loginRules"
              :label-width="isMobile ? 'auto' : '80px'"
              class="login-form"
            >
              <el-form-item label="账号/手机号" prop="username">
                <el-input
                  v-model="loginForm.username"
                  :placeholder="isMobile ? '账号/手机号' : '请输入账号或手机号'"
                >
                  <template #prefix>
                    <el-icon><User /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              
              <el-form-item label="密码" prop="password">
                <el-input
                  v-model="loginForm.password"
                  type="password"
                  :placeholder="isMobile ? '密码' : '请输入密码'"
                  show-password
                >
                  <template #prefix>
                    <el-icon><Lock /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              
              <el-form-item label="验证码" prop="code">
                <div class="code-input-wrapper">
                  <el-input
                    v-model="loginForm.code"
                    :placeholder="isMobile ? '验证码' : '请输入验证码'"
                    style="width: 60%"
                  >
                    <template #prefix>
                      <el-icon><Message /></el-icon>
                    </template>
                  </el-input>
                  <!-- 优先显示服务端返回的base64图片，降级时显示canvas -->
                  <img
                    v-if="captchaImage"
                    :src="'data:image/png;base64,' + captchaImage"
                    @click="refreshCaptcha"
                    style="width: 35%; margin-left: 5%; height: 40px; cursor: pointer; border-radius: 4px; object-fit: contain; background: #f5f7fa"
                    alt="点击刷新验证码"
                  />
                  <canvas
                    v-else
                    ref="captchaCanvas"
                    @click="refreshCaptcha"
                    style="width: 35%; margin-left: 5%; height: 40px; cursor: pointer; background: #f5f7fa; border-radius: 4px"
                    width="150"
                    height="40"
                  ></canvas>
                </div>
              </el-form-item>
              
              <el-form-item>
                <el-checkbox v-model="loginForm.remember" class="remember-checkbox">
                  记住密码
                </el-checkbox>
              </el-form-item>
              
              <el-form-item>
                <el-button
                  type="primary"
                  @click="handleLogin"
                  style="width: 100%"
                  :loading="loading"
                >
                  登录
                </el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
          
          <el-tab-pane label="手机登录" name="phone">
            <el-form
              ref="phoneFormRef"
              :model="phoneForm"
              :rules="phoneRules"
              :label-width="isMobile ? 'auto' : '80px'"
              class="login-form"
            >
              <el-form-item label="手机号" prop="phone">
                <el-input
                  v-model="phoneForm.phone"
                  :placeholder="isMobile ? '手机号' : '请输入手机号'"
                >
                  <template #prefix>
                    <el-icon><Phone /></el-icon>
                  </template>
                </el-input>
              </el-form-item>
              
              <el-form-item label="验证码" prop="code">
                <div class="code-input-wrapper">
                  <el-input
                    v-model="phoneForm.code"
                    :placeholder="isMobile ? '验证码' : '请输入验证码'"
                    style="width: 60%"
                  >
                    <template #prefix>
                      <el-icon><Message /></el-icon>
                    </template>
                  </el-input>
                  <el-button
                    type="primary"
                    :disabled="phoneCountdown > 0"
                    @click="getPhoneCode"
                    style="width: 35%; margin-left: 5%"
                  >
                    {{ phoneCountdown > 0 ? `${phoneCountdown}s后重试` : '获取验证码' }}
                  </el-button>
                </div>
              </el-form-item>
              
              <el-form-item>
                <el-checkbox v-model="phoneForm.remember" class="remember-checkbox">
                  记住手机号
                </el-checkbox>
              </el-form-item>
              
              <el-form-item>
                <el-button
                  type="primary"
                  @click="handlePhoneLogin"
                  style="width: 100%"
                  :loading="phoneLoading"
                >
                  登录
                </el-button>
              </el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Message, Phone } from '@element-plus/icons-vue'
import request from '@/utils/request'
import type { ApiResponse } from '@/utils/request'
import type { LoginForm as LoginFormType } from '@/types/user'
import { signPermissions } from '@/directives/permission'

// 路由实例
const router = useRouter()

// 登录方式
const activeTab = ref('account')

// 服务端验证码相关
const captchaId = ref('')
const captchaCode = ref('')
const captchaImage = ref('')  // 服务端返回的base64图片

// 移动端检测
const isMobile = ref(false)
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

// 生成验证码 - 从服务端获取（返回base64图片）
const refreshCaptcha = async () => {
  try {
    const response = await request.get('/api/v1/auth/captcha/generate') as { code: number; data: { captcha_id: string; image?: string; code?: string } }
    if (response && response.code === 200 && response.data) {
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
  } catch (error) {
    console.error('获取验证码失败，使用客户端降级:', error)
    fallbackCaptcha()
  }
}

// 在canvas上绘制验证码文字（降级/兼容模式）
const drawCaptchaOnCanvas = (code: string) => {
  const canvas = captchaCanvas.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = '#f5f7fa'
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  for (let i = 0; i < 5; i++) {
    ctx.strokeStyle = `rgb(${Math.random() * 255}, ${Math.random() * 255}, ${Math.random() * 255})`
    ctx.beginPath()
    ctx.moveTo(Math.random() * canvas.width, Math.random() * canvas.height)
    ctx.lineTo(Math.random() * canvas.width, Math.random() * canvas.height)
    ctx.stroke()
  }

  ctx.font = '24px Arial'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'

  for (let i = 0; i < code.length; i++) {
    ctx.fillStyle = `rgb(${Math.random() * 100 + 50}, ${Math.random() * 100 + 50}, ${Math.random() * 100 + 50})`
    const x = (i + 0.5) * (canvas.width / code.length)
    const y = canvas.height / 2 + (Math.random() - 0.5) * 10
    ctx.fillText(code[i], x, y)
  }
}

// 客户端降级验证码生成
const fallbackCaptcha = () => {
  const canvas = captchaCanvas.value
  if (!canvas) return
  
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  
  const code = Math.floor(1000 + Math.random() * 9000).toString()
  captchaCode.value = code
  captchaImage.value = ''  // 切换到canvas模式
  captchaId.value = '' // 降级模式不使用服务端验证
  
  ctx.fillStyle = '#f5f7fa'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  
  for (let i = 0; i < 5; i++) {
    ctx.strokeStyle = `rgb(${Math.random() * 255}, ${Math.random() * 255}, ${Math.random() * 255})`
    ctx.beginPath()
    ctx.moveTo(Math.random() * canvas.width, Math.random() * canvas.height)
    ctx.lineTo(Math.random() * canvas.width, Math.random() * canvas.height)
    ctx.stroke()
  }
  
  ctx.font = '24px Arial'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  
  for (let i = 0; i < code.length; i++) {
    ctx.fillStyle = `rgb(${Math.random() * 100 + 50}, ${Math.random() * 100 + 50}, ${Math.random() * 100 + 50})`
    const x = (i + 0.5) * (canvas.width / code.length)
    const y = canvas.height / 2 + (Math.random() - 0.5) * 10
    ctx.fillText(code[i], x, y)
  }
}

// 账号登录表单
const loginFormRef = ref()
const loading = ref(false)
const captchaCanvas = ref<HTMLCanvasElement>()

// 初始化
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  // 加载记住的密码
  loadRememberedPassword()
  loadRememberedPhone()
  // 初始化验证码
  setTimeout(() => {
    refreshCaptcha()
  }, 100)
})

const loginForm = reactive<LoginFormType>({
  username: '',
  password: '',
  code: '',
  remember: false
})

// 手机登录表单
const phoneFormRef = ref()
const phoneLoading = ref(false)
const phoneCountdown = ref(0)

const phoneForm = reactive({
  phone: '',
  code: '',
  remember: false
})

// 表单验证规则
const loginRules = {
  username: [
    { required: true, message: '请输入账号或手机号', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' }
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 4, max: 4, message: '验证码为4位数字', trigger: 'blur' }
  ]
}

const phoneRules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号', trigger: 'blur' }
  ],
  code: [
    { required: true, message: '请输入验证码', trigger: 'blur' },
    { min: 4, max: 4, message: '验证码为4位数字', trigger: 'blur' }
  ]
}

// 加密存储
const encryptStorage = (key: string, value: unknown): void => {
  try {
    const jsonString = JSON.stringify(value)
    const encoder = new TextEncoder()
    const data = encoder.encode(jsonString)
    const binString = Array.from(data, byte => String.fromCharCode(byte)).join('')
    const encrypted = btoa(binString)
    localStorage.setItem(key, encrypted)
  } catch (error) {
    console.error('加密存储失败:', error)
  }
}

// 解密存储
const decryptStorage = (key: string): unknown => {
  try {
    const encrypted = localStorage.getItem(key)
    if (encrypted) {
      const binString = atob(encrypted)
      const bytes = Uint8Array.from(binString, c => c.charCodeAt(0))
      const decoder = new TextDecoder()
      return JSON.parse(decoder.decode(bytes))
    }
  } catch (error) {
    console.error('解密存储失败:', error)
  }
  return null
}

// 加载记住的用户名（不再存储密码）
const loadRememberedPassword = () => {
  const remembered = localStorage.getItem('rememberedUsername')
  if (remembered) {
    loginForm.username = remembered
    loginForm.remember = true
  }
}

// 加载记住的手机号
const loadRememberedPhone = () => {
  const remembered = decryptStorage('rememberedPhone') as { phone?: string } | null
  if (remembered && remembered.phone) {
    phoneForm.phone = remembered.phone
    phoneForm.remember = true
  }
}

// 手机验证码功能已改为图形验证码，此函数不再需要
const getPhoneCode = (): void => {
  throw new Error('手机验证码功能已停用，请使用图形验证码')
}

// 处理账号登录
const handleLogin = async () => {
  if (!loginFormRef.value) return

  await loginFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true
      try {
        // 登录请求
        const loginUrl = '/api/v1/auth/login'

        // 使用URLSearchParams发送表单数据（包含验证码信息）
        const formData = new URLSearchParams()
        formData.append('username', loginForm.username)
        formData.append('password', loginForm.password)
        
        // 如果有服务端验证码ID，则发送给后端校验
        if (captchaId.value) {
          formData.append('captcha_id', captchaId.value)
          formData.append('captcha_code', loginForm.code)
        }

        const response = await request.post(loginUrl, formData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        }) as unknown as ApiResponse

        // 增强响应数据校验和错误提示
        if (!response) {
          throw new Error('服务器无响应')
        }

        const loginResponse = response as { code: number; data: { access_token: string } }
        if (loginResponse.code === 200 && loginResponse.data?.access_token) {
          localStorage.setItem('token', loginResponse.data.access_token)

          try {
            const userRes = await request.get('/api/v1/auth/me') as any
            const userData = userRes?.data || userRes
            if (userData) {
              const permissions = userData.permissions || userData.roles?.flatMap((r: any) => r.permissions || []) || []
              localStorage.setItem('userInfo', JSON.stringify(signPermissions(permissions)))
            }
          } catch {
            localStorage.setItem('userInfo', JSON.stringify(signPermissions([])))
          }

          // 记住用户名（不存储密码，提升安全性）
          if (loginForm.remember) {
            localStorage.setItem('rememberedUsername', loginForm.username)
          } else {
            localStorage.removeItem('rememberedUsername')
          }

          ElMessage.success('登录成功')

          // 直接跳转
          await router.push('/home/project')
        } else if (response.code === 401) {
          throw new Error(response.msg || response.message || '用户名或密码错误')
        } else if (response.code === 400) {
          throw new Error(response.msg || response.message || '请求参数错误')
        } else {
          throw new Error(response.msg || response.message || `登录失败（状态码: ${response.code || '未知'}）`)
        }
      } catch (error: any) {
        // 统一错误处理
        let errorMessage = '登录失败，请稍后重试'

        if (error.message) {
          errorMessage = error.message
        } else if (error.response?.data?.detail) {
          errorMessage = error.response.data.detail
        } else if (error.response?.data?.message) {
          errorMessage = error.response.data.message
        } else if (error.response?.status === 401) {
          errorMessage = '用户名或密码错误'
        } else if (error.response?.status === 403) {
          errorMessage = '账号已被禁用'
        } else if (error.response?.status === 429) {
          errorMessage = '操作太频繁，请稍后再试'
        } else if (error.code === 'ERR_NETWORK') {
          errorMessage = '网络连接失败，请检查网络或联系管理员'
        } else if (error.code === 'ECONNABORTED') {
          errorMessage = '请求超时，请稍后重试'
        }

        ElMessage.error(errorMessage)
        refreshCaptcha()
      } finally {
        loading.value = false
      }
    }
  })
}

// 处理手机登录
const handlePhoneLogin = async () => {
  if (!phoneFormRef.value) return
  
  await phoneFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      phoneLoading.value = true
      try {
        // 登录请求
        const formData = new URLSearchParams()
        formData.append('username', phoneForm.phone)
        formData.append('password', 'phone-login') // 手机登录特殊处理
        
        const response = await request.post('/api/v1/auth/login', formData, {
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded'
          }
        }) as unknown as ApiResponse

        // 存储token
        const formResponse = response as { code: number; data: { access_token: string } }
        if (formResponse && formResponse.code === 200 && formResponse.data && formResponse.data.access_token) {
          localStorage.setItem('token', formResponse.data.access_token)

          try {
            const userRes = await request.get('/api/v1/auth/me') as any
            const userData = userRes?.data || userRes
            if (userData) {
              const permissions = userData.permissions || userData.roles?.flatMap((r: any) => r.permissions || []) || []
              localStorage.setItem('userInfo', JSON.stringify(signPermissions(permissions)))
            }
          } catch {
            localStorage.setItem('userInfo', JSON.stringify(signPermissions([])))
          }
        } else {
          ElMessage.error('登录失败，返回数据格式错误')
          return
        }
        
        // 记住手机号
        if (phoneForm.remember) {
          encryptStorage('rememberedPhone', {
            phone: phoneForm.phone
          })
        } else {
          localStorage.removeItem('rememberedPhone')
        }
        
        // 暂时不获取用户信息，直接跳转到仪表盘
        // 后续可以在仪表盘页面或全局导航守卫中获取用户信息
        ElMessage.success('登录成功')
        router.push('/home/project')
      } catch (error: any) {
        ElMessage.error(error.response?.data?.message || '登录失败，请检查手机号和验证码')
      } finally {
        phoneLoading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-form-wrapper {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.login-title {
  text-align: center;
  margin-bottom: 30px;
  color: #303133;
}

.login-tabs {
  margin-bottom: 20px;
}

.login-form {
  width: 100%;
}

.code-input-wrapper {
  display: flex;
  align-items: center;
}

.remember-checkbox {
  margin-left: 10px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .login-form-wrapper {
    width: 90%;
    max-width: 350px;
    padding: 30px 20px;
    margin: 0 10px;
  }
  
  .login-title {
    font-size: 20px;
    margin-bottom: 25px;
  }
  
  :deep(.el-form-item) {
    margin-bottom: 20px;
  }
  
  :deep(.el-form-item__label) {
    display: none;
  }
  
  :deep(.el-form-item__content) {
    margin-left: 0 !important;
    justify-content: center;
  }
  
  :deep(.el-input__inner) {
    height: 44px;
    line-height: 44px;
  }
  
  .code-input-wrapper {
    flex-direction: column;
    gap: 10px;
  }
  
  .code-input-wrapper .el-input {
    width: 100% !important;
  }
  
  .code-input-wrapper .el-button {
    width: 100% !important;
    margin-left: 0 !important;
    height: 44px;
  }
  
  :deep(.el-button--primary) {
    height: 44px;
    font-size: 16px;
  }
  
  .remember-checkbox {
    margin-left: 0;
    text-align: center;
    display: block;
  }
}
</style>
