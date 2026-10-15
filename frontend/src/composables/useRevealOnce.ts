import { onUnmounted, ref } from 'vue'

// Mirrors --duration-slow / --stagger-step in variables.css and the
// 14-item cap in .ui-stagger.
const ENTER_MS = 420
const STEP_MS = 45
const MAX_STAGGERED = 14

/**
 * Keeps the `.ui-stagger` entrance class on a list only while it is first
 * revealed. CSS animations replay whenever a node is re-inserted, so leaving
 * the class on would replay the entrance on every drag reorder.
 */
export function useRevealOnce() {
  const revealing = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null

  function reveal(itemCount: number) {
    if (timer) clearTimeout(timer)
    revealing.value = true
    const ms = ENTER_MS + Math.min(itemCount, MAX_STAGGERED) * STEP_MS + 80
    timer = setTimeout(() => {
      revealing.value = false
      timer = null
    }, ms)
  }

  onUnmounted(() => {
    if (timer) clearTimeout(timer)
  })

  return { revealing, reveal }
}
