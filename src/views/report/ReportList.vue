<template>
  <div class="report-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>测试报告列表</span>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="项目">
          <el-select v-model="searchForm.project_id" placeholder="请选择项目" style="width: 200px">
            <el-option
              v-for="project in projects"
              :key="project.id"
              :label="project.name"
              :value="project.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="getReports">查询</el-button>
        </el-form-item>
      </el-form>

      <el-table :data="reports" style="width: 100%" border stripe>
        <el-table-column prop="id" label="报告ID" width="80" />
        <el-table-column prop="name" label="报告名称" min-width="200" />
        <el-table-column prop="total_cases" label="总用例数" width="100" />
        <el-table-column prop="passed_cases" label="通过数" width="100" />
        <el-table-column prop="failed_cases" label="失败数" width="100" />
        <el-table-column prop="blocked_cases" label="阻塞数" width="100" />
        <el-table-column prop="pass_rate" label="通过率" width="100">
          <template #default="scope"> {{ scope.row.pass_rate.toFixed(2) }}% </template>
        </el-table-column>
        <el-table-column prop="create_time" label="生成时间" width="180" />
        <el-table-column label="操作" width="250">
          <template #default="scope">
            <el-button type="primary" size="small" @click="handleView(scope.row)"> 查看 </el-button>
            <el-dropdown trigger="click">
              <el-button type="success" size="small">
                导出 <el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleExportPDF(scope.row)">导出PDF</el-dropdown-item>
                  <el-dropdown-item @click="handleExportHTML(scope.row)">导出HTML</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button type="danger" size="small" @click="handleDelete(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination" v-if="total > 0">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useReportStore } from '@/store/report'
import projectApi from '@/api/project'
import type { Report } from '@/api/report'

interface Project {
  id: number
  name: string
}

const router = useRouter()
const route = useRoute()
const reportStore = useReportStore()
const projects = ref<Project[]>([])
const page = ref(1)
const pageSize = ref(10)
const searchForm = ref({
  project_id: '' as number | '',
})

// 计算属性
const reports = computed(() => reportStore.reports)
const total = computed(() => reportStore.total)

// 获取项目列表
const getProjects = async () => {
  try {
    const response = await projectApi.getProjects({ page: 1, page_size: 100 })
    projects.value = response.data.items

    // 如果URL中有project_id参数，设置为默认值
    const projectId = route.query.project_id
    if (projectId) {
      searchForm.value.project_id = Number(projectId)
    }
  } catch (error) {
    console.error('获取项目列表失败:', error)
    ElMessage.error('获取项目列表失败')
  }
}

// 获取报告列表
const getReports = async () => {
  try {
    await reportStore.fetchReports({
      page: page.value,
      page_size: pageSize.value,
      project_id: searchForm.value.project_id || undefined,
    })
  } catch (error) {
    ElMessage.error('获取报告列表失败')
  }
}

// 处理分页
const handleSizeChange = (size: number) => {
  pageSize.value = size
  getReports()
}

const handleCurrentChange = (current: number) => {
  page.value = current
  getReports()
}

// 处理查看报告（需要project_id）
const handleView = (report: Report) => {
  if (!report.project_id) {
    ElMessage.error('报告缺少项目ID，无法查看详情')
    return
  }
  router.push({
    path: `/home/report/detail`,
    query: { id: report.id, project_id: report.project_id },
  })
}

// 处理导出PDF（需要project_id）
const handleExportPDF = async (report: Report) => {
  if (!report.project_id) {
    ElMessage.error('报告缺少项目ID，无法导出')
    return
  }
  try {
    const response = await reportStore.exportReportPDF(report.id, report.project_id)
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${report.name}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('导出PDF成功')
  } catch (error) {
    ElMessage.error('导出PDF失败')
  }
}

// 处理导出HTML（需要project_id）
const handleExportHTML = async (report: Report) => {
  if (!report.project_id) {
    ElMessage.error('报告缺少项目ID，无法导出')
    return
  }
  try {
    const response = await reportStore.exportReportHTML(report.id, report.project_id)
    const blob = new Blob([response.data], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${report.name}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('导出HTML成功')
  } catch (error) {
    ElMessage.error('导出HTML失败')
  }
}

// 处理删除报告（需要project_id）
const handleDelete = (report: Report) => {
  if (!report.project_id) {
    ElMessage.error('报告缺少项目ID，无法删除')
    return
  }
  ElMessageBox.confirm('确定要删除这个报告吗？', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(async () => {
    try {
      await reportStore.deleteReport(report.id, report.project_id)
      ElMessage.success('删除成功')
    } catch (error) {
      ElMessage.error('删除失败')
    }
  })
}

// 初始化
onMounted(() => {
  getProjects()
  getReports()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
