<template>
  <div class="profile">
    <el-card class="page-card">
      <template #header>
        <div class="card-header">
          <h2>个人中心</h2>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="basic">
          <el-form :model="userInfo" label-width="120px">
            <el-form-item label="用户名">
              <el-input v-model="userInfo.username" disabled />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="userInfo.email" disabled />
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model="userInfo.phone" disabled />
            </el-form-item>
            <el-form-item label="最后登录时间">
              <el-input v-model="userInfo.last_login_time" disabled />
            </el-form-item>
            <el-form-item label="创建时间">
              <el-input v-model="userInfo.created_at" disabled />
            </el-form-item>
            <el-form-item label="角色">
              <el-tag v-for="role in userInfo.roles" :key="role.id" class="role-tag">
                {{ role.name }}
              </el-tag>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 修改密码 -->
        <el-tab-pane label="修改密码" name="password">
          <el-form
            ref="passwordFormRef"
            :model="passwordForm"
            :rules="passwordRules"
            label-width="120px"
          >
            <el-form-item label="当前密码" prop="oldPassword">
              <el-input v-model="passwordForm.oldPassword" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码" prop="newPassword">
              <el-input v-model="passwordForm.newPassword" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input v-model="passwordForm.confirmPassword" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="changePassword" :loading="loading">
                确认修改
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 登录日志 -->
        <el-tab-pane label="登录日志" name="logs">
          <div class="log-filter">
            <el-date-picker
              v-model="logDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              style="width: 300px"
              @change="loadLoginLogs"
            />
            <el-button @click="loadLoginLogs" style="margin-left: 10px">
              <el-icon><Search /></el-icon>
              搜索
            </el-button>
          </div>

          <el-table :data="loginLogs" style="width: 100%" v-loading="logsLoading">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="username" label="用户名" />
            <el-table-column prop="ip" label="登录IP" width="150" />
            <el-table-column prop="user_agent" label="用户代理" />
            <el-table-column prop="login_time" label="登录时间" width="180" />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="scope">
                <el-tag :type="scope.row.status ? 'success' : 'danger'">
                  {{ scope.row.status ? '成功' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <div class="pagination">
            <el-pagination
              v-model:current-page="logsPagination.page"
              v-model:page-size="logsPagination.size"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              :total="logsPagination.total"
              @size-change="handleLogsSizeChange"
              @current-change="handleLogsCurrentChange"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import axios from '@/utils/request'
import type { User, Pagination } from '@/types/user'

// 状态管理
const activeTab = ref('basic')
const loading = ref(false)
const logsLoading = ref(false)

// 用户信息
const userInfo = reactive<User>({
  id: 0,
  username: '',
  email: '',
  phone: '',
  status: true,
  last_login_time: null,
  created_at: '',
  roles: [],
})

// 修改密码表单
const passwordFormRef = ref()
const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const passwordRules = {
  oldPassword: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度至少6位', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: any) => {
        if (value !== passwordForm.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur',
    },
  ],
}

// 登录日志
const loginLogs = ref<any[]>([])
const logDateRange = ref<[Date, Date] | null>(null)
const logsPagination = reactive<Pagination>({
  page: 1,
  size: 10,
  total: 0,
})

// 加载用户信息
const loadUserInfo = async () => {
  try {
    const response = await axios.get('/api/v1/user/me')
    Object.assign(userInfo, response.data)
  } catch (error) {
    ElMessage.error('获取用户信息失败')
  }
}

// 加载登录日志
const loadLoginLogs = async () => {
  logsLoading.value = true
  try {
    const response = await axios.get('/api/v1/user/login-logs', {
      params: {
        skip: (logsPagination.page - 1) * logsPagination.size,
        limit: logsPagination.size,
        start_date: logDateRange.value?.[0]?.toISOString(),
        end_date: logDateRange.value?.[1]?.toISOString(),
      },
    })
    loginLogs.value = response.data
    // 假设返回的数据包含total字段
    logsPagination.total = response.headers['x-total-count'] || loginLogs.value.length
  } catch (error) {
    ElMessage.error('获取登录日志失败')
  } finally {
    logsLoading.value = false
  }
}

// 修改密码
const changePassword = async () => {
  if (!passwordFormRef.value) return

  await passwordFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      loading.value = true
      try {
        await axios.post('/api/v1/user/change-password', {
          old_password: passwordForm.oldPassword,
          new_password: passwordForm.newPassword,
        })
        ElMessage.success('密码修改成功，请重新登录')
        // 重置表单
        Object.assign(passwordForm, {
          oldPassword: '',
          newPassword: '',
          confirmPassword: '',
        })
        // 实际项目中应该跳转到登录页
      } catch (error: any) {
        ElMessage.error(error.response?.data?.message || '密码修改失败')
      } finally {
        loading.value = false
      }
    }
  })
}

// 分页
const handleLogsSizeChange = (size: number) => {
  logsPagination.size = size
  loadLoginLogs()
}

const handleLogsCurrentChange = (page: number) => {
  logsPagination.page = page
  loadLoginLogs()
}

// 初始化
onMounted(() => {
  loadUserInfo()
  loadLoginLogs()
})
</script>

<style scoped>
.profile {
  padding: 20px;
}

.page-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.role-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}

.log-filter {
  margin-bottom: 20px;
  display: flex;
  align-items: center;
}

.pagination {
  margin-top: 20px;
  text-align: right;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .profile {
    padding: 10px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .log-filter {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .log-filter .el-date-picker {
    width: 100%;
  }

  .el-table {
    font-size: 12px;
  }

  .el-table th,
  .el-table td {
    padding: 8px 4px;
  }

  .pagination {
    margin-top: 10px;
  }

  :deep(.el-pagination) {
    font-size: 12px;
  }

  :deep(.el-pagination__sizes .el-input__inner) {
    width: 80px;
  }
}
</style>
