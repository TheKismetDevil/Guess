<script setup lang="ts">
/** HiddenToggleButton — admin eye toggle for a race's is_hidden flag. */
defineProps<{
  hidden: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()
</script>

<template>
  <button
    type="button"
    class="eye-btn"
    :class="{ 'eye-hidden': hidden }"
    :disabled="loading"
    :title="hidden ? '已隐藏，点击取消隐藏' : '点击隐藏比赛'"
    :aria-label="hidden ? '取消隐藏' : '隐藏'"
    :aria-pressed="hidden"
    @click.stop="emit('toggle')"
  >
    <span v-if="loading" class="ui-spinner"></span>
    <Transition v-else name="eye-swap" mode="out-in">
      <svg v-if="hidden" key="off" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
        <line x1="1" y1="1" x2="23" y2="23" />
      </svg>
      <svg v-else key="on" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    </Transition>
  </button>
</template>

<style scoped>
.eye-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-full);
  background: var(--color-surface-raised);
  color: var(--color-ink-secondary);
  cursor: pointer;
  transition:
    color var(--duration-fast) ease,
    border-color var(--duration-fast) ease,
    background-color var(--duration-fast) ease,
    transform var(--duration-fast) var(--ease-spring);
}

.eye-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
  transform: scale(1.08);
}

.eye-btn:active:not(:disabled) {
  transform: scale(0.94);
}

.eye-btn.eye-hidden {
  color: var(--color-destructive);
  border-color: var(--color-destructive);
  background: var(--color-destructive-tint);
}

.eye-btn.eye-hidden:hover:not(:disabled) {
  background: var(--color-destructive-light);
}

.eye-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.eye-swap-enter-active,
.eye-swap-leave-active {
  transition: opacity var(--duration-fast) ease, transform var(--duration-fast) var(--ease-out);
}

.eye-swap-enter-from {
  opacity: 0;
  transform: scale(0.6) rotate(-20deg);
}

.eye-swap-leave-to {
  opacity: 0;
  transform: scale(0.6) rotate(20deg);
}
</style>
