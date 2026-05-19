<template>
  <div class="login-container">
    <div class="login-form-wrapper">
      <div class="login-kicker">AI Test Platform</div>
      <h2 class="login-title">AI TestMaster 登录</h2>
      <p class="login-subtitle">统一访问测试点管理、执行工作台与智能生成能力</p>
      <div class="login-tabs">
        <el-tabs v-model="activeTab" class="login-tabs">
          <el-tab-pane label="账号登录" name="account">
            <el-form ref="loginFormRef" :model="loginForm" :rules="loginRules" :label-width="isMobile ? 'auto' : '80px'" class="login-form">
              <el-form-item label="账号/手机号" prop="username">
                <el-input v-model="loginForm.username" :placeholder="isMobile ? '账号/手机号' : '请输入账号或手机号'"><template #prefix><el-icon><User /></el-icon></template></el-input>
              </el-form-item>
              <el-form-item label="密码" prop="password">
                <el-input v-model="loginForm.password" type="password" :placeholder="isMobile ? '密码' : '请输入密码'" show-password><template #prefix><el-icon><Lock /></el-icon></template></el-input>
              </el-form-item>
              <el-form-item label="验证码" prop="code">
                <div class="code-input-wrapper">
                  <el-input v-model="loginForm.code" :placeholder="isMobile ? '验证码' : '请输入验证码'" class="code-input"><template #prefix><el-icon><Message /></el-icon></template></el-input>
                  <img v-if="captchaImage" :src="'data:image/png;base64,' + captchaImage" @click="refreshCaptcha" class="captcha-surface" alt="点击刷新验证码" />
                  <canvas v-else ref="captchaCanvas" @click="refreshCaptcha" class="captcha-surface" width="150" height="40"></canvas>
                </div>
              </el-form-item>
              <el-form-item><el-checkbox v-model="loginForm.remember" class="remember-checkbox">记住密码</el-checkbox></el-form-item>
              <el-form-item><el-button type="primary" @click="handleLogin" style="width: 100%" :loading="loading">登录</el-button></el-form-item>
            </el-form>
          </el-tab-pane>
          <el-tab-pane label="手机登录" name="phone">
            <el-form ref="phoneFormRef" :model="phoneForm" :rules="phoneRules" :label-width="isMobile ? 'auto' : '80px'" class="login-form">
              <el-form-item label="手机号" prop="phone">
                <el-input v-model="phoneForm.phone" :placeholder="isMobile ? '手机号' : '请输入手机号'"><template #prefix><el-icon><Phone /></el-icon></template></el-input>
              </el-form-item>
              <el-form-item label="验证码" prop="code">
                <div class="code-input-wrapper">
                  <el-input v-model="phoneForm.code" :placeholder="isMobile ? '验证码' : '请输入验证码'" style="width: 60%"><template #prefix><el-icon><Message /></el-icon></template></el-input>
                  <el-button type="primary" :disabled="phoneCountdown > 0" @click="getPhoneCode" class="code-action">{{ phoneCountdown > 0 ? `${phoneCountdown}s后重试` : '获取验证码' }}</el-button>
                </div>
              </el-form-item>
              <el-form-item><el-checkbox v-model="phoneForm.remember" class="remember-checkbox">记住手机号</el-checkbox></el-form-item>
              <el-form-item><el-button type="primary" @click="handlePhoneLogin" style="width: 100%" :loading="phoneLoading">登录</el-button></el-form-item>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { User, Lock, Message, Phone } from '@element-plus/icons-vue'
import { useLogin } from './useLogin'

const {
  activeTab, loading, phoneLoading, phoneCountdown, isMobile, captchaImage,
  captchaCanvas, loginFormRef, phoneFormRef, loginForm, phoneForm, loginRules,
  phoneRules, refreshCaptcha, getPhoneCode, handleLogin, handlePhoneLogin,
} = useLogin()
void captchaCanvas; void loginFormRef; void phoneFormRef
</script>

<style scoped>
.login-container { display: flex; justify-content: center; align-items: center; height: 100vh; padding: 24px; background: radial-gradient(circle at top left, rgba(255, 255, 255, 0.18), transparent 28%), linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.login-form-wrapper { width: 400px; padding: 40px; background: rgba(255, 255, 255, 0.96); border: 1px solid rgba(255, 255, 255, 0.42); border-radius: 24px; box-shadow: 0 24px 60px rgba(31, 45, 61, 0.24); backdrop-filter: blur(12px); }
.login-kicker { margin-bottom: 10px; font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #409eff; }
.login-title { text-align: center; margin-bottom: 8px; color: #1f2d3d; }
.login-subtitle { text-align: center; margin: 0 0 28px; color: #6b7684; line-height: 1.6; }
.login-tabs { margin-bottom: 20px; }
.login-form { width: 100%; }
.code-input-wrapper { display: flex; align-items: center; gap: 12px; }
.code-input { width: 60%; }
.captcha-surface, .code-action { width: 35%; height: 40px; }
.captcha-surface { cursor: pointer; border-radius: 14px; object-fit: contain; background: linear-gradient(180deg, #f7faff 0%, #eef4fb 100%); box-shadow: inset 0 0 0 1px rgba(220, 230, 241, 0.9); }
.remember-checkbox { margin-left: 10px; }
:deep(.login-tabs .el-tabs__nav-wrap::after) { background-color: rgba(228, 235, 243, 0.9); }
:deep(.login-tabs .el-tabs__item) { font-weight: 600; }
@media (max-width: 768px) {
  .login-form-wrapper { width: 90%; max-width: 350px; padding: 30px 20px; margin: 0 10px; }
  .login-title { font-size: 20px; margin-bottom: 25px; }
  :deep(.el-form-item) { margin-bottom: 20px; }
  :deep(.el-form-item__label) { display: none; }
  :deep(.el-form-item__content) { margin-left: 0 !important; justify-content: center; }
  :deep(.el-input__inner) { height: 44px; line-height: 44px; }
  .code-input-wrapper { flex-direction: column; gap: 10px; }
  .code-input, .captcha-surface, .code-action { width: 100%; }
  :deep(.el-button--primary) { height: 44px; font-size: 16px; }
  .remember-checkbox { margin-left: 0; text-align: center; display: block; }
}
</style>
