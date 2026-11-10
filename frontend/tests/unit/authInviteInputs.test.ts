import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import InviteCodeInput from '@/components/InviteCodeInput.vue'
import LoginPage from '@/pages/LoginPage.vue'
import RegisterPage from '@/pages/RegisterPage.vue'
import ResetPasswordPage from '@/pages/ResetPasswordPage.vue'
import * as authApi from '@/api/auth'

const push = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  useRoute: () => ({ query: {} }),
}))
vi.mock('@/api/auth', () => ({
  login: vi.fn(),
  register: vi.fn(),
  resetPassword: vi.fn(),
  refreshToken: vi.fn(),
}))

describe('InviteCodeInput segmented boxes across auth pages', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('renders 8 individual character boxes on LoginPage, RegisterPage and ResetPasswordPage', async () => {
    const loginWrapper = mount(LoginPage, { global: { stubs: { RouterLink: true } } })
    await loginWrapper.findAll('[role="tab"]')[2]!.trigger('click')
    await flushPromises()
    const loginBoxes = loginWrapper.findAll('.code-box')
    expect(loginBoxes).toHaveLength(8)
    expect(loginBoxes[0]!.attributes('id')).toBe('login-invite-code')

    const registerWrapper = mount(RegisterPage, { global: { stubs: { RouterLink: true } } })
    const registerBoxes = registerWrapper.findAll('.code-box')
    expect(registerBoxes).toHaveLength(8)
    expect(registerBoxes[0]!.attributes('id')).toBe('invite-code')

    const resetWrapper = mount(ResetPasswordPage, { global: { stubs: { RouterLink: true } } })
    const resetBoxes = resetWrapper.findAll('.code-box')
    expect(resetBoxes).toHaveLength(8)
    expect(resetBoxes[0]!.attributes('id')).toBe('reset-invite-code')
  })

  it('auto-advances focus on character entry, uppercases input, and supports Backspace & single-box overwrite', async () => {
    let code = ''
    const wrapper = mount(InviteCodeInput, {
      attachTo: document.body,
      props: {
        modelValue: code,
        'onUpdate:modelValue': (v: string) => { code = v },
      },
    })
    const boxes = wrapper.findAll<HTMLInputElement>('input.code-box')
    boxes[0]!.element.focus()

    await boxes[0]!.setValue('k')
    await flushPromises()
    expect(code).toBe('K')
    expect(document.activeElement).toBe(boxes[1]!.element)

    await boxes[1]!.setValue('7')
    await flushPromises()
    expect(code).toBe('K7')
    expect(document.activeElement).toBe(boxes[2]!.element)

    // Backspace on empty box[2] clears box[1] and moves focus back to box[1]
    await boxes[2]!.trigger('keydown', { key: 'Backspace' })
    await flushPromises()
    expect(code).toBe('K')
    expect(document.activeElement).toBe(boxes[1]!.element)

    // Overwriting an already-filled box[0] replaces only box[0] and moves to box[1]
    await boxes[0]!.setValue('Km')
    await flushPromises()
    expect(code).toBe('M')
    expect(document.activeElement).toBe(boxes[1]!.element)

    wrapper.unmount()
  })

  it('distributes pasted 8-character invite code into all boxes and submits uppercase value', async () => {
    vi.mocked(authApi.resetPassword).mockResolvedValueOnce({
      user: { id: 1, username: 'tester', qq: '123456', is_admin: false },
    })
    const wrapper = mount(ResetPasswordPage, { attachTo: document.body, global: { stubs: { RouterLink: true } } })
    const boxes = wrapper.findAll('input.code-box')

    // Paste into middle box with spaces/hyphens and lowercase letters
    await boxes[3]!.trigger('paste', {
      clipboardData: { getData: () => ' ab12-cd34 ' },
    })
    await flushPromises()

    expect(boxes.map(b => (b.element as HTMLInputElement).value)).toEqual([
      'A', 'B', '1', '2', 'C', 'D', '3', '4',
    ])

    await wrapper.get('#reset-new-password').setValue('newpass123')
    await wrapper.get('#reset-confirm-password').setValue('newpass123')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(authApi.resetPassword).toHaveBeenCalledWith({
      invite_code: 'AB12CD34',
      new_password: 'newpass123',
    })
    expect(push).toHaveBeenCalledWith('/login?reset=success')

    wrapper.unmount()
  })
})
