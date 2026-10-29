<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/authStore'
import { getLeaderboard, getLeaderboardRaces } from '@/api/leaderboard'
import apiClient from '@/api/client'
import axios from 'axios'
import type { LeaderboardEntry, LeaderboardFilters, LeaderboardRace } from '@/types/leaderboard'
import LeaderboardRow from '@/components/LeaderboardRow.vue'
import LeaderboardPodium from '@/components/LeaderboardPodium.vue'
import { useRevealOnce } from '@/composables/useRevealOnce'
import {
  AGE_RANGE_OPTIONS,
  SEX_RESTRICTION_OPTIONS,
  RACE_GRADE_OPTIONS,
  COUNTRY_OPTIONS,
  SURFACE_OPTIONS,
} from '@/constants/raceOptions'

type PageState = 'loading' | 'empty' | 'error' | 'success'
type TagField = 'age_range' | 'sex_restriction' | 'race_grade' | 'country' | 'surface'

const PODIUM_SIZE = 3

const authStore = useAuthStore()
const pageState = ref<PageState>('loading')
const leaderboard = ref<LeaderboardEntry[]>([])
const matchingRaces = ref<LeaderboardRace[]>([])
const raceListOpen = ref(false)
const dateFrom = ref('')
const dateTo = ref('')
const dateError = ref('')
let requestNumber = 0
const errorMessage = ref('加载失败，请刷新重试')
const refreshing = ref(false)
const importing = ref(false)
const importMessage = ref('')

async function importScores(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  importing.value = true
  importMessage.value = ''
  try {
    const response = await apiClient.post('/admin/historical-scores', await file.arrayBuffer(), { headers: { 'Content-Type': 'application/octet-stream' } })
    const result = response.data.data
    importMessage.value = `已导入 ${result.imported_races} 场比赛、${result.imported_scores} 条得分；跳过 ${result.skipped_races.length} 场已有比赛。${result.skipped_races.length ? `（${result.skipped_races.join('、')}）` : ''}`
    await loadData()
  } catch (err) {
    importMessage.value = axios.isAxiosError(err) ? (err.response?.data?.detail?.message || '导入失败，请检查文件') : '导入失败，请检查文件'
  } finally {
    importing.value = false
    input.value = ''
  }
}
const { revealing, reveal } = useRevealOnce()

const podiumEntries = computed(() => leaderboard.value.slice(0, PODIUM_SIZE))
const tableEntries = computed(() => leaderboard.value.slice(PODIUM_SIZE))

// Filter state
const filterOpen = ref(false)
const filters = ref<LeaderboardFilters>({})
const tagSections: { field: TagField; label: string; options: string[]; grid?: boolean }[] = [
  { field: 'age_range', label: '年龄范围', options: AGE_RANGE_OPTIONS },
  { field: 'sex_restriction', label: '性别限定', options: SEX_RESTRICTION_OPTIONS },
  { field: 'race_grade', label: '比赛等级', options: [...RACE_GRADE_OPTIONS, 'J·G1'] },
  { field: 'country', label: '国家或地区', options: COUNTRY_OPTIONS, grid: true },
  { field: 'surface', label: '场地', options: SURFACE_OPTIONS },
]
const distanceMin = ref<number | undefined>(undefined)
const distanceMax = ref<number | undefined>(undefined)
const horseCountMin = ref<number | undefined>(undefined)
const horseCountMax = ref<number | undefined>(undefined)

function hasActiveFilters(): boolean {
  return !!(
    filters.value.age_range?.length || filters.value.sex_restriction?.length ||
    filters.value.race_grade?.length || filters.value.country?.length ||
    filters.value.surface?.length ||
    dateFrom.value || dateTo.value ||
    distanceMin.value !== undefined || distanceMax.value !== undefined ||
    horseCountMin.value !== undefined || horseCountMax.value !== undefined
  )
}

const activeFilterCount = computed(() => {
  const tagCount = tagSections.reduce((n, s) => n + (filters.value[s.field]?.length ?? 0), 0)
  const rangeCount = [distanceMin, distanceMax, horseCountMin, horseCountMax]
    .filter(r => toNum(r.value) !== undefined).length
  return tagCount + rangeCount + Number(!!dateFrom.value) + Number(!!dateTo.value)
})

function toggleArrayField(field: TagField, value: string) {
  const arr = filters.value[field]
  if (arr?.includes(value)) {
    filters.value[field] = arr.filter(v => v !== value)
    if (filters.value[field]?.length === 0) filters.value[field] = undefined
  } else {
    filters.value[field] = [...(arr || []), value]
  }
}

function toNum(v: unknown): number | undefined {
  return typeof v === 'number' && !isNaN(v) ? v : undefined
}

async function loadData() {
  if (dateFrom.value && dateTo.value && dateFrom.value > dateTo.value) {
    dateError.value = '开始日期不能晚于结束日期'
    return
  }
  dateError.value = ''
  const currentRequest = ++requestNumber
  pageState.value = 'loading'
  errorMessage.value = '加载失败，请刷新重试'
  try {
    const allFilters: LeaderboardFilters = {
      ...filters.value,
      distance_min: toNum(distanceMin.value),
      distance_max: toNum(distanceMax.value),
      horse_count_min: toNum(horseCountMin.value),
      horse_count_max: toNum(horseCountMax.value),
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
    }
    const [data, races] = await Promise.all([getLeaderboard(allFilters), getLeaderboardRaces(allFilters)])
    if (currentRequest !== requestNumber) return
    leaderboard.value = data
    matchingRaces.value = races
    const hasActivity = data.length > 0 && data.some(e => e.races_participated > 0)
    pageState.value = hasActivity ? 'success' : 'empty'
    if (hasActivity) reveal(data.length)
  } catch (err) {
    if (currentRequest !== requestNumber) return
    console.error('Leaderboard load failed:', err)
    pageState.value = 'error'
  }
}

async function handleRefresh() {
  refreshing.value = true
  await loadData()
  refreshing.value = false
}

function clearFilters() {
  filters.value = {}
  distanceMin.value = undefined
  distanceMax.value = undefined
  horseCountMin.value = undefined
  horseCountMax.value = undefined
  dateFrom.value = ''
  dateTo.value = ''
  loadData()
}

function applyFilters() {
  loadData()
}

onMounted(loadData)
</script>

<template>
  <div class="leaderboard-page">
    <header class="ui-page-header">
      <div>
        <span class="ui-page-eyebrow">Leaderboard</span>
        <h1 class="ui-page-title">排行榜</h1>
        <p class="ui-page-subtitle">积分在每次比赛结算后自动更新</p>
      </div>
      <button class="ui-btn ui-btn--ghost ui-btn--sm refresh-btn" :disabled="refreshing" @click="handleRefresh">
        <svg class="refresh-icon" :class="{ spinning: refreshing }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
        </svg>
        {{ refreshing ? '刷新中…' : '刷新' }}
      </button>
    </header>

    <div v-if="authStore.isAdmin" class="historical-import">
      <label class="ui-btn ui-btn--ghost ui-btn--sm">
        {{ importing ? '导入中…' : '导入历史得分' }}
        <input type="file" accept=".xlsx" :disabled="importing" @change="importScores" />
      </label>
      <span>请使用包含“历史得分”和“赛事资料”工作表的 Excel，并填写 QQ 号。</span>
      <p v-if="importMessage" role="status">{{ importMessage }}</p>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar">
      <button
        class="filter-toggle"
        :class="{ open: filterOpen }"
        :aria-expanded="filterOpen"
        @click="filterOpen = !filterOpen"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="4" y1="6" x2="20" y2="6" /><line x1="8" y1="12" x2="20" y2="12" /><line x1="12" y1="18" x2="20" y2="18" />
        </svg>
        筛选
        <span v-if="hasActiveFilters()" :key="activeFilterCount" class="filter-badge">{{ activeFilterCount }}</span>
        <svg class="filter-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      <Transition name="ui-fade">
        <button v-if="hasActiveFilters()" class="clear-btn" @click="clearFilters">清除筛选</button>
      </Transition>
      <Transition name="ui-fade">
        <button v-if="filterOpen || hasActiveFilters()" class="ui-btn ui-btn--primary ui-btn--sm apply-btn" @click="applyFilters">应用筛选</button>
      </Transition>
    </div>

    <!-- Filter panel -->
    <Transition name="ui-collapse">
      <div v-if="filterOpen" class="filter-collapse">
        <div class="filter-panel">
          <div v-for="section in tagSections" :key="section.field" class="filter-section">
            <label class="filter-label">{{ section.label }}</label>
            <div class="filter-tags" :class="{ 'filter-grid': section.grid }">
              <button
                v-for="opt in section.options"
                :key="opt"
                class="filter-tag"
                :class="{ active: filters[section.field]?.includes(opt) }"
                :aria-pressed="!!filters[section.field]?.includes(opt)"
                @click="toggleArrayField(section.field, opt)"
              >{{ opt }}</button>
            </div>
          </div>
          <div class="filter-section">
            <label class="filter-label">比赛日期</label>
            <div class="filter-range date-range">
              <input type="date" v-model="dateFrom" aria-label="开始日期" />
              <span class="range-sep">—</span>
              <input type="date" v-model="dateTo" aria-label="结束日期" />
            </div>
            <p v-if="dateError" class="date-error" role="alert">{{ dateError }}</p>
          </div>
          <div class="filter-section">
            <label class="filter-label">长度范围（米）</label>
            <div class="filter-range">
              <input type="number" v-model.number="distanceMin" placeholder="最小" min="0" />
              <span class="range-sep">—</span>
              <input type="number" v-model.number="distanceMax" placeholder="最大" min="0" />
            </div>
          </div>
          <div class="filter-section">
            <label class="filter-label">马匹数量范围</label>
            <div class="filter-range">
              <input type="number" v-model.number="horseCountMin" placeholder="最少" min="0" />
              <span class="range-sep">—</span>
              <input type="number" v-model.number="horseCountMax" placeholder="最多" min="0" />
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <section v-if="pageState === 'success' || pageState === 'empty'" class="matching-races">
      <button class="race-list-toggle" :aria-expanded="raceListOpen" @click="raceListOpen = !raceListOpen">
        当前结果包含 {{ matchingRaces.length }} 场比赛 {{ raceListOpen ? '收起' : '查看' }}
      </button>
      <div v-if="raceListOpen" class="race-list">
        <p v-if="!matchingRaces.length">当前筛选没有符合条件的比赛。</p>
        <ul v-else>
          <li v-for="(race, index) in matchingRaces" :key="`${race.source}-${race.id ?? index}`">
            <span>{{ race.date || '—' }}</span>
            <router-link v-if="race.source === 'live' && race.id !== null" :to="`/races/${race.id}`">{{ race.name }}</router-link>
            <span v-else>{{ race.name }}</span>
            <span v-if="race.source === 'historical'" class="race-source">历史</span>
          </li>
        </ul>
      </div>
    </section>

    <!-- Loading skeleton -->
    <template v-if="pageState === 'loading'">
      <div class="skeleton-container" role="status" aria-live="polite" aria-label="加载中">
        <div class="skeleton-podium">
          <div class="ui-skeleton skeleton-step step-2"></div>
          <div class="ui-skeleton skeleton-step step-1"></div>
          <div class="ui-skeleton skeleton-step step-3"></div>
        </div>
        <div v-for="i in 4" :key="i" class="ui-skeleton skeleton-row"></div>
      </div>
    </template>

    <!-- Empty state -->
    <template v-else-if="pageState === 'empty'">
      <div class="ui-state" role="status" aria-live="polite">
        <span class="ui-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5C7 4 6 7 6 9z" /><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5C17 4 18 7 18 9z" /><path d="M4 22h16" /><path d="M10 22V14h4v8" /><path d="M12 14c-1.5 0-3-2-3-4V7c0-1.1.9-2 2-2h2a2 2 0 0 1 2 2v3c0 2-1.5 4-3 4z" />
          </svg>
        </span>
        <p class="ui-state-text">{{ hasActiveFilters() ? '当前筛选没有符合条件的成绩。' : '还没有人参与竞猜——成为第一个！' }}</p>
        <router-link to="/" class="ui-btn ui-btn--primary">去首页看看</router-link>
      </div>
    </template>

    <!-- Error state -->
    <template v-else-if="pageState === 'error'">
      <div class="ui-state ui-state--error" role="alert" aria-live="polite">
        <span class="ui-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </span>
        <p class="ui-state-text">{{ errorMessage }}</p>
        <button class="ui-btn ui-btn--primary" :disabled="refreshing" @click="handleRefresh">
          <span v-if="refreshing" class="ui-spinner"></span>
          {{ refreshing ? '刷新中…' : '刷新重试' }}
        </button>
      </div>
    </template>

    <!-- Leaderboard data -->
    <template v-else>
      <LeaderboardPodium :entries="podiumEntries" :current-username="authStore.user?.username" />

      <div v-if="tableEntries.length > 0" class="table-card">
        <table>
          <thead>
            <tr>
              <th scope="col" class="col-rank">排名</th>
              <th scope="col" class="col-name">用户名</th>
              <th scope="col" class="col-points">积分</th>
              <th scope="col" class="col-gap">距榜首</th>
              <th scope="col" class="col-gap">距上一名</th>
              <th scope="col" class="col-races">场数</th>
              <th scope="col" class="col-avg">场均</th>
            </tr>
          </thead>
          <tbody>
            <LeaderboardRow
              v-for="(entry, index) in tableEntries"
              :key="entry.username"
              :class="{ 'ui-stagger': revealing }"
              :style="{ '--i': index + PODIUM_SIZE }"
              :entry="entry"
              :rank="index + PODIUM_SIZE + 1"
              :leader-gap="leaderboard[0]!.total_points - entry.total_points"
              :previous-gap="leaderboard[index + PODIUM_SIZE - 1]!.total_points - entry.total_points"
              :is-current-user="entry.username === authStore.user?.username"
            />
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.matching-races { margin: 0 0 16px; }
.race-list-toggle { color: var(--color-primary); font-weight: 600; padding: 8px 0; }
.race-list { background: var(--color-surface-raised); border: 1px solid var(--color-border-hairline); border-radius: var(--rounded-md); max-height: 320px; overflow-y: auto; padding: 8px 12px; }
.race-list li { display: flex; align-items: center; gap: 12px; padding: 6px 0; font-size: 14px; border-bottom: 1px solid var(--color-border-hairline); }
.race-list li:last-child { border-bottom: 0; }
.race-list a { color: var(--color-primary); }
.race-source { color: var(--color-ink-secondary); font-size: 12px; }
.date-range input { width: auto; min-width: 0; max-width: 160px; }
.date-error { color: var(--color-destructive); font-size: 13px; }
th.col-gap { text-align: right; }
.historical-import { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; font-size: 14px; }
.historical-import label { cursor: pointer; }
.historical-import input { position: absolute; width: 1px; height: 1px; clip-path: inset(50%); overflow: hidden; }
.historical-import label:focus-within { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.historical-import p { width: 100%; }
.leaderboard-page {
  padding: var(--spacing-5) var(--spacing-4);
  max-width: 960px;
  margin: 0 auto;
}

.refresh-icon {
  width: 15px;
  height: 15px;
}

.refresh-icon.spinning {
  animation: spin 0.8s linear infinite;
}

/* Filter bar */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-2);
  margin-bottom: var(--spacing-4);
}

.filter-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--rounded-full);
  background: var(--color-surface-raised);
  color: var(--color-ink-primary);
  font-size: var(--text-body-sm);
  font-weight: 600;
  cursor: pointer;
  min-height: 40px;
  transition: border-color var(--duration-fast) ease, color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.filter-toggle:hover,
.filter-toggle.open {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.filter-toggle.open {
  background: var(--color-primary-tint);
}

.filter-chevron {
  transition: transform var(--duration-base) var(--ease-out);
}

.filter-toggle.open .filter-chevron {
  transform: rotate(180deg);
}

.filter-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--rounded-full);
  font-family: var(--font-display);
  font-size: 12px;
  line-height: 18px;
  text-align: center;
  color: #FFFFFF;
  background: var(--color-primary);
  animation: pop-in var(--duration-base) var(--ease-spring);
}

.clear-btn {
  padding: 8px 14px;
  border: 1px solid transparent;
  border-radius: var(--rounded-full);
  background: transparent;
  color: var(--color-destructive);
  font-size: var(--text-body-sm);
  font-weight: 600;
  cursor: pointer;
  min-height: 40px;
  transition: background var(--duration-fast) ease, border-color var(--duration-fast) ease;
}

.clear-btn:hover {
  border-color: var(--color-destructive-light);
  background: var(--color-destructive-tint);
}

.apply-btn {
  min-height: 40px;
  border-radius: var(--rounded-full);
}

/* Filter panel */
.filter-collapse {
  margin-bottom: var(--spacing-5);
}

.filter-panel {
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--spacing-4);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

.filter-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.filter-label {
  font-size: var(--text-caption);
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--color-ink-secondary);
}

.filter-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(76px, 1fr));
}

.filter-tag {
  padding: 5px 12px;
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-full);
  background: var(--color-surface-base);
  color: var(--color-ink-primary);
  font-size: var(--text-caption);
  cursor: pointer;
  transition:
    border-color var(--duration-fast) ease,
    background-color var(--duration-fast) ease,
    color var(--duration-fast) ease,
    transform var(--duration-fast) var(--ease-spring);
}

.filter-tag:hover {
  border-color: var(--color-primary);
}

.filter-tag:active {
  transform: scale(0.94);
}

.filter-tag.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #FFFFFF;
  font-weight: 600;
  animation: pop-in var(--duration-base) var(--ease-spring);
}

.filter-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-range input {
  width: 120px;
  padding: 7px 12px;
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-md);
  font-size: var(--text-body-sm);
  color: var(--color-ink-primary);
  background: var(--color-surface-base);
  transition: border-color var(--duration-fast) ease, box-shadow var(--duration-base) var(--ease-out);
}

.filter-range input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 4px rgba(26, 86, 50, 0.14);
}

.range-sep {
  color: var(--color-ink-secondary);
}

/* Skeleton */
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.skeleton-podium {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  align-items: end;
  gap: var(--spacing-3);
  max-width: 640px;
  width: 100%;
  margin: 0 auto var(--spacing-6);
}

.skeleton-step {
  border-radius: var(--rounded-md);
}

.step-1 { height: 220px; }
.step-2 { height: 190px; }
.step-3 { height: 165px; }

.skeleton-row {
  height: 52px;
}

/* Table */
.table-card {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  animation: rise-in var(--duration-slow) var(--ease-out) 200ms backwards;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-body-sm);
}

thead tr {
  background: var(--color-surface-base);
  border-bottom: 1px solid var(--color-border-hairline);
}

th {
  padding: var(--spacing-3) var(--spacing-2);
  font-size: var(--text-caption);
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--color-ink-secondary);
  white-space: nowrap;
  text-align: left;
}

th.col-rank { text-align: center; width: 64px; }
th.col-points { text-align: right; }
th.col-races { text-align: center; }
th.col-avg { text-align: right; padding-right: var(--spacing-4); }

.table-card :deep(td.col-avg) {
  padding-right: var(--spacing-4);
}

@media (max-width: 767px) {
  .skeleton-podium {
    gap: var(--spacing-2);
  }

  .step-1 { height: 180px; }
  .step-2 { height: 155px; }
  .step-3 { height: 135px; }

  th.col-rank { width: 48px; }
}

@media (prefers-reduced-motion: reduce) {
  .refresh-icon.spinning {
    animation: none;
  }
}
</style>
