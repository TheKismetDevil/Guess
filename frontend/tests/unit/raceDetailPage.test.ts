import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RaceDetailPage from '@/pages/RaceDetailPage.vue'
import { useAuthStore } from '@/stores/authStore'
import * as racesApi from '@/api/races'
import * as votesApi from '@/api/votes'
import type { RaceDetail, RaceStatus } from '@/types/race'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' } }),
  useRouter: () => ({ push: vi.fn(), go: vi.fn() }),
}))

vi.mock('@/api/races', () => ({
  getRace: vi.fn(),
  updateRace: vi.fn(),
  addRaceHorse: vi.fn(),
  updateRaceHorse: vi.fn(),
  updateGateOrder: vi.fn(),
  lockRace: vi.fn(),
  removeRaceHorse: vi.fn(),
  toggleRaceHidden: vi.fn(),
  deleteRace: vi.fn(),
}))

vi.mock('@/api/votes', () => ({
  submitVote: vi.fn(),
  getRaceVotes: vi.fn(),
  deleteVote: vi.fn(),
}))

vi.mock('@/api/results', () => ({
  submitResults: vi.fn(),
}))

vi.mock('@/api/horses', () => ({
  updateBestWin: vi.fn(),
  refreshRaceHorseSnapshot: vi.fn(),
}))

function makeRace(status: RaceStatus): RaceDetail {
  return {
    id: 1,
    name: 'the everest',
    date: '2026-10-18',
    age_range: '3岁以上',
    sex_restriction: '无限制',
    race_grade: 'G1',
    country: '澳大利亚',
    distance: '1200m',
    surface: '草地',
    status,
    is_hidden: false,
    custom_scoring: null,
    vote_count: 0,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
    horses: [
      {
        horse_id: 101,
        race_horse_id: 201,
        gate: 1,
        position: status === 'settled' ? 1 : null,
        weight: null,
        jockey: null,
        snapshot_data: {
          name: '海都之星',
          sex: '牡',
          birth_year: 2006,
          origin: '爱尔兰',
          hemisphere: 'N',
          location: null,
          sire: null,
          damsire: null,
          previous_result: 'kgv',
          previous_result_date: '2026-08-07',
          previous_result_position: 4,
          best_win: '七月杯',
          best_win_date: '2026-07-11',
        },
      },
      {
        horse_id: 102,
        race_horse_id: 202,
        gate: 2,
        position: status === 'settled' ? 2 : null,
        weight: null,
        jockey: null,
        snapshot_data: {
          name: '嘉应高升',
          sex: '骟',
          birth_year: 2020,
          origin: '香港',
          hemisphere: 'S',
          location: null,
          sire: 'Shamexpress',
          damsire: 'Per Incanto',
          previous_result: 'japan cup',
          previous_result_date: '2026-08-01',
          previous_result_position: 4,
          best_win: '七月杯',
          best_win_date: '2026-07-11',
        },
      },
      {
        horse_id: 103,
        race_horse_id: 203,
        gate: 3,
        position: status === 'settled' ? null : null,
        weight: null,
        jockey: null,
        snapshot_data: {
          name: '浪漫勇士',
          sex: '骟',
          birth_year: 2018,
          origin: '香港',
          hemisphere: 'N',
          location: null,
          sire: null,
          damsire: null,
          previous_result: 'kgv',
          previous_result_date: '2026-08-07',
          previous_result_position: 3,
          best_win: null,
          best_win_date: null,
        },
      },
    ],
  }
}

async function mountAdminRacePage(status: RaceStatus, isHidden = false) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const authStore = useAuthStore()
  authStore.setUser({
    id: 1,
    username: 'admin',
    qq: '10001',
    is_admin: true,
  })

  vi.mocked(racesApi.getRace).mockResolvedValue({ ...makeRace(status), is_hidden: isHidden })
  vi.mocked(votesApi.getRaceVotes).mockResolvedValue([])

  const wrapper = mount(RaceDetailPage, {
    attachTo: document.body,
    global: {
      plugins: [pinia],
      stubs: {
        VotingDetail: true,
        HorseSearchSelect: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('RaceDetailPage horse card layout and delete button visibility', () => {
  it('shows desktop inline delete buttons before jiggle mode and mobile corner delete buttons in voting jiggle mode', async () => {
    const wrapper = await mountAdminRacePage('voting')

    expect(wrapper.findAll('.gate-drag-item .horse-detail-card')).toHaveLength(3)
    expect(wrapper.findAll('.icon-btn-danger.desktop-only')).toHaveLength(3)
    expect(wrapper.find('.delete-zone').exists()).toBe(true)
    expect(wrapper.find('.delete-card-btn').exists()).toBe(false)

    await wrapper.get('.jiggle-toggle-btn').trigger('click')

    const cornerButtons = wrapper.findAll('.delete-card-btn.mobile-only')
    expect(cornerButtons).toHaveLength(3)
    expect(wrapper.findAll('.icon-btn-danger.desktop-only')).toHaveLength(3)

    wrapper.unmount()
  })

  it('does not render any horse delete buttons in locked post-race ranking mode', async () => {
    const wrapper = await mountAdminRacePage('locked')

    expect(wrapper.find('.jiggle-toggle-btn').exists()).toBe(false)
    expect(wrapper.find('.delete-card-btn').exists()).toBe(false)
    expect(wrapper.find('.icon-btn-danger').exists()).toBe(false)

    const finishBtn = wrapper.findAll('.admin-actions-bar button').find(btn => btn.text().includes('比赛结束'))!
    await finishBtn.trigger('click')

    expect(wrapper.findAll('.result-drag-item .horse-detail-card')).toHaveLength(3)
    expect(wrapper.find('.delete-card-btn').exists()).toBe(false)
    expect(wrapper.find('.icon-btn-danger').exists()).toBe(false)
    expect(wrapper.find('.delete-zone').exists()).toBe(false)
    expect(wrapper.find('.dnf-zone').exists()).toBe(true)

    wrapper.unmount()
  })

  it('does not render any horse delete buttons when modifying settled race results (including DNF cards)', async () => {
    const wrapper = await mountAdminRacePage('settled')

    const modifyBtn = wrapper.findAll('.admin-actions-bar button').find(btn => btn.text().includes('修改结果'))!
    await modifyBtn.trigger('click')

    expect(wrapper.findAll('.result-drag-item .horse-detail-card')).toHaveLength(2)
    expect(wrapper.findAll('.dnf-item .horse-detail-card')).toHaveLength(1)
    expect(wrapper.find('.delete-card-btn').exists()).toBe(false)
    expect(wrapper.find('.icon-btn-danger').exists()).toBe(false)
    expect(wrapper.find('.delete-zone').exists()).toBe(false)

    wrapper.unmount()
  })
})

describe('RaceDetailPage visibility after a cross-tab logout', () => {
  it.each([true, false])('rechecks cached race visibility (hidden: %s)', async (isHidden) => {
    const wrapper = await mountAdminRacePage('voting', isHidden)
    const authStore = useAuthStore()
    authStore.persistAuth({ accessToken: 'access', refreshToken: 'refresh', user: authStore.user! })
    expect(wrapper.find('.race-hero').exists()).toBe(true)

    localStorage.removeItem('auth')
    window.dispatchEvent(new StorageEvent('storage', { key: 'auth', newValue: null }))
    await wrapper.vm.$nextTick()

    expect(authStore.isAdmin).toBe(false)
    expect(wrapper.find('.race-hero').exists()).toBe(!isHidden)
    expect(wrapper.find('[role="alert"]').exists()).toBe(isHidden)
    if (isHidden) {
      expect(wrapper.get('[role="alert"]').text()).toContain('当前比赛已隐藏')
      expect(wrapper.text()).not.toContain('海都之星')
    }
    wrapper.unmount()
    authStore.$dispose()
  })
})
