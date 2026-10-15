<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import AuthShell from '@/components/AuthShell.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const qq = ref('')
const inviteCode = ref('')
const loading = ref(false)
const fieldErrors = ref<Record<string, string>>({})
const globalError = ref('')

function validateForm(): boolean {
  fieldErrors.value = {}
  globalError.value = ''

  if (!username.value.trim()) {
    fieldErrors.value.username = '用户名不能为空'
    return false
  }
  if (username.value.trim().length < 3 || username.value.trim().length > 20) {
    fieldErrors.value.username = '用户名长度需在 3-20 个字符之间'
    return false
  }

  if (!password.value) {
    fieldErrors.value.password = '密码不能为空'
    return false
  }
  if (password.value.length < 6) {
    fieldErrors.value.password = '密码至少需要 6 个字符'
    return false
  }

  if (!qq.value.trim()) {
    fieldErrors.value.qq = 'QQ 号不能为空'
    return false
  }
  if (qq.value.trim().length < 5 || qq.value.trim().length > 20) {
    fieldErrors.value.qq = 'QQ 号长度需在 5-20 个字符之间'
    return false
  }

  if (!inviteCode.value.trim()) {
    fieldErrors.value.inviteCode = '邀请码不能为空'
    return false
  }
  if (inviteCode.value.trim().length !== 8) {
    fieldErrors.value.inviteCode = '邀请码必须为 8 位字符'
    return false
  }

  return true
}

async function handleSubmit() {
  if (!validateForm()) return

  loading.value = true
  globalError.value = ''

  try {
    await authStore.register({
      username: username.value.trim(),
      password: password.value,
      qq: qq.value.trim(),
      invite_code: inviteCode.value.trim().toUpperCase(),
    })
    // Redirect after successful registration
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (err: any) {
    const detail = err?.response?.data?.detail
    if (detail?.code) {
      globalError.value = detail.message
    } else if (err?.response?.status === 422) {
      // Validation error — map field-level errors
      const errors = err?.response?.data?.detail || []
      for (const e of errors) {
        if (e.loc?.includes('body')) {
          fieldErrors.value[e.loc[e.loc.length - 1]] = e.msg || '字段校验失败'
        }
      }
    } else {
      globalError.value = '注册失败，请重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell title="注册" subtitle="凭邀请码加入竞猜圈">
    <form @submit.prevent="handleSubmit" novalidate>
      <!-- Global error -->
      <div v-if="globalError" :key="globalError" class="ui-banner ui-banner--error" role="alert" aria-live="polite">
        {{ globalError }}
      </div>

      <!-- Username -->
      <div class="ui-field">
        <label class="ui-label" for="username">用户名</label>
        <input
          id="username"
          v-model="username"
          class="ui-input"
          type="text"
          placeholder="请输入用户名"
          maxlength="20"
          :aria-invalid="!!fieldErrors.username"
          :aria-describedby="fieldErrors.username ? 'username-error' : undefined"
        />
        <p v-if="fieldErrors.username" :id="'username-error'" class="ui-field-error" role="alert">
          {{ fieldErrors.username }}
        </p>
      </div>

      <!-- Password -->
      <div class="ui-field">
        <label class="ui-label" for="password">密码（至少 6 位）</label>
        <input
          id="password"
          v-model="password"
          class="ui-input"
          type="password"
          placeholder="请输入密码"
          maxlength="128"
          :aria-invalid="!!fieldErrors.password"
          :aria-describedby="fieldErrors.password ? 'password-error' : undefined"
        />
        <p v-if="fieldErrors.password" :id="'password-error'" class="ui-field-error" role="alert">
          {{ fieldErrors.password }}
        </p>
      </div>

      <!-- QQ -->
      <div class="ui-field">
        <label class="ui-label" for="qq">QQ 号</label>
        <input
          id="qq"
          v-model="qq"
          class="ui-input"
          type="text"
          placeholder="请输入 QQ 号"
          maxlength="20"
          inputmode="numeric"
          :aria-invalid="!!fieldErrors.qq"
          :aria-describedby="fieldErrors.qq ? 'qq-error' : undefined"
        />
        <p v-if="fieldErrors.qq" :id="'qq-error'" class="ui-field-error" role="alert">
          {{ fieldErrors.qq }}
        </p>
      </div>

      <!-- Invite code -->
      <div class="ui-field">
        <label class="ui-label" for="invite-code">邀请码</label>
        <input
          id="invite-code"
          v-model="inviteCode"
          type="text"
          placeholder="请输入邀请码"
          maxlength="8"
          class="ui-input invite-input"
          :aria-invalid="!!fieldErrors.inviteCode"
          :aria-describedby="fieldErrors.inviteCode ? 'invite-code-error' : undefined"
        />
        <p v-if="fieldErrors.inviteCode" :id="'invite-code-error'" class="ui-field-error" role="alert">
          {{ fieldErrors.inviteCode }}
        </p>
      </div>

      <!-- Submit -->
      <button
        type="submit"
        class="ui-btn ui-btn--primary ui-btn--block submit-btn"
        :disabled="loading"
        :aria-busy="loading"
      >
        <span v-if="loading" class="ui-spinner"></span>
        {{ loading ? '注册中...' : '注  册' }}
      </button>
    </form>

    <template #footer>
      <p>已有账号？<router-link to="/login">去登录</router-link></p>
    </template>
  </AuthShell>
</template>

<style scoped>
.invite-input {
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
