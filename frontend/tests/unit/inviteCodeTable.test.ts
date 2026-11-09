import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import InviteCodeTable from '@/components/InviteCodeTable.vue'
import * as api from '@/api/admin'

vi.mock('@/api/admin', () => ({ getInviteCodes: vi.fn(), createInviteCode: vi.fn(), deleteInviteCode: vi.fn() }))

const placeholder = { code: 'PLACE001', status: 'unused' as const, bound_username: null, bound_qq: '12345', placeholder_username: '旧名', created_at: null }
const used = { code: 'USED0001', status: 'used' as const, bound_username: 'bob', bound_qq: '22222', placeholder_username: null, created_at: null }

beforeEach(() => {
  vi.mocked(api.getInviteCodes).mockResolvedValue([placeholder, used])
})

async function mountTable() {
  const wrapper = mount(InviteCodeTable, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

describe('invite code table', () => {
  it('shows placeholder users but offers no delete action for them', async () => {
    const wrapper = await mountTable()
    const [placeholderRow, usedRow] = wrapper.findAll('tbody tr')
    expect(placeholderRow!.text()).toContain('占位·待注册')
    expect(placeholderRow!.text()).toContain('旧名（占位）')
    expect(placeholderRow!.text()).toContain('不可删除')
    expect(placeholderRow!.find('.row-btn-danger').exists()).toBe(false)
    expect(placeholderRow!.get('.protected-note').classes()).toContain('row-action-end')
    expect(usedRow!.get('.row-btn-danger').classes()).toContain('row-action-end')
    expect(wrapper.get('.summary').text()).toContain('1 个历史成绩占位用户')
  })

  it('requires an all-digit QQ and surfaces the one-account-per-QQ error from the API', async () => {
    const wrapper = await mountTable()
    await wrapper.get('.qq-input').setValue('12345a')
    await wrapper.get('form.generate-group').trigger('submit')
    expect(api.createInviteCode).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('QQ 号必须是 5-20 位数字')

    vi.mocked(api.createInviteCode).mockRejectedValueOnce({ response: { data: { detail: { code: 'QQ_ALREADY_REGISTERED', message: '该 QQ 已注册用户「bob」' } } } })
    await wrapper.get('.qq-input').setValue('22222')
    await wrapper.get('form.generate-group').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('该 QQ 已注册用户「bob」')
  })
})
