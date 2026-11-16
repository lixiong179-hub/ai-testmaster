import { vi } from 'vitest'

export interface FormInstanceMock {
  validate: ReturnType<typeof vi.fn>
  validateField: ReturnType<typeof vi.fn>
  clearValidate: ReturnType<typeof vi.fn>
  resetFields: ReturnType<typeof vi.fn>
  scrollToField: ReturnType<typeof vi.fn>
}

export interface FormInstanceMockOptions {
  /** 校验是否通过，默认 true */
  valid?: boolean
  /** 校验失败时抛出/拒绝的错误，默认 Error('表单校验未通过') */
  error?: unknown
  /**
   * 是否以回调方式通知校验结果。
   *
   * Element Plus 的 `validate(callback)` 会在返回 Promise 的同时调用回调，
   * 被测代码若写成 `await formRef.validate((valid) => {...})`，必须开启此项，
   * 否则回调不会执行。开启后 Promise 不会拒绝，避免测试出现未处理拒绝。
   */
  withCallback?: boolean
}

/**
 * 构造 Element Plus `FormInstance` 桩。
 *
 * 被测代码通常会以 `externalFormRef as never` 的方式传入，因此这里只需
 * 覆盖 validate 系列方法；返回类型刻意保持宽松，便于直接断言调用。
 */
export function createFormInstanceMock(options: FormInstanceMockOptions = {}): FormInstanceMock {
  const { valid = true, error = new Error('表单校验未通过'), withCallback = false } = options

  const validate = withCallback
    ? vi.fn((callback?: (isValid: boolean) => void) => {
        callback?.(valid)
        return Promise.resolve(valid)
      })
    : valid
      ? vi.fn().mockResolvedValue(true)
      : vi.fn().mockRejectedValue(error)

  return {
    validate,
    validateField: vi.fn().mockResolvedValue(true),
    clearValidate: vi.fn(),
    resetFields: vi.fn(),
    scrollToField: vi.fn(),
  }
}
