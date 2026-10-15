<script setup lang="ts">
const emit = defineEmits<{
  click: []
}>()

function handleClick() {
  emit('click')
}
</script>

<template>
  <button
    class="add-horse-card"
    type="button"
    aria-label="添加马匹"
    @click="handleClick"
  >
    <span class="plus-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round">
        <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
      </svg>
    </span>
    <span class="add-label">添加马匹</span>
  </button>
</template>

<style scoped>
.add-horse-card {
  width: 100%;
  min-height: 96px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2, 8px);
  background: var(--color-surface-raised, #FFFFFF);
  border: 2px dashed var(--color-border-strong, #A8B8A4);
  border-radius: var(--rounded-lg, 14px);
  padding: var(--spacing-4, 16px);
  cursor: pointer;
  transition:
    border-color var(--duration-fast) ease,
    background-color var(--duration-fast) ease,
    transform var(--duration-base) var(--ease-out);
}

.add-horse-card:hover {
  border-color: var(--color-primary, #1A5632);
  background: var(--color-primary-tint, #EDF5EF);
}

.add-horse-card:active {
  transform: scale(0.99);
}

.add-horse-card:focus-visible {
  outline: 2px solid var(--color-primary, #1A5632);
  outline-offset: 2px;
}

.plus-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  color: #FFFFFF;
  background: var(--gradient-brand-soft);
  box-shadow: 0 6px 14px -6px rgba(26, 86, 50, 0.6);
  transition: transform var(--duration-slow) var(--ease-spring);
}

.plus-icon svg {
  width: 18px;
  height: 18px;
}

.add-horse-card:hover .plus-icon {
  transform: rotate(90deg) scale(1.08);
}

.add-label {
  font-size: var(--text-body-sm, 14px);
  color: var(--color-ink-secondary, #4A5A4A);
  font-weight: 600;
}

.add-horse-card:hover .add-label {
  color: var(--color-primary, #1A5632);
}

@media (max-width: 767px) {
  .add-horse-card {
    min-height: 72px;
  }

  .plus-icon {
    width: 30px;
    height: 30px;
  }

  .add-label {
    font-size: var(--text-caption, 12px);
  }
}
</style>
