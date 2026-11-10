import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
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

describe('invite code inputs across auth pages', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('uses standard ui-input styling without display-font classes on LoginPage, RegisterPage and ResetPasswordPage', async () => {
    const loginWrapper = mount(LoginPage, { global: { stubs: { RouterLink: true } } })
    await loginWrapper.findAll('[role="tab"]')[2]!.trigger('click')
    await flushPromises()
    const loginInput = loginWrapper.get('#login-invite-code')
    expect(loginInput.classes()).toEqual(['ui-input'])

    const registerWrapper = mount(RegisterPage, { global: { stubs: { RouterLink: true } } })
    const registerInput = registerWrapper.get('#invite-code')
    expect(registerInput.classes()).toEqual(['ui-input'])

    const resetWrapper = mount(ResetPasswordPage, { global: { stubs: { RouterLink: true } } })
    const resetInput = resetWrapper.get('#reset-invite-code')
    expect(resetInput.classes()).toEqual(['ui-input'])
  })

  it('normalizes lowercase invite codes to uppercase when resetting password', async () => {
    vi.mocked(authApi.resetPassword).mockResolvedValueOnce({
      user: { id: 1, username: 'tester', qq: '123456', is_admin: false },
    })
    const wrapper = mount(ResetPasswordPage, { global: { stubs: { RouterLink: true } } })
    await wrapper.get('#reset-invite-code').setValue('ab12cd34')
    await wrapper.get('#reset-new-password').setValue('newpass123')
    await wrapper.get('#reset-confirm-password').setValue('newpass123')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(authApi.resetPassword).toHaveBeenCalledWith({
      invite_code: 'AB12CD34',
      new_password: 'newpass123',
    })
    expect(push).toHaveBeenCalledWith('/login?reset=success')
  })
})
