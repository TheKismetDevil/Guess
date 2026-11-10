import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import Page from '@/pages/LeaderboardPage.vue'
import * as api from '@/api/leaderboard'

vi.mock('@/api/leaderboard', () => ({ getLeaderboard: vi.fn(), getLeaderboardRaces: vi.fn(), getComparisonParticipants: vi.fn(), getHeadToHead: vi.fn() }))
const row = { username: '选手', total_points: 20, races_participated: 3, avg_points: 6.667 }
beforeEach(() => {
  vi.mocked(api.getLeaderboard).mockResolvedValue([row])
  vi.mocked(api.getLeaderboardRaces).mockResolvedValue(Array.from({ length: 5 }, (_, id) => ({ id, name: `比赛${id}`, date: '2026-01-01', source: 'live' as const })))
})
async function mountPage() {
  const wrapper = mount(Page, { attachTo: document.body, global: { plugins: [createPinia()], stubs: {
    RouterLink: { template: '<a><slot /></a>' }, HeadToHeadComparison: true,
  } } })
  await flushPromises()
  return wrapper
}
async function selectAverage(wrapper: Awaited<ReturnType<typeof mountPage>>) {
  await wrapper.get('[role="combobox"]').trigger('click')
  await wrapper.findAll('[role="option"]')[1]!.trigger('click')
  await flushPromises()
}

describe('ranking page interactions', () => {
  it('changes sorting through the real dropdown and displays the 60% eligibility note', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.average-rule').exists()).toBe(false)
    await selectAverage(wrapper)
    expect(api.getLeaderboard).toHaveBeenLastCalledWith(expect.any(Object), 'avg_points')
    expect(wrapper.get('.average-rule').text()).toContain('当前共 5 场')
    expect(wrapper.get('.average-rule').text()).toContain('至少需参与 3 场')
    expect(wrapper.get('[aria-sort="descending"]').text()).toBe('场均')
    expect(wrapper.get('.col-avg').element.tagName).toBe('TH')
    expect(wrapper.get('tbody .col-avg').text()).toBe('6.667')
  })

  it('shows a specific eligibility empty state when all users are excluded', async () => {
    const wrapper = await mountPage()
    vi.mocked(api.getLeaderboard).mockResolvedValueOnce([])
    await selectAverage(wrapper)
    expect(wrapper.text()).toContain('暂无选手达到当前筛选下的 60%')
    expect(wrapper.find('tbody').exists()).toBe(false)
  })

  it('applies race date filters and recalculates the displayed threshold', async () => {
    const wrapper = await mountPage()
    await selectAverage(wrapper)
    await wrapper.get('.filter-toggle:not([aria-controls])').trigger('click')
    const startInput = wrapper.get('input[aria-label="开始日期"]')
    const endInput = wrapper.get('input[aria-label="结束日期"]')
    expect(startInput.classes()).toContain('is-empty')
    expect(endInput.classes()).toContain('is-empty')
    await startInput.setValue('2026-01-01')
    await endInput.setValue('2026-01-02')
    expect(startInput.classes()).not.toContain('is-empty')
    expect(endInput.classes()).not.toContain('is-empty')
    vi.mocked(api.getLeaderboardRaces).mockResolvedValueOnce([{ id: 1, name: '比赛', date: '2026-01-01', source: 'live' }])
    await wrapper.get('.apply-btn').trigger('click')
    await flushPromises()
    expect(api.getLeaderboard).toHaveBeenLastCalledWith(expect.objectContaining({ date_from: '2026-01-01', date_to: '2026-01-02' }), 'avg_points')
    expect(wrapper.get('.average-rule').text()).toContain('至少需参与 1 场')
    await wrapper.get('.clear-btn').trigger('click')
    await flushPromises()
    expect(startInput.classes()).toContain('is-empty')
    expect(endInput.classes()).toContain('is-empty')
  })

  it('shows only the five supported race grade filter options', async () => {
    const wrapper = await mountPage()
    await wrapper.get('.filter-toggle:not([aria-controls])').trigger('click')
    const gradeSection = wrapper.findAll('.filter-section').find(s => s.get('.filter-label').text() === '比赛等级')!
    const labels = gradeSection.findAll('.filter-tag').map(btn => btn.text())
    expect(labels).toEqual(['G1', 'G2', 'JPN1', '其他', '自定义'])
  })

  it('ignores an older total-score response that arrives after the new average ranking', async () => {
    let finishOld!: (value: typeof row[]) => void
    vi.mocked(api.getLeaderboard).mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    const wrapper = mount(Page, { global: { plugins: [createPinia()], stubs: { RouterLink: true } } })
    await selectAverage(wrapper)
    finishOld([{ ...row, username: '过期结果' }])
    await flushPromises()
    expect(wrapper.text()).toContain('选手')
    expect(wrapper.text()).not.toContain('过期结果')
    expect(wrapper.get('[aria-sort="descending"]').text()).toBe('场均')
  })
})
