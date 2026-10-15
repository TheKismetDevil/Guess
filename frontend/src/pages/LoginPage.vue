<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute, type LocationQueryValue } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import AuthShell from '@/components/AuthShell.vue'

type LoginMode = 'username' | 'qq' | 'invite_code'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loginMode = ref<LoginMode>('username')
const username = ref('')
const qq = ref('')
const inviteCode = ref('')
const password = ref('')
const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref(
  normalizeQuery(route.query.reset) === 'success' ? '密码重置成功，请用新密码登录' : ''
)
const sessionExpiredMessage = computed(() =>
  normalizeQuery(route.query.session) === 'expired' ? '登录状态已过期，请重新登录' : ''
)

function normalizeQuery(value: LocationQueryValue | LocationQueryValue[]): string | undefined {
  if (value === null || value === undefined) return undefined
  const first = Array.isArray(value) ? value[0] : value
  return first ?? undefined
}

const tabs = [
  { mode: 'username' as LoginMode, label: '用户名登录' },
  { mode: 'qq' as LoginMode, label: 'QQ登录' },
  { mode: 'invite_code' as LoginMode, label: '邀请码登录' },
]
const activeTabIndex = computed(() => tabs.findIndex(t => t.mode === loginMode.value))

function switchMode(mode: LoginMode) {
  loginMode.value = mode
  errorMessage.value = ''
}

function clearError() {
  errorMessage.value = ''
}

function validateForm(): boolean {
  if (loginMode.value === 'username') {
    if (!username.value.trim()) {
      errorMessage.value = '用户名不能为空'
      return false
    }
    if (!password.value) {
      errorMessage.value = '密码不能为空'
      return false
    }
  } else if (loginMode.value === 'qq') {
    if (!qq.value.trim()) {
      errorMessage.value = 'QQ 号不能为空'
      return false
    }
    if (!password.value) {
      errorMessage.value = '密码不能为空'
      return false
    }
  } else {
    if (!inviteCode.value.trim()) {
      errorMessage.value = '邀请码不能为空'
      return false
    }
    if (inviteCode.value.trim().length !== 8) {
      errorMessage.value = '邀请码必须为 8 位字符'
      return false
    }
  }
  return true
}

async function handleSubmit() {
  if (!validateForm()) return

  loading.value = true
  errorMessage.value = ''

  try {
    const loginData: Record<string, string> = {}
    if (loginMode.value === 'username') {
      loginData.username = username.value.trim()
      loginData.password = password.value
    } else if (loginMode.value === 'qq') {
      loginData.qq = qq.value.trim()
      loginData.password = password.value
    } else {
      loginData.invite_code = inviteCode.value.trim().toUpperCase()
    }
    await authStore.login(loginData as any)
    const redirect = normalizeQuery(route.query.redirect) || '/'
    router.push(redirect)
  } catch (err: any) {
    if (err?.response?.status === 422) {
      errorMessage.value = '输入格式有误'
    } else if (err?.message === 'Network Error') {
      errorMessage.value = '网络错误，请重试'
    } else if (err?.response?.status === 500) {
      errorMessage.value = '服务器错误，请稍后重试'
    } else {
      errorMessage.value = '用户名或密码错误'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell title="登录" subtitle="欢迎回来，今天看好哪匹马？">
    <form @submit.prevent="handleSubmit" novalidate>
      <!-- Session expired -->
      <div v-if="sessionExpiredMessage" class="ui-banner ui-banner--error" role="alert" aria-live="polite">
        {{ sessionExpiredMessage }}
      </div>

      <!-- Success banner -->
      <div v-if="successMessage" class="ui-banner ui-banner--success" role="status" aria-live="polite">
        {{ successMessage }}
      </div>

      <!-- Error -->
      <div v-if="errorMessage" :key="errorMessage" class="ui-banner ui-banner--error" role="alert" aria-live="polite">
        {{ errorMessage }}
      </div>

      <!-- Mode tabs -->
      <div class="tab-bar" role="tablist" :style="{ '--tab-index': activeTabIndex, '--tab-count': tabs.length }">
        <span class="tab-thumb" aria-hidden="true"></span>
        <button
          v-for="tab in tabs"
          :key="tab.mode"
          :class="['tab-btn', { active: loginMode === tab.mode }]"
          :aria-selected="loginMode === tab.mode"
          role="tab"
          type="button"
          @click="switchMode(tab.mode)"
        >
          {{ tab.label }}
        </button>
      </div>

      <Transition name="mode-swap" mode="out-in">
        <!-- Username mode -->
        <div v-if="loginMode === 'username'" key="username">
          <div class="ui-field">
            <label class="ui-label" for="username">用户名</label>
            <input
              id="username"
              v-model="username"
              class="ui-input"
              type="text"
              placeholder="请输入用户名"
              maxlength="20"
              :aria-invalid="!!errorMessage"
              autocomplete="username"
              @input="clearError"
            />
          </div>
          <div class="ui-field">
            <label class="ui-label" for="password">密码</label>
            <input
              id="password"
              v-model="password"
              class="ui-input"
              type="password"
              placeholder="请输入密码"
              maxlength="128"
              :aria-invalid="!!errorMessage"
              autocomplete="current-password"
              @input="clearError"
            />
          </div>
        </div>

        <!-- QQ mode -->
        <div v-else-if="loginMode === 'qq'" key="qq">
          <div class="ui-field">
            <label class="ui-label" for="login-qq">QQ 号</label>
            <input
              id="login-qq"
              v-model="qq"
              class="ui-input"
              type="text"
              placeholder="请输入绑定的 QQ 号"
              maxlength="20"
              inputmode="numeric"
              :aria-invalid="!!errorMessage"
              @input="clearError"
            />
          </div>
          <div class="ui-field">
            <label class="ui-label" for="qq-password">密码</label>
            <input
              id="qq-password"
              v-model="password"
              class="ui-input"
              type="password"
              placeholder="请输入密码"
              maxlength="128"
              :aria-invalid="!!errorMessage"
              autocomplete="current-password"
              @input="clearError"
            />
          </div>
        </div>

        <!-- Invite code mode -->
        <div v-else key="invite_code">
          <div class="ui-field">
            <label class="ui-label" for="login-invite-code">邀请码</label>
            <input
              id="login-invite-code"
              v-model="inviteCode"
              class="ui-input code-input"
              type="text"
              placeholder="请输入 8 位邀请码"
              maxlength="8"
              :aria-invalid="!!errorMessage"
              autocomplete="off"
              @input="clearError"
            />
          </div>
        </div>
      </Transition>

      <!-- Submit -->
      <button
        type="submit"
        class="ui-btn ui-btn--primary ui-btn--block submit-btn"
        :disabled="loading"
        :aria-busy="loading"
      >
        <span v-if="loading" class="ui-spinner"></span>
        {{ loading ? '登录中…' : '登录' }}
      </button>
    </form>

    <template #footer>
      <router-link to="/register">没有账号？注册</router-link>
      <router-link to="/reset-password">忘记密码？</router-link>
    </template>
  </AuthShell>
</template>

<style scoped>
.tab-bar {
  position: relative;
  display: flex;
  margin-bottom: var(--spacing-5);
  padding: 4px;
  border-radius: var(--rounded-md);
  background: var(--color-surface-sunken);
}

/* Sliding pill behind the active tab */
.tab-thumb {
  position: absolute;
  top: 4px;
  bottom: 4px;
  left: 4px;
  width: calc((100% - 8px) / var(--tab-count));
  border-radius: var(--rounded-sm);
  background: var(--color-surface-raised);
  box-shadow: 0 2px 8px -2px rgba(13, 58, 31, 0.2);
  transform: translateX(calc(var(--tab-index) * 100%));
  transition: transform var(--duration-slow) var(--ease-out);
}

.tab-btn {
  position: relative;
  flex: 1;
  min-height: 40px;
  padding: var(--spacing-2);
  font-size: 14px;
  font-weight: 600;
  border-radius: var(--rounded-sm);
  white-space: nowrap;
  color: var(--color-ink-secondary);
  transition: color var(--duration-base) ease;
}

.tab-btn:hover:not(.active) {
  color: var(--color-ink-primary);
}

.tab-btn.active {
  color: var(--color-primary);
}

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

.mode-swap-enter-active,
.mode-swap-leave-active {
  transition: opacity var(--duration-fast) ease, transform var(--duration-base) var(--ease-out);
}

.mode-swap-enter-from {
  opacity: 0;
  transform: translateX(12px);
}

.mode-swap-leave-to {
  opacity: 0;
  transform: translateX(-12px);
}

@media (prefers-reduced-motion: reduce) {
  .tab-thumb {
    transition: none;
  }
}
</style>
