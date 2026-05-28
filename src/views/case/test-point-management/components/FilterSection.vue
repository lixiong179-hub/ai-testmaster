<template>
  <el-card class="section-card filter-card" shadow="never">
    <div class="section-header">
      <div>
        <div class="section-title">筛选与定位</div>
        <div class="section-subtitle">快速收敛测试点范围，聚焦需要处理的模块、需求和负责人。</div>
      </div>
      <div class="section-actions">
        <el-button type="primary" :icon="Search" @click="fetchTestPoints">查询</el-button>
        <el-button :icon="RefreshRight" @click="resetFilters">重置</el-button>
      </div>
    </div>
    <el-form :model="filters" inline class="filter-form">
      <el-form-item label="模块">
        <el-input v-model="filters.module" placeholder="模块名称" clearable />
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="filters.priority" placeholder="全部" clearable>
          <el-option label="高" :value="1" />
          <el-option label="中" :value="2" />
          <el-option label="低" :value="3" />
        </el-select>
      </el-form-item>
      <el-form-item label="需求">
        <el-select
          v-model="filters.requirement_id"
          placeholder="全部需求"
          clearable
          filterable
          class="requirement-select"
        >
          <el-option
            v-for="item in requirementOptions"
            :key="item.id"
            :label="`${item.req_no} - ${item.title}`"
            :value="item.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="创建人">
        <el-input v-model="filters.created_by" placeholder="创建人" clearable />
      </el-form-item>
      <el-form-item label="创建时间">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
      </el-form-item>
      <el-form-item label="关键词">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索模块/功能/测试点"
          clearable
          @keyup.enter="fetchTestPoints"
        />
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { RefreshRight, Search } from '@element-plus/icons-vue'
import { TestPointMgmtKey } from '../useTestPointManagement'

const mgmt = inject(TestPointMgmtKey)!
const { filters, dateRange, requirementOptions, fetchTestPoints, resetFilters } = mgmt
</script>

<style scoped>
.section-card {
  border: none;
  border-radius: 20px;
  box-shadow: 0 10px 28px rgba(31, 45, 61, 0.05);
}
.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.section-title {
  font-size: 18px;
  font-weight: 700;
  color: #1f2d3d;
}
.section-subtitle {
  margin-top: 6px;
  color: #7a8594;
  line-height: 1.5;
}
.section-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.filter-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 2px 12px;
  margin-bottom: 0;
}
:deep(.filter-form .el-form-item) {
  margin-right: 0;
  margin-bottom: 16px;
}
:deep(.filter-form .el-input),
:deep(.filter-form .el-select),
:deep(.filter-form .el-date-editor) {
  width: 100%;
}
.requirement-select {
  width: 100%;
}
</style>
