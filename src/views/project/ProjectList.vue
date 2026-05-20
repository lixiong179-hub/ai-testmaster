<template>
  <div class="project-list">
    <el-card class="project-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">项目列表</div>
            <div class="card-subtitle">
              从项目进入任务、执行与测试点管理，是整条测试业务链路的起点。
            </div>
          </div>
          <el-button type="primary" @click="openCreateDialog">创建项目</el-button>
        </div>
      </template>

      <div class="search-bar">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索项目名称"
          clearable
          class="search-input"
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button @click="handleSearch">搜索</el-button>
          </template>
        </el-input>
        <el-tag effect="plain" type="info">共 {{ projectStore.total }} 个项目</el-tag>
      </div>

      <el-table
        class="project-table"
        v-loading="projectStore.loading"
        :data="filteredProjects"
        style="width: 100%"
        border
      >
        <el-table-column prop="id" label="项目ID" width="80" />
        <el-table-column prop="name" label="项目名称">
          <template #default="scope">
            <el-link @click="goToDetail(scope.row.id)">{{ scope.row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="project_type" label="项目类型" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.project_type === 'web' ? 'success' : 'warning'">
              {{ scope.row.project_type === 'web' ? 'Web端' : 'C端' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="项目描述" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="create_time" label="创建时间" width="180" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="scope">
            <el-space wrap>
              <el-button size="small" @click="goToDetail(scope.row.id)">详情</el-button>
              <el-button size="small" type="primary" plain @click="goToTaskList(scope.row.id)"
                >任务</el-button
              >
              <el-button
                size="small"
                type="success"
                plain
                @click="goToTestPointManagement(scope.row.id)"
                >测试点</el-button
              >
              <el-button size="small" type="danger" @click="confirmDelete(scope.row.id)"
                >删除</el-button
              >
            </el-space>
          </template>
        </el-table-column>
        <template #empty>
          <div class="project-empty-state">
            <div class="project-empty-title">还没有可用项目</div>
            <div class="project-empty-text">
              建议先创建项目，后续任务、执行与测试点管理都会围绕项目展开。
            </div>
            <el-button type="primary" @click="openCreateDialog">创建首个项目</el-button>
          </div>
        </template>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="projectStore.currentPage"
          v-model:page-size="projectStore.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="projectStore.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" title="创建项目" width="700px">
      <el-form :model="projectForm" :rules="projectRules" ref="projectFormRef" label-width="100px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="projectForm.name" placeholder="请输入项目名称" />
        </el-form-item>

        <el-form-item label="项目类型" prop="project_type">
          <el-radio-group v-model="projectForm.project_type">
            <el-radio value="web">Web端</el-radio>
            <el-radio value="app">C端 (预留)</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="项目描述" prop="description">
          <el-input
            v-model="projectForm.description"
            type="textarea"
            placeholder="请输入项目描述"
            :rows="3"
          />
        </el-form-item>

        <template v-if="projectForm.project_type === 'web'">
          <el-divider content-position="left">Web端多环境配置（选填）</el-divider>

          <el-form-item label="测试环境">
            <el-row :gutter="10">
              <el-col :span="10">
                <el-input v-model="projectForm.web_env_configs.test.url" placeholder="测试环境URL" autocomplete="off" />
              </el-col>
              <el-col :span="6">
                <el-input v-model="projectForm.web_env_configs.test.username" placeholder="账号" autocomplete="off" />
              </el-col>
              <el-col :span="6">
                <el-input v-model="projectForm.web_env_configs.test.password" type="password" placeholder="密码" show-password autocomplete="new-password" />
              </el-col>
            </el-row>
          </el-form-item>

          <el-form-item label="灰度环境">
            <el-row :gutter="10">
              <el-col :span="10">
                <el-input v-model="projectForm.web_env_configs.staging.url" placeholder="灰度环境URL" autocomplete="off" />
              </el-col>
              <el-col :span="6">
                <el-input v-model="projectForm.web_env_configs.staging.username" placeholder="账号" autocomplete="off" />
              </el-col>
              <el-col :span="6">
                <el-input v-model="projectForm.web_env_configs.staging.password" type="password" placeholder="密码" show-password autocomplete="new-password" />
              </el-col>
            </el-row>
          </el-form-item>

          <el-form-item label="正式环境">
            <el-row :gutter="10">
              <el-col :span="10">
                <el-input v-model="projectForm.web_env_configs.prod.url" placeholder="正式环境URL" autocomplete="off" />
              </el-col>
              <el-col :span="6">
                <el-input v-model="projectForm.web_env_configs.prod.username" placeholder="账号" autocomplete="off" />
              </el-col>
              <el-col :span="6">
                <el-input v-model="projectForm.web_env_configs.prod.password" type="password" placeholder="密码" show-password autocomplete="new-password" />
              </el-col>
            </el-row>
          </el-form-item>
        </template>

        <template v-else>
          <el-divider content-position="left">C端设备配置（预留）</el-divider>
          <el-form-item>
            <el-alert type="info" :closable="false">
              C端测试功能正在开发中，设备配置功能暂不可用。
            </el-alert>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="createProject">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { useProjectList } from './useProjectList'

const {
  projectStore, dialogVisible, projectFormRef, searchKeyword, projectForm, projectRules,
  filteredProjects, getStatusType, getStatusText, handleSearch, handleCurrentChange,
  handleSizeChange, openCreateDialog, createProject, goToDetail, goToTaskList,
  goToTestPointManagement, confirmDelete,
} = useProjectList()
</script>

<style scoped lang="scss">
@import './ProjectList.scss';
</style>
