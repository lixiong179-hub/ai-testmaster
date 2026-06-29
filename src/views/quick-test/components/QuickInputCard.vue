<template>
    <el-card class="quick-input-card" shadow="never">
        <template #header>
            <div class="card-header">
                <div>
                    <div class="card-title">⚡ 快速测试</div>
                    <div class="card-subtitle">输入网址，5 分钟出报告：自动建项 → 探索站点 → 生成用例 → 执行任务 → 报告</div>
                </div>
            </div>
        </template>

        <div class="quick-input-body">
            <!-- URL 输入：必填 + http(s) 前缀校验 + 回车触发 -->
            <el-input
                v-model="url"
                placeholder="https://example.com"
                clearable
                size="large"
                class="quick-input-url"
                :status="error ? 'error' : undefined"
                @keyup.enter="handleSubmit"
                @input="clearError"
            >
                <template #prefix>
                    <el-icon><Link /></el-icon>
                </template>
            </el-input>

            <div v-if="error" class="quick-input-error">{{ error }}</div>

            <!-- 高级选项折叠区：描述 + 登录凭据 -->
            <el-collapse v-model="advancedOpen" class="quick-input-advanced">
                <el-collapse-item title="高级选项（选填）" name="advanced">
                    <el-form label-position="top" class="quick-input-form">
                        <el-form-item label="测试范围描述">
                            <el-input
                                v-model="description"
                                type="textarea"
                                :rows="2"
                                placeholder="如：重点测登录和搜索功能"
                            />
                        </el-form-item>
                        <el-form-item label="登录凭据（仅登录页场景）">
                            <el-row :gutter="10">
                                <el-col :span="12">
                                    <el-input
                                        v-model="username"
                                        placeholder="账号"
                                        autocomplete="off"
                                    />
                                </el-col>
                                <el-col :span="12">
                                    <el-input
                                        v-model="password"
                                        type="password"
                                        placeholder="密码"
                                        show-password
                                        autocomplete="new-password"
                                    />
                                </el-col>
                            </el-row>
                        </el-form-item>
                    </el-form>
                </el-collapse-item>
            </el-collapse>

            <div class="quick-input-actions">
                <el-button @click="resetCard">重置</el-button>
                <el-button type="primary" size="large" :loading="loading" @click="handleSubmit">
                    开始测试
                </el-button>
            </div>
        </div>
    </el-card>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { Link } from '@element-plus/icons-vue'
import { useQuickTestCard } from '@/views/project/useQuickTestEntry'
import { useQuickTestStore } from '@/store/quickTest'

const props = defineProps<{
    /** 默认 URL：rerun 场景下回填 store.lastUrl */
    defaultUrl?: string | null
}>()

const emit = defineEmits<{
    /** 启动成功：父组件据此切换到 running 视图并订阅 WS */
    (e: 'launched'): void
}>()

// 复用 Task 10 落地的 useQuickTestCard（校验 + store.launch + 跳转 + 错误提示）
const {
    url,
    description,
    username,
    password,
    error,
    loading,
    clearError,
    submitCard,
    resetCard,
} = useQuickTestCard()

const store = useQuickTestStore()
const advancedOpen = ref<string[]>([])

/** 提交：调用 useQuickTestCard.submitCard，成功后通知父组件 */
async function handleSubmit(): Promise<void> {
    await submitCard()
    // submitCard 内部已调 store.launch：phase 变 running 即代表启动成功
    if (store.isRunning) {
        emit('launched')
    }
}

// rerun 回填：defaultUrl 变化或挂载时，若输入框为空则回填上次 URL
onMounted(() => {
    if (props.defaultUrl && !url.value) {
        url.value = props.defaultUrl
    }
})

watch(
    () => props.defaultUrl,
    (val) => {
        if (val && !url.value) url.value = val
    }
)
</script>

<style scoped lang="scss">
.quick-input-card {
    border: none;
    border-radius: 8px;
}

.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
}

.card-title {
    font-size: 18px;
    font-weight: 700;
    color: #1f2d3d;
}

.card-subtitle {
    margin-top: 6px;
    color: #7a8594;
    line-height: 1.6;
}

.quick-input-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.quick-input-url {
    width: 100%;
}

.quick-input-error {
    color: #f56c6c;
    font-size: 12px;
    line-height: 1.4;
    margin-top: -8px;
}

.quick-input-advanced {
    border-top: none;
}

.quick-input-advanced :deep(.el-collapse-item__header) {
    font-size: 13px;
    color: #7a8594;
}

.quick-input-advanced :deep(.el-collapse-item__wrap) {
    border-bottom: none;
}

.quick-input-form {
    margin-top: 4px;
}

.quick-input-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
}

@media (max-width: 768px) {
    .card-header {
        flex-direction: column;
        align-items: stretch;
    }
}
</style>
