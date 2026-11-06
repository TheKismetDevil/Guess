import { computed, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'
import axios from 'axios'
import { getComparisonParticipants, getHeadToHead } from '@/api/leaderboard'
import type { ComparisonParticipant, HeadToHeadResult, LeaderboardFilters } from '@/types/leaderboard'

type PageState = 'idle' | 'loading' | 'empty' | 'error' | 'success'

export function useHeadToHead(filters: Ref<LeaderboardFilters>) {
  const people = ref<ComparisonParticipant[]>([])
  const peopleState = ref<PageState>('loading')
  const state = ref<PageState>('idle')
  const selected = ref<string[]>([])
  const search = ref('')
  const result = ref<HeadToHeadResult | null>(null)
  const error = ref('')
  let requestNumber = 0
  let disposed = false

  const visiblePeople = computed(() => people.value.filter(p => p.username.toLocaleLowerCase().includes(search.value.trim().toLocaleLowerCase())))
  const selectedPeople = computed(() => selected.value.map(id => people.value.find(p => p.id === id)).filter((p): p is ComparisonParticipant => !!p))
  const totals = computed(() => result.value?.participants.map((_, index) => result.value!.races.reduce((sum, race) => sum + race.scores[index]!, 0)) ?? [])

  function removePerson(id: string) {
    selected.value = selected.value.filter(value => value !== id)
  }
  async function loadPeople() {
    peopleState.value = 'loading'
    try {
      const data = await getComparisonParticipants()
      if (disposed) return
      people.value = data
      selected.value = selected.value.filter(id => data.some(p => p.id === id))
      peopleState.value = data.length ? 'success' : 'empty'
    } catch (err) {
      if (disposed) return
      console.error('Failed to load comparison participants:', err)
      peopleState.value = 'error'
    }
  }
  async function compare() {
    const request = ++requestNumber
    result.value = null
    error.value = ''
    if (selected.value.length < 2) { state.value = 'idle'; return }
    state.value = 'loading'
    try {
      const data = await getHeadToHead([...selected.value], filters.value)
      if (disposed || request !== requestNumber) return
      result.value = data
      state.value = data.races.length ? 'success' : 'empty'
    } catch (err) {
      if (disposed || request !== requestNumber) return
      error.value = axios.isAxiosError(err) ? err.response?.data?.detail?.message || '对比加载失败，请重试' : '对比加载失败，请重试'
      state.value = 'error'
    }
  }
  watch([selected, filters], compare, { deep: true })
  onMounted(loadPeople)
  onUnmounted(() => { disposed = true; ++requestNumber })
  return { people, peopleState, state, selected, search, result, error, visiblePeople, selectedPeople, totals, removePerson, loadPeople, compare }
}
