import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import axios from './utils/request'
import { registerPermissionDirective } from './directives/permission'

const app = createApp(App)

// 配置Pinia
const pinia = createPinia()
app.use(pinia)

// 配置Element Plus
app.use(ElementPlus)

// 配置路由
app.use(router)

// 注册权限指令
registerPermissionDirective(app)

// 全局配置Axios
app.config.globalProperties.$axios = axios

app.mount('#app')
