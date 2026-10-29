<script setup lang="ts">
/**
 * LeaderboardPodium — top three players on stepped blocks (2nd · 1st · 3rd).
 * Blocks rise from the floor one after another; points count up.
 */
import { computed } from 'vue'
import CountUpNumber from '@/components/CountUpNumber.vue'
import type { LeaderboardEntry } from '@/types/leaderboard'

const props = defineProps<{
  entries: LeaderboardEntry[]
  currentUsername?: string | null
}>()

const MEDALS = ['🥇', '🥈', '🥉']

// Visual order: 2nd, 1st, 3rd (skip missing places)
const places = computed(() =>
  [1, 0, 2]
    .filter(i => i < props.entries.length)
    .map(i => ({ rank: i + 1, medal: MEDALS[i], entry: props.entries[i] })),
)
</script>

<template>
  <ol class="podium" aria-label="前三名">
    <li
      v-for="(place, order) in places"
      :key="place.entry.username"
      class="podium-place"
      :class="[`rank-${place.rank}`, { 'is-me': place.entry.username === currentUsername }]"
      :style="{ '--order': order }"
      :aria-label="`第${place.rank}名，${place.entry.username}，${place.entry.total_points}分`"
    >
      <div class="podium-player">
        <span class="podium-avatar" aria-hidden="true">
          {{ place.entry.username.charAt(0).toUpperCase() }}
          <span class="podium-medal">{{ place.medal }}</span>
        </span>
        <span class="podium-name" :title="place.entry.username">
          {{ place.entry.username }}
          <span v-if="place.entry.username === currentUsername" class="me-tag">我</span>
        </span>
        <span class="podium-points">
          <CountUpNumber :value="place.entry.total_points" />
          <small>分</small>
        </span>
        <span class="podium-sub">{{ place.entry.races_participated }} 场 · 场均 {{ place.entry.avg_points.toFixed(1) }}</span>
        <span class="podium-sub">距榜首 {{ entries[0]!.total_points - place.entry.total_points }} · 距上一名 {{ place.rank === 1 ? '—' : entries[place.rank - 2]!.total_points - place.entry.total_points }}</span>
      </div>
      <div class="podium-block" aria-hidden="true">
        <span class="podium-rank">{{ place.rank }}</span>
      </div>
    </li>
  </ol>
</template>

<style scoped>
.podium {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-items: end;
  gap: var(--spacing-3);
  max-width: 640px;
  margin: 0 auto var(--spacing-6);
  padding: 0;
}

.podium-place {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  min-width: 0;
}

.podium-player {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding-bottom: var(--spacing-3);
  text-align: center;
  animation: rise-in var(--duration-slow) var(--ease-out) backwards;
  animation-delay: calc(300ms + var(--order) * 120ms);
}

.podium-avatar {
  position: relative;
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  margin-bottom: var(--spacing-2);
  border-radius: 50%;
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: #FFFFFF;
  background: var(--gradient-brand-soft);
  box-shadow: 0 0 0 3px #FFFFFF, 0 8px 18px -8px rgba(13, 58, 31, 0.6);
}

.rank-1 .podium-avatar {
  width: 68px;
  height: 68px;
  font-size: 30px;
  box-shadow: 0 0 0 3px #FFFFFF, 0 0 0 6px rgba(184, 150, 12, 0.45), 0 12px 24px -10px rgba(143, 116, 6, 0.8);
}

.podium-medal {
  position: absolute;
  right: -6px;
  bottom: -4px;
  font-size: 22px;
  line-height: 1;
  animation: pop-in var(--duration-slow) var(--ease-spring) backwards;
  animation-delay: calc(650ms + var(--order) * 120ms);
}

.podium-name {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-body-sm);
  font-weight: 700;
  color: var(--color-ink-primary);
}

.me-tag {
  flex-shrink: 0;
  padding: 0 6px;
  border-radius: var(--rounded-full);
  font-size: 11px;
  color: #FFFFFF;
  background: var(--color-primary);
}

.podium-points {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--color-primary);
}

.rank-1 .podium-points {
  font-size: 34px;
  color: var(--color-accent-dark);
}

.podium-points small {
  margin-left: 2px;
  font-family: var(--font-body);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink-secondary);
}

.podium-sub {
  font-size: 11px;
  color: var(--color-ink-secondary);
}

.podium-block {
  position: relative;
  display: flex;
  justify-content: center;
  padding-top: var(--spacing-3);
  border-radius: var(--rounded-md) var(--rounded-md) 4px 4px;
  overflow: hidden;
  transform-origin: bottom;
  animation: podium-grow 0.7s var(--ease-out) backwards;
  animation-delay: calc(var(--order) * 120ms);
}

/* Subtle sheen on the blocks */
.podium-block::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.28), transparent 45%);
  pointer-events: none;
}

@keyframes podium-grow {
  from { transform: scaleY(0); }
  to { transform: scaleY(1); }
}

.rank-1 .podium-block {
  height: 132px;
  background: var(--gradient-gold);
  box-shadow: 0 16px 30px -18px rgba(143, 116, 6, 0.9);
}

.rank-2 .podium-block {
  height: 100px;
  background: var(--gradient-silver);
}

.rank-3 .podium-block {
  height: 76px;
  background: var(--gradient-bronze);
}

.podium-rank {
  position: relative;
  font-family: var(--font-display);
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
  color: rgba(255, 255, 255, 0.92);
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
}

.is-me .podium-avatar {
  background: var(--gradient-gold);
}

@media (max-width: 767px) {
  .podium {
    gap: var(--spacing-2);
  }

  .podium-avatar {
    width: 46px;
    height: 46px;
    font-size: 20px;
  }

  .rank-1 .podium-avatar {
    width: 56px;
    height: 56px;
    font-size: 24px;
  }

  .podium-points {
    font-size: 22px;
  }

  .rank-1 .podium-points {
    font-size: 26px;
  }

  .podium-sub {
    font-size: 10px;
  }

  .rank-1 .podium-block { height: 104px; }
  .rank-2 .podium-block { height: 80px; }
  .rank-3 .podium-block { height: 60px; }

  .podium-rank {
    font-size: 30px;
  }
}
</style>
