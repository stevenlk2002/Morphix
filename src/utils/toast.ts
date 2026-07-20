/**
 * 轻量全局 toast 提示工具。
 * - 完全自包含（使用内联样式，不依赖任何全局 / 共享 CSS）。
 * - 演示环境用于反馈「功能未接入 / 已上线」等占位提示。
 */

interface ToastOptions {
  /** 展示时长（ms），默认 1800。 */
  duration?: number
}

/** 取得（或创建）toast 容器节点。 */
function getToastContainer(): HTMLElement {
  let container = document.getElementById('morphix-toast-root')
  if (!container) {
    container = document.createElement('div')
    container.id = 'morphix-toast-root'
    container.style.cssText =
      'position:fixed;top:98px;right:28px;z-index:3000;display:flex;' +
      'flex-direction:column;align-items:flex-end;gap:8px;pointer-events:none;'
    if (document.body) document.body.appendChild(container)
  }
  return container
}

/**
 * 弹出一条 toast 提示。
 * @param message 提示文案
 * @param options 可选配置（展示时长）
 */
export function toast(message: string, options: ToastOptions = {}): void {
  const duration = options.duration ?? 1800
  const container = getToastContainer()
  const el = document.createElement('div')
  el.textContent = message
  el.style.cssText =
    'max-width:320px;padding:10px 14px;border-radius:12px;background:#102033;color:#fff;' +
    'box-shadow:0 8px 24px rgba(15,40,90,0.18);font-size:13px;line-height:1.5;opacity:0;' +
    'transform:translateY(-6px);transition:opacity 180ms ease,transform 180ms ease;pointer-events:auto;'
  container.appendChild(el)

  requestAnimationFrame(() => {
    el.style.opacity = '1'
    el.style.transform = 'translateY(0)'
  })

  window.setTimeout(() => {
    el.style.opacity = '0'
    el.style.transform = 'translateY(-6px)'
    window.setTimeout(() => {
      el.remove()
    }, 200)
  }, duration)
}

/** 将未知类型的异常统一转换为可读文案。 */
export function errText(e: unknown): string {
  if (e instanceof Error) return e.message
  if (typeof e === 'string') return e
  try {
    return JSON.stringify(e)
  } catch {
    return String(e)
  }
}
