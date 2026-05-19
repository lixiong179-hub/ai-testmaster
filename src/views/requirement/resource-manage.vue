<template>
  <div class="resource-manage-container">
    <el-card class="filter-card">
      <el-form :inline="true" :model="ctx.resourceList.filterForm">
        <el-form-item label="项目">
          <el-select v-model="ctx.resourceList.filterForm.project_id" placeholder="请先选择项目" style="width: 200px" clearable filterable>
            <el-option v-for="project in ctx.projects.value" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="ctx.resourceList.filterForm.resource_type" placeholder="全部" style="width: 150px" clearable @change="ctx.resourceList.handleSearch">
            <el-option v-for="option in RESOURCE_TYPE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="ctx.resourceList.handleSearch">查询</el-button>
          <el-button @click="ctx.handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <div class="main-content">
      <IterationPanel />
      <ResourceTable />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { provideResourceManage, RESOURCE_TYPE_OPTIONS } from '@/composables/requirement/useResourceManage'
import IterationPanel from './components/IterationPanel.vue'
import ResourceTable from './components/ResourceTable.vue'

const ctx = provideResourceManage()

onMounted(ctx.init)
onUnmounted(ctx.cleanup)
</script>

<style scoped>
.resource-manage-container { padding: 20px; display: flex; flex-direction: column; height: calc(100vh - 100px); }
.filter-card { margin-bottom: 15px; flex-shrink: 0; }
.main-content { display: flex; flex: 1; min-height: 0; gap: 16px; }
</style>
