import { writable } from 'svelte/store'

export const user = writable(null)

export const theme = writable('light')

export function applyTheme(value) {
  document.documentElement.setAttribute('data-theme', value)
  theme.set(value)
}

/* ===== Toasts ===== */
export const toasts = writable([])
let toastId = 0

export function toast(message, kind = 'info') {
  const id = ++toastId
  toasts.update((list) => [...list, { id, message, kind }])
  setTimeout(() => {
    toasts.update((list) => list.filter((t) => t.id !== id))
  }, 3200)
}
