import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import App from './App.vue'
import router from './router'
import axios from './utils/request'
import { registerPermissionDirective } from './directives/permission'

const app = createApp(App)

// 配置Pinia
const pinia = createPinia()
app.use(pinia)
const testWindow = window as typeof window & { Cypress?: unknown; __pinia?: typeof pinia }
if (import.meta.env.MODE === 'test' || typeof testWindow.Cypress !== 'undefined') {
  testWindow.__pinia = pinia
}

// 配置 Element Plus
app.use(ElementPlus, { locale: zhCn })

// 配置路由
app.use(router)

// 注册权限指令
registerPermissionDirective(app)

// 全局配置Axios
app.config.globalProperties.$axios = axios

app.mount('#app')
