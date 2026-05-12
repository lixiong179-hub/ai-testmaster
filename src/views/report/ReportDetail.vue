<template>
  <div class="report-detail">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>报告详情</span>
          <div>
            <el-dropdown trigger="click" :disabled="exportLoading">
              <el-button type="primary" size="small" :loading="exportLoading">
                导出 <el-icon class="el-icon--right"><arrow-down /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="handleExportPDF">导出PDF</el-dropdown-item>
                  <el-dropdown-item @click="handleExportHTML">导出HTML</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button type="primary" size="small" @click="goBack" style="margin-left: 10px">
              返回列表
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="report" class="report-content">
        <!-- 报告基本信息 -->
        <el-card shadow="hover" class="mb-4">
          <el-form :model="report" label-width="120px">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="报告名称">
                  <el-input v-model="report.name" disabled />
                </el-form-item>
                <el-form-item label="项目">
                  <el-input v-model="report.project_name" disabled />
                </el-form-item>
                <el-form-item label="测试任务">
                  <el-input v-model="report.test_task_name" disabled />
                </el-form-item>
                <el-form-item label="创建时间">
                  <el-input v-model="report.created_at" disabled />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="总用例数">
                  <el-input v-model="report.total_cases" disabled />
                </el-form-item>
                <el-form-item label="通过用例">
                  <el-input v-model="report.passed_cases" disabled />
                </el-form-item>
                <el-form-item label="失败用例">
                  <el-input v-model="report.failed_cases" disabled />
                </el-form-item>
                <el-form-item label="通过率">
                  <el-input v-model="report.pass_rate" disabled />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </el-card>

        <!-- 报告统计 -->
        <ReportStat :report="report" />

        <!-- 用例详情表格 -->
        <ReportTable
          :testCases="report.test_cases || []"
          :total="report.total_cases || 0"
          @pageChange="handlePageChange"
        />
      </div>
      <div v-else class="loading">
        <el-skeleton :rows="10" animated />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElLoading } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useReportStore } from '@/store/report'
import ReportStat from '@/components/report/ReportStat.vue'
import ReportTable from '@/components/report/ReportTable.vue'

const route = useRoute()
const router = useRouter()
const reportStore = useReportStore()
const exportLoading = ref(false)

// 计算属性
const reportId = computed(() => {
  const id = Number(route.query.id)
  return isNaN(id) || id <= 0 ? 0 : id
})

const projectId = computed(() => {
  const id = Number(route.query.project_id)
  return isNaN(id) || id <= 0 ? 0 : id
})

const report = computed(() => reportStore.currentReport)

// 返回列表
const goBack = () => {
  router.push('/home/report')
}

// 处理分页
const handlePageChange = (_page: number, _pageSize: number) => {
}

// 处理导出PDF
const handleExportPDF = async () => {
  if (!reportId.value) return

  exportLoading.value = true
  try {
    const loadingInstance = ElLoading.service({
      lock: true,
      text: '正在导出PDF...',
      background: 'rgba(0, 0, 0, 0.7)',
    })

    const response = await reportStore.exportReportPDF(reportId.value, projectId.value)
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${report.value?.name || '测试报告'}.pdf`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    loadingInstance.close()
    ElMessage.success('导出PDF成功')
  } catch (error: any) {
    ElMessage.error(`导出PDF失败: ${error.message || '未知错误'}`)
  } finally {
    exportLoading.value = false
  }
}

// 处理导出HTML
const handleExportHTML = async () => {
  if (!reportId.value) return

  exportLoading.value = true
  try {
    const loadingInstance = ElLoading.service({
      lock: true,
      text: '正在导出HTML...',
      background: 'rgba(0, 0, 0, 0.7)',
    })

    const response = await reportStore.exportReportHTML(reportId.value, projectId.value)
    const blob = new Blob([response.data], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${report.value?.name || '测试报告'}.html`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    loadingInstance.close()
    ElMessage.success('导出HTML成功')
  } catch (error: any) {
    ElMessage.error(`导出HTML失败: ${error.message || '未知错误'}`)
  } finally {
    exportLoading.value = false
  }
}

// 获取报告详情
const fetchReportDetail = async () => {
  if (!reportId.value) {
    ElMessage.error('报告ID无效')
    return
  }

  if (!projectId.value) {
    ElMessage.error('项目ID无效')
    return
  }

  try {
    await reportStore.fetchReportDetail(reportId.value, projectId.value)
  } catch (error: any) {
    ElMessage.error(error.message || '获取报告详情失败')
  }
}

// 初始化
onMounted(() => {
  fetchReportDetail()
})
</script>

<style scoped>
.report-detail {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-content {
  margin-top: 20px;
}

.loading {
  margin-top: 20px;
}

.mb-4 {
  margin-bottom: 20px;
}
</style>
