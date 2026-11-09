import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import Page from '@/pages/admin/HistoricalScoresPage.vue'
import * as api from '@/api/historical'
import type { ImportPreview } from '@/types/historical'

vi.mock('@/api/historical', () => ({
  previewHistory: vi.fn(), importHistory: vi.fn(), getHistoryBatches: vi.fn(),
  getBatchRaces: vi.fn(), getHistoryScores: vi.fn(), saveHistoryScore: vi.fn(), undoHistoryBatch: vi.fn(),
}))

const preview = (): ImportPreview => ({ participants: 1, imported_races: 0, imported_scores: 0,
  conflicting_races: 1, reimported_races: 0, skipped_races: [], preview_token: 'review-1',
  options: { skip_identical: true, skip_empty: true },
  races: [{ name: '测试赛', date: '2026-01-01', race_id: 1, action: 'conflict', reason: '', score_count: 1,
    differences: [{ kind: 'score', qq: '12345', before: { qq: '12345', points: 0 }, after: { qq: '12345', points: 8 } }] }],
})

beforeEach(() => {
  vi.mocked(api.getHistoryBatches).mockResolvedValue([])
  vi.mocked(api.previewHistory).mockResolvedValue(preview())
  vi.mocked(api.importHistory).mockResolvedValue({ imported_races: 0, imported_scores: 0, updated_races: 1, skipped_races: [] })
})
async function mountPage() {
  const wrapper = mount(Page, { attachTo: document.body, global: { stubs: { RouterLink: { template: '<a><slot /></a>' } } } })
  await flushPromises()
  return wrapper
}
async function upload(wrapper: Awaited<ReturnType<typeof mountPage>>) {
  const input = wrapper.get<HTMLInputElement>('input[type="file"]')
  const file = new File(['fixture'], '成绩.xlsx')
  Object.defineProperty(file, 'arrayBuffer', { value: () => Promise.resolve(new ArrayBuffer(4)) })
  Object.defineProperty(input.element, 'files', { configurable: true, value: [file] })
  await input.trigger('change')
  await flushPromises()
}

describe('historical import page user flow', () => {
  it('defaults both options to checked and blocks submission until every conflict is chosen', async () => {
    const wrapper = await mountPage()
    expect(wrapper.findAll<HTMLInputElement>('input[type="checkbox"]').every(box => box.element.checked)).toBe(true)
    await upload(wrapper)
    expect(api.previewHistory).toHaveBeenCalledWith(expect.any(ArrayBuffer), { skip_identical: true, skip_empty: true })
    expect(wrapper.text()).toContain('0 分')
    expect(wrapper.text()).toContain('8 分')
    const submit = wrapper.findAll('button').find(button => button.text().startsWith('确认处理'))!
    expect(submit.attributes('disabled')).toBeDefined()
    expect(api.importHistory).not.toHaveBeenCalled()
    await wrapper.get('input[value="replace"]').setValue(true)
    expect(submit.attributes('disabled')).toBeUndefined()
    await submit.trigger('click')
    await flushPromises()
    expect(api.importHistory).toHaveBeenCalledWith(expect.any(ArrayBuffer), '成绩.xlsx', 'review-1', { '1': 'replace' }, { skip_identical: true, skip_empty: true })
    expect(wrapper.text()).toContain('更新 1 场')
  })

  it('re-previews with changed options and clears the previous conflict choice', async () => {
    const wrapper = await mountPage()
    await upload(wrapper)
    await wrapper.get('input[value="replace"]').setValue(true)
    await wrapper.findAll('input[type="checkbox"]')[1]!.setValue(false)
    await flushPromises()
    expect(api.previewHistory).toHaveBeenLastCalledWith(expect.any(ArrayBuffer), { skip_identical: true, skip_empty: false })
    expect(wrapper.get<HTMLInputElement>('input[value="replace"]').element.checked).toBe(false)
    expect(wrapper.text()).toContain('还有 1 场差异未选择')
  })

  it('rejects oversized uploads before calling the API', async () => {
    const wrapper = await mountPage()
    const file = new File(['x'], '太大.xlsx')
    Object.defineProperty(file, 'size', { value: 10 * 1024 * 1024 + 1 })
    Object.defineProperty(wrapper.get<HTMLInputElement>('input[type="file"]').element, 'files', { value: [file] })
    await wrapper.get('input[type="file"]').trigger('change')
    expect(wrapper.get('[role="alert"]').text()).toContain('10 MB')
    expect(api.previewHistory).not.toHaveBeenCalled()
  })

  it('discards a stale preview on 409 and requires a new review', async () => {
    const wrapper = await mountPage()
    await upload(wrapper)
    await wrapper.get('input[value="replace"]').setValue(true)
    vi.mocked(api.importHistory).mockRejectedValueOnce({ isAxiosError: true, response: { status: 409, data: { detail: { message: '数据已变化，请重新预览' } } } })
    await wrapper.findAll('button').find(button => button.text().startsWith('确认处理'))!.trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toContain('重新预览')
    expect(wrapper.find('input[value="replace"]').exists()).toBe(false)
  })

  it('requires explicit confirmation before undoing a batch', async () => {
    vi.mocked(api.getHistoryBatches).mockResolvedValue([{ id: 1, filename: '旧成绩.xlsx', created_at: '2026-01-01T00:00:00Z', race_count: 2, score_count: 10, updated_races: 0 }])
    vi.mocked(api.undoHistoryBatch).mockResolvedValue({ removed_races: 2, removed_scores: 10 })
    const wrapper = await mountPage()
    await wrapper.findAll('button').find(button => button.text() === '撤销批次')!.trigger('click')
    expect(api.undoHistoryBatch).not.toHaveBeenCalled()
    expect(wrapper.get('.undo-confirm').text()).toContain('10 条成绩')
    await wrapper.findAll('button').find(button => button.text() === '确认撤销')!.trigger('click')
    await flushPromises()
    expect(api.undoHistoryBatch).toHaveBeenCalledWith(1)
  })
})
