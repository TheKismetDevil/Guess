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

    for (const [wrapper, firstBoxId] of [
      [loginWrapper, 'login-invite-code'],
      [registerWrapper, 'invite-code'],
      [resetWrapper, 'reset-invite-code'],
    ] as const) {
      const group = wrapper.get('[role="group"]')
      const labelId = group.attributes('aria-labelledby')
      expect(labelId).toBeTruthy()
      expect(wrapper.get(`label[for="${firstBoxId}"]`).attributes('id')).toBe(labelId)
      expect(group.get('input').attributes('aria-label')).toBe('邀请码第 1 位')
    }
    expect(resetWrapper.get('label[for="reset-invite-code"]').text()).toContain('注册时绑定的')
  })

  it('leaves composing key presses to the input method without editing slots or moving focus', async () => {
    const wrapper = mount(InviteCodeInput, {
      attachTo: document.body,
      props: { modelValue: 'K' },
    })
    const boxes = wrapper.findAll<HTMLInputElement>('input.code-box')
    const composingBox = boxes[1]!.element
    composingBox.focus()

    for (const key of ['Backspace', 'ArrowLeft', 'ArrowRight', ' ']) {
      const event = new KeyboardEvent('keydown', { key, isComposing: true, cancelable: true })
      composingBox.dispatchEvent(event)
      expect(event.defaultPrevented).toBe(false)
    }
    await flushPromises()

    expect(boxes[0]!.element.value).toBe('K')
    expect(document.activeElement).toBe(composingBox)
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
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
