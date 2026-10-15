<script setup lang="ts">
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { getHorses, getOriginsStats, getLocationsStats, createHorse, updateHorse, deleteHorse, toggleHemisphere } from '@/api/horses'
import type { Horse, HorseCreatePayload, HorseUpdatePayload } from '@/types/horse'
import ConfirmDeleteModal from '@/components/ConfirmDeleteModal.vue'

type PageState = 'loading' | 'empty' | 'error' | 'success'

const pageState = ref<PageState>('loading')
const errorMessage = ref('加载失败，请刷新重试')
const refreshing = ref(false)
const horses = ref<Horse[]>([])
const search = ref('')
const searching = ref(false)

// Delete confirmation + inline notice for failures in the list view
const deleteTarget = ref<Horse | null>(null)
const deleting = ref(false)
const listNotice = ref('')
let noticeTimer: ReturnType<typeof setTimeout> | null = null

function showNotice(message: string) {
  listNotice.value = message
  if (noticeTimer) clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => { listNotice.value = '' }, 4000)
}

function finishClass(position: number | null): string {
  if (position === null) return ''
  if (position === 0) return 'finish-out'
  if (position <= 3) return `finish-${position}`
  if (position <= 5) return 'finish-board'
  return ''
}

/** "中山金杯 7着" → "中山金杯" when the finish is shown as a chip. */
function stripFinish(text: string, position: number | null): string {
  if (position && position > 0) return text.replace(new RegExp(`\\s*${position}着$`), '') || text
  if (position === 0) return text.replace(/\s*除外\/取消$/, '') || text
  return text
}

// DB-sourced lists
const sortedCountries = ref<string[]>([])
const countryHemispheres = ref<Record<string, string>>({})  // origin → hemisphere
const sortedLocations = ref<string[]>([])

// Modal state
const showModal = ref(false)
const editingHorse = ref<Horse | null>(null)
const saving = ref(false)
const modalError = ref('')

// Sex options
const sexOptions = ['牡', '牝', '骟']

// Hemisphere options
const hemisphereOptions = [
  { value: 'north', label: '北半球' },
  { value: 'south', label: '南半球' },
]

// Country state: select or add-new mode
const isAddingCountry = ref(false)
const newCountryHemisphere = ref('north')

// Location state: select or add-new mode
const isAddingLocation = ref(false)

// Form fields
const formName = ref('')
const formSex = ref('')
const formBirthYear = ref<number | null>(null)
const formOrigin = ref('')
const formHemisphere = ref('')
const formNewCountry = ref('')
const formLocation = ref('')
const formNewLocation = ref('')
const formSire = ref('')
const formDamsire = ref('')
const formPreviousResult = ref('')
const formPreviousResultDate = ref('')
const formPreviousResultPosition = ref<number | null>(null)
const formBestWin = ref('')
const formBestWinDate = ref('')

let debounceTimer: ReturnType<typeof setTimeout> | null = null

// Origin-related
function handleOriginSelect(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  if (val === '__new__') {
    isAddingCountry.value = true
    newCountryHemisphere.value = 'north'
    formOrigin.value = ''
    formHemisphere.value = ''
  } else {
    formOrigin.value = val
    formHemisphere.value = countryHemispheres.value[val] || ''
  }
}

const togglingHemisphere = ref(false)

async function handleToggleHemisphere() {
  if (!formOrigin.value || togglingHemisphere.value) return
  togglingHemisphere.value = true
  try {
    const result = await toggleHemisphere(formOrigin.value)
    formHemisphere.value = result.new_hemisphere
    countryHemispheres.value[formOrigin.value] = result.new_hemisphere
  } catch {
    // silent
  } finally {
    togglingHemisphere.value = false
  }
}

function confirmNewCountry() {
  const name = formNewCountry.value.trim()
  if (!name) return
  formOrigin.value = name
  formHemisphere.value = newCountryHemisphere.value
  isAddingCountry.value = false
  countryHemispheres.value[name] = newCountryHemisphere.value
  // Note: sortedCountries is NOT modified here — the new country only
  // appears as a temporary option in the select until the form is saved.
  // After save, refreshCountryList() adds it to sortedCountries.
}

function cancelNewCountry() {
  isAddingCountry.value = false
  formOrigin.value = ''
  formHemisphere.value = ''
}

function handleLocationSelect(e: Event) {
  const val = (e.target as HTMLSelectElement).value
  if (val === '__new__') {
    isAddingLocation.value = true
    formLocation.value = ''
  } else {
    formLocation.value = val
  }
}

function confirmNewLocation() {
  const name = formNewLocation.value.trim()
  if (!name) return
  formLocation.value = name
  isAddingLocation.value = false
  // Not added to sortedLocations until saved. Shows as temporary option.
}

function cancelNewLocation() {
  isAddingLocation.value = false
  formLocation.value = ''
}

async function loadHorses(options: { quiet?: boolean } = {}) {
  if (options.quiet && pageState.value === 'success') {
    searching.value = true
  } else {
    pageState.value = 'loading'
  }
  errorMessage.value = '加载失败，请刷新重试'

  try {
    const [data, stats, locStats] = await Promise.all([
      getHorses(search.value || undefined),
      getOriginsStats(),
      getLocationsStats(),
    ])
    horses.value = data
    // Build country list and hemisphere map
    const sorted = [...stats].sort((a, b) => {
      if (a.count !== b.count) return b.count - a.count
      return a.origin.localeCompare(b.origin)
    })
    sortedCountries.value = sorted.map(s => s.origin)
    const hMap: Record<string, string> = {}
    for (const s of sorted) {
      if (s.hemisphere) hMap[s.origin] = s.hemisphere
    }
    countryHemispheres.value = hMap
    // Build location list
    sortedLocations.value = [...locStats]
      .sort((a, b) => {
        if (a.count !== b.count) return b.count - a.count
        return a.location.localeCompare(b.location)
      })
      .map(s => s.location)
    // An empty result for a search is "no hits", not an empty library
    pageState.value = data.length === 0 && !search.value ? 'empty' : 'success'
  } catch {
    pageState.value = 'error'
  } finally {
    searching.value = false
  }
}

async function refreshCountryList() {
  try {
    const [stats, locStats] = await Promise.all([
      getOriginsStats(),
      getLocationsStats(),
    ])
    const sorted = [...stats].sort((a, b) => {
      if (a.count !== b.count) return b.count - a.count
      return a.origin.localeCompare(b.origin)
    })
    sortedCountries.value = sorted.map(s => s.origin)
    const hMap: Record<string, string> = {}
    for (const s of sorted) {
      if (s.hemisphere) hMap[s.origin] = s.hemisphere
    }
    countryHemispheres.value = hMap
    sortedLocations.value = [...locStats]
      .sort((a, b) => {
        if (a.count !== b.count) return b.count - a.count
        return a.location.localeCompare(b.location)
      })
      .map(s => s.location)
  } catch {
    // silently ignore
  }
}

async function handleRefresh() {
  refreshing.value = true
  await loadHorses()
  refreshing.value = false
}

function debouncedSearch() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    loadHorses({ quiet: true })
  }, 300)
}

watch(search, debouncedSearch)

function resetForm() {
  formName.value = ''
  formSex.value = ''
  formBirthYear.value = null
  formOrigin.value = ''
  formHemisphere.value = ''
  formNewCountry.value = ''
  isAddingCountry.value = false
  newCountryHemisphere.value = 'north'
  formLocation.value = ''
  formNewLocation.value = ''
  isAddingLocation.value = false
  formSire.value = ''
  formDamsire.value = ''
  formPreviousResult.value = ''
  formPreviousResultDate.value = ''
  formPreviousResultPosition.value = null
  formBestWin.value = ''
  formBestWinDate.value = ''
  modalError.value = ''
}

function openCreateModal() {
  editingHorse.value = null
  resetForm()
  showModal.value = true
}

function openEditModal(horse: Horse) {
  editingHorse.value = horse
  isAddingCountry.value = false
  isAddingLocation.value = false
  formNewCountry.value = ''
  formNewLocation.value = ''
  formName.value = horse.name
  formSex.value = horse.sex || ''
  formBirthYear.value = horse.birth_year
  formOrigin.value = horse.origin || ''
  formHemisphere.value = horse.hemisphere || countryHemispheres.value[horse.origin || ''] || ''
  formLocation.value = horse.location || ''
  formSire.value = horse.sire || ''
  formDamsire.value = horse.damsire || ''
  formPreviousResult.value = horse.previous_result || ''
  formPreviousResultDate.value = horse.previous_result_date || ''
  formPreviousResultPosition.value = horse.previous_result_position
  formBestWin.value = horse.best_win || ''
  formBestWinDate.value = horse.best_win_date || ''
  modalError.value = ''
  showModal.value = true
}

function handleSave() {
  const name = formName.value.trim()
  if (!name) {
    modalError.value = '马匹名称不能为空'
    return
  }

  // Validate previous_result fields: if any is provided, all must be
  const hasPrevResult = !!formPreviousResult.value
  const hasPrevDate = !!formPreviousResultDate.value
  const hasPrevPos = formPreviousResultPosition.value !== null
  if (hasPrevResult || hasPrevDate || hasPrevPos) {
    if (!hasPrevResult || !hasPrevDate || !hasPrevPos) {
      modalError.value = '前走成绩必须同时填写比赛名称、日期和名次'
      return
    }
  }

  // Validate best_win fields
  const hasBestWin = !!formBestWin.value
  const hasBestDate = !!formBestWinDate.value
  if (hasBestWin !== hasBestDate) {
    modalError.value = '主要胜鞍必须同时填写比赛名称和日期'
    return
  }

  saving.value = true
  modalError.value = ''

  // Wrap in async to use await
  ;(async () => {
    try {
      if (editingHorse.value) {
        const payload: HorseUpdatePayload = {}
        if (name !== editingHorse.value.name) payload.name = name
        if (formSex.value !== (editingHorse.value.sex || '')) payload.sex = formSex.value || null
        if (formBirthYear.value !== editingHorse.value.birth_year) payload.birth_year = formBirthYear.value
        if (formOrigin.value !== (editingHorse.value.origin || '')) payload.origin = formOrigin.value || null
        if (formHemisphere.value !== (editingHorse.value.hemisphere || '')) payload.hemisphere = formHemisphere.value || null
        if (formLocation.value !== (editingHorse.value.location || '')) payload.location = formLocation.value || null
        if (formSire.value !== (editingHorse.value.sire || '')) payload.sire = formSire.value || null
        if (formDamsire.value !== (editingHorse.value.damsire || '')) payload.damsire = formDamsire.value || null
        if (formPreviousResult.value !== (editingHorse.value.previous_result || '')) payload.previous_result = formPreviousResult.value || null
        if (formPreviousResultDate.value !== (editingHorse.value.previous_result_date || '')) payload.previous_result_date = formPreviousResultDate.value || null
        if (formPreviousResultPosition.value !== editingHorse.value.previous_result_position) payload.previous_result_position = formPreviousResultPosition.value
        if (formBestWin.value !== (editingHorse.value.best_win || '')) payload.best_win = formBestWin.value || null
        if (formBestWinDate.value !== (editingHorse.value.best_win_date || '')) payload.best_win_date = formBestWinDate.value || null

        const updated = await updateHorse(editingHorse.value.id, payload)
        const idx = horses.value.findIndex((h) => h.id === updated.id)
        if (idx !== -1) horses.value[idx] = updated
      } else {
        const payload: HorseCreatePayload = {
          name,
          sex: formSex.value || null,
          birth_year: formBirthYear.value,
          origin: formOrigin.value || null,
          hemisphere: formHemisphere.value || null,
          location: formLocation.value || null,
          sire: formSire.value || null,
          damsire: formDamsire.value || null,
          previous_result: formPreviousResult.value || null,
          previous_result_date: formPreviousResultDate.value || null,
          previous_result_position: formPreviousResultPosition.value,
          best_win: formBestWin.value || null,
          best_win_date: formBestWinDate.value || null,
        }
        const created = await createHorse(payload)
        horses.value.push(created)
        horses.value.sort((a, b) => a.name.localeCompare(b.name))
        pageState.value = 'success'
      }

      // Refresh country list to include any newly added country
      await refreshCountryList()

      showModal.value = false
    } catch (err: unknown) {
      const response = (err as Record<string, unknown>)?.response as Record<string, unknown> | undefined
      const detail = response?.data as Record<string, unknown> | undefined
      const message = ((detail?.detail as Record<string, unknown> | undefined)?.message as string) || '保存失败，请重试'
      modalError.value = message
    } finally {
      saving.value = false
    }
  })()
}

function handleDelete(horse: Horse) {
  deleteTarget.value = horse
}

async function confirmDelete() {
  const horse = deleteTarget.value
  if (!horse || deleting.value) return
  deleting.value = true
  try {
    await deleteHorse(horse.id)
    horses.value = horses.value.filter((h) => h.id !== horse.id)
    if (horses.value.length === 0 && !search.value) pageState.value = 'empty'
    deleteTarget.value = null
  } catch (err: unknown) {
    const response = (err as Record<string, unknown>)?.response as Record<string, unknown> | undefined
    const detail = response?.data as Record<string, unknown> | undefined
    const message = ((detail?.detail as Record<string, unknown> | undefined)?.message as string) || '删除失败，请重试'
    deleteTarget.value = null
    showNotice(message)
  } finally {
    deleting.value = false
  }
}

onMounted(loadHorses)
onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (noticeTimer) clearTimeout(noticeTimer)
})
</script>

<template>
  <div class="horses-page">
    <header class="ui-page-header">
      <div>
        <span class="ui-page-eyebrow">Admin</span>
        <h1 class="ui-page-title">马匹管理</h1>
        <p class="ui-page-subtitle">参赛马匹的档案库。改这里不会影响已创建比赛里的快照，需要时在比赛页点 ↻ 刷新。</p>
      </div>
    </header>

    <!-- Toolbar stays mounted while searching so the input keeps focus -->
    <div v-if="pageState !== 'empty'" class="toolbar">
      <div class="search-box">
        <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          v-model="search"
          type="search"
          class="ui-input search-input"
          placeholder="搜索马匹名称…"
          aria-label="搜索马匹名称"
        />
        <span v-if="searching" class="ui-spinner search-spinner" aria-hidden="true"></span>
        <button
          v-else-if="search"
          type="button"
          class="search-clear"
          aria-label="清空搜索"
          @click="search = ''"
        >✕</button>
      </div>
      <span v-if="pageState === 'success'" class="count-text">
        {{ search ? `找到 ${horses.length} 匹` : `共 ${horses.length} 匹` }}
      </span>
      <button class="ui-btn ui-btn--primary create-btn" @click="openCreateModal">
        <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
          <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
        </svg>
        新建马匹
      </button>
    </div>

    <Transition name="ui-fade">
      <p v-if="listNotice" class="ui-banner ui-banner--error" role="alert">{{ listNotice }}</p>
    </Transition>

    <!-- Skeleton loading -->
    <div v-if="pageState === 'loading'" class="skeleton-container" role="status" aria-live="polite" aria-label="加载中">
      <div v-for="i in 6" :key="i" class="ui-skeleton skeleton-row"></div>
    </div>

    <!-- Empty library -->
    <div v-else-if="pageState === 'empty'" class="ui-state" role="status" aria-live="polite">
      <span class="ui-state-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 22V4" /><path d="M4 4h12l-2 4 2 4H4" />
        </svg>
      </span>
      <p class="ui-state-text">马匹库为空——创建第一场比赛时，参赛马匹将自动入库。</p>
      <button class="ui-btn ui-btn--primary" @click="openCreateModal">新建马匹</button>
    </div>

    <!-- Error state -->
    <div v-else-if="pageState === 'error'" class="ui-state ui-state--error" role="alert" aria-live="polite">
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

    <!-- No search hits -->
    <div v-else-if="horses.length === 0" class="ui-state no-hits" role="status" aria-live="polite">
      <p class="ui-state-text">没有找到名字包含「{{ search }}」的马匹</p>
      <button class="ui-btn ui-btn--ghost ui-btn--sm" @click="search = ''">清空搜索</button>
    </div>

    <!-- Horse table (cards on phones) -->
    <div v-else class="table-wrapper" :class="{ 'is-searching': searching }">
      <table class="horse-table">
        <thead>
          <tr>
            <th scope="col">马匹</th>
            <th scope="col">产地 · 所属</th>
            <th scope="col">血统</th>
            <th scope="col">前走</th>
            <th scope="col">主要胜鞍</th>
            <th scope="col" class="col-actions"><span class="sr-only">操作</span></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="horse in horses" :key="horse.id">
            <td class="cell-name">
              <div class="name-stack">
                <span class="horse-name">{{ horse.name }}</span>
                <span class="name-meta">
                  <span v-if="horse.sex" class="meta-chip">{{ horse.sex }}</span>
                  <span v-if="horse.birth_year" class="meta-year">{{ horse.birth_year }} 年生</span>
                </span>
              </div>
            </td>
            <td data-label="产地 · 所属">
              <span v-if="horse.origin">{{ horse.origin }}<small v-if="horse.hemisphere" class="muted">（{{ horse.hemisphere === 'south' ? '南' : '北' }}）</small></span>
              <span v-else class="muted">-</span>
              <span class="muted sep">·</span>
              <span :class="{ muted: !horse.location }">{{ horse.location || '-' }}</span>
            </td>
            <td data-label="血统">
              <span>{{ horse.sire || '-' }}</span>
              <span class="cross">×</span>
              <span class="muted">{{ horse.damsire || '-' }}</span>
            </td>
            <td data-label="前走">
              <template v-if="horse.previous_result">
                <span
                  v-if="horse.previous_result_position !== null"
                  class="finish-chip"
                  :class="finishClass(horse.previous_result_position)"
                >{{ horse.previous_result_position === 0 ? '除外' : `${horse.previous_result_position}着` }}</span>
                <span>{{ stripFinish(horse.previous_result, horse.previous_result_position) }}</span>
                <span v-if="horse.previous_result_date" class="cell-date">{{ horse.previous_result_date }}</span>
              </template>
              <span v-else class="muted">-</span>
            </td>
            <td data-label="主要胜鞍">
              <template v-if="horse.best_win">
                <span>{{ horse.best_win }}</span>
                <span v-if="horse.best_win_date" class="cell-date">{{ horse.best_win_date }}</span>
              </template>
              <span v-else class="muted">-</span>
            </td>
            <td class="col-actions">
              <div class="row-actions">
                <button class="row-btn" :title="`编辑「${horse.name}」`" :aria-label="`编辑${horse.name}`" @click="openEditModal(horse)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
                  </svg>
                  <span class="row-btn-label">编辑</span>
                </button>
                <button class="row-btn row-btn-danger" :title="`删除「${horse.name}」`" :aria-label="`删除${horse.name}`" @click="handleDelete(horse)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6" /><path d="M14 11v6" />
                  </svg>
                  <span class="row-btn-label">删除</span>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Delete confirmation -->
    <ConfirmDeleteModal
      v-if="deleteTarget"
      title="删除马匹"
      :item-name="deleteTarget.name"
      message="确定删除马匹「{name}」？此操作不可撤销。"
      :loading="deleting"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />

    <!-- Create/Edit Modal -->
    <Teleport to="body">
      <div v-if="showModal" class="modal-overlay ui-anim-overlay">
        <div class="modal-content ui-anim-dialog" role="dialog" :aria-label="editingHorse ? '编辑马匹' : '新建马匹'">
          <h2 class="modal-title">{{ editingHorse ? '编辑马匹' : '新建马匹' }}</h2>

          <div v-if="modalError" class="ui-banner ui-banner--error">{{ modalError }}</div>

          <form @submit.prevent="handleSave" class="horse-form">
            <div class="form-row">
              <label class="form-label">
                <span>名称 <span class="required">*</span></span>
                <input v-model="formName" type="text" class="form-input" required maxlength="100" placeholder="马匹名称" />
              </label>
            </div>
            <div class="form-grid">
              <label class="form-label">
                性别
                <select v-model="formSex" class="form-input">
                  <option value="" disabled>选择性别</option>
                  <option v-for="s in sexOptions" :key="s" :value="s">{{ s }}</option>
                </select>
              </label>
              <label class="form-label">
                出生年
                <input v-model.number="formBirthYear" type="number" class="form-input" min="1900" :max="new Date().getFullYear()" placeholder="如 2022" />
              </label>
              <label class="form-label">
                出生国
                <template v-if="!isAddingCountry">
                  <select class="form-input" v-model="formOrigin" @change="handleOriginSelect">
                    <option value="" disabled>选择国家或新增</option>
                    <option value="__new__">＋ 新增国家</option>
                    <!-- Pending new country (confirmed but not yet saved) -->
                    <option v-if="formOrigin && !sortedCountries.includes(formOrigin)" :value="formOrigin">{{ formOrigin }} (未保存)</option>
                    <option v-for="c in sortedCountries" :key="c" :value="c">{{ c }}</option>
                  </select>
                  <div v-if="formHemisphere" class="hemisphere-row">
                    <span class="hemisphere-badge">{{ formHemisphere === 'north' ? '北半球' : '南半球' }}</span>
                    <button
                      v-if="sortedCountries.includes(formOrigin)"
                      type="button"
                      class="btn btn-hemisphere-toggle"
                      :disabled="togglingHemisphere"
                      @click="handleToggleHemisphere"
                    >
                      {{ togglingHemisphere ? '切换中…' : '切换半球' }}
                    </button>
                  </div>
                </template>
                <template v-else>
                  <input
                    v-model="formNewCountry"
                    type="text"
                    class="form-input"
                    maxlength="100"
                    placeholder="输入新增国家名称"
                    autofocus
                  />
                  <div class="hemisphere-select-row">
                    <label v-for="h in hemisphereOptions" :key="h.value" class="radio-label">
                      <input type="radio" v-model="newCountryHemisphere" :value="h.value" />
                      {{ h.label }}
                    </label>
                  </div>
                  <div class="add-cancel-row">
                    <button type="button" class="btn btn-sm btn-primary" :disabled="!formNewCountry.trim()" @click="confirmNewCountry">确认</button>
                    <button type="button" class="btn btn-sm" @click="cancelNewCountry">取消</button>
                  </div>
                </template>
              </label>
              <label class="form-label">
                所属地
                <template v-if="!isAddingLocation">
                  <select class="form-input" v-model="formLocation" @change="handleLocationSelect">
                    <option value="" disabled>选择所属地或新增</option>
                    <option value="__new__">＋ 新增所属地</option>
                    <!-- Pending new location (confirmed but not yet saved) -->
                    <option v-if="formLocation && !sortedLocations.includes(formLocation)" :value="formLocation">{{ formLocation }} (未保存)</option>
                    <option v-for="l in sortedLocations" :key="l" :value="l">{{ l }}</option>
                  </select>
                </template>
                <template v-else>
                  <input
                    v-model="formNewLocation"
                    type="text"
                    class="form-input"
                    maxlength="100"
                    placeholder="输入新增所属地名"
                    autofocus
                  />
                  <div class="add-cancel-row">
                    <button type="button" class="btn btn-sm btn-primary" :disabled="!formNewLocation.trim()" @click="confirmNewLocation">确认</button>
                    <button type="button" class="btn btn-sm" @click="cancelNewLocation">取消</button>
                  </div>
                </template>
              </label>
              <label class="form-label">
                父系
                <input v-model="formSire" type="text" class="form-input" maxlength="100" placeholder="父马名称" />
              </label>
              <label class="form-label">
                母父
                <input v-model="formDamsire" type="text" class="form-input" maxlength="100" placeholder="母父名称" />
              </label>
            </div>

            <!-- 前走成绩 box (3 sub-fields) -->
            <div class="field-box">
              <div class="field-box-header">前走成绩</div>
              <div class="field-box-body field-box-col-3">
                <label class="form-label">
                  比赛名称
                  <input v-model="formPreviousResult" type="text" class="form-input" maxlength="100" placeholder="如 东京优骏 1着" />
                </label>
                <label class="form-label">
                  日期
                  <input v-model="formPreviousResultDate" type="date" class="form-input" :class="{ 'is-empty': !formPreviousResultDate }" />
                </label>
                <label class="form-label">
                  名次
                  <input v-model.number="formPreviousResultPosition" type="number" class="form-input" min="0" max="99" placeholder="如 1" />
                </label>
              </div>
            </div>

            <!-- 主要胜鞍 box (2 sub-fields) -->
            <div class="field-box">
              <div class="field-box-header">主要胜鞍</div>
              <div class="field-box-body field-box-col-2">
                <label class="form-label">
                  比赛名称
                  <input v-model="formBestWin" type="text" class="form-input" maxlength="100" placeholder="如 有马纪念(G1)" />
                </label>
                <label class="form-label">
                  日期
                  <input v-model="formBestWinDate" type="date" class="form-input" :class="{ 'is-empty': !formBestWinDate }" />
                </label>
              </div>
            </div>

            <div class="form-actions">
              <button type="button" class="ui-btn ui-btn--ghost" @click="showModal = false">取消</button>
              <button type="submit" class="ui-btn ui-btn--primary" :disabled="saving">
                <span v-if="saving" class="ui-spinner"></span>
                {{ saving ? '保存中...' : (editingHorse ? '保存修改' : '确认创建') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.horses-page {
  padding: var(--spacing-5) var(--spacing-4);
  max-width: 1280px;
  margin: 0 auto;
}

/* =========================================
   Toolbar
   ========================================= */

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
}

.search-box {
  position: relative;
  flex: 1 1 260px;
  max-width: 420px;
}

.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  width: 16px;
  height: 16px;
  color: var(--color-ink-disabled);
  transform: translateY(-50%);
  pointer-events: none;
}

.search-input {
  padding-left: 40px;
  padding-right: 40px;
  background: var(--color-surface-raised);
}

.search-input::-webkit-search-cancel-button {
  display: none;
}

.search-spinner,
.search-clear {
  position: absolute;
  right: 14px;
  top: 50%;
  margin-top: -8px;
}

.search-spinner {
  color: var(--color-primary);
}

.search-clear {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  margin-top: -10px;
  right: 12px;
  border-radius: 50%;
  font-size: 11px;
  color: #FFFFFF;
  background: var(--color-ink-disabled);
  transition: background var(--duration-fast) ease;
}

.search-clear:hover {
  background: var(--color-ink-secondary);
}

.count-text {
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
}

.create-btn {
  margin-left: auto;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.skeleton-row {
  height: 56px;
  border-radius: var(--rounded-md);
}

.no-hits {
  min-height: 30vh;
}

/* =========================================
   Table
   ========================================= */

.table-wrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  animation: rise-in var(--duration-slow) var(--ease-out) backwards;
  transition: opacity var(--duration-base) ease;
}

.table-wrapper.is-searching {
  opacity: 0.55;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-body-sm);
}

thead tr {
  background: var(--color-surface-base);
}

th {
  padding: var(--spacing-3) var(--spacing-3);
  font-size: var(--text-caption);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-align: left;
  white-space: nowrap;
  color: var(--color-ink-secondary);
  border-bottom: 1px solid var(--color-border-hairline);
}

td {
  padding: var(--spacing-3);
  vertical-align: middle;
  white-space: nowrap;
  border-bottom: 1px solid var(--color-border-hairline);
}

tbody tr {
  transition: background var(--duration-fast) ease;
}

tbody tr:hover {
  background: var(--color-primary-tint);
}

tbody tr:last-child td {
  border-bottom: none;
}

.name-stack {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.horse-name {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--color-ink-primary);
}

.name-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-chip {
  padding: 0 7px;
  border-radius: var(--rounded-full);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-ink-secondary);
  background: var(--color-surface-sunken);
}

.meta-year {
  font-size: 12px;
  color: var(--color-ink-secondary);
}

.muted {
  color: var(--color-ink-secondary);
}

.sep,
.cross {
  margin: 0 6px;
  font-size: 12px;
  color: var(--color-ink-disabled);
}

.cell-date {
  margin-left: 6px;
  font-family: var(--font-display);
  font-size: 12px;
  color: var(--color-ink-disabled);
}

.finish-chip {
  display: inline-block;
  margin-right: 6px;
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

.col-actions {
  width: 1%;
  text-align: right;
}

.row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}

.row-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 32px;
  padding: 0 10px;
  border-radius: var(--rounded-full);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-secondary);
  transition: color var(--duration-fast) ease, background var(--duration-fast) ease, transform var(--duration-fast) var(--ease-out);
}

.row-btn svg {
  width: 15px;
  height: 15px;
}

.row-btn:hover {
  color: var(--color-primary);
  background: var(--color-surface-raised);
  box-shadow: inset 0 0 0 1px var(--color-primary-tint-strong);
}

.row-btn:active {
  transform: scale(0.95);
}

.row-btn-danger:hover {
  color: var(--color-destructive);
  box-shadow: inset 0 0 0 1px var(--color-destructive-light);
}

/* Phones: each row becomes a card, cells become labelled lines */
@media (max-width: 767px) {
  .create-btn {
    margin-left: 0;
  }

  .search-box {
    flex-basis: 100%;
    max-width: none;
  }

  .table-wrapper {
    overflow: visible;
    background: transparent;
    border: none;
    box-shadow: none;
  }

  .horse-table thead {
    display: none;
  }

  .horse-table,
  .horse-table tbody,
  .horse-table tr,
  .horse-table td {
    display: block;
  }

  .horse-table tbody {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-3);
  }

  .horse-table tr {
    position: relative;
    padding: var(--spacing-3) var(--spacing-4);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border-hairline);
    border-radius: var(--rounded-lg);
    box-shadow: var(--shadow-sm);
  }

  .horse-table tbody tr:hover {
    background: var(--color-surface-raised);
  }

  .horse-table td {
    padding: 3px 0;
    border: none;
    white-space: normal;
  }

  .horse-table td[data-label] {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    font-size: 13px;
  }

  .horse-table td[data-label]::before {
    content: attr(data-label);
    flex: 0 0 5.5em;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-ink-disabled);
  }

  .cell-name {
    padding-right: 96px !important;
    margin-bottom: 4px;
  }

  .horse-table .col-actions {
    position: absolute;
    top: var(--spacing-3);
    right: var(--spacing-3);
    width: auto;
    padding: 0;
  }

  .row-btn {
    width: 36px;
    height: 36px;
    padding: 0;
    justify-content: center;
    background: var(--color-surface-base);
  }

  .row-btn-label {
    display: none;
  }
}

.modal-overlay { position: fixed; inset: 0; background: rgba(13, 30, 18, 0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: var(--spacing-4); }
.modal-content { background: var(--color-surface-raised, #FFFFFF); border-radius: var(--rounded-xl); padding: var(--spacing-6); width: 100%; max-width: 640px; max-height: 90vh; overflow-y: auto; }
.modal-title { font-family: var(--font-display); font-size: var(--text-heading); font-weight: 700; color: var(--color-ink-primary); margin-bottom: var(--spacing-5); }
.horse-form { display: flex; flex-direction: column; gap: var(--spacing-4); }
.form-row { width: 100%; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-4); }
@media (max-width: 768px) { .form-grid { grid-template-columns: 1fr; } }
.form-label { display: flex; flex-direction: column; gap: var(--spacing-1, 4px); font-size: var(--text-body-sm, 14px); font-weight: 500; color: var(--color-ink-primary, #1A2E1A); }
.required { color: var(--color-destructive, #C53030); }
.form-input { min-height: 42px; padding: 8px 12px; border: 1px solid var(--color-border-hairline); border-radius: var(--rounded-md); font-size: var(--text-body); font-family: var(--font-body); color: var(--color-ink-primary); background: var(--color-surface-base); transition: border-color var(--duration-fast) ease, box-shadow var(--duration-base) var(--ease-out), background var(--duration-fast) ease; }
.form-input:focus { outline: none; background: var(--color-surface-raised); border-color: var(--color-primary); box-shadow: 0 0 0 4px rgba(26, 86, 50, 0.14); }
select.form-input { cursor: pointer; appearance: auto; }
.hemisphere-row { display: flex; align-items: center; gap: var(--spacing-2); margin-top: 4px; }
.hemisphere-badge { display: inline-block; padding: 1px 10px; font-size: var(--text-caption, 12px); font-weight: 600; border-radius: var(--rounded-full); background: var(--color-primary-tint); color: var(--color-primary); }
.hemisphere-select-row { display: flex; gap: 16px; margin-top: 8px; }
.radio-label { display: flex; align-items: center; gap: 4px; font-size: var(--text-body-sm, 14px); cursor: pointer; }
.add-cancel-row { display: flex; gap: 8px; margin-top: 8px; }
.btn-sm.btn-primary { background: var(--color-primary, #1A5632); color: #fff; border: none; }
.btn-hemisphere-toggle { padding: 2px 10px; font-size: var(--text-caption, 12px); border: 1px solid var(--color-border-strong); border-radius: var(--rounded-sm, 6px); background: transparent; cursor: pointer; min-height: 28px; color: var(--color-primary); }
.btn-hemisphere-toggle:hover:not(:disabled) { background: var(--color-surface-base); }
.btn-hemisphere-toggle:disabled { opacity: 0.5; cursor: not-allowed; }

/* Field boxes for grouped form sections */
.field-box {
  border: 1px solid var(--color-border-hairline, #D4DCD0);
  border-radius: var(--rounded-md, 10px);
  background: var(--color-surface-base, #F8FAF7);
  padding: var(--spacing-3, 12px);
}
.field-box-header {
  font-size: var(--text-body-sm, 14px);
  font-weight: 600;
  color: var(--color-ink-secondary, #4A5A4A);
  margin-bottom: var(--spacing-2, 8px);
  padding-bottom: var(--spacing-1, 4px);
  border-bottom: 1px solid var(--color-border-hairline, #D4DCD0);
}
.field-box-body {
  display: grid;
  gap: var(--spacing-3, 12px);
}
.field-box-col-3 {
  grid-template-columns: 1fr 1fr 1fr;
}
.field-box-col-2 {
  grid-template-columns: 1fr 1fr;
}
@media (max-width: 768px) {
  .field-box-col-3,
  .field-box-col-2 {
    grid-template-columns: 1fr;
  }
}

.form-actions { display: flex; gap: var(--spacing-3); justify-content: flex-end; margin-top: var(--spacing-2); }


/* Small buttons inside the edit modal (country / location add rows) */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--rounded-sm);
  cursor: pointer;
  white-space: nowrap;
  transition: transform var(--duration-fast) var(--ease-out), filter var(--duration-fast) ease, background var(--duration-fast) ease;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn:active:not(:disabled) { transform: scale(0.97); }
.btn-sm {
  padding: 4px 12px;
  min-height: 32px;
  font-size: var(--text-caption);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  color: var(--color-ink-primary);
}
.btn-sm:hover { background: var(--color-surface-base); }
.btn-sm.btn-primary { background: var(--gradient-brand-soft); color: #FFFFFF; border: none; }
.btn-sm.btn-primary:hover:not(:disabled) { filter: brightness(1.08); }
</style>
