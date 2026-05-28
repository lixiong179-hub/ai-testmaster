<template>
  <div class="login-page">
    <div class="login-shell">
      <section class="brand-panel" aria-label="AI TestMaster">
        <div class="brand-badge">AI TEST PLATFORM</div>
        <div class="brand-copy">
          <h1>AI TestMaster</h1>
          <p>统一管理测试点、执行任务与智能生成能力，让测试资产流转更清晰。</p>
        </div>
        <div class="feature-grid">
          <div class="feature-item">
            <span class="feature-value">AI</span>
            <span class="feature-label">用例生成</span>
          </div>
          <div class="feature-item">
            <span class="feature-value">E2E</span>
            <span class="feature-label">执行工作台</span>
          </div>
          <div class="feature-item">
            <span class="feature-value">QA</span>
            <span class="feature-label">质量闭环</span>
          </div>
        </div>
      </section>

      <section class="login-card" aria-label="登录">
        <div class="login-header">
          <div class="login-kicker">Welcome back</div>
          <h2 class="login-title">登录 AI TestMaster</h2>
          <p class="login-subtitle">选择登录方式后进入测试管理工作台</p>
        </div>

        <el-tabs v-model="activeTab" class="login-tabs" stretch>
          <el-tab-pane label="账号登录" name="account">
            <el-form
              :ref="setLoginFormRef"
              :model="loginForm"
              :rules="loginRules"
              label-position="top"
              class="login-form"
            >
              <el-form-item label="账号/手机号" prop="username">
                <el-input
                  v-model="loginForm.username"
                  placeholder="请输入账号或手机号"
                  size="large"
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
                  placeholder="请输入密码"
                  show-password
                  size="large"
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
                    placeholder="请输入验证码"
                    class="code-input"
                    size="large"
                  >
                    <template #prefix>
                      <el-icon><Message /></el-icon>
                    </template>
                  </el-input>
                  <img
                    v-if="captchaImage"
                    :src="'data:image/png;base64,' + captchaImage"
                    @click="refreshCaptcha"
                    class="captcha-surface"
                    alt="点击刷新验证码"
                  />
                  <canvas
                    v-else
                    :ref="setCaptchaCanvasRef"
                    @click="refreshCaptcha"
                    class="captcha-surface"
                    width="150"
                    height="44"
                  ></canvas>
                </div>
              </el-form-item>

              <div class="form-options">
                <el-checkbox v-model="loginForm.remember" class="remember-checkbox">
                  记住密码
                </el-checkbox>
              </div>

              <el-button
                type="primary"
                @click="handleLogin"
                class="login-submit"
                :loading="loading"
              >
                登录
              </el-button>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="手机登录" name="phone">
            <el-form
              :ref="setPhoneFormRef"
              :model="phoneForm"
              :rules="phoneRules"
              label-position="top"
              class="login-form"
            >
              <el-form-item label="手机号" prop="phone">
                <el-input v-model="phoneForm.phone" placeholder="请输入手机号" size="large">
                  <template #prefix>
                    <el-icon><Phone /></el-icon>
                  </template>
                </el-input>
              </el-form-item>

              <el-form-item label="验证码" prop="code">
                <div class="code-input-wrapper">
                  <el-input
                    v-model="phoneForm.code"
                    placeholder="请输入验证码"
                    class="code-input"
                    size="large"
                  >
                    <template #prefix>
                      <el-icon><Message /></el-icon>
                    </template>
                  </el-input>
                  <el-button
                    type="primary"
                    :disabled="phoneCountdown > 0"
                    @click="getPhoneCode"
                    class="code-action"
                  >
                    {{ phoneCountdown > 0 ? `${phoneCountdown}s后重试` : '获取验证码' }}
                  </el-button>
                </div>
              </el-form-item>

              <div class="form-options">
                <el-checkbox v-model="phoneForm.remember" class="remember-checkbox">
                  记住手机号
                </el-checkbox>
              </div>

              <el-button
                type="primary"
                @click="handlePhoneLogin"
                class="login-submit"
                :loading="phoneLoading"
              >
                登录
              </el-button>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { User, Lock, Message, Phone } from '@element-plus/icons-vue'
import { useLogin } from './useLogin'

const {
  activeTab,
  loading,
  phoneLoading,
  phoneCountdown,
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
} = useLogin()

const setCaptchaCanvasRef = (el: unknown) => {
  captchaCanvas.value = el instanceof HTMLCanvasElement ? el : undefined
}
const setLoginFormRef = (el: unknown) => {
  loginFormRef.value = el
}
const setPhoneFormRef = (el: unknown) => {
  phoneFormRef.value = el
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  padding: 40px 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at 16% 18%, rgba(64, 158, 255, 0.22), transparent 28%),
    radial-gradient(circle at 84% 76%, rgba(103, 194, 58, 0.16), transparent 30%),
    linear-gradient(135deg, #eef5ff 0%, #f7fbf9 48%, #f4f1ff 100%);
  color: #172033;
}

.login-shell {
  width: min(1040px, 100%);
  min-height: 620px;
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) 430px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(210, 220, 235, 0.9);
  border-radius: 28px;
  box-shadow: 0 26px 80px rgba(49, 67, 96, 0.18);
  backdrop-filter: blur(18px);
}

.brand-panel {
  position: relative;
  padding: 56px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
  background:
    linear-gradient(145deg, rgba(28, 86, 177, 0.92), rgba(35, 139, 121, 0.88)),
    linear-gradient(180deg, #1d5fbf, #24796c);
  color: #fff;
}

.brand-panel::before {
  content: '';
  position: absolute;
  inset: 72px -120px auto auto;
  width: 320px;
  height: 320px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 50%;
}

.brand-panel::after {
  content: '';
  position: absolute;
  left: 56px;
  right: 56px;
  bottom: 174px;
  height: 1px;
  background: rgba(255, 255, 255, 0.2);
}

.brand-badge {
  width: fit-content;
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: rgba(255, 255, 255, 0.86);
}

.brand-copy {
  position: relative;
  z-index: 1;
  max-width: 420px;
}

.brand-copy h1 {
  margin: 0 0 18px;
  font-size: 46px;
  line-height: 1.08;
  font-weight: 800;
}

.brand-copy p {
  margin: 0;
  font-size: 17px;
  line-height: 1.8;
  color: rgba(255, 255, 255, 0.82);
}

.feature-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.feature-item {
  padding: 18px 16px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.11);
}

.feature-value {
  display: block;
  margin-bottom: 8px;
  font-size: 19px;
  font-weight: 800;
}

.feature-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.78);
}

.login-card {
  padding: 54px 46px;
  background: rgba(255, 255, 255, 0.96);
}

.login-header {
  margin-bottom: 28px;
}

.login-kicker {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.11em;
  text-transform: uppercase;
  color: #1f7aec;
}

.login-title {
  margin: 0 0 10px;
  font-size: 26px;
  line-height: 1.25;
  color: #172033;
}

.login-subtitle {
  margin: 0;
  color: #697386;
  line-height: 1.7;
}

.login-tabs {
  --el-color-primary: #1f7aec;
}

.login-form {
  padding-top: 8px;
}

.code-input-wrapper {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 118px;
  gap: 12px;
  width: 100%;
}

.captcha-surface,
.code-action {
  width: 118px;
  height: 44px;
}

.captcha-surface {
  cursor: pointer;
  border-radius: 10px;
  object-fit: contain;
  background: #f4f8fd;
  border: 1px solid #dce6f2;
}

.form-options {
  margin: 2px 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.login-submit {
  width: 100%;
  height: 46px;
  border-radius: 10px;
  font-weight: 700;
  background: linear-gradient(135deg, #1f7aec 0%, #2aa18c 100%);
  border: 0;
  box-shadow: 0 12px 24px rgba(31, 122, 236, 0.22);
}

:deep(.el-tabs__header) {
  margin-bottom: 24px;
}

:deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: #e6edf5;
}

:deep(.el-tabs__item) {
  height: 42px;
  font-weight: 700;
}

:deep(.el-form-item) {
  margin-bottom: 20px;
}

:deep(.el-form-item__label) {
  margin-bottom: 8px;
  color: #3d4a5c;
  font-weight: 700;
  line-height: 1.2;
}

:deep(.el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 0 0 1px #dce5ef inset;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #b9c9dc inset;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px #1f7aec inset,
    0 0 0 3px rgba(31, 122, 236, 0.12);
}

:deep(.el-checkbox__label) {
  color: #5e6b7d;
}

@media (max-width: 900px) {
  .login-page {
    padding: 24px 16px;
    align-items: flex-start;
  }

  .login-shell {
    min-height: auto;
    grid-template-columns: 1fr;
    border-radius: 22px;
  }

  .brand-panel {
    min-height: 250px;
    padding: 34px;
    gap: 34px;
  }

  .brand-panel::after {
    display: none;
  }

  .brand-copy h1 {
    font-size: 34px;
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }

  .login-card {
    padding: 34px 24px 38px;
  }
}

@media (max-width: 520px) {
  .brand-panel {
    display: none;
  }

  .login-card {
    padding: 30px 20px 34px;
  }

  .login-title {
    font-size: 23px;
  }

  .code-input-wrapper {
    grid-template-columns: 1fr;
  }

  .captcha-surface,
  .code-action {
    width: 100%;
  }
}
</style>
