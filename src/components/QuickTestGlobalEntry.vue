<template>
    <el-popover
        v-model:visible="visible"
        placement="bottom-end"
        :width="340"
        trigger="click"
        :hide-after="0"
    >
        <template #reference>
            <el-button
                link
                class="quick-global-entry"
                title="快速测试"
                aria-label="快速测试"
            >
                <el-icon class="quick-global-entry-icon"><Lightning /></el-icon>
                <span class="quick-global-entry-text">快速测试</span>
            </el-button>
        </template>

        <div class="quick-popover">
            <div class="quick-popover-title">⚡ 快速测试</div>
            <div class="quick-popover-subtitle">输入网址，5 分钟出报告</div>

            <el-input
                v-model="url"
                placeholder="https://example.com"
                clearable
                class="quick-popover-input"
                :status="error ? 'error' : undefined"
                @keyup.enter="handleLaunch"
                @input="clearError"
            >
                <template #prefix>
                    <el-icon><Link /></el-icon>
                </template>
            </el-input>

            <div v-if="error" class="quick-popover-error">{{ error }}</div>

            <el-button
                type="primary"
                :loading="loading"
                class="quick-popover-submit"
                @click="handleLaunch"
            >
                开始测试
            </el-button>
        </div>
    </el-popover>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Lightning, Link } from '@element-plus/icons-vue'
import { useQuickTestEntry } from '@/views/project/useQuickTestEntry'

const { loading, validateUrl, launchByUrl } = useQuickTestEntry()

const visible = ref(false)
const url = ref('')
const error = ref('')

function clearError(): void {
    if (error.value) error.value = ''
}

async function handleLaunch(): Promise<void> {
    const err = validateUrl(url.value)
    if (err) {
        error.value = err
        return
    }
    error.value = ''
    const ok = await launchByUrl(url.value)
    if (ok) {
        visible.value = false
    }
}

// 关闭浮层时清理内联错误，避免下次打开残留
watch(visible, (open) => {
    if (!open) error.value = ''
})
</script>

<style scoped lang="scss">
.quick-global-entry {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 6px 8px;
    color: #1f2d3d;
}

.quick-global-entry-icon {
    color: #f0a020;
    font-size: 18px;
}

.quick-global-entry-text {
    font-size: 14px;
}

.quick-popover {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.quick-popover-title {
    font-size: 16px;
    font-weight: 700;
    color: #1f2d3d;
}

.quick-popover-subtitle {
    color: #7a8594;
    font-size: 12px;
    line-height: 1.5;
    margin-top: -4px;
}

.quick-popover-input {
    width: 100%;
}

.quick-popover-error {
    color: #f56c6c;
    font-size: 12px;
    line-height: 1.4;
    margin-top: -4px;
}

.quick-popover-submit {
    width: 100%;
}

@media (max-width: 768px) {
    .quick-global-entry-text {
        display: none;
    }
}
</style>
