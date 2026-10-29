<script setup lang="ts">
import type { LeaderboardEntry } from '@/types/leaderboard'

defineProps<{
  entry: LeaderboardEntry
  rank: number
  isCurrentUser: boolean
  leaderGap: number
  previousGap: number
}>()
</script>

<template>
  <tr
    class="leaderboard-row"
    :class="{ 'current-user': isCurrentUser }"
    :aria-label="`第${rank}名，${entry.username}，${entry.total_points}分`"
  >
    <td class="col-rank" :class="{ 'top-three': rank <= 3 }">
      <span class="rank-pill">{{ rank }}</span>
    </td>
    <td class="col-name">
      <span class="name-cell">
        <span class="row-avatar" aria-hidden="true">{{ entry.username.charAt(0).toUpperCase() }}</span>
        <span class="row-name">{{ entry.username }}</span>
        <span v-if="isCurrentUser" class="me-tag">我</span>
      </span>
    </td>
    <td class="col-points" :class="{ negative: entry.total_points < 0 }">{{ entry.total_points }}</td>
    <td class="col-gap">{{ leaderGap }}</td>
    <td class="col-gap">{{ previousGap }}</td>
    <td class="col-races">{{ entry.races_participated }}</td>
    <td class="col-avg">{{ entry.avg_points.toFixed(1) }}</td>
  </tr>
</template>

<style scoped>
.leaderboard-row {
  border-bottom: 1px solid var(--color-border-hairline, #D4DCD0);
  transition: background var(--duration-fast) ease;
}

.leaderboard-row:last-child {
  border-bottom: none;
}

.leaderboard-row:hover {
  background: var(--color-surface-base, #F8FAF7);
}

.leaderboard-row.current-user {
  background: var(--color-primary-tint, #EDF5EF);
  box-shadow: inset 3px 0 0 var(--color-primary, #1A5632);
}

td {
  padding: var(--spacing-3, 12px) var(--spacing-2, 8px);
  vertical-align: middle;
  white-space: nowrap;
}

.col-rank {
  text-align: center;
}

.rank-pill {
  display: inline-grid;
  place-items: center;
  min-width: 30px;
  height: 30px;
  padding: 0 6px;
  border-radius: var(--rounded-full);
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  color: var(--color-ink-secondary, #4A5A4A);
  background: var(--color-surface-sunken, #F1F5F0);
}

.col-rank.top-three .rank-pill {
  color: #FFFFFF;
  background: var(--gradient-gold);
}

.col-name {
  max-width: 0;
  width: 100%;
}

.name-cell {
  display: flex;
  align-items: center;
  gap: var(--spacing-2, 8px);
  min-width: 0;
}

.row-avatar {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--color-primary, #1A5632);
  background: var(--color-primary-tint, #EDF5EF);
}

.current-user .row-avatar {
  color: #FFFFFF;
  background: var(--gradient-brand-soft);
}

.row-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: var(--text-body, 16px);
  color: var(--color-ink-primary, #1A2E1A);
}

.me-tag {
  flex-shrink: 0;
  padding: 0 6px;
  border-radius: var(--rounded-full);
  font-size: 11px;
  font-weight: 600;
  color: #FFFFFF;
  background: var(--color-primary, #1A5632);
}

.col-points {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  color: var(--color-primary, #1A5632);
  text-align: right;
}

.col-points.negative {
  color: var(--color-destructive, #C53030);
}

.col-races {
  font-size: var(--text-body-sm, 14px);
  color: var(--color-ink-secondary, #4A5A4A);
  text-align: center;
}

.col-gap { text-align: right; color: var(--color-ink-secondary); font-size: var(--text-body-sm); }

.col-avg {
  font-size: var(--text-body-sm, 14px);
  color: var(--color-ink-secondary, #4A5A4A);
  text-align: right;
}

@media (max-width: 767px) {
  .row-avatar {
    display: none;
  }

  .row-name {
    font-size: var(--text-body-sm, 14px);
  }

  .col-points {
    font-size: 18px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .leaderboard-row {
    transition: none;
  }
}
</style>
