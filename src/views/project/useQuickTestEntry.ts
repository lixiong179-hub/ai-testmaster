import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useQuickTestStore } from '@/store/quickTest'
import type { QuickTestLaunchRequest } from '@/api/quickTest'

/** URL 合法性校验：必填 + http/https 前缀 */
const URL_PATTERN = /^https?:\/\/.+/i

/**
 * 快速测试入口共享逻辑。
 * 顶部全局入口（QuickTestGlobalEntry）与首页置顶卡片（ProjectList 内）复用，
 * 避免重复实现"校验 → store.launch → 跳转 → 错误提示"链路。
 */
export function useQuickTestEntry() {
    const router = useRouter()
    const store = useQuickTestStore()
    const loading = ref(false)

    /** 校验 URL，返回错误提示字符串；合法返回 null */
    function validateUrl(url: string): string | null {
        const trimmed = (url || '').trim()
        if (!trimmed) return '请输入网址'
        if (!URL_PATTERN.test(trimmed)) return '网址必须以 http:// 或 https:// 开头'
        return null
    }

    /**
     * 发起快速测试。
     * 调用方应在调用前自行 validateUrl 并展示内联错误；
     * 本方法处理 store.launch + 跳转 + 运行时异常 ElMessage.error。
     * @returns 是否成功（成功已跳转到 /home/quick-test）
     */
    async function launch(payload: QuickTestLaunchRequest): Promise<boolean> {
        loading.value = true
        try {
            await store.launch(payload)
            await router.push('/home/quick-test')
            return true
        } catch (error: unknown) {
            const msg = error instanceof Error ? error.message : '快速测试启动失败'
            ElMessage.error(msg)
            return false
        } finally {
            loading.value = false
        }
    }

    /** 仅 URL 的便捷重载（全局入口场景） */
    async function launchByUrl(url: string): Promise<boolean> {
        return launch({ url: (url || '').trim() })
    }

    return {
        loading,
        validateUrl,
        launch,
        launchByUrl,
    }
}

/**
 * 首页置顶快速测试卡片表单逻辑。
 * 持有 URL/描述/凭据等表单状态，封装校验与提交，避免 ProjectList.vue 膨胀。
 */
export function useQuickTestCard() {
    const { loading, validateUrl, launch } = useQuickTestEntry()
    const url = ref('')
    const description = ref('')
    const username = ref('')
    const password = ref('')
    const error = ref('')

    function clearError(): void {
        if (error.value) error.value = ''
    }

    /** 组装启动请求体：仅当描述/凭据非空时附带，避免发送空字段 */
    function buildPayload(): QuickTestLaunchRequest {
        const payload: QuickTestLaunchRequest = { url: url.value.trim() }
        const desc = description.value.trim()
        if (desc) payload.description = desc
        const u = username.value.trim()
        const p = password.value
        // 凭据需成对提供，缺一则忽略（避免后端拿到半截凭据）
        if (u && p) payload.credentials = { username: u, password: p }
        return payload
    }

    /** 校验 URL 并提交，成功后由 launch 跳转到 /home/quick-test */
    async function submitCard(): Promise<void> {
        const err = validateUrl(url.value)
        if (err) {
            error.value = err
            return
        }
        error.value = ''
        await launch(buildPayload())
    }

    function resetCard(): void {
        url.value = ''
        description.value = ''
        username.value = ''
        password.value = ''
        error.value = ''
    }

    return {
        url,
        description,
        username,
        password,
        error,
        loading,
        clearError,
        submitCard,
        resetCard,
    }
}
