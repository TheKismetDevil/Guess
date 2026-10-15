<script setup lang="ts">
import { computed, ref, nextTick, onMounted } from 'vue'
import type { HorseSnapshotData } from '@/types/race'
import { gateBracketColor } from '@/utils/gateBracket'

function computeAge(birthYear: number, hemisphere: string, onDate: Date): number {
  const cutoffMonth = hemisphere === 'south' ? 8 : 1
  const thisYear = onDate.getFullYear()
  const cutoff = new Date(thisYear, cutoffMonth - 1, 1)
  const effectiveYear = onDate >= cutoff ? thisYear : thisYear - 1
  return effectiveYear - birthYear
}

const props = withDefaults(defineProps<{
  snapshotData?: HorseSnapshotData | null
  horseId: number
  jockey?: string | null
  birthYear?: number | null
  hemisphere?: string | null
  referenceDate?: string | null
  votable?: boolean
  voted?: boolean
  submitting?: boolean
  gate?: number | null
  position?: number | null
  editable?: boolean
  draggable?: boolean
  isDnf?: boolean
  showDeleteButton?: boolean
  isJiggling?: boolean
  /** Runner count; when set, the gate number uses JRA bracket (枠) colours. */
  fieldSize?: number | null
}>(), {
  snapshotData: () => ({
    name: '',
    sex: null,
    birth_year: null,
    hemisphere: null,
    location: null,
    origin: null,
    sire: null,
    damsire: null,
    previous_result: null,
    previous_result_date: null,
    previous_result_position: null,
    best_win: null,
    best_win_date: null,
  }),
  jockey: null,
  birthYear: null,
  hemisphere: null,
  referenceDate: null,
  votable: false,
  voted: false,
  submitting: false,
  gate: null,
  position: null,
  editable: false,
  draggable: false,
  isDnf: false,
  showDeleteButton: false,
  isJiggling: false,
  fieldSize: null,
})

// The template has two roots (card + Teleport), so attrs such as the
// parent's `voted-horse-locked` class must be forwarded to the card by hand.
defineOptions({ inheritAttrs: false })

const emit = defineEmits<{
  voteToggle: []
  updateField: [{ field: 'jockey'; value: string | null }]
  dragStart: []
  dragEnd: []
  refresh: []
  deleteClick: []
}>()

const isMobile = ref(false)

onMounted(() => {
  isMobile.value = window.matchMedia('(max-width: 767px)').matches
})

const showRefreshConfirm = ref(false)
const refreshLoading = ref(false)

function openRefreshConfirm() {
  showRefreshConfirm.value = true
}

function closeRefreshConfirm() {
  if (refreshLoading.value) return
  showRefreshConfirm.value = false
}

function confirmRefresh() {
  emit('refresh')
  showRefreshConfirm.value = false
}

const safeData = computed(() => props.snapshotData ?? {
  name: '',
  sex: null,
  birth_year: null,
  hemisphere: null,
  location: null,
  origin: null,
  sire: null,
  damsire: null,
  previous_result: null,
  previous_result_date: null,
  previous_result_position: null,
  best_win: null,
  best_win_date: null,
})

const rawBirthYear = computed(() => props.birthYear ?? props.snapshotData?.birth_year ?? null)
const rawHemisphere = computed(() => props.hemisphere ?? props.snapshotData?.hemisphere ?? null)

const displayAge = computed(() => {
  if (rawBirthYear.value === null || rawBirthYear.value === undefined) return null
  const refDate = props.referenceDate ? new Date(props.referenceDate) : new Date()
  const hs = rawHemisphere.value || 'north'
  return computeAge(rawBirthYear.value, hs, refDate)
})

const displayJockey = computed(() => props.jockey ?? null)

// Jockey inline edit
const editingField = ref(false)
const editValue = ref('')
const jockeyInput = ref<HTMLInputElement | null>(null)

function startEdit() {
  if (!props.editable) return
  editingField.value = true
  editValue.value = displayJockey.value || ''
  nextTick(() => jockeyInput.value?.focus())
}

function submitEdit() {
  if (!editingField.value) return
  const trimmed = editValue.value.trim()
  const value = trimmed === '' ? null : trimmed
  if (value !== displayJockey.value) {
    emit('updateField', { field: 'jockey', value })
  }
  editingField.value = false
}

function cancelEdit() {
  editingField.value = false
}

function handleEditKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    submitEdit()
  } else if (e.key === 'Escape') {
    cancelEdit()
  }
}

/** Tapping the jockey on mobile edits it; on desktop it's a double-click or the ✎ button. */
function handleJockeyClick(e: MouseEvent) {
  if (!props.editable) return
  e.stopPropagation()
  if (isMobile.value) startEdit()
}

function handleDragStart(e: DragEvent) {
  if (!props.draggable) {
    e.preventDefault()
    return
  }
  emit('dragStart')
}

function handleDragEnd() {
  emit('dragEnd')
}

function handleClick() {
  if (props.editable && editingField.value) return
  if (props.submitting || !props.votable) return
  emit('voteToggle')
}

const gateStyle = computed(() => {
  if (props.gate == null || !props.fieldSize) return undefined
  const color = gateBracketColor(props.gate, props.fieldSize)
  return color ? { background: color.bg, color: color.fg } : undefined
})

/** Leading badge shows the finishing position once there is one, otherwise the gate. */
const showsPosition = computed(() => props.position != null)

const positionClass = computed(() => {
  if (props.position === 0) return 'badge-dnf'
  if (props.position === 1) return 'badge-p1'
  if (props.position === 2) return 'badge-p2'
  if (props.position === 3) return 'badge-p3'
  return ''
})

const sexAgeStr = computed(() => {
  const sex = safeData.value.sex || '-'
  const age = displayAge.value !== null ? `${displayAge.value}` : '-'
  return `${sex}${age}`
})

// 前走: pull the finish ("7着") out into a coloured chip
const prevPosition = computed(() => safeData.value.previous_result_position ?? null)

const prevFinishClass = computed(() => {
  const p = prevPosition.value
  if (p === null) return ''
  if (p === 0) return 'finish-out'
  if (p === 1) return 'finish-1'
  if (p === 2) return 'finish-2'
  if (p === 3) return 'finish-3'
  if (p <= 5) return 'finish-board'
  return ''
})

const prevRaceText = computed(() => {
  const text = safeData.value.previous_result
  if (!text) return null
  const p = prevPosition.value
  if (p && p > 0) return text.replace(new RegExp(`\\s*${p}着$`), '') || text
  if (p === 0) return text.replace(/\s*除外\/取消$/, '') || text
  return text
})

function handleConfirmKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && !refreshLoading.value) {
    closeRefreshConfirm()
  }
}

function handleContextMenu(e: MouseEvent) {
  if (window.matchMedia('(max-width: 767px)').matches) {
    e.preventDefault()
  }
}
</script>

<template>
  <div
    v-bind="$attrs"
    class="horse-detail-card"
    :class="{
      votable,
      voted,
      'submitting': submitting && voted,
      'draggable-card': draggable,
      'dnf-card': isDnf,
      'is-jiggling': isJiggling,
    }"
    :role="votable ? 'button' : undefined"
    :tabindex="votable ? 0 : undefined"
    :aria-pressed="votable ? voted : undefined"
    :aria-label="votable ? `${safeData.name}${voted ? '，已投票，点击取消' : '，点击投票'}` : undefined"
    :draggable="draggable && !isMobile ? true : undefined"
    @click="handleClick"
    @keydown.enter="handleClick"
    @keydown.space.prevent="handleClick"
    @dragstart="handleDragStart"
    @dragend="handleDragEnd"
    @contextmenu="handleContextMenu"
  >
    <!-- Leading badge: finishing position (settled / ranking) or gate number -->
    <div
      v-if="showsPosition"
      class="lead-badge"
      :class="positionClass"
      :aria-label="position === 0 ? '弃权' : `第${position}名`"
    >
      <span class="lead-number">{{ position === 0 ? 'DNF' : position }}</span>
      <span v-if="position !== 0" class="lead-unit">着</span>
    </div>
    <div
      v-else-if="gate != null"
      class="lead-badge gate-cloth"
      :class="{ 'is-bracket': gateStyle }"
      :style="gateStyle"
      :aria-label="`${gate}号闸`"
    >
      <span class="lead-number">{{ gate }}</span>
    </div>

    <div class="card-main">
      <div class="name-row">
        <svg v-if="draggable" class="drag-grip" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <circle cx="9" cy="6" r="1.6" /><circle cx="15" cy="6" r="1.6" />
          <circle cx="9" cy="12" r="1.6" /><circle cx="15" cy="12" r="1.6" />
          <circle cx="9" cy="18" r="1.6" /><circle cx="15" cy="18" r="1.6" />
        </svg>
        <h3 class="horse-name" :title="safeData.name">{{ safeData.name }}</h3>
        <span
          v-if="showsPosition && gate != null"
          class="gate-chip"
          :class="{ 'is-bracket': gateStyle }"
          :style="gateStyle"
          :title="`${gate}号闸`"
        >{{ gate }}</span>
        <span class="meta-chip">{{ sexAgeStr }}</span>
        <span v-if="safeData.location" class="meta-text">{{ safeData.location }}</span>
      </div>

      <dl class="facts">
        <div class="fact">
          <dt>骑手</dt>
          <dd
            class="jockey"
            :class="{ editable }"
            @click="handleJockeyClick"
            @dblclick.stop="startEdit()"
          >
            <input
              v-if="editingField"
              ref="jockeyInput"
              v-model="editValue"
              class="inline-input"
              type="text"
              placeholder="骑手名"
              @click.stop
              @blur="submitEdit"
              @keydown="handleEditKeydown"
            />
            <template v-else>
              <span class="fact-value">{{ displayJockey || '-' }}</span>
              <button
                v-if="editable"
                type="button"
                class="inline-edit-btn"
                aria-label="编辑骑手"
                title="编辑骑手"
                @click.stop="startEdit()"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                </svg>
              </button>
            </template>
          </dd>
        </div>

        <div class="fact">
          <dt>血统</dt>
          <dd :title="`父 ${safeData.sire || '-'} / 母父 ${safeData.damsire || '-'}`">
            <span class="fact-value">{{ safeData.sire || '-' }}</span>
            <span class="cross" aria-hidden="true">×</span>
            <span class="fact-value muted">{{ safeData.damsire || '-' }}</span>
          </dd>
        </div>

        <div class="fact">
          <dt>前走</dt>
          <dd>
            <template v-if="prevRaceText">
              <span
                v-if="prevPosition !== null"
                class="finish-chip"
                :class="prevFinishClass"
              >{{ prevPosition === 0 ? '除外' : `${prevPosition}着` }}</span>
              <span class="fact-value">{{ prevRaceText }}</span>
              <span v-if="safeData.previous_result_date" class="fact-date">{{ safeData.previous_result_date }}</span>
            </template>
            <span v-else class="fact-value muted">-</span>
          </dd>
        </div>

        <div class="fact">
          <dt>主胜</dt>
          <dd>
            <template v-if="safeData.best_win">
              <span class="fact-value">{{ safeData.best_win }}</span>
              <span v-if="safeData.best_win_date" class="fact-date">{{ safeData.best_win_date }}</span>
            </template>
            <span v-else class="fact-value muted">-</span>
          </dd>
        </div>
      </dl>
    </div>

    <div v-if="votable || editable" class="card-side">
      <!-- Vote pill is a visual cue only: the whole card is the button -->
      <span v-if="votable" class="vote-pill" :class="{ 'is-voted': voted }" aria-hidden="true">
        <span v-if="submitting && voted" class="ui-spinner"></span>
        <template v-else-if="voted">
          <span class="pill-default">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
            已投
          </span>
          <span class="pill-hover">取消</span>
        </template>
        <template v-else>选它</template>
      </span>

      <template v-if="editable">
        <button
          type="button"
          class="icon-btn"
          :title="`刷新「${safeData.name}」数据`"
          aria-label="刷新马匹数据"
          @click.stop="openRefreshConfirm"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="23 4 23 10 17 10" /><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
        </button>
        <button
          v-if="!showDeleteButton"
          type="button"
          class="icon-btn icon-btn-danger desktop-only"
          :title="`从比赛中移除「${safeData.name}」`"
          aria-label="从比赛中移除"
          @click.stop="emit('deleteClick')"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6" /><path d="M14 11v6" />
          </svg>
        </button>
      </template>
    </div>

    <button
      v-if="showDeleteButton && !isDnf"
      class="delete-card-btn"
      aria-label="删除此马匹"
      @click.stop="emit('deleteClick')"
    >✕</button>
  </div>

  <!-- Refresh Confirm Modal -->
  <Teleport to="body">
    <div
      v-if="showRefreshConfirm"
      class="refresh-confirm-overlay ui-anim-overlay"
      @mousedown.self="closeRefreshConfirm"
      @keydown="handleConfirmKeydown"
    >
      <div class="refresh-confirm-content ui-anim-dialog" role="dialog" aria-label="确认刷新">
        <h3 class="refresh-confirm-title">确认更新</h3>
        <p class="refresh-confirm-message">确定刷新「{{ safeData.name }}」的数据为后台最新信息？</p>
        <div class="refresh-confirm-actions">
          <button class="ui-btn ui-btn--ghost" :disabled="refreshLoading" @click="closeRefreshConfirm">
            取消
          </button>
          <button class="ui-btn ui-btn--primary" :disabled="refreshLoading" @click="confirmRefresh">
            更新
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* =========================================
   Card shell
   ========================================= */

.horse-detail-card {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  grid-template-areas: "badge main side";
  align-items: stretch;
  min-height: 88px;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition:
    border-color var(--duration-fast) ease,
    box-shadow var(--duration-base) var(--ease-out),
    background-color var(--duration-base) ease,
    transform var(--duration-base) var(--ease-out);
}

.horse-detail-card.votable {
  cursor: pointer;
  user-select: none;
}

.horse-detail-card.votable:hover {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px var(--color-primary), var(--shadow-lg);
  transform: translateY(-2px);
}

.horse-detail-card.votable:active {
  transform: translateY(0) scale(0.99);
}

.horse-detail-card.votable:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.horse-detail-card.voted {
  border-color: var(--color-accent);
  background: linear-gradient(100deg, var(--color-accent-tint) 0%, #FFFFFF 70%);
  box-shadow: var(--shadow-glow-gold);
}

/* One-off shine sweep when a card becomes the user's pick */
.horse-detail-card.voted::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(105deg, transparent 35%, rgba(255, 255, 255, 0.85) 50%, transparent 65%);
  transform: translateX(-110%);
  animation: vote-shine 0.9s var(--ease-out) 0.1s 1 forwards;
}

@keyframes vote-shine {
  to { transform: translateX(110%); }
}

.horse-detail-card.voted-horse-locked {
  border-color: var(--color-accent);
  box-shadow: var(--shadow-glow-gold);
}

.horse-detail-card.votable.voted:hover {
  border-color: var(--color-accent-dark);
  box-shadow: 0 0 0 1px var(--color-accent-dark), var(--shadow-lg);
}

.horse-detail-card.submitting {
  opacity: 0.7;
  pointer-events: none;
}

.horse-detail-card.draggable-card {
  cursor: grab;
}

.horse-detail-card.draggable-card:hover {
  border-color: var(--color-border-strong);
  box-shadow: var(--shadow-md);
}

.horse-detail-card.draggable-card:active {
  cursor: grabbing;
}

.horse-detail-card.dnf-card {
  opacity: 0.6;
  background: var(--color-surface-sunken);
  box-shadow: none;
}

/* =========================================
   Leading badge
   ========================================= */

.lead-badge {
  grid-area: badge;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 52px;
  color: #FFFFFF;
  background: var(--color-primary);
  font-family: var(--font-display);
  line-height: 1;
}

.lead-number {
  font-size: 28px;
  font-weight: 700;
}

.lead-unit {
  margin-top: 2px;
  font-family: var(--font-body);
  font-size: 11px;
  font-weight: 600;
  opacity: 0.85;
}

.gate-cloth {
  background: var(--gradient-gold);
}

/* JRA bracket colour: white bracket 1 needs an edge to stay visible */
.gate-cloth.is-bracket {
  box-shadow: inset -1px 0 0 rgba(0, 0, 0, 0.08);
}

.badge-p1 {
  background: var(--gradient-gold);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.badge-p2 {
  background: var(--gradient-silver);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.badge-p3 {
  background: var(--gradient-bronze);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.badge-dnf {
  background: var(--color-destructive);
}

.badge-dnf .lead-number {
  font-size: 14px;
  letter-spacing: 0.04em;
}

/* =========================================
   Main column
   ========================================= */

.card-main {
  grid-area: main;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  padding: 12px 16px;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.drag-grip {
  flex-shrink: 0;
  width: 16px;
  height: 16px;
  margin-left: -4px;
  color: var(--color-ink-disabled);
  transition: color var(--duration-fast) ease;
}

.horse-detail-card:hover .drag-grip {
  color: var(--color-ink-secondary);
}

.horse-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  line-height: 1.15;
  color: var(--color-ink-primary);
}

.gate-chip {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  min-width: 22px;
  height: 22px;
  padding: 0 5px;
  border-radius: 6px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: #FFFFFF;
  background: var(--gradient-gold);
}

.gate-chip.is-bracket {
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.12);
}

.meta-chip {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: var(--rounded-full);
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink-secondary);
  background: var(--color-surface-sunken);
}

.meta-text {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-ink-secondary);
}

/* Facts: two aligned columns so cards stacked in a list scan like a table */
.facts {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.25fr);
  gap: 4px 20px;
  margin: 0;
}

.fact {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.fact dt {
  flex-shrink: 0;
  width: 2.4em;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-ink-disabled);
}

.fact dd {
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  font-size: var(--text-body-sm);
  color: var(--color-ink-primary);
  white-space: nowrap;
}

.fact-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fact-value.muted {
  color: var(--color-ink-secondary);
}

.cross {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-ink-disabled);
}

.fact-date {
  flex-shrink: 0;
  font-family: var(--font-display);
  font-size: 12px;
  color: var(--color-ink-disabled);
}

.finish-chip {
  flex-shrink: 0;
  align-self: center;
  padding: 0 6px;
  border-radius: 4px;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
  color: var(--color-ink-secondary);
  background: var(--color-surface-sunken);
}

.finish-chip.finish-1 { color: #FFFFFF; background: var(--gradient-gold); }
.finish-chip.finish-2 { color: #FFFFFF; background: var(--gradient-silver); }
.finish-chip.finish-3 { color: #FFFFFF; background: var(--gradient-bronze); }
.finish-chip.finish-board { color: var(--color-primary); background: var(--color-primary-tint); }
.finish-chip.finish-out { color: var(--color-destructive); background: var(--color-destructive-tint); }

/* Jockey inline edit */
.jockey.editable {
  cursor: text;
}

.inline-edit-btn {
  flex-shrink: 0;
  align-self: center;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  color: var(--color-ink-disabled);
  transition: color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.inline-edit-btn svg {
  width: 13px;
  height: 13px;
}

.inline-edit-btn:hover {
  color: var(--color-primary);
  background: var(--color-primary-tint);
}

.inline-input {
  width: 100%;
  max-width: 180px;
  padding: 2px 8px;
  border: 1px solid var(--color-primary);
  border-radius: 6px;
  font-size: var(--text-body-sm);
  background: #FFFFFF;
}

.inline-input:focus {
  outline: none;
  box-shadow: 0 0 0 3px rgba(26, 86, 50, 0.18);
}

/* =========================================
   Side column: vote pill + admin actions
   ========================================= */

.card-side {
  grid-area: side;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 14px 0 0;
}

.vote-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: 64px;
  height: 34px;
  padding: 0 14px;
  border-radius: var(--rounded-full);
  font-size: var(--text-body-sm);
  font-weight: 700;
  white-space: nowrap;
  color: var(--color-primary);
  background: var(--color-surface-raised);
  box-shadow: inset 0 0 0 1.5px var(--color-primary);
  transition:
    background var(--duration-fast) ease,
    color var(--duration-fast) ease,
    box-shadow var(--duration-fast) ease,
    transform var(--duration-base) var(--ease-spring);
}

.vote-pill svg {
  width: 13px;
  height: 13px;
}

.horse-detail-card.votable:hover .vote-pill:not(.is-voted) {
  color: #FFFFFF;
  background: var(--gradient-brand-soft);
  box-shadow: 0 6px 14px -6px rgba(26, 86, 50, 0.7);
  transform: scale(1.04);
}

.vote-pill.is-voted {
  color: #FFFFFF;
  background: var(--gradient-gold);
  box-shadow: 0 6px 14px -6px rgba(143, 116, 6, 0.8);
  animation: pop-in var(--duration-slow) var(--ease-spring);
}

.pill-default {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.pill-hover {
  display: none;
}

/* Only hover-capable pointers get the "取消" swap; touch keeps "已投" */
@media (hover: hover) {
  .horse-detail-card.votable:hover .vote-pill.is-voted {
    color: var(--color-destructive);
    background: var(--color-surface-raised);
    box-shadow: inset 0 0 0 1.5px var(--color-destructive);
  }

  .horse-detail-card.votable:hover .vote-pill.is-voted .pill-default {
    display: none;
  }

  .horse-detail-card.votable:hover .vote-pill.is-voted .pill-hover {
    display: inline;
  }
}

.icon-btn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: var(--color-ink-secondary);
  background: transparent;
  opacity: 0.7;
  transition:
    color var(--duration-fast) ease,
    background var(--duration-fast) ease,
    opacity var(--duration-fast) ease,
    transform var(--duration-fast) var(--ease-spring);
}

.icon-btn svg {
  width: 16px;
  height: 16px;
}

.horse-detail-card:hover .icon-btn {
  opacity: 1;
}

.icon-btn:hover {
  color: var(--color-primary);
  background: var(--color-primary-tint);
  transform: scale(1.08);
}

.icon-btn:hover svg {
  animation: refresh-hover-spin 0.6s var(--ease-out);
}

.icon-btn-danger:hover {
  color: var(--color-destructive);
  background: var(--color-destructive-tint);
}

.icon-btn-danger:hover svg {
  animation: none;
}

@keyframes refresh-hover-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* =========================================
   Mobile
   ========================================= */

@media (max-width: 767px) {
  .horse-detail-card {
    min-height: 0;
    width: 100%;
    touch-action: manipulation;
    -webkit-touch-callout: none;
    -webkit-user-drag: none;
    user-select: none;
  }

  .horse-detail-card.votable:hover {
    transform: none;
  }

  .lead-badge {
    width: 36px;
  }

  .lead-number {
    font-size: 20px;
  }

  .lead-unit {
    font-size: 10px;
  }

  .card-main {
    gap: 6px;
    padding: 10px 10px 10px 12px;
  }

  .name-row {
    flex-wrap: wrap;
    row-gap: 4px;
  }

  .horse-name {
    font-size: 19px;
  }

  .facts {
    grid-template-columns: minmax(0, 1fr);
    gap: 3px;
  }

  .fact dt {
    width: 2.6em;
    font-size: 11px;
  }

  /* Narrow screens: wrap instead of truncating both pedigree names */
  .fact dd {
    flex-wrap: wrap;
    row-gap: 0;
    white-space: normal;
    font-size: 13px;
  }

  .fact-value {
    overflow: visible;
    word-break: break-word;
  }

  .card-side {
    flex-direction: column;
    justify-content: center;
    padding: 8px 10px 8px 0;
  }

  .vote-pill {
    min-width: 54px;
    height: 32px;
    padding: 0 10px;
    font-size: 13px;
  }

  .icon-btn {
    opacity: 1;
  }
}

/* =========================================
   Refresh confirm modal
   ========================================= */

.refresh-confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(13, 30, 18, 0.5);
  padding: var(--spacing-4);
}

.refresh-confirm-content {
  background: var(--color-surface-raised);
  border-radius: var(--rounded-xl);
  padding: var(--spacing-6);
  max-width: 380px;
  width: 100%;
}

.refresh-confirm-title {
  font-family: var(--font-display);
  font-size: var(--text-heading);
  font-weight: 700;
  color: var(--color-ink-primary);
  margin: 0 0 var(--spacing-3);
}

.refresh-confirm-message {
  font-size: var(--text-body);
  color: var(--color-ink-secondary);
  line-height: 1.6;
  margin: 0 0 var(--spacing-5);
}

.refresh-confirm-actions {
  display: flex;
  gap: var(--spacing-3);
  justify-content: flex-end;
}

/* =========================================
   Jiggle (mobile edit mode) + corner delete
   ========================================= */

@keyframes jiggle {
  0% { transform: rotate(0deg) translate(0, 0); }
  25% { transform: rotate(-0.8deg) translate(-1px, 0); }
  75% { transform: rotate(0.8deg) translate(1px, 1px); }
  100% { transform: rotate(0deg) translate(0, 0); }
}

.horse-detail-card.is-jiggling {
  touch-action: none;
  overflow: visible;
}

/* Clip the leading badge to the card corners while overflow is visible */
.horse-detail-card.is-jiggling .lead-badge {
  border-radius: var(--rounded-lg) 0 0 var(--rounded-lg);
}

@media (max-width: 767px) {
  .horse-detail-card.is-jiggling {
    animation: jiggle 0.3s ease-in-out infinite alternate;
  }
}

.delete-card-btn {
  position: absolute;
  top: -12px;
  right: -12px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid #FFFFFF;
  background: var(--color-destructive);
  color: #FFFFFF;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 2;
  padding: 0;
  line-height: 1;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
  animation: pop-in var(--duration-base) var(--ease-spring);
  transition: transform 0.12s, background 0.12s;
}

.delete-card-btn:hover {
  transform: scale(1.15);
  background: var(--color-destructive-dark);
}

.delete-card-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .horse-detail-card,
  .vote-pill {
    transition: none;
    animation: none;
  }

  .horse-detail-card.voted::after {
    display: none;
  }

  .horse-detail-card.is-jiggling {
    animation: none;
  }
}
</style>
