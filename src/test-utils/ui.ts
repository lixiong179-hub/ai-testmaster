import { vi } from 'vitest'
import { ElMessage, ElMessageBox } from 'element-plus'

export type MessageType = 'success' | 'error' | 'warning' | 'info'

/**
 * 静默 Element Plus 的消息提示，避免测试输出噪音与挂起。
 * 默认静默全部四种，也可以只静默用到的类型。
 *
 * 断言仍可直接使用 `expect(ElMessage.success)`，因为 spy 挂在原对象上。
 */
export function silenceElMessage(...types: MessageType[]): void {
  const targets: MessageType[] = types.length > 0 ? types : ['success', 'error', 'warning', 'info']
  for (const type of targets) {
    vi.spyOn(ElMessage, type).mockImplementation(() => ({}) as never)
  }
}

/**
 * 让 `ElMessageBox.confirm` 直接确认。
 * 注意：返回的 Promise 由被测代码消费，测试中不要断言其实现细节。
 */
export function mockConfirm(): void {
  vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm' as never)
}

/**
 * 让 `ElMessageBox.confirm` 被用户取消。
 *
 * 若被测代码使用 `.then()` 而未挂 `.catch()`，拒绝会产生未处理的 Promise，
 * 这类场景建议改用返回「永不回调 then」的 thenable（见各 spec 注释）。
 */
export function mockCancel(): void {
  vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel' as never)
}

/** 静默 console 输出，默认静默 error 与 warn */
export function silenceConsole(
  ...methods: Array<'log' | 'info' | 'warn' | 'error' | 'debug'>
): void {
  const targets = methods.length > 0 ? methods : (['error', 'warn'] as const)
  for (const method of targets) {
    vi.spyOn(console, method).mockImplementation(() => {})
  }
}
