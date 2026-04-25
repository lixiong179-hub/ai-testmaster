<template>
  <div class="main-layout">
    <!-- 侧边栏 -->
    <div class="sidebar" :class="{ expanded: sidebarExpanded }">
      <div class="logo" @click="toggleSidebar">
        <h3>AI TestMaster</h3>
        <el-icon v-if="isMobile" class="mobile-toggle">
          <ArrowDown v-if="!sidebarExpanded" />
          <ArrowUp v-if="sidebarExpanded" />
        </el-icon>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="sidebar-menu"
        router
        unique-opened
        background-color="#1f2d3d"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        @select="handleMenuSelect"
      >
        <el-menu-item index="/home/project">
          <el-icon><HomeFilled /></el-icon>
          <span>项目列表</span>
        </el-menu-item>
        <el-sub-menu index="requirement">
          <template #title>
            <el-icon><Message /></el-icon>
            <span>资源管理</span>
          </template>
          <el-menu-item index="/home/requirement">
            <span>资源列表</span>
          </el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="case">
          <template #title>
            <el-icon><Check /></el-icon>
            <span>测试用例管理</span>
          </template>
          <el-menu-item index="/home/case">
            <span>用例列表</span>
          </el-menu-item>
          <el-menu-item index="/home/case/test-point-management">
            <span>测试点管理</span>
          </el-menu-item>
          <el-menu-item index="/home/case/ai-generate">
            <span>AI生成用例</span>
          </el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="task">
          <template #title>
            <el-icon><Timer /></el-icon>
            <span>测试任务管理</span>
          </template>
          <el-menu-item index="/home/task">
            <span>任务列表</span>
          </el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/home/report">
          <el-icon><DataAnalysis /></el-icon>
          <span>测试报告</span>
        </el-menu-item>
        <el-sub-menu index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/home/system/user">
            <span>用户管理</span>
          </el-menu-item>
          <el-menu-item index="/home/system/role">
            <span>角色管理</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </div>

    <!-- 主内容区 -->
    <div class="main-container">
      <!-- 顶部导航 -->
      <div class="top-nav">
        <div class="nav-left">
          <el-button link @click="toggleSidebar" class="sidebar-toggle">
            <el-icon><Menu /></el-icon>
          </el-button>
          <el-breadcrumb separator="/" class="breadcrumb">
            <el-breadcrumb-item :to="{ path: '/home/project' }">工作台</el-breadcrumb-item>
            <el-breadcrumb-item v-for="(item, index) in breadcrumbList" :key="index">
              {{ item.name }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="nav-right">
          <el-dropdown>
            <span class="user-info">
              <el-avatar :size="32" :src="userAvatar"></el-avatar>
              <span class="username">{{ username }}</span>
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleProfile">
                  <el-icon><User /></el-icon>
                  <span>个人中心</span>
                </el-dropdown-item>
                <el-dropdown-item @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon>
                  <span>退出登录</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <!-- 内容区域 -->
      <div class="main-content">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  HomeFilled,
  DataAnalysis,
  Setting,
  Menu,
  ArrowDown,
  ArrowUp,
  User,
  SwitchButton,
  Message,
  Check,
  Timer,
} from '@element-plus/icons-vue'

// 路由实例
const router = useRouter()
const route = useRoute()

// 移动端检测
const isMobile = ref(false)
const sidebarExpanded = ref(false)

// 检测是否为移动端
const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

// 组件挂载
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkMobile)
})

// 用户信息
const username = ref('测试管理员')
const userAvatar = ref('')

// 计算当前激活的菜单
const activeMenu = computed(() => {
  return route.path
})

// 面包屑列表
const breadcrumbList = ref<{ path: string; name: string }[]>([])

// 更新面包屑
const updateBreadcrumb = (path: string) => {
  const breadcrumbMap: Record<string, string> = {
    '/home/dashboard': '仪表盘',
    '/home/project': '项目列表',
    '/home/project/detail': '项目详情',
    '/home/requirement': '资源管理',
    '/home/requirement/upload': '上传需求',
    '/home/requirement/ui-prototype': 'UI原型图',
    '/home/case': '测试用例管理',
    '/home/case/test-point-management': '测试点管理',
    '/home/case/ai-generate': 'AI生成用例',
    '/home/task': '测试任务管理',
    '/home/report': '测试报告',
    '/home/system': '系统管理',
    '/home/system/user': '用户管理',
    '/home/system/role': '角色管理',
  }

  const pathParts = path.split('/').filter(Boolean)
  const result: { path: string; name: string }[] = []
  let currentPath = ''

  for (let i = 0; i < pathParts.length; i++) {
    currentPath += '/' + pathParts[i]
    const name = breadcrumbMap[currentPath]
    if (name) {
      result.push({ path: currentPath, name })
    }
  }

  breadcrumbList.value = result
}

// 监听路由变化，更新面包屑
watch(
  () => route.path,
  (newPath) => {
    updateBreadcrumb(newPath)
  },
  { immediate: true }
)

// 切换侧边栏
const toggleSidebar = () => {
  if (isMobile.value) {
    sidebarExpanded.value = !sidebarExpanded.value
  }
}

// 处理菜单选择
const handleMenuSelect = () => {
  if (isMobile.value) {
    sidebarExpanded.value = false
  }
}

// 处理个人中心
const handleProfile = () => {
  router.push('/home/system/profile')
}

// 处理退出登录
const handleLogout = () => {
  localStorage.removeItem('token')
  ElMessage.success('退出登录成功')
  router.push('/login')
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: row;
  background-color: #f5f7fa;
}

.sidebar {
  display: flex;
  flex-direction: column;
  background-color: #1f2d3d;
  color: #fff;
  width: 220px;
  height: 100%;
  flex-shrink: 0;
  transition: all 0.3s;
}

.main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
}

.top-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  height: 60px;
  flex-shrink: 0;
}

.main-content {
  flex: 1;
  padding: 20px;
  background-color: #f5f7fa;
  overflow-y: auto;
  min-height: 0;
  display: block;
}

.logo {
  flex-shrink: 0;
  padding: 18px 16px;
  text-align: center;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
}

.logo h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: #fff;
}

.mobile-toggle {
  cursor: pointer;
  font-size: 16px;
}

.sidebar-menu {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  border-right: none !important;
}

/* 与 Element Plus 深色菜单配合：子菜单缩进区域背景 */
.sidebar-menu :deep(.el-sub-menu .el-menu) {
  background-color: #151e2a !important;
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  margin: 2px 8px;
  border-radius: 6px;
}

.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background-color: rgba(255, 255, 255, 0.06) !important;
}

.nav-left {
  display: flex;
  align-items: center;
}

.sidebar-toggle {
  margin-right: 20px;
}

.breadcrumb {
  font-size: 14px;
}

.nav-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 20px;
  transition: background-color 0.3s;
}

.user-info:hover {
  background-color: #f5f7fa;
}

.username {
  margin: 0 8px;
  font-size: 14px;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .main-layout {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    height: auto;
    max-height: 60px;
    overflow: hidden;
    transition: max-height 0.3s;
  }

  .sidebar.expanded {
    max-height: 100vh;
  }

  .logo {
    padding: 15px;
  }

  .logo h3 {
    font-size: 16px;
  }

  .sidebar-menu {
    max-height: calc(100vh - 60px);
    overflow-y: auto;
  }

  .sidebar-menu .el-menu-item,
  .sidebar-menu .el-sub-menu__title {
    height: 50px;
    line-height: 50px;
    margin: 0 5px;
  }

  .top-nav {
    padding: 0 10px;
    height: 50px;
  }

  .breadcrumb {
    display: none;
  }

  .username {
    display: none;
  }

  .main-content {
    padding: 10px;
  }
}
</style>
