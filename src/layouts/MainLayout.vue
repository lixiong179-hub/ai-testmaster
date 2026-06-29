<template>
  <div class="main-layout">
    <div class="sidebar" :class="{ expanded: sidebarExpanded, collapsed: sidebarCollapsed }">
      <div class="logo" @click="toggleSidebar">
        <h3 v-show="!sidebarCollapsed || isMobile">AI TestMaster</h3>
        <h3 v-show="sidebarCollapsed && !isMobile" class="logo-mark">AI</h3>
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
        :collapse="sidebarCollapsed && !isMobile"
        :collapse-transition="false"
        background-color="#1f2d3d"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        @select="handleMenuSelect"
      >
        <template v-for="item in menuItems" :key="item.index">
          <el-sub-menu v-if="item.children && item.children.length > 0" :index="item.index">
            <template #title>
              <el-icon><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </template>
            <el-menu-item v-for="child in item.children" :key="child.index" :index="child.index">
              <span>{{ child.label }}</span>
            </el-menu-item>
          </el-sub-menu>
          <el-menu-item v-else :index="item.index">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.label }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </div>

    <div class="main-container">
      <div class="top-nav">
        <div class="nav-left">
          <el-button link @click="toggleSidebar" class="sidebar-toggle">
            <el-icon><Menu /></el-icon>
          </el-button>
          <el-breadcrumb separator="/" class="breadcrumb">
            <el-breadcrumb-item :to="{ path: '/home/project' }">工作台</el-breadcrumb-item>
            <el-breadcrumb-item v-for="(item, index) in breadcrumbList" :key="index">{{
              item.name
            }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="nav-right">
          <QuickTestGlobalEntry class="nav-quick-entry" />
          <el-dropdown>
            <span class="user-info">
              <el-avatar :size="32" :src="userAvatar"></el-avatar>
              <span class="username">{{ username }}</span>
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleProfile"
                  ><el-icon><User /></el-icon><span>个人中心</span></el-dropdown-item
                >
                <el-dropdown-item @click="handleLogout"
                  ><el-icon><SwitchButton /></el-icon><span>退出登录</span></el-dropdown-item
                >
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>

      <div class="main-content">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Menu, ArrowDown, ArrowUp, User, SwitchButton } from '@element-plus/icons-vue'
import { useMainLayout } from './useMainLayout'
import QuickTestGlobalEntry from '@/components/QuickTestGlobalEntry.vue'

const {
  isMobile,
  sidebarExpanded,
  sidebarCollapsed,
  username,
  userAvatar,
  activeMenu,
  breadcrumbList,
  menuItems,
  toggleSidebar,
  handleMenuSelect,
  handleProfile,
  handleLogout,
} = useMainLayout()
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
  transition:
    width 0.2s ease,
    max-height 0.2s ease;
  box-shadow: 2px 0 10px rgba(18, 31, 46, 0.08);
}

.sidebar.collapsed {
  width: 64px;
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
  padding: 16px;
  background-color: #f5f7fa;
  overflow: auto;
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
  white-space: nowrap;
}

.logo-mark {
  letter-spacing: 0;
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

.sidebar-menu:not(.el-menu--collapse) {
  width: 100%;
}

.sidebar-menu.el-menu--collapse {
  width: 64px;
}

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
  min-width: 0;
}

.sidebar-toggle {
  margin-right: 20px;
  flex-shrink: 0;
}

.breadcrumb {
  font-size: 14px;
  min-width: 0;
}

.nav-right {
  display: flex;
  align-items: center;
}

.nav-quick-entry {
  margin-right: 16px;
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

  .sidebar.collapsed {
    width: 100%;
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
