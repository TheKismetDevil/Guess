<script setup lang="ts">
/**
 * StatusBadge — Race status capsule indicator.
 *
 * Statuses:
 * - voting: Green background + pulsing live dot
 * - locked: Gray background + lock icon
 * - settled: Dark green background + check icon
 */

defineProps<{
  status: string
}>()

const labelMap: Record<string, string> = {
  voting: '投票中',
  locked: '已锁定',
  settled: '已结算',
}
</script>

<template>
  <span class="status-badge" :class="`status-${status}`">
    <span v-if="status === 'voting'" class="live-dot" aria-hidden="true"></span>
    <svg v-else-if="status === 'locked'" class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
    <svg v-else-if="status === 'settled'" class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <polyline points="20 6 9 17 4 12" />
    </svg>
    {{ labelMap[status] || status }}
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: var(--rounded-full);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  white-space: nowrap;
  color: #FFFFFF;
}

.status-voting {
  background: var(--gradient-brand-soft);
  box-shadow: 0 2px 10px -4px rgba(45, 122, 79, 0.8);
}

.status-locked {
  background: var(--color-ink-muted);
}

.status-settled {
  background: var(--color-primary-dark);
}

.status-icon {
  width: 12px;
  height: 12px;
}

.live-dot {
  position: relative;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #B9F5C9;
}

.live-dot::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: #B9F5C9;
  animation: pulse-ring 1.8s var(--ease-out) infinite;
}

@media (prefers-reduced-motion: reduce) {
  .live-dot::after {
    animation: none;
  }
}
</style>
