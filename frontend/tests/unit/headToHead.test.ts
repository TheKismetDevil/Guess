import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Comparison from '@/components/HeadToHeadComparison.vue'
import * as api from '@/api/leaderboard'
import type { HeadToHeadResult } from '@/types/leaderboard'

vi.mock('@/api/leaderboard', () => ({ getComparisonParticipants: vi.fn(), getHeadToHead: vi.fn() }))
const people = [{ id: 'a', username: 'Alpha', kind: 'user' as const }, { id: 'b', username: 'Beta', kind: 'historical' as const }]
const result = (): HeadToHeadResult => ({ participants: people, races: [
  { key: 'live:1', id: 1, name: '共同赛1', date: '2026-01-01', source: 'live', scores: [0, -5] },
  { key: 'historical:2', id: null, name: '共同赛2', date: '2026-01-02', source: 'historical', scores: [10, 3] },
] })
beforeEach(() => {
  vi.mocked(api.getComparisonParticipants).mockResolvedValue(people)
  vi.mocked(api.getHeadToHead).mockResolvedValue(result())
})
async function selectUsers() {
  const wrapper = mount(Comparison, { props: { filters: {} }, attachTo: document.body,
    global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } } })
  await flushPromises()
  await wrapper.findAll('input[type="checkbox"]')[0]!.setValue(true)
  expect(api.getHeadToHead).not.toHaveBeenCalled()
  await wrapper.findAll('input[type="checkbox"]')[1]!.setValue(true)
  await flushPromises()
  return wrapper
}
describe('head to head table', () => {
  it('selects users, renders each common race, zero/negative scores and common totals', async () => {
    const wrapper = await selectUsers()
    expect(api.getHeadToHead).toHaveBeenCalledWith(['a', 'b'], {})
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.findAll('tbody tr')[0]!.findAll('td').map(cell => cell.text())).toEqual(['0', '-5'])
    expect(wrapper.findAll('tfoot td').map(cell => cell.text())).toEqual(['10', '-2'])
    expect(wrapper.get('tbody a').attributes('href')).toBe('/races/1')
    expect(wrapper.text()).toContain('共同参与 2 场')
  })

  it('applies new race filters and lets users remove a selection while searching', async () => {
    const wrapper = await selectUsers()
    await wrapper.setProps({ filters: { country: ['日本'] } })
    await flushPromises()
    expect(api.getHeadToHead).toHaveBeenLastCalledWith(['a', 'b'], { country: ['日本'] })
    await wrapper.get('input[type="search"]').setValue('Alpha')
    expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(1)
    await wrapper.get('button[aria-label="移除 Beta（历史）"]').trigger('click')
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.text()).toContain('至少两位用户')
  })

  it('distinguishes no common races from a failed request and supports retry', async () => {
    vi.mocked(api.getHeadToHead).mockResolvedValueOnce({ participants: people, races: [] })
    const wrapper = await selectUsers()
    expect(wrapper.text()).toContain('没有所有所选用户都参与')
    vi.mocked(api.getHeadToHead).mockRejectedValueOnce(new Error('offline'))
    await wrapper.setProps({ filters: { race_grade: ['G1'] } })
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('加载失败')
    await wrapper.findAll('button').find(button => button.text() === '重试对比')!.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('tbody tr')).toHaveLength(2)
  })
})
