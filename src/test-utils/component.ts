import { defineComponent, h, type Component } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'

/**
 * 组合式函数宿主
 *
 * 用于测试 `provideXxx()` 形式的组合式函数：在宿主组件的 `setup()` 中
 * 执行工厂函数（内部完成 provide + 返回上下文），挂载后通过 `ctx` 读取。
 *
 * 全局插件（Element Plus）与 stub 已由 `vitest.setup.ts` 统一注入。
 */
export interface ComposableHost<T> {
  /** 宿主组件，可直接传给 mount */
  component: Component
  /** 挂载并等待首轮微任务完成 */
  mount: () => Promise<VueWrapper>
  /** 挂载后的组合式函数返回值；未挂载时访问会抛错 */
  readonly ctx: T
  /** 是否已完成挂载 */
  readonly isMounted: boolean
}

export function createComposableHost<T>(factory: () => T): ComposableHost<T> {
  let ctx: T | undefined

  const component = defineComponent({
    name: 'ComposableHost',
    setup() {
      ctx = factory()
      return () => h('div')
    },
  })

  return {
    component,
    async mount() {
      const wrapper = mount(component)
      await flushPromises()
      return wrapper
    },
    get ctx() {
      if (ctx === undefined) {
        throw new Error('宿主组件尚未挂载：请先调用 host.mount() 再读取 ctx')
      }
      return ctx
    },
    get isMounted() {
      return ctx !== undefined
    },
  }
}
