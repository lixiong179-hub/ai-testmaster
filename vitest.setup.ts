import ElementPlus from 'element-plus'
import { config } from '@vue/test-utils'
import { installBrowserStubs } from './src/test-utils/env'

config.global.plugins = [ElementPlus]
config.global.stubs = {
  teleport: true,
  transition: false,
}

// 统一安装浏览器 API 桩，避免每个 spec 重复定义
installBrowserStubs()
