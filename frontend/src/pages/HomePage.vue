<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import RaceCard from '@/components/RaceCard.vue'
import RaceTags from '@/components/RaceTags.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import HiddenToggleButton from '@/components/HiddenToggleButton.vue'
import { getRaces, createRace, toggleRaceHidden } from '@/api/races'
import { useRevealOnce } from '@/composables/useRevealOnce'
import {
  AGE_RANGE_OPTIONS,
  SEX_RESTRICTION_OPTIONS,
  RACE_GRADE_OPTIONS,
  COUNTRY_OPTIONS,
  SURFACE_OPTIONS,
} from '@/constants/raceOptions'
import type { RaceListItem, RaceStatus } from '@/types/race'

const showCustomFields = computed(() => createForm.value.race_grade === '自定义')

type PageState = 'loading' | 'empty' | 'error' | 'success'
type StatusFilter = 'all' | RaceStatus

const authStore = useAuthStore()
const router = useRouter()
const pageState = ref<PageState>('loading')
const races = ref<RaceListItem[]>([])
const errorMessage = ref('加载失败，请刷新重试')
const refreshing = ref(false)
const { revealing, reveal } = useRevealOnce()

// Client-side filter: non-admin users should not see hidden races
// This ensures immediate effect when logging out without a re-fetch
const visibleRaces = computed(() => {
  if (authStore.isAdmin) return races.value
  return races.value.filter(r => !r.is_hidden)
})

// Status segmented filter
const statusFilter = ref<StatusFilter>('all')
const statusTabs = computed(() => {
  const count = (s: RaceStatus) => visibleRaces.value.filter(r => r.status === s).length
  return [
    { value: 'all' as StatusFilter, label: '全部', count: visibleRaces.value.length },
    { value: 'voting' as StatusFilter, label: '投票中', count: count('voting') },
    { value: 'locked' as StatusFilter, label: '已锁定', count: count('locked') },
    { value: 'settled' as StatusFilter, label: '已结算', count: count('settled') },
  ]
})
const statusTabIndex = computed(() => statusTabs.value.findIndex(t => t.value === statusFilter.value))
const filteredRaces = computed(() =>
  statusFilter.value === 'all'
    ? visibleRaces.value
    : visibleRaces.value.filter(r => r.status === statusFilter.value),
)

function selectStatus(value: StatusFilter) {
  if (statusFilter.value === value) return
  statusFilter.value = value
  reveal(filteredRaces.value.length)
}

/** "2024-12-22" → { year, month, day } for the calendar block. */
function dateParts(date: string) {
  const [year, month, day] = date.slice(0, 10).split('-')
  if (!year || !month || !day) return null
  return { year, month: `${Number(month)}月`, day: String(Number(day)) }
}

// Create race modal
const showCreateModal = ref(false)
const createForm = ref({
  name: '',
  date: '',
  age_range: '2岁',
  sex_restriction: '无',
  race_grade: 'G1',
  country: '日本',
  distance: '',
  surface: '草地',
  positiveScores: '',
  penaltyRules: '',
})
const creating = ref(false)
const createError = ref('')

// Toggle hidden state
const togglingHiddenId = ref<number | null>(null)

async function handleToggleHidden(raceId: number) {
  if (togglingHiddenId.value !== null) return
  togglingHiddenId.value = raceId
  try {
    const result = await toggleRaceHidden(raceId)
    const race = races.value.find(r => r.id === raceId)
    if (race) race.is_hidden = result.is_hidden
  } catch {
    // silently fail
  } finally {
    togglingHiddenId.value = null
  }
}

async function loadData() {
  pageState.value = 'loading'
  errorMessage.value = '加载失败，请刷新重试'

  try {
    const data = await getRaces()
    races.value = data
    if (data.length === 0) {
      pageState.value = 'empty'
    } else {
      pageState.value = 'success'
      await nextTick()
      reveal(filteredRaces.value.length)
    }
  } catch {
    pageState.value = 'error'
  }
}

async function handleRefresh() {
  refreshing.value = true
  await loadData()
  refreshing.value = false
}

function goToRaceDetail(raceId: number) {
  router.push(`/races/${raceId}`)
}

function openCreateModal() {
  createForm.value = { name: '', date: '', age_range: '2岁', sex_restriction: '无', race_grade: 'G1', country: '日本', distance: '', surface: '草地', positiveScores: '', penaltyRules: '' }
  createError.value = ''
  showCreateModal.value = true
}

function closeCreateModal() {
  showCreateModal.value = false
}

async function handleCreateRace() {
  if (!createForm.value.name.trim() || !createForm.value.date || !createForm.value.distance.trim() || creating.value) return
  creating.value = true
  createError.value = ''
  try {
    const customScoring = createForm.value.race_grade === '自定义'
      ? parseCustomScoring()
      : undefined
    const data = await createRace({
      name: createForm.value.name.trim(),
      date: createForm.value.date,
      age_range: createForm.value.age_range,
      sex_restriction: createForm.value.sex_restriction,
      race_grade: createForm.value.race_grade,
      country: createForm.value.country,
      distance: createForm.value.distance.trim(),
      surface: createForm.value.surface,
      horse_ids: [],
      custom_scoring: customScoring,
      is_hidden: true,
    })
    closeCreateModal()
    router.push(`/races/${data.id}`)
  } catch (err: any) {
    createError.value = err?.response?.data?.detail?.message || '创建失败'
  } finally {
    creating.value = false
  }
}

function parseCustomScoring() {
  const scores = createForm.value.positiveScores
    .split(',')
    .map(s => parseInt(s.trim()))
    .filter(n => !isNaN(n))
  const penalties = createForm.value.penaltyRules
    ? createForm.value.penaltyRules
        .split(',')
        .map(p => {
          const [pos, pts] = p.split(':')
          return { position: parseInt(pos.trim()), points: parseInt(pts.trim()) }
        })
        .filter(r => !isNaN(r.position) && !isNaN(r.points))
    : []
  return { positive_scores: scores, penalty_rules: penalties.length > 0 ? penalties : undefined }
}

const tagGroups = [
  { key: 'age_range', label: '年龄范围', options: AGE_RANGE_OPTIONS },
  { key: 'sex_restriction', label: '性别限定', options: SEX_RESTRICTION_OPTIONS },
  { key: 'race_grade', label: '比赛等级', options: RACE_GRADE_OPTIONS },
  { key: 'country', label: '国家或地区', options: COUNTRY_OPTIONS, grid: true },
  { key: 'surface', label: '场地', options: SURFACE_OPTIONS },
] as const

onMounted(loadData)
</script>

<template>
  <div class="home-page">
    <header class="home-hero ui-page-header">
      <div>
        <span class="ui-page-eyebrow">Race Picks</span>
        <h1 class="ui-page-title">赛马竞猜</h1>
        <p class="ui-page-subtitle">每场比赛选一匹你看好的马，结算后按名次自动计分。</p>
      </div>

      <div
        v-if="pageState === 'success'"
        class="status-filter"
        role="tablist"
        aria-label="按状态筛选比赛"
        :style="{ '--seg-index': statusTabIndex, '--seg-count': statusTabs.length }"
      >
        <span class="status-filter-thumb" aria-hidden="true"></span>
        <button
          v-for="tab in statusTabs"
          :key="tab.value"
          type="button"
          role="tab"
          class="status-filter-tab"
          :class="{ active: statusFilter === tab.value }"
          :aria-selected="statusFilter === tab.value"
          @click="selectStatus(tab.value)"
        >
          <span class="tab-label">{{ tab.label }}</span><span class="tab-count">{{ tab.count }}</span>
        </button>
      </div>
    </header>

    <!-- Skeleton loading -->
    <template v-if="pageState === 'loading'">
      <div class="race-list" role="status" aria-live="polite" aria-label="加载中">
        <RaceCard v-for="i in 4" :key="i" skeleton />
      </div>
    </template>

    <!-- Empty state -->
    <template v-else-if="pageState === 'empty'">
      <div class="ui-state" role="status" aria-live="polite">
        <span class="ui-state-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 22V4" /><path d="M4 4h12l-2 4 2 4H4" />
          </svg>
        </span>
        <p v-if="authStore.isLoggedIn" class="ui-state-text">
          还没有比赛。管理员正在筹备中——
        </p>
        <p v-else class="ui-state-text">
          还没有比赛。
        </p>
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
        <button
          class="ui-btn ui-btn--primary"
          :disabled="refreshing"
          @click="handleRefresh"
        >
          <span v-if="refreshing" class="ui-spinner"></span>
          {{ refreshing ? '刷新中…' : '刷新重试' }}
        </button>
      </div>
    </template>

    <!-- Race list -->
    <template v-else>
      <div v-if="filteredRaces.length === 0" class="ui-state filter-empty" role="status" aria-live="polite">
        <p class="ui-state-text">这个分类下暂时没有比赛</p>
        <button class="ui-btn ui-btn--ghost ui-btn--sm" @click="selectStatus('all')">查看全部</button>
      </div>
      <div v-else :key="statusFilter" class="race-list">
        <div
          v-for="(race, index) in filteredRaces"
          :key="race.id"
          class="race-card-wrapper"
          :class="[`is-${race.status}`, { 'race-hidden': race.is_hidden, 'ui-stagger': revealing }]"
          :style="{ '--i': index }"
          role="link"
          tabindex="0"
          :aria-label="`${race.name}，${race.date}`"
          @click="goToRaceDetail(race.id)"
          @keydown.enter="goToRaceDetail(race.id)"
        >
          <article class="race-card">
            <div v-if="dateParts(race.date)" class="date-block" aria-hidden="true">
              <span class="date-month">{{ dateParts(race.date)!.month }}</span>
              <span class="date-day">{{ dateParts(race.date)!.day }}</span>
              <span class="date-year">{{ dateParts(race.date)!.year }}</span>
            </div>

            <div class="card-main">
              <div class="card-title-row">
                <h2 class="race-name">{{ race.name }}</h2>
                <span v-if="race.is_hidden" class="hidden-tag">已隐藏</span>
              </div>
              <RaceTags :race="race" />
              <div class="card-meta">
                <span class="meta-item">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
                  </svg>
                  {{ race.date }}
                </span>
                <span class="meta-item">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M4 22V4" /><path d="M4 4h12l-2 4 2 4H4" />
                  </svg>
                  {{ race.horse_count }} 匹参赛
                </span>
                <span class="meta-item">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
                  </svg>
                  {{ race.vote_count }} 人已投
                </span>
              </div>
            </div>

            <div class="card-side">
              <StatusBadge :status="race.status" />
              <span
                v-if="race.status === 'voting' && authStore.isLoggedIn && !authStore.isAdmin"
                class="vote-status"
                :class="{ voted: race.has_voted }"
              >
                <svg v-if="race.has_voted" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                <span v-else class="todo-dot" aria-hidden="true"></span>
                {{ race.has_voted ? '已投票' : '未投票' }}
              </span>
              <HiddenToggleButton
                v-if="authStore.isAdmin"
                :hidden="race.is_hidden"
                :loading="togglingHiddenId === race.id"
                @toggle="handleToggleHidden(race.id)"
              />
              <svg class="card-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </div>
          </article>
        </div>
      </div>

    </template>

    <!-- Floating action button — always visible for admin -->
    <button
      v-if="authStore.isAdmin"
      class="create-race-fab"
      type="button"
      aria-label="创建比赛"
      @click="openCreateModal"
    >
      <svg class="fab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
        <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
      </svg>
      创建比赛
    </button>

    <!-- Create race modal -->
    <div v-if="showCreateModal" class="modal-backdrop ui-anim-overlay">
      <div class="modal-content ui-anim-dialog" role="dialog" aria-modal="true" aria-labelledby="create-race-title">
        <h3 id="create-race-title" class="modal-title">创建比赛</h3>
        <div class="form-group">
          <label for="race-name">比赛名称</label>
          <input
            id="race-name"
            v-model="createForm.name"
            class="ui-input"
            type="text"
            placeholder="输入比赛名称"
          />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label for="race-date">比赛日期</label>
            <input id="race-date" v-model="createForm.date" class="ui-input" type="date" :class="{ 'is-empty': !createForm.date }" />
          </div>
          <div class="form-group">
            <label for="race-distance">长度</label>
            <input id="race-distance" v-model="createForm.distance" class="ui-input" type="text" placeholder="例：1200m" />
          </div>
        </div>
        <div v-for="group in tagGroups" :key="group.key" class="form-group">
          <label>{{ group.label }}</label>
          <div class="tag-options" :class="{ 'tag-grid': 'grid' in group }">
            <label
              v-for="opt in group.options"
              :key="opt"
              class="tag-option"
              :class="{ active: createForm[group.key] === opt }"
            >
              <input v-model="createForm[group.key]" type="radio" :value="opt" />
              <span>{{ opt }}</span>
            </label>
          </div>
        </div>

        <!-- Custom scoring fields -->
        <Transition name="ui-fade">
          <div v-if="showCustomFields" class="custom-scoring-fields">
            <div class="form-group">
              <label for="positive-scores">
                正序积分列表 <span class="required">*</span>
              </label>
              <input
                id="positive-scores"
                v-model="createForm.positiveScores"
                class="ui-input"
                type="text"
                placeholder="例：10,7,5,3,2,1"
              />
              <p class="field-hint">从第 1 名开始的积分，用逗号分隔</p>
            </div>
            <div class="form-group">
              <label for="penalty-rules">扣分规则（选填）</label>
              <input
                id="penalty-rules"
                v-model="createForm.penaltyRules"
                class="ui-input"
                type="text"
                placeholder="例：-1:-5,-2:-2"
              />
              <p class="field-hint">格式：倒数位置:扣分，用逗号分隔</p>
            </div>
          </div>
        </Transition>

        <p v-if="createError" class="ui-banner ui-banner--error">{{ createError }}</p>
        <div class="modal-actions">
          <button
            class="ui-btn ui-btn--primary modal-btn"
            :disabled="creating || !createForm.name.trim() || !createForm.date || !createForm.distance.trim() || (showCustomFields && !createForm.positiveScores.trim())"
            @click="handleCreateRace"
          >
            <span v-if="creating" class="ui-spinner"></span>
            {{ creating ? '创建中…' : '创建' }}
          </button>
          <button class="ui-btn ui-btn--ghost modal-btn" @click="closeCreateModal">
            取消
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-page {
  padding: var(--spacing-5) var(--spacing-4);
  max-width: 1280px;
  margin: 0 auto;
  padding-bottom: calc(var(--spacing-16) + env(safe-area-inset-bottom, 0px));
}

/* =========================================
   Status segmented filter
   ========================================= */

.status-filter {
  position: relative;
  display: flex;
  padding: 4px;
  border-radius: var(--rounded-full);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  box-shadow: var(--shadow-sm);
}

.status-filter-thumb {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  width: calc((100% - 8px) / var(--seg-count));
  border-radius: var(--rounded-full);
  background: var(--gradient-brand-soft);
  box-shadow: 0 4px 12px -6px rgba(26, 86, 50, 0.7);
  transform: translateX(calc(var(--seg-index) * 100%));
  transition: transform var(--duration-slow) var(--ease-out);
}

.status-filter-tab {
  position: relative;
  flex: 1 1 0;
  min-width: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 36px;
  padding: 0 14px;
  border-radius: var(--rounded-full);
  font-size: var(--text-body-sm);
  font-weight: 600;
  white-space: nowrap;
  color: var(--color-ink-secondary);
  transition: color var(--duration-base) ease;
}

.status-filter-tab:hover:not(.active) {
  color: var(--color-primary);
}

.status-filter-tab.active {
  color: #FFFFFF;
}

.tab-label {
  line-height: 1;
}

.tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--rounded-full);
  font-family: var(--font-display);
  font-size: 12px;
  line-height: 18px;
  background: var(--color-surface-sunken);
  color: var(--color-ink-secondary);
  transition: background var(--duration-base) ease, color var(--duration-base) ease;
}

.status-filter-tab.active .tab-count {
  background: rgba(255, 255, 255, 0.2);
  color: #FFFFFF;
}

/* =========================================
   Race list
   ========================================= */

.race-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.race-card-wrapper {
  --status-color: var(--color-primary-light);
  cursor: pointer;
  border-radius: var(--rounded-lg);
  outline-offset: 3px;
}

.race-card-wrapper.is-locked { --status-color: var(--color-ink-muted); }
.race-card-wrapper.is-settled { --status-color: var(--color-primary-dark); }

.race-card {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-areas: "date main side";
  align-items: center;
  gap: var(--spacing-4);
  padding: var(--spacing-4) var(--spacing-5) var(--spacing-4) calc(var(--spacing-4) + 4px);
  overflow: hidden;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  transition:
    transform var(--duration-base) var(--ease-out),
    box-shadow var(--duration-base) var(--ease-out),
    border-color var(--duration-fast) ease;
}

/* Status accent strip */
.race-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: var(--status-color);
  transition: width var(--duration-base) var(--ease-out);
}

.race-card-wrapper:hover .race-card {
  transform: translateY(-2px);
  border-color: var(--color-primary-tint-strong);
  box-shadow: var(--shadow-lg);
}

.race-card-wrapper:hover .race-card::before {
  width: 6px;
}

.race-card-wrapper:active .race-card {
  transform: translateY(0) scale(0.995);
  box-shadow: var(--shadow-sm);
}

.race-hidden .race-card {
  opacity: 0.55;
  background: repeating-linear-gradient(-45deg, #FFFFFF, #FFFFFF 10px, #FAFBF9 10px, #FAFBF9 20px);
}

/* Calendar block */
.date-block {
  grid-area: date;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 64px;
  padding: 6px 0 5px;
  border-radius: var(--rounded-md);
  background: var(--color-surface-base);
  box-shadow: inset 0 0 0 1px var(--color-border-hairline);
  line-height: 1;
  transition: background var(--duration-base) ease, box-shadow var(--duration-base) ease;
}

.race-card-wrapper:hover .date-block {
  background: var(--color-primary-tint);
  box-shadow: inset 0 0 0 1px var(--color-primary-tint-strong);
}

.date-month {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-accent);
}

.date-day {
  margin: 3px 0 2px;
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--color-ink-primary);
}

.date-year {
  font-family: var(--font-display);
  font-size: 11px;
  color: var(--color-ink-disabled);
}

.card-main {
  grid-area: main;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  min-width: 0;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  min-width: 0;
}

.race-name {
  margin: 0;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-subheading);
  font-weight: 700;
  color: var(--color-ink-primary);
  transition: color var(--duration-fast) ease;
}

.race-card-wrapper:hover .race-name {
  color: var(--color-primary);
}

.hidden-tag {
  flex-shrink: 0;
  padding: 0 6px;
  border-radius: var(--rounded-sm);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-destructive);
  background: var(--color-destructive-tint);
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px var(--spacing-4);
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.meta-item svg {
  width: 13px;
  height: 13px;
  color: var(--color-ink-disabled);
}

.card-side {
  grid-area: side;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.vote-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: var(--rounded-full);
  font-size: var(--text-caption);
  font-weight: 600;
  white-space: nowrap;
  color: var(--color-accent-dark);
  background: var(--color-accent-tint);
  box-shadow: inset 0 0 0 1px rgba(184, 150, 12, 0.35);
}

.vote-status svg {
  width: 12px;
  height: 12px;
}

.vote-status.voted {
  color: var(--color-primary);
  background: var(--color-primary-tint);
  box-shadow: inset 0 0 0 1px var(--color-primary-tint-strong);
}

/* Gentle nudge for races the user has not voted on yet */
.todo-dot {
  position: relative;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-accent);
}

.todo-dot::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: var(--color-accent);
  animation: pulse-ring 1.8s var(--ease-out) infinite;
}

.card-arrow {
  width: 20px;
  height: 20px;
  color: var(--color-ink-disabled);
  transition: transform var(--duration-base) var(--ease-out), color var(--duration-fast) ease;
}

.race-card-wrapper:hover .card-arrow {
  color: var(--color-primary);
  transform: translateX(4px);
}

.filter-empty {
  min-height: 30vh;
}

/* =========================================
   FAB
   ========================================= */

.create-race-fab {
  position: fixed;
  right: var(--spacing-6);
  bottom: calc(var(--spacing-6) + env(safe-area-inset-bottom, 0px));
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  min-height: 52px;
  padding: 14px 24px;
  border: none;
  border-radius: var(--rounded-full);
  background: var(--gradient-gold);
  color: #FFFFFF;
  font-size: var(--text-body);
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 14px 30px -12px rgba(143, 116, 6, 0.75);
  z-index: 50;
  animation: pop-in var(--duration-slow) var(--ease-spring) 200ms backwards;
  transition: transform var(--duration-base) var(--ease-spring), box-shadow var(--duration-base) ease, filter var(--duration-fast) ease;
}

.fab-icon {
  width: 20px;
  height: 20px;
  transition: transform var(--duration-slow) var(--ease-spring);
}

.create-race-fab:hover {
  transform: translateY(-3px);
  filter: brightness(1.06);
  box-shadow: 0 18px 34px -12px rgba(143, 116, 6, 0.85);
}

.create-race-fab:hover .fab-icon {
  transform: rotate(90deg);
}

.create-race-fab:active {
  transform: scale(0.96);
}

/* =========================================
   Create race modal
   ========================================= */

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(13, 30, 18, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: var(--spacing-4);
}

.modal-content {
  background: var(--color-surface-raised);
  border-radius: var(--rounded-xl);
  padding: var(--spacing-6);
  width: 100%;
  max-width: 520px;
  max-height: 86vh;
  overflow-y: auto;
}

.modal-title {
  font-family: var(--font-display);
  font-size: var(--text-heading);
  font-weight: 700;
  margin: 0 0 var(--spacing-5);
  color: var(--color-ink-primary);
}

.form-group {
  margin-bottom: var(--spacing-4);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-3);
}

.form-group > label {
  display: block;
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
  margin-bottom: var(--spacing-2);
  font-weight: 600;
}

.tag-options {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.tag-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
}

.tag-option {
  position: relative;
  flex: 1 0 auto;
  min-width: 60px;
  white-space: nowrap;
  padding: 7px 10px;
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-full);
  text-align: center;
  cursor: pointer;
  font-size: var(--text-body-sm);
  color: var(--color-ink-primary);
  background: var(--color-surface-raised);
  transition:
    border-color var(--duration-fast) ease,
    background-color var(--duration-fast) ease,
    color var(--duration-fast) ease,
    transform var(--duration-fast) var(--ease-spring);
}

.tag-option:hover {
  border-color: var(--color-primary);
}

.tag-option:active {
  transform: scale(0.95);
}

.tag-option.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #FFFFFF;
  font-weight: 600;
  animation: pop-in var(--duration-base) var(--ease-spring);
}

.tag-option:has(input:focus-visible) {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.tag-option input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

.custom-scoring-fields {
  padding: var(--spacing-4);
  background: var(--color-surface-base);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--rounded-md);
  margin-bottom: var(--spacing-4);
}

.custom-scoring-fields .form-group {
  margin-bottom: var(--spacing-3);
}

.custom-scoring-fields .form-group:last-child {
  margin-bottom: 0;
}

.required {
  color: var(--color-destructive);
}

.field-hint {
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
  margin: var(--spacing-1) 0 0;
}

.modal-actions {
  display: flex;
  gap: var(--spacing-3);
  margin-top: var(--spacing-5);
}

.modal-btn {
  flex: 1;
}

/* =========================================
   Responsive
   ========================================= */

@media (max-width: 767px) {
  .home-page {
    padding-top: var(--spacing-5);
    padding-bottom: calc(96px + env(safe-area-inset-bottom, 0px));
  }

  .status-filter {
    width: 100%;
  }

  .status-filter-tab {
    padding: 0 6px;
    font-size: 13px;
  }

  .create-race-fab {
    left: var(--spacing-4);
    right: var(--spacing-4);
    width: auto;
    bottom: calc(var(--bottom-nav-height) + var(--spacing-4) + env(safe-area-inset-bottom, 0px));
  }

  .race-card {
    grid-template-columns: auto minmax(0, 1fr);
    grid-template-areas:
      "date main"
      "date side";
    align-items: start;
    gap: var(--spacing-3);
    padding: var(--spacing-3) var(--spacing-3) var(--spacing-3) calc(var(--spacing-3) + 4px);
  }

  .date-block {
    width: 54px;
    align-self: stretch;
  }

  .date-day {
    font-size: 24px;
  }

  .race-name {
    white-space: normal;
    font-size: var(--text-body);
  }

  .card-side {
    justify-content: flex-start;
  }

  .card-arrow {
    display: none;
  }

  .form-row {
    grid-template-columns: 1fr;
    gap: 0;
  }

  .modal-actions {
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  .race-card,
  .create-race-fab,
  .status-filter-thumb {
    transition: none;
  }

  .todo-dot::after {
    animation: none;
  }
}
</style>
