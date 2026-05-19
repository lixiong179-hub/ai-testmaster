<template>
  <div class="main-layout">
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
          <el-menu-item index="/home/requirement"><span>资源列表</span></el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="case">
          <template #title>
            <el-icon><Check /></el-icon>
            <span>测试用例管理</span>
          </template>
          <el-menu-item index="/home/case"><span>用例列表</span></el-menu-item>
          <el-menu-item index="/home/case/test-point-management"><span>测试点管理</span></el-menu-item>
          <el-menu-item index="/home/case/ai-generate"><span>AI生成用例</span></el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="task">
          <template #title>
            <el-icon><Timer /></el-icon>
            <span>测试任务管理</span>
          </template>
          <el-menu-item index="/home/task"><span>任务列表</span></el-menu-item>
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
          <el-menu-item index="/home/system/user"><span>用户管理</span></el-menu-item>
          <el-menu-item index="/home/system/role"><span>角色管理</span></el-menu-item>
        </el-sub-menu>
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
            <el-breadcrumb-item v-for="(item, index) in breadcrumbList" :key="index">{{ item.name }}</el-breadcrumb-item>
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
                <el-dropdown-item @click="handleProfile"><el-icon><User /></el-icon><span>个人中心</span></el-dropdown-item>
                <el-dropdown-item @click="handleLogout"><el-icon><SwitchButton /></el-icon><span>退出登录</span></el-dropdown-item>
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
import {
  HomeFilled, DataAnalysis, Setting, Menu, ArrowDown, ArrowUp, User, SwitchButton, Message, Check, Timer,
} from '@element-plus/icons-vue'
import { useMainLayout } from './useMainLayout'

const {
  isMobile, sidebarExpanded, username, userAvatar, activeMenu, breadcrumbList,
  toggleSidebar, handleMenuSelect, handleProfile, handleLogout,
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
