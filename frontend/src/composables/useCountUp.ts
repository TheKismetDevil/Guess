import { onUnmounted, ref, watch, type WatchSource } from 'vue'

/**
 * Animates a number from its previous value to the new one with an ease-out
 * curve. Jumps straight to the value when the user prefers reduced motion.
 */
export function useCountUp(source: WatchSource<number>, duration = 900) {
  const display = ref(0)
  let frame = 0

  const reduceMotion = typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches

  function animate(from: number, to: number) {
    cancelAnimationFrame(frame)
    if (reduceMotion || from === to) {
      display.value = to
      return
    }
    const start = performance.now()
    const step = (now: number) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      display.value = Math.round(from + (to - from) * eased)
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
  }

  watch(source, (to, from) => animate(from ?? 0, to), { immediate: true })

  onUnmounted(() => cancelAnimationFrame(frame))

  return display
}
