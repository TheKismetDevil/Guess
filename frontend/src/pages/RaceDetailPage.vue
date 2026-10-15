<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, shallowRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import StatusBadge from '@/components/StatusBadge.vue'
import RaceTags from '@/components/RaceTags.vue'
import HiddenToggleButton from '@/components/HiddenToggleButton.vue'
import HorseDetailCard from '@/components/HorseDetailCard.vue'
import AddHorseCard from '@/components/AddHorseCard.vue'
import RaceHeaderEditor from '@/components/RaceHeaderEditor.vue'
import VotingDetail from '@/components/VotingDetail.vue'
import HorseSearchSelect from '@/components/HorseSearchSelect.vue'
import ConfirmDeleteModal from '@/components/ConfirmDeleteModal.vue'

import {
  getRace,
  updateRace,
  addRaceHorse,
  updateRaceHorse,
  updateGateOrder,
  lockRace,
  removeRaceHorse,
  toggleRaceHidden,
  deleteRace,
} from '@/api/races'
import { submitResults } from '@/api/results'
import { updateBestWin, refreshRaceHorseSnapshot } from '@/api/horses'
import { useVote } from '@/composables/useVote'
import { useDragSort } from '@/composables/useDragSort'
import { useDragAutoScroll } from '@/composables/useDragAutoScroll'
import { useRevealOnce } from '@/composables/useRevealOnce'
import type { RaceDetail, ResultPosition } from '@/types/race'
import type { Horse } from '@/types/horse'

type PageState = 'loading' | 'error' | 'success'
type ResultMode = 'idle' | 'ranking'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const raceId = Number(route.params.id)

const pageState = ref<PageState>('loading')
const race = ref<RaceDetail | null>(null)
const errorMessage = ref('加载失败，请刷新重试')
const isJiggleMode = ref(false)
const { revealing: listRevealing, reveal: revealList } = useRevealOnce()

// JRA bracket colours only make sense for Japanese races
const bracketFieldSize = computed(() =>
  race.value?.country === '日本' ? race.value.horses.length : null,
)

const {
  votedHorseName,
  votedRaceHorseId,
  isSubmitting,
  votes,
  votesLoading,
  errorMessage: voteError,
  toggleVote,
  loadVotes,
} = useVote()

function checkUserVote() {
  if (!authStore.isLoggedIn || !authStore.user) return
  const myVote = votes.value.find(v => v.user_id === authStore.user!.id)
  if (myVote) {
    votedHorseName.value = myVote.horse_name
    votedRaceHorseId.value = myVote.race_horse_id
  }
}

const isRaceVoting = computed(() => race.value?.status === 'voting')
const isRaceLocked = computed(() => race.value?.status === 'locked')
const isRaceSettled = computed(() => race.value?.status === 'settled')

const horsePositions = computed<Record<string, number> | undefined>(() => {
  if (!race.value || !isRaceSettled.value) return undefined
  const map: Record<string, number> = {}
  for (const h of race.value.horses) {
    if (h.position && h.position >= 1 && h.position <= 3) {
      map[h.snapshot_data.name ?? ''] = h.position
    }
  }
  return map
})

const isAdmin = computed(() => authStore.isAdmin)

const canEnterJiggleMode = computed(() =>
  isAdmin.value && (
    isRaceVoting.value ||
    ((isRaceLocked.value || isRaceSettled.value) && resultMode.value === 'ranking')
  ),
)

function toggleJiggleMode() {
  if (!canEnterJiggleMode.value) return
  if (isJiggleMode.value) {
    // Exit jiggle mode: reset all drag state
    isJiggleMode.value = false
    gateTouchIndex.value = -1
    gateDragOverIndex.value = -1
    gateDragSort.value?.endDrag()
    resultTouchIndex.value = -1
    resultDragOverIndex.value = -1
    resultDragSource.value = 'active'
    resultDragSort.value?.endDrag()
  } else {
    isJiggleMode.value = true
  }
}

const canVote = computed(() =>
  isRaceVoting.value && authStore.isLoggedIn && !authStore.isAdmin,
)
// Guests get clickable cards as well: handleCardClick redirects them to login
const cardsVotable = computed(() =>
  isRaceVoting.value && !authStore.isAdmin,
)

const isGuestVoting = computed(() =>
  isRaceVoting.value && !authStore.isLoggedIn,
)

function isHorseVoted(raceHorseId: number): boolean {
  return votedRaceHorseId.value === raceHorseId
}

function handleCardClick(horse: RaceDetail['horses'][0]) {
  if (!authStore.isLoggedIn) {
    router.push({ path: '/login', query: { redirect: `/races/${raceId}` } })
    return
  }
  if (authStore.isAdmin) return
  if (!isRaceVoting.value) return
  toggleVote(horse, raceId)
}

// Header editing
const headerSaveError = ref('')
const headerSaveSuccess = ref(false)
const dateEditing = ref(false)
const editDate = ref('')
const dateInputRef = ref<HTMLInputElement | null>(null)

function startDateEdit() {
  if (!isAdmin.value || !isRaceVoting.value || !race.value) return
  editDate.value = race.value.date.slice(0, 10)
  dateEditing.value = true
  nextTick(() => dateInputRef.value?.focus())
}

function saveDate() {
  if (!race.value || !editDate.value) return
  dateEditing.value = false
  handleHeaderSave({ name: race.value.name, date: editDate.value })
}

function cancelDateEdit() {
  dateEditing.value = false
}

async function handleHeaderSave({ name, date }: { name: string; date: string }) {
  if (!race.value || !isAdmin.value || !isRaceVoting.value) return
  headerSaveError.value = ''
  headerSaveSuccess.value = false

  const payload: { name?: string; date?: string } = {}
  if (name !== race.value.name) payload.name = name
  if (date !== race.value.date.slice(0, 10)) payload.date = date

  if (Object.keys(payload).length === 0) return

  try {
    race.value = await updateRace(raceId, payload)
    headerSaveSuccess.value = true
    setTimeout(() => { headerSaveSuccess.value = false }, 2000)
  } catch (err: any) {
    headerSaveError.value = err?.response?.data?.detail?.message || '保存失败'
  }
}

// Lock
const locking = ref(false)
const lockError = ref('')
const showLockConfirm = ref(false)

async function handleLock() {
  if (!race.value || !isAdmin.value || !isRaceVoting.value || locking.value) return
  locking.value = true
  lockError.value = ''
  try {
    await lockRace(raceId)
    showLockConfirm.value = false
    race.value = await getRace(raceId)
    await loadVotes(raceId)
    isJiggleMode.value = false
  } catch (err: any) {
    lockError.value = err?.response?.data?.detail?.message || '锁定失败'
  } finally {
    locking.value = false
  }
}

// Add horse modal
const showAddHorseModal = ref(false)
const selectedAddHorse = ref<Horse[]>([])
const addHorseError = ref('')
const addHorseSaving = ref(false)

// Delete horse via drag
const deleteHover = ref(false)
const deleteTarget = ref<{ raceHorseId: number; name: string } | null>(null)
const showDeleteConfirm = ref(false)
const deleting = ref(false)

function handleGateDragItemDragStart(e: DragEvent, horse: RaceDetail['horses'][0]) {
  if (!isAdmin.value || !isRaceVoting.value) return
  e.dataTransfer?.setData(
    'application/json',
    JSON.stringify({
      raceHorseId: horse.race_horse_id,
      name: horse.snapshot_data.name ?? '未知',
    }),
  )
}

function handleDeleteDragEnter() {
  deleteHover.value = true
}

function handleDeleteDragLeave() {
  deleteHover.value = false
}

function handleDeleteDrop(e: DragEvent) {
  e.preventDefault()
  deleteHover.value = false
  const raw = e.dataTransfer?.getData('application/json')
  if (!raw) return
  try {
    const data = JSON.parse(raw)
    deleteTarget.value = { raceHorseId: data.raceHorseId, name: data.name }
    showDeleteConfirm.value = true
  } catch {
    // ignore invalid data
  }
}

async function confirmDeleteHorse() {
  if (!race.value || !deleteTarget.value || deleting.value) return
  deleting.value = true
  try {
    await removeRaceHorse(raceId, deleteTarget.value.raceHorseId)
    race.value = await getRace(raceId)
    showDeleteConfirm.value = false
    deleteTarget.value = null
  } catch (err: any) {
    alert(err?.response?.data?.detail?.message || '删除马匹失败')
  } finally {
    deleting.value = false
  }
}

function openAddHorseModal() {
  if (!isAdmin.value || !isRaceVoting.value) return
  selectedAddHorse.value = []
  addHorseError.value = ''
  showAddHorseModal.value = true
}

function closeAddHorseModal() {
  showAddHorseModal.value = false
}

async function confirmAddHorse() {
  if (!race.value || selectedAddHorse.value.length === 0 || addHorseSaving.value) return
  addHorseSaving.value = true
  addHorseError.value = ''
  try {
    for (const horse of selectedAddHorse.value) {
      await addRaceHorse(raceId, { horse_id: horse.id })
    }
    race.value = await getRace(raceId)
    closeAddHorseModal()
  } catch (err: any) {
    addHorseError.value = err?.response?.data?.detail?.message || '添加马匹失败'
  } finally {
    addHorseSaving.value = false
  }
}

// Delete race
const showDeleteRaceModal = ref(false)
const deletingRace = ref(false)
const deleteRaceError = ref('')

async function handleDeleteRace() {
  if (!race.value || deletingRace.value) return
  deletingRace.value = true
  deleteRaceError.value = ''
  try {
    await deleteRace(raceId)
    router.push('/')
  } catch (err: any) {
    deleteRaceError.value = err?.response?.data?.detail?.message || '删除比赛失败'
  } finally {
    deletingRace.value = false
  }
}
async function handleUpdateJockey(
  horse: RaceDetail['horses'][0],
  value: string | null,
) {
  if (!isAdmin.value || !isRaceVoting.value) return
  try {
    await updateRaceHorse(raceId, horse.race_horse_id, { jockey: value })
    race.value = await getRace(raceId)
  } catch (err: any) {
    alert(err?.response?.data?.detail?.message || '保存失败')
  }
}

async function handleRefresh(horse: RaceDetail['horses'][0]) {
  if (!isAdmin.value || !race.value) return
  try {
    await refreshRaceHorseSnapshot(raceId, horse.race_horse_id)
    race.value = await getRace(raceId)
  } catch (err: any) {
    alert(err?.response?.data?.detail?.message || '刷新失败')
  }
}

// Gate drag mode
const gateDragSort = computed(() => {
  if (!race.value) return null
  return useDragSort(race.value.horses, undefined, { mode: 'gate' })
})

const gateHorses = computed(() => gateDragSort.value?.activeList.value ?? race.value?.horses ?? [])
const isGateDragging = computed(() => gateDragSort.value?.isDragging.value ?? false)

// For normal view (non-result mode): sort by gate (voting/locked) or position (settled)
const displayHorses = computed(() => {
  if (!race.value) return []
  if (isRaceSettled.value) {
    return [...race.value.horses].sort((a, b) => {
      const posA = a.position === 0 ? 999 : (a.position ?? 999)
      const posB = b.position === 0 ? 999 : (b.position ?? 999)
      if (posA !== posB) return posA - posB
      // For DNF horses (position 0), sort by gate to match DNF zone order
      return (a.gate ?? 999) - (b.gate ?? 999)
    })
  }
  return gateHorses.value
})

const gateDragOverIndex = ref(-1)

function handleGateDragStart(index: number) {
  gateDragSort.value?.startDrag(index)
  gateDragOverIndex.value = -1
}

function handleGateDrop(event: DragEvent) {
  event.preventDefault()
  const sort = gateDragSort.value
  if (!sort || sort.draggedIndex.value < 0) return

  const dropZone = event.currentTarget as HTMLElement
  const cards = dropZone.querySelectorAll('.gate-drag-item')
  let targetIndex = cards.length - 1
  const mouseY = event.clientY
  for (let i = 0; i < cards.length; i++) {
    const rect = cards[i].getBoundingClientRect()
    const midY = rect.top + rect.height / 2
    if (mouseY < midY) {
      targetIndex = i
      break
    }
  }
  sort.commitReorder(sort.draggedIndex.value, targetIndex)
  submitGateOrder()
  gateDragOverIndex.value = -1
}

function handleGateDragEnd() {
  gateDragSort.value?.endDrag()
  gateDragOverIndex.value = -1
  dragClientY.value = 0
}

async function submitGateOrder() {
  if (!race.value || !isAdmin.value || !isRaceVoting.value) return
  const order = gateHorses.value.map(h => h.race_horse_id)
  try {
    race.value = await updateGateOrder(raceId, { order })
  } catch (err: any) {
    alert(err?.response?.data?.detail?.message || '闸位排序保存失败')
    await loadRace()
  }
}

// Mobile touch gate drag (jiggle mode only)
const gateTouchIndex = ref(-1)

function handleGateTouchStart(_event: TouchEvent, index: number) {
  if (!authStore.isAdmin || !isRaceVoting.value || !isJiggleMode.value) return
  gateTouchIndex.value = index
  gateDragSort.value?.startDrag(index)
}

// Cache card positions to avoid getBoundingClientRect() on every touchmove
let cachedGateCardRects: { top: number; bottom: number }[] = []
let gateCardRectsCacheTime = 0
let cachedResultCardRects: { top: number; bottom: number }[] = []
let resultCardRectsCacheTime = 0

function handleGateTouchMove(event: TouchEvent) {
  if (gateTouchIndex.value < 0) return
  event.preventDefault()
  dragClientY.value = event.touches[0].clientY

  // Refresh card rect cache every 200ms
  const now = Date.now()
  if (now - gateCardRectsCacheTime > 200) {
    const cards = document.querySelectorAll('.gate-drag-item')
    cachedGateCardRects = []
    for (let i = 0; i < cards.length; i++) {
      const rect = cards[i].getBoundingClientRect()
      cachedGateCardRects.push({ top: rect.top, bottom: rect.bottom })
    }
    gateCardRectsCacheTime = now
  }

  const touchY = event.touches[0].clientY
  for (let i = 0; i < cachedGateCardRects.length; i++) {
    if (touchY >= cachedGateCardRects[i].top && touchY <= cachedGateCardRects[i].bottom) {
      if (i !== gateTouchIndex.value && gateDragSort.value) {
        const item = gateDragSort.value.activeList.value.splice(gateTouchIndex.value, 1)[0]
        if (item) {
          gateDragSort.value.activeList.value.splice(i, 0, item)
          gateTouchIndex.value = i
          gateDragOverIndex.value = i
          gateCardRectsCacheTime = 0
        }
      }
      break
    }
  }
}

function handleGateTouchEnd() {
  if (gateTouchIndex.value >= 0) {
    submitGateOrder()
  }
  gateTouchIndex.value = -1
  gateDragOverIndex.value = -1
  dragClientY.value = 0
  gateDragSort.value?.endDrag()
}

// Result ranking mode
const resultMode = ref<ResultMode>('idle')
const resultEntryVersion = ref(0)
const existingPositions = ref<Map<number, number> | undefined>(undefined)
const resultDragSort = shallowRef<ReturnType<typeof useDragSort> | null>(null)
const resultDragOverIndex = ref(-1)
const resultSubmitting = ref(false)
const resultSubmitError = ref('')

const resultActiveList = computed(() => resultDragSort.value?.activeList.value ?? [])
const resultDnfList = computed(() => resultDragSort.value?.dnfList.value ?? [])
const isResultDragging = computed(() => resultDragSort.value?.isDragging.value ?? false)
const resultDragSource = ref<'active' | 'dnf'>('active')
const resultTouchIndex = ref(-1)

// Auto-scroll during drag
const dragClientY = ref(0)
const autoScrollEnabled = computed(() =>
  gateDragSort.value?.isDragging.value ||
  resultDragSort.value?.isDragging.value ||
  gateTouchIndex.value >= 0 ||
  resultTouchIndex.value >= 0,
)
const { autoScrollDirection } = useDragAutoScroll({ enabled: autoScrollEnabled, clientY: dragClientY })

function initResultDragSort() {
  if (!race.value) return
  const hasPositions = race.value.horses.some(h => h.position !== null && h.position !== undefined)
  if (hasPositions) {
    existingPositions.value = new Map(
      race.value.horses.map(h => [h.race_horse_id, h.position ?? 0]),
    )
  } else {
    existingPositions.value = undefined
  }
  resultDragSort.value = useDragSort([...race.value.horses], existingPositions.value, { mode: 'result' })
}

function enterResultMode() {
  if (!isAdmin.value || (!isRaceLocked.value && !isRaceSettled.value)) return
  resultMode.value = 'ranking'
  resultEntryVersion.value++
  resultSubmitError.value = ''
  resultDragOverIndex.value = -1
  resultTouchIndex.value = -1
  resultDragSource.value = 'active'
  initResultDragSort()
  isJiggleMode.value = true
  revealList(race.value?.horses.length ?? 0)
}

function exitResultMode() {
  resultMode.value = 'idle'
  resultDragSort.value = null
  isJiggleMode.value = false
  resultDragOverIndex.value = -1
  resultTouchIndex.value = -1
  resultDragSource.value = 'active'
}

function handleResultDragStart(index: number, source: 'active' | 'dnf' = 'active') {
  resultDragSort.value?.startDrag(index)
  resultDragSource.value = source
  resultDragOverIndex.value = -1
}

function handleResultDrop(event: DragEvent) {
  event.preventDefault()
  if (!resultDragSort.value || resultDragSort.value.draggedIndex.value < 0) return

  if (resultDragSource.value === 'dnf') {
    resultDragSort.value.moveToActive(resultDragSort.value.draggedIndex.value)
  } else {
    const dropZone = event.currentTarget as HTMLElement
    const cards = dropZone.querySelectorAll('.result-drag-item')
    let targetIndex = cards.length - 1
    const mouseY = event.clientY
    for (let i = 0; i < cards.length; i++) {
      const rect = cards[i].getBoundingClientRect()
      const midY = rect.top + rect.height / 2
      if (mouseY < midY) {
        targetIndex = i
        break
      }
    }
    resultDragSort.value.commitReorder(resultDragSort.value.draggedIndex.value, targetIndex)
  }
  resultDragOverIndex.value = -1
}

function handleResultDragEnd() {
  resultDragSort.value?.endDrag()
  resultDragOverIndex.value = -1
  dragClientY.value = 0
}

function handleDnfDrop(event: DragEvent) {
  event.preventDefault()
  if (resultDragSort.value && resultDragSort.value.draggedIndex.value >= 0 && resultDragSource.value === 'active') {
    resultDragSort.value.moveToDnf(resultDragSort.value.draggedIndex.value)
  }
  resultDragSort.value?.endDrag()
  resultDragOverIndex.value = -1
}

function handleDnfClick(index: number) {
  resultDragSort.value?.moveToActive(index)
}

// Mobile touch result ranking (jiggle mode)
function handleResultTouchStart(index: number, source: 'active' | 'dnf') {
  if (!isJiggleMode.value) return
  resultTouchIndex.value = index
  resultDragSource.value = source
  resultDragSort.value?.startDrag(index)
}

function handleResultTouchMove(event: TouchEvent) {
  if (resultTouchIndex.value < 0 || !resultDragSort.value) return
  event.preventDefault()
  dragClientY.value = event.touches[0].clientY

  // Refresh card rect cache every 200ms
  const now = Date.now()
  if (now - resultCardRectsCacheTime > 200) {
    const cards = document.querySelectorAll('.result-drag-item')
    cachedResultCardRects = []
    for (let i = 0; i < cards.length; i++) {
      const rect = cards[i].getBoundingClientRect()
      cachedResultCardRects.push({ top: rect.top, bottom: rect.bottom })
    }
    resultCardRectsCacheTime = now
  }

  const touch = event.touches[0]
  for (let i = 0; i < cachedResultCardRects.length; i++) {
    if (touch.clientY >= cachedResultCardRects[i].top && touch.clientY <= cachedResultCardRects[i].bottom) {
      if (i !== resultTouchIndex.value && resultDragSource.value === 'active') {
        const item = resultDragSort.value.activeList.value.splice(resultTouchIndex.value, 1)[0]
        if (item) {
          resultDragSort.value.activeList.value.splice(i, 0, item)
          resultTouchIndex.value = i
          resultDragOverIndex.value = i
          resultCardRectsCacheTime = 0
        }
      }
      break
    }
  }
}

function handleResultTouchEnd(event: TouchEvent) {
  if (resultTouchIndex.value < 0) return

  // Check if released over DNF zone
  if (resultDragSource.value === 'active') {
    const dnfZone = document.querySelector('.dnf-zone')
    if (dnfZone) {
      const dnfRect = dnfZone.getBoundingClientRect()
      const touchY = event.changedTouches[0].clientY
      if (touchY >= dnfRect.top && touchY <= dnfRect.bottom) {
        resultDragSort.value?.moveToDnf(resultTouchIndex.value)
      }
    }
  } else if (resultDragSource.value === 'dnf') {
    // DNF card tap → move back to active
    const activeZone = document.querySelector('.drop-zone')
    if (activeZone) {
      const activeRect = activeZone.getBoundingClientRect()
      const touchY = event.changedTouches[0].clientY
      if (touchY < activeRect.bottom) {
        resultDragSort.value?.moveToActive(resultTouchIndex.value)
      }
    }
  }

  resultTouchIndex.value = -1
  resultDragOverIndex.value = -1
  dragClientY.value = 0
  resultDragSort.value?.endDrag()
}

function handleResultTouchCancel() {
  resultTouchIndex.value = -1
  resultDragOverIndex.value = -1
  dragClientY.value = 0
  resultDragSort.value?.endDrag()
}

const allPositioned = computed(() => {
  return resultActiveList.value.length + resultDnfList.value.length === (race.value?.horses.length ?? 0)
    && resultActiveList.value.length > 0
})

const confirmResultDisabled = computed(() => {
  return !allPositioned.value || resultSubmitting.value
})

const confirmResultText = computed(() => {
  if (resultSubmitting.value) return '提交中…'
  if (!allPositioned.value) return '请排列所有马匹的名次（含弃权区）'
  return '确认结果'
})

async function handleConfirmResult() {
  if (!race.value || confirmResultDisabled.value) return

  resultSubmitting.value = true
  resultSubmitError.value = ''

  const positions: ResultPosition[] = [
    ...resultActiveList.value.map((horse, index) => ({
      race_horse_id: horse.race_horse_id,
      position: index + 1,
    })),
    ...resultDnfList.value.map(horse => ({
      race_horse_id: horse.race_horse_id,
      position: 0,
    })),
  ]

  try {
    await submitResults(raceId, positions)
    // Exit result mode first, then refresh data to prevent stale rendering state
    exitResultMode()
    await nextTick()
    race.value = await getRace(raceId)
    if (race.value.status === 'settled') {
      await loadVotes(raceId)
      checkUserVote()
    }
  } catch (err: any) {
    const code = err?.response?.data?.detail?.code
    if (code === 'RACE_NOT_LOCKED') {
      resultSubmitError.value = err?.response?.data?.detail?.message || '比赛处于投票中状态，请先锁定'
    } else if (err?.response?.status === 422) {
      const details = err?.response?.data?.detail
      if (Array.isArray(details)) {
        resultSubmitError.value = details.map((d: any) => d.msg || '').join('；') || '数据校验失败'
      } else {
        resultSubmitError.value = details?.message || '数据校验失败'
      }
    } else {
      resultSubmitError.value = err?.response?.data?.detail?.message || '提交失败，请重试'
    }
  } finally {
    resultSubmitting.value = false
  }
}

// Toggle hidden
const togglingHidden = ref(false)

async function handleToggleHidden() {
  if (!race.value || togglingHidden.value) return
  togglingHidden.value = true
  try {
    const result = await toggleRaceHidden(race.value.id)
    race.value.is_hidden = result.is_hidden
  } catch {
    // silently fail
  } finally {
    togglingHidden.value = false
  }
}

// Best win update
const updatingBestWin = ref(false)
const bestWinUpdateError = ref('')
const bestWinUpdateSuccess = ref(false)

const winnerHorse = computed(() => {
  if (!race.value || !isRaceSettled.value) return null
  return race.value.horses.find(h => h.position === 1) ?? null
})

const canUpdateBestWin = computed(() => {
  if (!winnerHorse.value || !race.value) return false
  if (winnerHorse.value.snapshot_data.best_win === race.value.name) return false
  return true
})

async function handleUpdateBestWin() {
  if (!winnerHorse.value || !race.value || updatingBestWin.value) return
  updatingBestWin.value = true
  bestWinUpdateError.value = ''
  bestWinUpdateSuccess.value = false
  try {
    await updateBestWin(winnerHorse.value.horse_id, race.value.id)
    bestWinUpdateSuccess.value = true
  } catch (err: any) {
    bestWinUpdateError.value = err?.response?.data?.detail?.message || '更新主胜鞍失败'
  } finally {
    updatingBestWin.value = false
  }
}

async function loadRace() {
  pageState.value = 'loading'
  errorMessage.value = '加载失败，请刷新重试'
  try {
    race.value = await getRace(raceId)
    pageState.value = 'success'
    revealList(race.value.horses.length)
    await loadVotes(raceId)
    checkUserVote()
  } catch (err: any) {
    pageState.value = 'error'
    const code = err?.response?.data?.detail?.code
    if (code === 'RACE_HIDDEN') {
      errorMessage.value = '当前比赛已隐藏'
    }
  }
}

onMounted(loadRace)

onUnmounted(() => {
  isJiggleMode.value = false
})
</script>

<template>
  <div class="race-detail-page">
    <!-- Auto-scroll hints -->
    <div class="scroll-hint scroll-hint-up" :class="{ active: autoScrollDirection === 'up' }">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="18 15 12 9 6 15"/></svg>
    </div>
    <div class="scroll-hint scroll-hint-down" :class="{ active: autoScrollDirection === 'down' }">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <!-- Loading -->
    <div v-if="pageState === 'loading'" class="detail-skeleton" role="status" aria-live="polite" aria-label="加载中">
      <div class="ui-skeleton skeleton-hero"></div>
      <div v-for="i in 4" :key="i" class="ui-skeleton skeleton-horse"></div>
    </div>

    <!-- Error -->
    <div v-else-if="pageState === 'error'" class="ui-state ui-state--error" role="alert">
      <span class="ui-state-icon">
        <svg v-if="errorMessage === '当前比赛已隐藏'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" /><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" /><line x1="1" y1="1" x2="23" y2="23" />
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </span>
      <p class="ui-state-text">{{ errorMessage }}</p>
      <button
        v-if="errorMessage !== '当前比赛已隐藏'"
        class="ui-btn ui-btn--primary"
        @click="router.go(0)"
      >
        刷新重试
      </button>
      <button
        v-if="errorMessage === '当前比赛已隐藏'"
        class="ui-btn ui-btn--primary"
        @click="router.push('/')"
      >
        返回首页
      </button>
    </div>

    <!-- Race Detail -->
    <template v-else-if="race">
      <section class="race-hero" :class="`is-${race.status}`">
        <svg class="hero-track" viewBox="0 0 400 200" preserveAspectRatio="none" aria-hidden="true">
          <path d="M-20 175 C 110 130, 250 125, 420 35" />
          <path d="M-20 195 C 110 150, 250 145, 420 55" />
          <path d="M-20 215 C 110 170, 250 165, 420 75" />
        </svg>

        <div class="race-header-top">
          <button class="back-btn" @click="router.push('/')" aria-label="返回首页">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            返回
          </button>
          <div class="hero-top-right">
            <StatusBadge :status="race.status" />
            <HiddenToggleButton
              v-if="isAdmin"
              :hidden="race.is_hidden"
              :loading="togglingHidden"
              @toggle="handleToggleHidden"
            />
          </div>
        </div>

        <RaceTags :race="race" on-dark class="hero-tags" />

        <div class="race-title-row">
          <RaceHeaderEditor
            v-if="isAdmin && isRaceVoting"
            :name="race.name"
            :date="race.date"
            @save="handleHeaderSave"
          />
          <h1 v-else class="race-name">{{ race.name }}</h1>
        </div>

        <div class="race-subinfo">
          <div class="date-row">
            <svg class="subinfo-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            <template v-if="isAdmin && isRaceVoting && dateEditing">
              <input
                ref="dateInputRef"
                v-model="editDate"
                type="date"
                class="date-input"
                @blur="saveDate"
                @keydown.enter.prevent="saveDate"
                @keydown.escape.prevent="cancelDateEdit"
              />
            </template>
            <p
              v-else
              class="race-date"
              :class="{ 'date-editable': isAdmin && isRaceVoting }"
              :title="isAdmin && isRaceVoting ? '双击修改日期' : undefined"
              @dblclick="startDateEdit"
            >{{ race.date }}</p>
            <button
              v-if="isAdmin && isRaceVoting && !dateEditing"
              type="button"
              class="hero-edit-btn"
              aria-label="修改日期"
              title="修改日期"
              @click="startDateEdit"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
              </svg>
            </button>
          </div>
          <p class="race-meta">
            <span class="meta-stat"><strong>{{ race.horses.length }}</strong> 匹参赛</span>
            <span class="meta-stat"><strong>{{ race.vote_count }}</strong> 人已投</span>
          </p>
        </div>

        <Transition name="ui-fade">
          <p v-if="headerSaveError" class="header-message error">{{ headerSaveError }}</p>
        </Transition>
        <Transition name="ui-fade">
          <p v-if="headerSaveSuccess" class="header-message success">保存成功</p>
        </Transition>
      </section>

      <!-- Admin actions for voting state -->
      <div v-if="isAdmin && isRaceVoting && resultMode === 'idle'" class="admin-actions-bar">
        <button
          class="ui-btn ui-btn--primary"
          :disabled="locking"
          @click="showLockConfirm = true; lockError = ''"
        >
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" />
          </svg>
          锁定
        </button>
        <button
          v-if="canEnterJiggleMode"
          class="jiggle-toggle-btn mobile-only"
          :class="{ active: isJiggleMode }"
          :aria-label="isJiggleMode ? '退出编辑闸位模式' : '进入编辑闸位模式'"
          :aria-pressed="isJiggleMode"
          @click="toggleJiggleMode"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          <span>{{ isJiggleMode ? '完成' : '编辑闸位' }}</span>
        </button>
        <button
          class="ui-btn ui-btn--danger delete-btn"
          @click="showDeleteRaceModal = true; deleteRaceError = ''"
        >
          删除比赛
        </button>
        <p v-if="lockError" class="admin-error">{{ lockError }}</p>
        <p v-if="deleteRaceError" class="admin-error">{{ deleteRaceError }}</p>
      </div>

      <!-- Admin result mode entry -->
      <div v-if="isAdmin && isRaceLocked && resultMode === 'idle'" class="admin-actions-bar">
        <button class="ui-btn ui-btn--gold" @click="enterResultMode">
          <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M4 22V4" /><path d="M4 4h12l-2 4 2 4H4" />
          </svg>
          比赛结束
        </button>
        <button
          class="ui-btn ui-btn--danger delete-btn"
          @click="showDeleteRaceModal = true; deleteRaceError = ''"
        >
          删除比赛
        </button>
        <p v-if="deleteRaceError" class="admin-error">{{ deleteRaceError }}</p>
      </div>

      <div v-if="isAdmin && isRaceSettled && resultMode === 'idle'" class="admin-actions-bar">
        <button class="ui-btn ui-btn--outline" @click="enterResultMode">
          修改结果
        </button>
        <button
          v-if="canUpdateBestWin"
          class="ui-btn ui-btn--outline"
          :disabled="updatingBestWin"
          @click="handleUpdateBestWin"
        >
          {{ updatingBestWin ? '更新中…' : '更新主胜鞍' }}
        </button>
        <p v-if="bestWinUpdateSuccess" class="admin-success">主胜鞍已更新为「{{ race.name }}」</p>
        <p v-if="bestWinUpdateError" class="admin-error">{{ bestWinUpdateError }}</p>
      </div>

      <!-- Admin result confirmation / cancel in ranking mode (at top, same position as 修改结果) -->
      <div v-if="isAdmin && resultMode === 'ranking'" class="admin-actions-bar ranking-actions-bar">
        <button
          class="ui-btn ui-btn--gold confirm-result-btn"
          :disabled="confirmResultDisabled"
          @click="handleConfirmResult"
        >
          <span v-if="resultSubmitting" class="ui-spinner"></span>
          {{ confirmResultText }}
        </button>
        <button class="ui-btn ui-btn--ghost" @click="exitResultMode">
          取消
        </button>
        <p v-if="resultSubmitError" class="admin-error">{{ resultSubmitError }}</p>
      </div>


      <!-- Custom scoring info -->
      <div v-if="race.custom_scoring" class="custom-scoring-info">
        <p class="scoring-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 20V10" /><path d="M18 20V4" /><path d="M6 20v-4" />
          </svg>
          自定义积分规则
        </p>
        <div class="scoring-chips">
          <span
            v-for="(points, i) in race.custom_scoring.positive_scores"
            :key="'plus-' + i"
            class="score-chip plus"
          >第{{ i + 1 }}名 <strong>+{{ points }}</strong></span>
          <span
            v-for="(rule, i) in race.custom_scoring.penalty_rules ?? []"
            :key="'minus-' + i"
            class="score-chip minus"
          >倒数第{{ Math.abs(rule.position) }}名 <strong>-{{ Math.abs(rule.points) }}</strong></span>
        </div>
      </div>

      <!-- Vote hints -->
      <Transition name="hint-swap" mode="out-in">
        <div v-if="canVote && !votedHorseName" key="pick" class="vote-hint">
          <svg class="hint-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M9 11V6a3 3 0 0 1 6 0v5" /><path d="M5 11h14l-1.5 9a2 2 0 0 1-2 1.7H8.5a2 2 0 0 1-2-1.7z" />
          </svg>
          <span>看好哪匹就点它的卡片（或右侧「选它」），再点一次取消</span>
        </div>
        <div v-else-if="canVote && votedHorseName" :key="'voted-' + votedHorseName" class="vote-hint voted">
          <svg class="hint-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span>已投 <strong>{{ votedHorseName }}</strong>，点击该马匹可取消投票，点击其他马匹可更换选择</span>
        </div>
        <div v-else-if="isGuestVoting" key="guest" class="vote-hint">
          <svg class="hint-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /><polyline points="10 17 15 12 10 7" /><line x1="15" y1="12" x2="3" y2="12" />
          </svg>
          <span>登录后即可投票——点任意马匹会带你去登录</span>
        </div>
      </Transition>

      <!-- Horse list -->
      <div class="horse-list">
        <h2 class="section-title">
          参赛马匹
          <span class="count-chip">{{ race.horses.length }}</span>
        </h2>

        <!-- Normal / gate drag view -->
        <div
          v-if="resultMode !== 'ranking'"
          class="horse-list-content"
          :class="{ 'gate-dragging': isGateDragging }"
          @dragover.prevent
          @drop="handleGateDrop"
        >
          <!-- Admin voting: with touch/drag handlers for gate reorder -->
          <template v-if="isAdmin && isRaceVoting">
            <div
              v-for="(horse, index) in displayHorses"
              :key="horse.race_horse_id"
              class="gate-drag-item"
              :class="{ 'drag-over-top': gateDragOverIndex === index && isGateDragging, 'touch-dragging': gateTouchIndex >= 0, 'ui-stagger': listRevealing }"
              :style="{ '--i': index }"
              @dragstart="(e: DragEvent) => handleGateDragItemDragStart(e, horse)"
              @touchstart="(e: TouchEvent) => handleGateTouchStart(e, index)"
              @touchmove="handleGateTouchMove"
              @touchend="handleGateTouchEnd"
              @touchcancel="handleGateTouchEnd"
            >
              <HorseDetailCard
                :snapshot-data="horse.snapshot_data"
                :horse-id="horse.horse_id"
                :jockey="horse.jockey"
                :birth-year="horse.snapshot_data.birth_year"
                :hemisphere="horse.snapshot_data.hemisphere"
                :reference-date="race.date"
                :votable="cardsVotable"
                :voted="isHorseVoted(horse.race_horse_id)"
                :submitting="isSubmitting"
                :gate="horse.gate"
                :field-size="bracketFieldSize"
                :position="isRaceSettled ? (horse.position ?? null) : null"
                :editable="isAdmin && isRaceVoting"
                :draggable="(isAdmin && isRaceVoting) ? true : undefined"
                :show-delete-button="isJiggleMode"
                :is-jiggling="isJiggleMode"
                :class="{ 'voted-horse-locked': (isRaceLocked || isRaceSettled) && votedHorseName && horse.snapshot_data.name === votedHorseName }"
                @vote-toggle="handleCardClick(horse)"
                @update-field="(payload) => handleUpdateJockey(horse, payload.value)"
                @drag-start="handleGateDragStart(index)"
                @drag-end="handleGateDragEnd"
                @refresh="handleRefresh(horse)"
                @delete-click="deleteTarget = { raceHorseId: horse.race_horse_id, name: horse.snapshot_data.name ?? '未知' }; showDeleteConfirm = true"
              />
            </div>
          </template>
          <!-- Regular users / non-voting: NO touch/drag handlers to avoid mobile freeze -->
          <template v-else>
            <div
              v-for="(horse, index) in displayHorses"
              :key="horse.race_horse_id"
              class="gate-drag-item"
              :class="{ 'ui-stagger': listRevealing }"
              :style="{ '--i': index }"
            >
              <HorseDetailCard
                :snapshot-data="horse.snapshot_data"
                :horse-id="horse.horse_id"
                :jockey="horse.jockey"
                :birth-year="horse.snapshot_data.birth_year"
                :hemisphere="horse.snapshot_data.hemisphere"
                :reference-date="race.date"
                :votable="cardsVotable"
                :voted="isHorseVoted(horse.race_horse_id)"
                :submitting="isSubmitting"
                :gate="horse.gate"
                :field-size="bracketFieldSize"
                :position="isRaceSettled ? (horse.position ?? null) : null"
                :editable="isAdmin && isRaceVoting"
                :class="{ 'voted-horse-locked': (isRaceLocked || isRaceSettled) && votedHorseName && horse.snapshot_data.name === votedHorseName }"
                @vote-toggle="handleCardClick(horse)"
                @refresh="handleRefresh(horse)"
              />
            </div>
          </template>
          <div v-if="isAdmin && isRaceVoting && !isJiggleMode" class="add-delete-row">
            <AddHorseCard @click="openAddHorseModal" />
            <div
              class="delete-zone"
              :class="{ 'delete-hover': deleteHover }"
              @dragenter.prevent="handleDeleteDragEnter"
              @dragover.prevent="handleDeleteDragEnter"
              @dragleave="handleDeleteDragLeave"
              @drop="handleDeleteDrop"
            >
              <svg class="delete-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
              </svg>
              <span class="delete-label">拖拽至此删除</span>
            </div>
          </div>
        </div>

        <!-- Result ranking mode -->
        <div v-else class="result-ranking-area" :key="'ranking-' + resultEntryVersion">
          <div class="instructions">
            <svg class="hint-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polyline points="5 9 2 12 5 15" /><polyline points="9 5 12 2 15 5" /><polyline points="15 19 12 22 9 19" /><polyline points="19 9 22 12 19 15" /><line x1="2" y1="12" x2="22" y2="12" /><line x1="12" y1="2" x2="12" y2="22" />
            </svg>
            <span>拖拽马匹卡片调整名次顺序。<span class="text-muted">第1名在顶部，弃权马匹拖入下方 DNF 区。</span></span>
          </div>

          <div class="drop-zone" @dragover.prevent @drop="handleResultDrop">
            <div
              v-for="(horse, index) in resultActiveList"
              :key="'result-active-' + horse.race_horse_id"
              class="result-drag-item"
              :class="{ 'drag-over-top': resultDragOverIndex === index && isResultDragging, 'touch-dragging': resultTouchIndex >= 0, 'ui-stagger': listRevealing }"
              :style="{ '--i': index }"
              @touchstart="handleResultTouchStart(index, 'active')"
              @touchmove="handleResultTouchMove"
              @touchend="handleResultTouchEnd"
              @touchcancel="handleResultTouchCancel"
            >
              <HorseDetailCard
                :snapshot-data="horse.snapshot_data"
                :horse-id="horse.horse_id"
                :jockey="horse.jockey"
                :birth-year="horse.snapshot_data.birth_year"
                :hemisphere="horse.snapshot_data.hemisphere"
                :reference-date="race.date"
                :gate="horse.gate"
                :field-size="bracketFieldSize"
                :position="index + 1"
                :draggable="true"
                :is-dnf="false"
                :show-delete-button="isJiggleMode"
                :is-jiggling="isJiggleMode"
                @drag-start="handleResultDragStart(index, 'active')"
                @drag-end="handleResultDragEnd"
                @refresh="handleRefresh(horse)"
                @delete-click="deleteTarget = { raceHorseId: horse.race_horse_id, name: horse.snapshot_data.name ?? '未知' }; showDeleteConfirm = true"
              />
            </div>
          </div>

          <div
            class="dnf-zone"
            @dragover.prevent
            @drop="handleDnfDrop"
          >
            <div class="dnf-zone-header">
              <span class="dnf-label">DNF/弃权区</span>
              <span v-if="resultDnfList.length > 0" class="dnf-tip">点卡片可移回名次区</span>
              <span v-if="resultDnfList.length > 0" class="dnf-count">{{ resultDnfList.length }}匹</span>
            </div>
            <div v-if="resultDnfList.length === 0" class="dnf-empty-hint">
              将弃权马匹拖拽至此
            </div>
            <div
              v-for="(horse, index) in resultDnfList"
              :key="'result-dnf-' + horse.race_horse_id"
              class="dnf-item"
              @click="handleDnfClick(index)"
              @touchstart="handleResultTouchStart(index, 'dnf')"
              @touchmove="handleResultTouchMove"
              @touchend="handleResultTouchEnd"
              @touchcancel="handleResultTouchCancel"
            >
              <HorseDetailCard
                :snapshot-data="horse.snapshot_data"
                :horse-id="horse.horse_id"
                :jockey="horse.jockey"
                :birth-year="horse.snapshot_data.birth_year"
                :hemisphere="horse.snapshot_data.hemisphere"
                :reference-date="race.date"
                :gate="horse.gate"
                :field-size="bracketFieldSize"
                :draggable="true"
                :is-dnf="true"
                :show-delete-button="isJiggleMode"
                :is-jiggling="isJiggleMode"
                @drag-start="handleResultDragStart(index, 'dnf')"
                @drag-end="handleResultDragEnd"
                @refresh="handleRefresh(horse)"
                @delete-click="deleteTarget = { raceHorseId: horse.race_horse_id, name: horse.snapshot_data.name ?? '未知' }; showDeleteConfirm = true"
              />
            </div>
          </div>

        </div>
      </div>

      <p v-if="voteError" class="vote-error">{{ voteError }}</p>

      <VotingDetail
        v-if="resultMode !== 'ranking'"
        :votes="votes"
        :loading="votesLoading"
        :horse-positions="horsePositions"
      />
    </template>

    <!-- Add Horse Modal -->
    <div v-if="showAddHorseModal" class="modal-backdrop ui-anim-overlay">
      <div class="modal-content add-horse-modal ui-anim-dialog" role="dialog" aria-modal="true" aria-label="添加马匹">
        <h3 class="modal-title">添加马匹</h3>
        <p class="modal-hint">搜索马名后点选，可连续添加多匹，最后一次性提交。</p>
        <HorseSearchSelect v-model:selected-horses="selectedAddHorse" />
        <p v-if="addHorseError" class="modal-error">{{ addHorseError }}</p>
        <div class="modal-actions">
          <button class="ui-btn ui-btn--ghost modal-btn" @click="closeAddHorseModal">
            取消
          </button>
          <button class="ui-btn ui-btn--primary modal-btn" :disabled="addHorseSaving || selectedAddHorse.length === 0" @click="confirmAddHorse">
            <span v-if="addHorseSaving" class="ui-spinner"></span>
            {{ addHorseSaving ? '添加中…' : selectedAddHorse.length > 0 ? `添加 ${selectedAddHorse.length} 匹` : '添加' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Horse Confirm Modal -->
    <ConfirmDeleteModal
      v-if="showDeleteConfirm && deleteTarget"
      title="从比赛中移除"
      :item-name="deleteTarget.name"
      message="确定将「{name}」从本场比赛中移除？此操作不可撤销。"
      :loading="deleting"
      @confirm="confirmDeleteHorse"
      @cancel="showDeleteConfirm = false"
    />

    <!-- Lock Race Confirm Modal -->
    <ConfirmDeleteModal
      v-if="showLockConfirm && race"
      title="锁定比赛"
      :item-name="race.name"
      message="确定锁定比赛「{name}」？锁定后不可再修改闸位与马匹信息。"
      :loading="locking"
      confirm-text="确认锁定"
      loading-text="锁定中…"
      @confirm="handleLock"
      @cancel="showLockConfirm = false"
    />

    <!-- Delete Race Confirm Modal -->
    <ConfirmDeleteModal
      v-if="showDeleteRaceModal && race"
      title="删除比赛"
      :item-name="race.name"
      message="确定删除比赛「{name}」？此操作不可撤销，所有相关数据将被清除。"
      :loading="deletingRace"
      @confirm="handleDeleteRace"
      @cancel="showDeleteRaceModal = false"
    />
  </div>
</template>

<style scoped>
.race-detail-page {
  padding: var(--spacing-5) var(--spacing-4);
  max-width: 960px;
  margin: 0 auto;
}

/* =========================================
   Loading skeleton
   ========================================= */

.detail-skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.skeleton-hero {
  height: 190px;
  margin-bottom: var(--spacing-3);
  border-radius: var(--rounded-xl);
}

.skeleton-horse {
  height: 84px;
  border-radius: var(--rounded-lg);
}

/* =========================================
   Hero banner
   ========================================= */

.race-hero {
  position: relative;
  overflow: hidden;
  isolation: isolate;
  margin-bottom: var(--spacing-5);
  padding: var(--spacing-4) var(--spacing-6) var(--spacing-6);
  border-radius: var(--rounded-xl);
  color: #FFFFFF;
  background: var(--gradient-brand);
  box-shadow: var(--shadow-lg);
  animation: rise-in var(--duration-slow) var(--ease-out) backwards;
}

.race-hero.is-locked {
  background: linear-gradient(135deg, #26322C 0%, #3F4D45 55%, #56665D 100%);
}

.race-hero.is-settled {
  background: linear-gradient(135deg, #06221A 0%, #0D3A1F 50%, #1A5632 100%);
}

/* Gold finish line along the bottom edge */
.race-hero::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 3px;
  background: var(--gradient-gold);
  opacity: 0.9;
}

/* Racetrack rails in the background */
.hero-track {
  position: absolute;
  inset: 0;
  z-index: -1;
  width: 100%;
  height: 100%;
}

.hero-track path {
  fill: none;
  stroke: rgba(255, 255, 255, 0.06);
  stroke-width: 14;
}

.race-header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
}

.hero-top-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 36px;
  padding: 0 14px 0 8px;
  border-radius: var(--rounded-full);
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: #FFFFFF;
  background: rgba(255, 255, 255, 0.12);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
  cursor: pointer;
  transition: background var(--duration-fast) ease, transform var(--duration-fast) var(--ease-out);
}

.back-btn svg {
  width: 18px;
  height: 18px;
  transition: transform var(--duration-base) var(--ease-out);
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.back-btn:hover svg {
  transform: translateX(-3px);
}

.back-btn:active {
  transform: scale(0.96);
}

.hero-tags {
  margin-bottom: var(--spacing-3);
}

.race-title-row {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-3);
}

/* Keep the ✎ button right after the title instead of at the banner edge */
.race-title-row .race-header-editor {
  flex: 0 1 auto;
  max-width: 100%;
}

.race-name,
.race-title-row :deep(.race-name) {
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 700;
  line-height: 1.1;
  color: #FFFFFF;
  margin: 0;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.25);
}

.race-subinfo {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-2) var(--spacing-5);
  color: rgba(255, 255, 255, 0.85);
}

.date-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.subinfo-icon {
  width: 16px;
  height: 16px;
  opacity: 0.8;
}

.race-date {
  font-family: var(--font-display);
  font-size: var(--text-subheading);
  font-weight: 600;
  letter-spacing: 0.02em;
  margin: 0;
}

.date-editable {
  cursor: pointer;
  padding: 2px 8px;
  margin: 0 -8px;
  border-radius: var(--rounded-sm);
  transition: background var(--duration-fast) ease;
}

.date-editable:hover {
  background: rgba(255, 255, 255, 0.14);
}

.hero-edit-btn {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  color: rgba(255, 255, 255, 0.75);
  transition: background var(--duration-fast) ease, color var(--duration-fast) ease, transform var(--duration-fast) var(--ease-spring);
}

.hero-edit-btn svg {
  width: 14px;
  height: 14px;
}

.hero-edit-btn:hover {
  color: #FFFFFF;
  background: rgba(255, 255, 255, 0.16);
  transform: rotate(-12deg) scale(1.1);
}

.date-input {
  padding: 4px 8px;
  border: 1px solid transparent;
  border-radius: var(--rounded-sm);
  font-size: var(--text-body);
  color: var(--color-ink-primary);
  background: var(--color-surface-raised);
}

.date-input:focus {
  outline: 2px solid var(--color-accent-light);
  outline-offset: 2px;
}

.race-meta {
  display: flex;
  gap: var(--spacing-4);
  font-size: var(--text-body-sm);
  margin: 0;
}

.meta-stat strong {
  margin-right: 2px;
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--color-accent-light);
}

.header-message {
  display: inline-block;
  font-size: var(--text-body-sm);
  margin: var(--spacing-3) 0 0;
  padding: 6px 12px;
  border-radius: var(--rounded-full);
}

.header-message.error {
  color: var(--color-destructive);
  background: rgba(255, 245, 245, 0.95);
}

.header-message.success {
  color: var(--color-primary);
  background: rgba(237, 245, 239, 0.95);
}

/* =========================================
   Admin toolbar
   ========================================= */

.admin-actions-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-5);
  padding: var(--spacing-3);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  animation: rise-in var(--duration-slow) var(--ease-out) 60ms backwards;
}

.admin-actions-bar::before {
  content: '管理';
  padding: 2px 10px;
  border-radius: var(--rounded-full);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--color-accent-dark);
  background: var(--color-accent-tint);
}

.btn-icon {
  width: 16px;
  height: 16px;
}

.delete-btn {
  margin-left: auto;
}

.confirm-result-btn {
  white-space: normal;
  text-align: center;
}

.confirm-result-btn:disabled {
  background: var(--color-ink-disabled);
  box-shadow: none;
}

.admin-error,
.admin-success {
  flex-basis: 100%;
  font-size: var(--text-body-sm);
  margin: 0;
}

.admin-error {
  color: var(--color-destructive);
}

.admin-success {
  color: var(--color-primary);
}

/* Jiggle mode toggle button (mobile only) */
.jiggle-toggle-btn {
  display: none;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--rounded-md);
  background: var(--color-surface-raised);
  color: var(--color-ink-primary);
  font-size: var(--text-body);
  font-weight: 600;
  cursor: pointer;
  min-height: 44px;
  transition:
    background var(--duration-fast) ease,
    border-color var(--duration-fast) ease,
    color var(--duration-fast) ease,
    transform var(--duration-fast) var(--ease-out);
}

.jiggle-toggle-btn:hover {
  background: var(--color-surface-base);
  border-color: var(--color-primary);
}

.jiggle-toggle-btn:active {
  transform: scale(0.97);
}

.jiggle-toggle-btn.active {
  background: var(--color-primary);
  color: #FFFFFF;
  border-color: var(--color-primary);
}

.jiggle-toggle-btn.active:hover {
  background: var(--color-primary-light);
}

@media (max-width: 767px) {
  .jiggle-toggle-btn {
    display: inline-flex;
  }
}

/* =========================================
   Scoring rules + vote hints
   ========================================= */

.custom-scoring-info {
  padding: var(--spacing-4);
  margin-bottom: var(--spacing-5);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
}

.scoring-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  font-size: var(--text-body-sm);
  color: var(--color-ink-primary);
  margin: 0 0 var(--spacing-3);
}

.scoring-title svg {
  width: 16px;
  height: 16px;
  color: var(--color-accent);
}

.scoring-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.score-chip {
  padding: 2px 10px;
  border-radius: var(--rounded-full);
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
}

.score-chip strong {
  font-family: var(--font-display);
  font-size: 14px;
}

.score-chip.plus {
  background: var(--color-primary-tint);
}

.score-chip.plus strong {
  color: var(--color-primary);
}

.score-chip.minus {
  background: var(--color-destructive-tint);
}

.score-chip.minus strong {
  color: var(--color-destructive);
}

.vote-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
  margin-bottom: var(--spacing-4);
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  text-align: center;
}

.hint-icon {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  color: var(--color-primary);
}

.vote-hint.voted {
  border-color: var(--color-accent);
  background: linear-gradient(100deg, var(--color-accent-tint), #FFFFFF);
  color: var(--color-ink-primary);
  box-shadow: var(--shadow-glow-gold);
}

.vote-hint.voted .hint-icon {
  padding: 3px;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  color: #FFFFFF;
  background: var(--gradient-gold);
  animation: pop-in var(--duration-slow) var(--ease-spring);
}

.vote-hint.voted strong {
  color: var(--color-accent-dark);
}

.hint-swap-enter-active,
.hint-swap-leave-active {
  transition: opacity var(--duration-base) ease, transform var(--duration-base) var(--ease-out);
}

.hint-swap-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.hint-swap-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* =========================================
   Horse list
   ========================================= */

.section-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--text-subheading);
  font-weight: 700;
  color: var(--color-ink-primary);
  margin: 0;
}

.count-chip {
  min-width: 24px;
  padding: 0 8px;
  border-radius: var(--rounded-full);
  font-family: var(--font-display);
  font-size: 14px;
  line-height: 22px;
  text-align: center;
  color: var(--color-primary);
  background: var(--color-primary-tint);
}

.horse-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  margin-top: var(--spacing-2);
}

.horse-list-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  min-height: 80px;
}

.gate-drag-item {
  width: 100%;
  transition: transform var(--duration-fast) ease;
}

.gate-drag-item.drag-over-top,
.result-drag-item.drag-over-top {
  position: relative;
}

.gate-drag-item.drag-over-top::before,
.result-drag-item.drag-over-top::before {
  content: '';
  position: absolute;
  top: -8px;
  left: 0;
  right: 0;
  height: 4px;
  background: var(--gradient-gold);
  border-radius: 2px;
  box-shadow: 0 0 10px rgba(184, 150, 12, 0.6);
  z-index: 1;
}

/* Add / Delete row */
.add-delete-row {
  display: flex;
  gap: var(--spacing-3);
}

.add-delete-row > .add-horse-card {
  flex: 1;
  min-width: 0;
}

.delete-zone {
  flex-shrink: 0;
  width: 110px;
  min-height: 96px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  background: var(--color-surface-raised);
  border: 2px dashed var(--color-border-strong);
  border-radius: var(--rounded-lg);
  padding: var(--spacing-2);
  transition:
    border-color var(--duration-fast) ease,
    background-color var(--duration-fast) ease,
    transform var(--duration-base) var(--ease-spring);
  cursor: default;
  user-select: none;
}

.delete-zone.delete-hover {
  border-color: var(--color-destructive);
  background: var(--color-destructive-tint);
  transform: scale(1.04);
}

.delete-icon {
  width: 24px;
  height: 24px;
  color: var(--color-ink-secondary);
}

.delete-zone.delete-hover .delete-icon {
  color: var(--color-destructive);
  animation: shake-x 0.45s var(--ease-out);
}

.delete-label {
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
  font-weight: 600;
  text-align: center;
  line-height: 1.3;
}

.delete-zone.delete-hover .delete-label {
  color: var(--color-destructive);
}

@media (max-width: 767px) {
  .delete-zone {
    display: none;
  }
}

.vote-error {
  color: var(--color-destructive);
  font-size: var(--text-body-sm);
  margin: var(--spacing-2) 0;
  text-align: center;
}

/* =========================================
   Result ranking mode
   ========================================= */

.result-ranking-area {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.instructions {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--text-body-sm);
  color: var(--color-ink-primary);
  padding: 10px 14px;
  background: var(--color-primary-tint);
  border: 1px solid var(--color-primary-tint-strong);
  border-radius: var(--rounded-lg);
}

.text-muted {
  color: var(--color-ink-muted);
}

.drop-zone {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  min-height: 80px;
}

.result-drag-item {
  display: flex;
  align-items: stretch;
  gap: 8px;
}

.dnf-zone {
  margin-top: var(--spacing-4);
  border: 2px dashed var(--color-border-strong);
  border-radius: var(--rounded-lg);
  padding: var(--spacing-3);
  min-height: 80px;
  background: var(--color-surface-sunken);
  transition: border-color var(--duration-fast) ease, background var(--duration-fast) ease;
}

.dnf-zone:hover {
  border-color: var(--color-destructive);
}

.dnf-zone-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-2);
}

.dnf-label {
  font-size: var(--text-body-sm);
  font-weight: 700;
  color: var(--color-destructive);
}

.dnf-tip {
  margin-left: auto;
  margin-right: var(--spacing-2);
  font-size: var(--text-caption);
  color: var(--color-ink-secondary);
}

.dnf-count {
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-destructive);
  background: var(--color-destructive-light);
  padding: 2px 8px;
  border-radius: var(--rounded-full);
  animation: pop-in var(--duration-base) var(--ease-spring);
}

.dnf-empty-hint {
  font-size: var(--text-body-sm);
  color: var(--color-ink-disabled);
  text-align: center;
  padding: 20px 0;
}

.dnf-item {
  cursor: pointer;
  margin-bottom: var(--spacing-3);
  animation: rise-in var(--duration-base) var(--ease-out);
}

.dnf-item:last-child {
  margin-bottom: 0;
}

/* =========================================
   Add-horse modal
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
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-title {
  font-family: var(--font-display);
  font-size: var(--text-heading);
  font-weight: 700;
  margin: 0 0 var(--spacing-4);
  color: var(--color-ink-primary);
}

.modal-error {
  color: var(--color-destructive);
  font-size: var(--text-body-sm);
  margin: var(--spacing-2) 0 0;
}

.modal-actions {
  display: flex;
  gap: var(--spacing-3);
  margin-top: var(--spacing-5);
}

.modal-hint {
  margin: calc(-1 * var(--spacing-2)) 0 var(--spacing-4);
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
}

/* The search dropdown is absolutely positioned; let it hang over the
   backdrop instead of being clipped by the dialog's scroll box. */
.add-horse-modal {
  overflow: visible;
  max-height: none;
}

.modal-btn {
  flex: 1;
}

/* =========================================
   Responsive
   ========================================= */

@media (max-width: 767px) {
  .race-detail-page {
    padding-top: var(--spacing-3);
  }

  .race-hero {
    padding: var(--spacing-3) var(--spacing-4) var(--spacing-5);
    border-radius: var(--rounded-lg);
  }

  .race-name,
  .race-title-row :deep(.race-name) {
    font-size: 26px;
    word-break: break-word;
  }

  .race-subinfo {
    gap: var(--spacing-2) var(--spacing-4);
  }

  .admin-actions-bar::before {
    display: none;
  }

  .delete-btn {
    margin-left: 0;
  }

  .ranking-actions-bar {
    flex-wrap: nowrap;
    width: 100%;
  }

  .ranking-actions-bar .confirm-result-btn {
    flex: 1;
  }

  .gate-drag-item,
  .result-drag-item {
    touch-action: manipulation;
  }

  .gate-drag-item.touch-dragging,
  .result-drag-item.touch-dragging {
    touch-action: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .gate-drag-item,
  .result-drag-item {
    transition: none;
  }
}

/* Auto-scroll hints */
.scroll-hint {
  position: fixed;
  left: 0;
  right: 0;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 50;
  opacity: 0;
  transition: opacity 0.2s ease;
  color: var(--color-primary);
}

.scroll-hint.active {
  opacity: 1;
}

.scroll-hint-up {
  top: var(--header-height, 0px);
  background: linear-gradient(to bottom, rgba(26, 86, 50, 0.12), transparent);
}

.scroll-hint-down {
  bottom: calc(var(--bottom-nav-height, 0px) + env(safe-area-inset-bottom, 0px));
  background: linear-gradient(to top, rgba(26, 86, 50, 0.12), transparent);
}

@media (min-width: 768px) {
  .scroll-hint-down {
    bottom: 0;
  }
}

@media (max-width: 767px) {
  .scroll-hint-up {
    top: 0;
  }
}

.scroll-hint svg {
  animation: scroll-bounce 0.6s ease-in-out alternate infinite;
}

@keyframes scroll-bounce {
  from { transform: translateY(-4px); }
  to   { transform: translateY(4px); }
}

@media (prefers-reduced-motion: reduce) {
  .scroll-hint svg {
    animation: none;
  }
}
</style>
