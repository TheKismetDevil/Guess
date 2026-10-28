<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { resetPassword } from '@/api/auth'
import AuthShell from '@/components/AuthShell.vue'

const router = useRouter()

const inviteCode = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

function clearError() {
  error.value = ''
}

function validateForm(): boolean {
  if (!inviteCode.value.trim()) {
    error.value = '邀请码不能为空'
    return false
  }
  if (inviteCode.value.trim().length !== 8) {
    error.value = '邀请码必须为 8 位字符'
    return false
  }
  const pwd = newPassword.value.trim()
  const confirmPwd = confirmPassword.value.trim()
  if (!pwd) {
    error.value = '新密码不能为空'
    return false
  }
  if (pwd.length < 6) {
    error.value = '密码至少需要 6 个字符'
    return false
  }
  if (pwd.length > 128) {
    error.value = '密码长度不能超过 128 个字符'
    return false
  }
  if (!confirmPwd) {
    error.value = '请确认新密码'
    return false
  }
  if (pwd !== confirmPwd) {
    error.value = '两次密码输入不一致'
    return false
  }
  return true
}

async function handleSubmit() {
  if (!validateForm()) return

  loading.value = true
  error.value = ''

  try {
    await resetPassword({
      invite_code: inviteCode.value.trim(),
      new_password: newPassword.value.trim(),
    })
    router.push('/login?reset=success')
  } catch (err: any) {
    if (err?.response?.status === 422) {
      const errors = err?.response?.data?.detail
      if (Array.isArray(errors)) {
        for (const e of errors) {
          if (e.loc?.includes('body')) {
            const field = e.loc[e.loc.length - 1]
            if (field === 'invite_code') {
              error.value = '邀请码格式不正确'
            } else if (field === 'new_password') {
              error.value = '密码格式不正确'
            }
            break
          }
        }
        if (!error.value) error.value = '输入格式有误'
      }
    } else if (err?.response?.status === 400) {
      error.value = '邀请码无效'
    } else if (err?.message === 'Network Error') {
      error.value = '网络错误，请重试'
    } else if (err?.response?.status === 500) {
      error.value = '服务器错误，请稍后重试'
    } else {
      error.value = '邀请码无效'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell title="重置密码" subtitle="用注册时绑定的邀请码设置新密码">
    <form @submit.prevent="handleSubmit" novalidate>
      <div v-if="error" :key="error" class="ui-banner ui-banner--error" role="alert" aria-live="polite">
        {{ error }}
      </div>

      <div class="ui-field">
        <label class="ui-label" for="reset-invite-code">邀请码（注册时绑定的）</label>
        <input
          id="reset-invite-code"
          v-model="inviteCode"
          class="ui-input code-input"
          type="text"
          placeholder="请输入 8 位邀请码"
          maxlength="8"
          :aria-invalid="!!error"
          autocomplete="off"
          @input="clearError"
        />
      </div>

      <div class="ui-field">
        <label class="ui-label" for="reset-new-password">新密码</label>
        <input
          id="reset-new-password"
          v-model="newPassword"
          class="ui-input"
          type="password"
          placeholder="请输入新密码（至少6位）"
          maxlength="128"
          :aria-invalid="!!error"
          autocomplete="new-password"
          @input="clearError"
        />
      </div>

      <div class="ui-field">
        <label class="ui-label" for="reset-confirm-password">确认新密码</label>
        <input
          id="reset-confirm-password"
          v-model="confirmPassword"
          class="ui-input"
          type="password"
          placeholder="再次输入新密码"
          maxlength="128"
          :aria-invalid="!!error"
          autocomplete="new-password"
          @input="clearError"
        />
      </div>

      <button
        type="submit"
        class="ui-btn ui-btn--primary ui-btn--block submit-btn"
        :disabled="loading"
        :aria-busy="loading"
      >
        <span v-if="loading" class="ui-spinner"></span>
        {{ loading ? '重置中…' : '确认重置' }}
      </button>
    </form>

    <template #footer>
      <router-link to="/login">已有账号？去登录</router-link>
    </template>
  </AuthShell>
</template>

<style scoped>
.code-input {
  font-family: var(--font-display);
  font-size: 20px;
  letter-spacing: 0.3em;
  text-transform: uppercase;
}

.submit-btn {
  margin-top: var(--spacing-2);
  min-height: 48px;
}
</style>
