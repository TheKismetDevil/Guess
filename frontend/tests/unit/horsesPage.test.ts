import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import HorsesPage from '@/pages/admin/HorsesPage.vue'
import * as api from '@/api/horses'

vi.mock('@/api/horses', () => ({
  getHorses: vi.fn(),
  getOriginsStats: vi.fn(),
  getLocationsStats: vi.fn(),
  createHorse: vi.fn(),
  updateHorse: vi.fn(),
  deleteHorse: vi.fn(),
  toggleHemisphere: vi.fn(),
}))

const sampleHorses = () => [
  {
    id: 1,
    name: 'Equinox',
    sex: '牡',
    birth_year: 2019,
    origin: '日本',
    hemisphere: 'north',
    location: '美浦',
    sire: 'Kitasan Black',
    damsire: 'King Halo',
    previous_result: null,
    previous_result_date: null,
    previous_result_position: null,
    best_win: null,
    best_win_date: null,
  },
  {
    id: 2,
    name: 'Liberty Island',
    sex: '牝',
    birth_year: 2020,
    origin: '日本',
    hemisphere: 'north',
    location: '栗东',
    sire: 'Duramente',
    damsire: 'All American',
    previous_result: null,
    previous_result_date: null,
    previous_result_position: null,
    best_win: null,
    best_win_date: null,
  },
]

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.getHorses).mockResolvedValue(sampleHorses())
  vi.mocked(api.getOriginsStats).mockResolvedValue([
    { origin: '日本', count: 2, hemisphere: 'north' },
  ])
  vi.mocked(api.getLocationsStats).mockResolvedValue([
    { location: '栗东', count: 1 },
    { location: '美浦', count: 1 },
  ])
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('HorsesPage origin and hemisphere consistency', () => {
  it('blocks conflicting hemisphere when re-entering an existing country in add-country mode', async () => {
    const wrapper = mount(HorsesPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.get('button.create-btn').trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]')!
    const selects = dialog.querySelectorAll('select')
    const originSelect = selects[1] as HTMLSelectElement
    originSelect.value = '__new__'
    originSelect.dispatchEvent(new Event('change'))
    await flushPromises()

    const countryInput = dialog.querySelector('input[placeholder="输入新增国家名称"]') as HTMLInputElement
    countryInput.value = '日本'
    countryInput.dispatchEvent(new Event('input'))

    const southRadio = dialog.querySelector('input[type="radio"][value="south"]') as HTMLInputElement
    southRadio.click()
    await flushPromises()

    const confirmBtn = Array.from(dialog.querySelectorAll('button')).find((b) => b.textContent?.trim() === '确认')!
    confirmBtn.click()
    await flushPromises()

    expect(dialog.textContent).toContain('出生国「日本」已存在且绑定为北半球')
    // Stays in add-new-country mode instead of corrupting the existing mapping
    expect(dialog.querySelector('input[placeholder="输入新增国家名称"]')).not.toBeNull()

    // Selecting matching hemisphere reuses existing country cleanly
    const northRadio = dialog.querySelector('input[type="radio"][value="north"]') as HTMLInputElement
    northRadio.click()
    await flushPromises()
    confirmBtn.click()
    await flushPromises()

    expect(dialog.querySelector('input[placeholder="输入新增国家名称"]')).toBeNull()
    expect(dialog.querySelector('.hemisphere-badge')?.textContent).toBe('北半球')
    wrapper.unmount()
  })

  it('updates all horses of that origin in the table immediately when toggling hemisphere', async () => {
    vi.mocked(api.toggleHemisphere).mockResolvedValue({
      origin: '日本',
      new_hemisphere: 'south',
      affected_count: 2,
    })

    const wrapper = mount(HorsesPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.findAll('.row-btn')[0]!.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]')!
    const toggleBtn = dialog.querySelector('.btn-hemisphere-toggle') as HTMLButtonElement
    toggleBtn.click()
    await flushPromises()

    expect(api.toggleHemisphere).toHaveBeenCalledWith('日本')
    expect(dialog.querySelector('.hemisphere-badge')?.textContent).toBe('南半球')

    // Even if modal is cancelled, both 日本 rows in the table reflect （南）
    const cancelBtn = Array.from(dialog.querySelectorAll('button')).find((b) => b.textContent?.trim() === '取消')!
    cancelBtn.click()
    await flushPromises()

    const rows = wrapper.findAll('tbody tr')
    expect(rows[0]!.text()).toContain('日本（南）')
    expect(rows[1]!.text()).toContain('日本（南）')
    wrapper.unmount()
  })

  it('includes hemisphere in update payload when changing origin to a new country with the same hemisphere', async () => {
    vi.mocked(api.updateHorse).mockImplementation(async (id, payload) => ({
      ...sampleHorses()[0]!,
      id,
      origin: payload.origin ?? null,
      hemisphere: payload.hemisphere ?? null,
    }))

    const wrapper = mount(HorsesPage, { attachTo: document.body })
    await flushPromises()

    await wrapper.findAll('.row-btn')[0]!.trigger('click')
    await flushPromises()

    const dialog = document.body.querySelector('[role="dialog"]')!
    const originSelect = dialog.querySelectorAll('select')[1] as HTMLSelectElement
    originSelect.value = '__new__'
    originSelect.dispatchEvent(new Event('change'))
    await flushPromises()

    const countryInput = dialog.querySelector('input[placeholder="输入新增国家名称"]') as HTMLInputElement
    countryInput.value = '法国'
    countryInput.dispatchEvent(new Event('input'))
    await flushPromises()

    const confirmBtn = Array.from(dialog.querySelectorAll('button')).find((b) => b.textContent?.trim() === '确认')!
    confirmBtn.click()
    await flushPromises()

    const form = dialog.querySelector('form.horse-form')!
    form.dispatchEvent(new Event('submit', { cancelable: true }))
    await flushPromises()

    expect(api.updateHorse).toHaveBeenCalledWith(1, {
      origin: '法国',
      hemisphere: 'north',
    })
    wrapper.unmount()
  })
})
