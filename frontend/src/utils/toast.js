import { reactive } from 'vue'

export const toasts = reactive([])
let seq = 0

/** kind: '' | 'error' | 'success' */
export function toast(message, kind = '', ms = 3200) {
  const id = ++seq
  toasts.push({ id, message, kind })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i >= 0) toasts.splice(i, 1)
  }, ms)
  return id
}
export const toastError = (e) => toast(e?.message || String(e), 'error')
export const toastOk = (m) => toast(m, 'success')
