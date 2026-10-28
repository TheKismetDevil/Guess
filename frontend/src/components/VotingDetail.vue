<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
} from 'chart.js'
import type { VoteListEntry } from '@/types/vote'
import { useCountUp } from '@/composables/useCountUp'

ChartJS.register(ArcElement, Tooltip)

const props = defineProps<{
  votes: VoteListEntry[]
  loading?: boolean
  /** horse_name → position (1=winner, 2=second, 3=third). Only applicable for settled races. */
  horsePositions?: Record<string, number>
}>()

// Prefers reduced motion
const prefersReducedMotion = ref(false)
let motionMedia: MediaQueryList | null = null
const reducedMotionHandler = (e: MediaQueryListEvent) => {
  prefersReducedMotion.value = e.matches
}

onMounted(() => {
  motionMedia = window.matchMedia('(prefers-reduced-motion: reduce)')
  prefersReducedMotion.value = motionMedia.matches
  motionMedia.addEventListener('change', reducedMotionHandler)
})

onUnmounted(() => {
  if (motionMedia) {
    motionMedia.removeEventListener('change', reducedMotionHandler)
  }
})

// Medal config
const CHAMPION_ICON = '🏆'
const CHAMPION_BORDER = '#B8960C'

// Group votes by horse, most-voted first so chart and legend share one order
const totalVotes = computed(() => props.votes.length)
const animatedTotal = useCountUp(totalVotes, 700)

const horseGroups = computed(() => {
  const groups: Record<string, { count: number; voters: string[] }> = {}
  for (const vote of props.votes) {
    if (!groups[vote.horse_name]) {
      groups[vote.horse_name] = { count: 0, voters: [] }
    }
    groups[vote.horse_name].count++
    groups[vote.horse_name].voters.push(vote.username)
  }
  return Object.entries(groups)
    .map(([horseName, data]) => {
      const pos = props.horsePositions?.[horseName]
      return {
        horseName,
        count: data.count,
        percentage: totalVotes.value > 0 ? Math.round((data.count / totalVotes.value) * 100) : 0,
        voters: data.voters,
        isChampion: pos === 1,
      }
    })
    .sort((a, b) => b.count - a.count)
})

const COLORS = [
  '#1A5632', '#B8960C', '#2B6CB0', '#C53030',
  '#6B46C1', '#319795', '#D69E2E', '#38A169',
  '#DD6B20', '#4FD1C5', '#805AD5', '#E53E3E',
]

function colorAt(i: number) {
  return COLORS[i % COLORS.length]
}

// Legend ↔ chart hover sync
const chartRef = ref<{ chart?: ChartJS<'doughnut'> } | null>(null)
const activeIndex = ref<number | null>(null)

function highlight(index: number | null) {
  activeIndex.value = index
  const chart = chartRef.value?.chart
  if (!chart) return
  chart.setActiveElements(index === null ? [] : [{ datasetIndex: 0, index }])
  chart.update()
}

// Bars grow from 0 once the legend is on screen
const barsReady = ref(false)
watch(
  () => props.votes.length > 0 && !props.loading,
  async (ready) => {
    if (!ready) {
      barsReady.value = false
      return
    }
    await nextTick()
    requestAnimationFrame(() => { barsReady.value = true })
  },
  { immediate: true },
)

const chartData = computed(() => {
  const groups = horseGroups.value
  return {
    labels: groups.map(g =>
      g.isChampion ? `${CHAMPION_ICON} ${g.horseName}` : g.horseName,
    ),
    datasets: [
      {
        data: groups.map(g => g.count),
        backgroundColor: groups.map((_, i) => colorAt(i)),
        borderWidth: groups.map(g => (g.isChampion ? 4 : 2)),
        borderColor: groups.map(g =>
          g.isChampion ? CHAMPION_BORDER : '#FFFFFF',
        ),
        hoverOffset: groups.map(g => (g.isChampion ? 12 : 8)),
        offset: groups.map(g => (g.isChampion ? 8 : 0)),
      },
    ],
  }
})

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: true,
  cutout: '64%',
  layout: { padding: 10 },
  onHover: (_event: unknown, elements: { index: number }[]) => {
    activeIndex.value = elements.length > 0 ? elements[0].index : null
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      enabled: true,
      backgroundColor: 'rgba(26, 44, 26, 0.92)',
      titleFont: { size: 14, weight: 'bold' as const },
      bodyFont: { size: 13 },
      padding: 12,
      cornerRadius: 8,
      displayColors: true,
      callbacks: {
        label(ctx: any) {
          const group = horseGroups.value[ctx.dataIndex]
          if (!group) return ''
          return ` ${group.count}/${totalVotes.value} 票 (${group.percentage}%)`
        },
        afterLabel(ctx: any) {
          const group = horseGroups.value[ctx.dataIndex]
          if (!group) return ''
          const names = group.voters.join('、')
          return `投票人: ${names}`
        },
      },
    },
  },
  animation: prefersReducedMotion.value
    ? false
    : { animateRotate: true, animateScale: true, duration: 900 },
}))
</script>

<template>
  <section class="voting-detail">
    <header class="section-head">
      <h3 class="section-title">投票分布</h3>
      <span v-if="!loading && votes.length > 0" class="total-chip">共 {{ totalVotes }} 票</span>
    </header>

    <!-- Loading state -->
    <div v-if="loading" class="skeleton-chart">
      <div class="ui-skeleton skeleton-circle" />
      <div class="skeleton-legend">
        <div v-for="i in 3" :key="i" class="ui-skeleton skeleton-line" />
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="votes.length === 0" class="empty-state">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21.21 15.89A10 10 0 1 1 8 2.83" /><path d="M22 12A10 10 0 0 0 12 2v10z" />
      </svg>
      暂无投票
    </div>

    <!-- Chart -->
    <div v-else class="chart-layout">
      <div class="chart-wrapper">
        <Doughnut ref="chartRef" :data="chartData" :options="chartOptions" />
        <div class="chart-center" aria-hidden="true">
          <span class="center-number">{{ animatedTotal }}</span>
          <span class="center-label">票</span>
        </div>
      </div>

      <ul class="legend" @mouseleave="highlight(null)">
        <li
          v-for="(group, i) in horseGroups"
          :key="group.horseName"
          class="legend-row"
          :class="{ active: activeIndex === i, dimmed: activeIndex !== null && activeIndex !== i }"
          :style="{ '--row-color': colorAt(i), '--i': i }"
          @mouseenter="highlight(i)"
        >
          <div class="legend-top">
            <span class="legend-dot" aria-hidden="true"></span>
            <span class="legend-name">
              {{ group.horseName }}
              <span v-if="group.isChampion" class="champion-tag">🏆 冠军</span>
            </span>
            <span class="legend-count">{{ group.count }} 票 · {{ group.percentage }}%</span>
          </div>
          <div class="legend-bar">
            <span class="legend-bar-fill" :style="{ width: barsReady ? `${group.percentage}%` : '0%' }"></span>
          </div>
          <p class="legend-voters" :title="group.voters.join('、')">{{ group.voters.join('、') }}</p>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.voting-detail {
  margin-top: var(--spacing-6, 24px);
  padding: var(--spacing-5, 20px);
  background: var(--color-surface-raised, #FFFFFF);
  border: 1px solid var(--color-border-hairline, #D4DCD0);
  border-radius: var(--rounded-lg, 14px);
  box-shadow: var(--shadow-sm);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3, 12px);
  margin-bottom: var(--spacing-4, 16px);
}

.section-title {
  font-size: var(--text-subheading, 18px);
  font-weight: 700;
  color: var(--color-ink-primary, #1A2E1A);
  margin: 0;
}

.total-chip {
  padding: 2px 10px;
  border-radius: var(--rounded-full);
  font-size: var(--text-caption, 12px);
  font-weight: 600;
  color: var(--color-primary);
  background: var(--color-primary-tint);
}

/* Loading */
.skeleton-chart {
  display: flex;
  align-items: center;
  gap: var(--spacing-6, 24px);
  padding: var(--spacing-2, 8px) 0;
}

.skeleton-circle {
  flex-shrink: 0;
  width: 180px;
  height: 180px;
  border-radius: 50%;
}

.skeleton-legend {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3, 12px);
}

.skeleton-line {
  height: 28px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-2, 8px);
  padding: var(--spacing-6, 24px) 0;
  font-size: var(--text-body-sm, 14px);
  color: var(--color-ink-secondary, #4A5A4A);
}

.empty-state svg {
  width: 32px;
  height: 32px;
  color: var(--color-ink-disabled);
}

/* Chart + legend */
.chart-layout {
  display: grid;
  grid-template-columns: minmax(200px, 260px) minmax(0, 1fr);
  align-items: center;
  gap: var(--spacing-6, 24px);
}

.chart-wrapper {
  position: relative;
  width: 100%;
  max-width: 260px;
  margin: 0 auto;
}

.chart-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.center-number {
  font-family: var(--font-display);
  font-size: 40px;
  font-weight: 700;
  line-height: 1;
  color: var(--color-ink-primary);
}

.center-label {
  margin-top: 2px;
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
}

.legend {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.legend-row {
  padding: 8px 10px;
  border-radius: var(--rounded-md);
  cursor: default;
  animation: rise-in var(--duration-slow) var(--ease-out) backwards;
  animation-delay: calc(min(var(--i, 0), 12) * 50ms);
  transition: background var(--duration-fast) ease, opacity var(--duration-base) ease;
}

.legend-row.active {
  background: var(--color-surface-base);
}

.legend-row.dimmed {
  opacity: 0.55;
}

.legend-top {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  min-width: 0;
}

.legend-dot {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: var(--row-color);
}

.legend-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink-primary);
}

.champion-tag {
  margin-left: 4px;
  padding: 0 6px;
  border-radius: var(--rounded-full);
  font-size: 11px;
  font-weight: 700;
  color: var(--color-accent-dark);
  background: var(--color-accent-tint);
}

.legend-count {
  flex-shrink: 0;
  font-family: var(--font-display);
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-ink-secondary);
}

.legend-bar {
  height: 6px;
  margin: 6px 0 4px 18px;
  border-radius: var(--rounded-full);
  background: var(--color-surface-sunken);
  overflow: hidden;
}

.legend-bar-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--row-color);
  transition: width 900ms var(--ease-out);
}

.legend-voters {
  margin: 0 0 0 18px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
}

@media (max-width: 767px) {
  .voting-detail {
    padding: var(--spacing-4, 16px);
  }

  .chart-layout,
  .skeleton-chart {
    grid-template-columns: 1fr;
    flex-direction: column;
    gap: var(--spacing-4, 16px);
  }

  .skeleton-legend {
    width: 100%;
  }

  .chart-wrapper {
    max-width: 220px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .legend-bar-fill {
    transition: none;
  }
}
</style>
