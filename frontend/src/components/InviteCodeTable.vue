<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { getInviteCodes, createInviteCode, deleteInviteCode } from '@/api/admin'
import type { InviteCode, InviteCodeStatus } from '@/types/admin'
import ConfirmDeleteModal from '@/components/ConfirmDeleteModal.vue'

const search = ref('')
const qq = ref('')
const inviteCodes = ref<InviteCode[]>([])
const loading = ref(true)
const searching = ref(false)
const loadError = ref<string | null>(null)
const notice = ref<string | null>(null)
const generating = ref(false)
const lastCreated = ref<InviteCode | null>(null)
const copiedCode = ref<string | null>(null)
const deleteTarget = ref<InviteCode | null>(null)
const deleting = ref(false)

let debounceTimer: ReturnType<typeof setTimeout> | null = null
let noticeTimer: ReturnType<typeof setTimeout> | null = null
let copiedTimer: ReturnType<typeof setTimeout> | null = null

const statusLabels: Record<InviteCodeStatus, string> = {
  unused: '尚未使用',
  used: '已绑定',
}

function statusLabel(status: InviteCodeStatus): string {
  return statusLabels[status] || status
}

const unusedCount = computed(() => inviteCodes.value.filter(c => c.status === 'unused').length)

function showNotice(message: string) {
  notice.value = message
  if (noticeTimer) clearTimeout(noticeTimer)
  noticeTimer = setTimeout(() => { notice.value = null }, 3500)
}

/** First load shows a skeleton; searches keep the current rows on screen. */
async function loadCodes(options: { quiet?: boolean } = {}) {
  if (options.quiet) searching.value = true
  else loading.value = true
  loadError.value = null
  try {
    inviteCodes.value = await getInviteCodes(search.value || undefined)
  } catch {
    loadError.value = '加载失败，请刷新重试'
  } finally {
    loading.value = false
    searching.value = false
  }
}

function debouncedSearch() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    loadCodes({ quiet: true })
  }, 300)
}

watch(search, debouncedSearch)

async function handleCreate() {
  const value = qq.value.trim()
  if (!value) {
    showNotice('请先输入 QQ 号')
    return
  }
  if (value.length < 5 || value.length > 20) {
    showNotice('QQ 号长度需在 5-20 个字符之间')
    return
  }
  generating.value = true
  try {
    const code = await createInviteCode(value)
    inviteCodes.value.unshift(code)
    lastCreated.value = code
    qq.value = ''
  } catch {
    showNotice('生成邀请码失败，请重试')
  } finally {
    generating.value = false
  }
}

function handleDelete(item: InviteCode) {
  deleteTarget.value = item
}

const deleteMessage = computed(() => {
  const item = deleteTarget.value
  if (!item) return ''
  return item.status === 'used'
    ? `确定删除邀请码「{name}」？这会同时删除用户「${item.bound_username}」及其所有投票记录，不可撤销！`
    : '确定删除邀请码「{name}」？此操作不可撤销。'
})

async function confirmDelete() {
  const item = deleteTarget.value
  if (!item || deleting.value) return
  deleting.value = true
  try {
    await deleteInviteCode(item.code)
    inviteCodes.value = inviteCodes.value.filter((c) => c.code !== item.code)
    if (lastCreated.value?.code === item.code) lastCreated.value = null
    deleteTarget.value = null
  } catch {
    deleteTarget.value = null
    showNotice('删除失败，请重试')
  } finally {
    deleting.value = false
  }
}

async function copyCode(code: string) {
  try {
    await navigator.clipboard.writeText(code)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = code
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  copiedCode.value = code
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => { copiedCode.value = null }, 1600)
}

onMounted(() => loadCodes())
onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (noticeTimer) clearTimeout(noticeTimer)
  if (copiedTimer) clearTimeout(copiedTimer)
})
</script>

<template>
  <div class="invite-code-table">
    <div class="toolbar">
      <div class="search-box">
        <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          v-model="search"
          type="search"
          class="ui-input search-input"
          placeholder="搜索邀请码、用户名或 QQ 号…"
          aria-label="搜索邀请码、用户名或QQ号"
        />
        <span v-if="searching" class="ui-spinner search-spinner" aria-hidden="true"></span>
        <button v-else-if="search" type="button" class="search-clear" aria-label="清空搜索" @click="search = ''">✕</button>
      </div>

      <form class="generate-group" @submit.prevent="handleCreate">
        <input
          v-model="qq"
          type="text"
          class="ui-input qq-input"
          placeholder="绑定的 QQ 号"
          maxlength="20"
          inputmode="numeric"
          aria-label="绑定 QQ 号"
        />
        <button type="submit" class="ui-btn ui-btn--primary" :disabled="generating">
          <span v-if="generating" class="ui-spinner"></span>
          <svg v-else class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          {{ generating ? '生成中…' : '生成邀请码' }}
        </button>
      </form>
    </div>

    <!-- Fresh code: show it big with a copy button so it can be sent right away -->
    <Transition name="ui-fade">
      <div v-if="lastCreated" class="created-banner" role="status">
        <div class="created-text">
          <span class="created-label">已为 QQ {{ lastCreated.bound_qq }} 生成邀请码</span>
          <code class="created-code">{{ lastCreated.code }}</code>
        </div>
        <button type="button" class="ui-btn ui-btn--gold ui-btn--sm" @click="copyCode(lastCreated.code)">
          {{ copiedCode === lastCreated.code ? '已复制 ✓' : '复制' }}
        </button>
        <button type="button" class="created-close" aria-label="关闭" @click="lastCreated = null">✕</button>
      </div>
    </Transition>

    <Transition name="ui-fade">
      <p v-if="notice" class="ui-banner ui-banner--error" role="alert">{{ notice }}</p>
    </Transition>

    <div v-if="loading" class="skeleton" role="status" aria-label="加载中">
      <div v-for="i in 5" :key="i" class="ui-skeleton skeleton-row"></div>
    </div>

    <div v-else-if="loadError" class="ui-state ui-state--error" role="alert">
      <p class="ui-state-text">{{ loadError }}</p>
      <button class="ui-btn ui-btn--primary" @click="loadCodes()">刷新重试</button>
    </div>

    <div v-else-if="inviteCodes.length === 0" class="ui-state empty-state" role="status">
      <p class="ui-state-text">
        <template v-if="search">没有找到匹配「{{ search }}」的邀请码</template>
        <template v-else>还没有邀请码。输入 QQ 号后点击「生成邀请码」创建第一个。</template>
      </p>
      <button v-if="search" class="ui-btn ui-btn--ghost ui-btn--sm" @click="search = ''">清空搜索</button>
    </div>

    <template v-else>
      <p class="summary">
        共 {{ inviteCodes.length }} 个，其中 <strong>{{ unusedCount }}</strong> 个尚未使用
      </p>
      <div class="table-wrapper" :class="{ 'is-searching': searching }">
        <table class="code-table">
          <thead>
            <tr>
              <th scope="col">邀请码</th>
              <th scope="col">状态</th>
              <th scope="col">绑定用户</th>
              <th scope="col">QQ</th>
              <th scope="col" class="col-actions"><span class="sr-only">操作</span></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in inviteCodes"
              :key="item.code"
              :class="{ 'is-new': lastCreated?.code === item.code }"
            >
              <td class="cell-code"><code class="code-text">{{ item.code }}</code></td>
              <td data-label="状态">
                <span class="status-chip" :class="`status-${item.status}`">{{ statusLabel(item.status) }}</span>
              </td>
              <td data-label="绑定用户" :class="{ muted: !item.bound_username }">{{ item.bound_username || '-' }}</td>
              <td data-label="QQ" :class="{ muted: !item.bound_qq }">{{ item.bound_qq || '-' }}</td>
              <td class="col-actions">
                <div class="row-actions">
                  <button
                    class="row-btn"
                    :class="{ 'is-copied': copiedCode === item.code }"
                    :aria-label="`复制邀请码 ${item.code}`"
                    @click="copyCode(item.code)"
                  >
                    <svg v-if="copiedCode === item.code" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                    <span class="row-btn-label">{{ copiedCode === item.code ? '已复制' : '复制' }}</span>
                  </button>
                  <button
                    class="row-btn row-btn-danger"
                    :aria-label="`删除邀请码 ${item.code}`"
                    @click="handleDelete(item)"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" /><path d="M10 11v6" /><path d="M14 11v6" />
                    </svg>
                    <span class="row-btn-label">删除</span>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <ConfirmDeleteModal
      v-if="deleteTarget"
      :title="deleteTarget.status === 'used' ? '删除用户与邀请码' : '删除邀请码'"
      :item-name="deleteTarget.code"
      :message="deleteMessage"
      :loading="deleting"
      @confirm="confirmDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<style scoped>
/* =========================================
   Toolbar
   ========================================= */

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
}

.search-box {
  position: relative;
  flex: 1 1 260px;
  max-width: 420px;
}

.search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  width: 16px;
  height: 16px;
  color: var(--color-ink-disabled);
  transform: translateY(-50%);
  pointer-events: none;
}

.search-input {
  padding-left: 40px;
  padding-right: 40px;
  background: var(--color-surface-raised);
}

.search-input::-webkit-search-cancel-button {
  display: none;
}

.search-spinner {
  position: absolute;
  right: 14px;
  top: 50%;
  margin-top: -8px;
  color: var(--color-primary);
}

.search-clear {
  position: absolute;
  right: 12px;
  top: 50%;
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  margin-top: -10px;
  border-radius: 50%;
  font-size: 11px;
  color: #FFFFFF;
  background: var(--color-ink-disabled);
}

.search-clear:hover {
  background: var(--color-ink-secondary);
}

.generate-group {
  display: flex;
  gap: var(--spacing-2);
  margin-left: auto;
}

.qq-input {
  width: 170px;
  background: var(--color-surface-raised);
}

.btn-icon {
  width: 16px;
  height: 16px;
}

/* =========================================
   New-code banner
   ========================================= */

.created-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-4);
  padding: var(--spacing-3) var(--spacing-4);
  border: 1px solid var(--color-accent);
  border-radius: var(--rounded-lg);
  background: linear-gradient(100deg, var(--color-accent-tint), #FFFFFF);
  box-shadow: var(--shadow-glow-gold);
}

.created-text {
  flex: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px var(--spacing-3);
  min-width: 0;
}

.created-label {
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
}

.created-code {
  font-family: var(--font-display);
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 0.18em;
  color: var(--color-accent-dark);
  animation: pop-in var(--duration-slow) var(--ease-spring);
}

.created-close {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 12px;
  color: var(--color-ink-secondary);
}

.created-close:hover {
  background: rgba(0, 0, 0, 0.05);
}

/* =========================================
   States
   ========================================= */

.skeleton {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.skeleton-row {
  height: 52px;
  border-radius: var(--rounded-md);
}

.empty-state {
  min-height: 30vh;
}

.summary {
  margin-bottom: var(--spacing-2);
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
}

.summary strong {
  color: var(--color-primary);
}

/* =========================================
   Table
   ========================================= */

.table-wrapper {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  box-shadow: var(--shadow-sm);
  animation: rise-in var(--duration-slow) var(--ease-out) backwards;
  transition: opacity var(--duration-base) ease;
}

.table-wrapper.is-searching {
  opacity: 0.55;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-body-sm);
}

thead tr {
  background: var(--color-surface-base);
}

th {
  padding: var(--spacing-3);
  font-size: var(--text-caption);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-align: left;
  white-space: nowrap;
  color: var(--color-ink-secondary);
  border-bottom: 1px solid var(--color-border-hairline);
}

td {
  padding: var(--spacing-3);
  white-space: nowrap;
  border-bottom: 1px solid var(--color-border-hairline);
}

tbody tr {
  transition: background var(--duration-fast) ease;
}

tbody tr:hover {
  background: var(--color-primary-tint);
}

tbody tr:last-child td {
  border-bottom: none;
}

tbody tr.is-new {
  background: var(--color-accent-tint);
  animation: rise-in var(--duration-slow) var(--ease-out);
}

.code-text {
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--color-ink-primary);
}

.status-chip {
  display: inline-block;
  padding: 1px 10px;
  border-radius: var(--rounded-full);
  font-size: 12px;
  font-weight: 600;
}

.status-unused {
  color: var(--color-primary);
  background: var(--color-primary-tint);
}

.status-used {
  color: var(--color-ink-secondary);
  background: var(--color-surface-sunken);
}

.muted {
  color: var(--color-ink-disabled);
}

.col-actions {
  width: 1%;
  text-align: right;
}

.row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 4px;
}

.row-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 32px;
  padding: 0 10px;
  border-radius: var(--rounded-full);
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-ink-secondary);
  transition: color var(--duration-fast) ease, background var(--duration-fast) ease, transform var(--duration-fast) var(--ease-out);
}

.row-btn svg {
  width: 15px;
  height: 15px;
}

.row-btn:hover {
  color: var(--color-primary);
  background: var(--color-surface-raised);
  box-shadow: inset 0 0 0 1px var(--color-primary-tint-strong);
}

.row-btn:active {
  transform: scale(0.95);
}

.row-btn.is-copied {
  color: var(--color-primary);
}

.row-btn-danger:hover {
  color: var(--color-destructive);
  box-shadow: inset 0 0 0 1px var(--color-destructive-light);
}

/* Phones: rows become cards */
@media (max-width: 767px) {
  .search-box {
    flex-basis: 100%;
    max-width: none;
  }

  .generate-group {
    flex: 1 1 100%;
    min-width: 0;
    margin-left: 0;
  }

  .qq-input {
    flex: 1;
    width: auto;
    min-width: 0;
  }

  .created-banner {
    flex-wrap: wrap;
  }

  .table-wrapper {
    overflow: visible;
    background: transparent;
    border: none;
    box-shadow: none;
  }

  .code-table thead {
    display: none;
  }

  .code-table,
  .code-table tbody,
  .code-table tr,
  .code-table td {
    display: block;
  }

  .code-table tbody {
    display: flex;
    flex-direction: column;
    gap: var(--spacing-2);
  }

  .code-table tr {
    position: relative;
    padding: var(--spacing-3) var(--spacing-4);
    background: var(--color-surface-raised);
    border: 1px solid var(--color-border-hairline);
    border-radius: var(--rounded-lg);
    box-shadow: var(--shadow-sm);
  }

  .code-table tbody tr:hover {
    background: var(--color-surface-raised);
  }

  .code-table tbody tr.is-new {
    background: var(--color-accent-tint);
  }

  .code-table td {
    padding: 2px 0;
    border: none;
  }

  .code-table td[data-label] {
    display: flex;
    align-items: center;
    font-size: 13px;
  }

  .code-table td[data-label]::before {
    content: attr(data-label);
    flex: 0 0 5em;
    font-size: 11px;
    font-weight: 600;
    color: var(--color-ink-disabled);
  }

  .cell-code {
    margin-bottom: 4px;
  }

  .code-table .col-actions {
    position: absolute;
    top: var(--spacing-3);
    right: var(--spacing-3);
    width: auto;
    padding: 0;
  }

  .row-btn {
    width: 36px;
    height: 36px;
    padding: 0;
    justify-content: center;
    background: var(--color-surface-base);
  }

  .row-btn-label {
    display: none;
  }
}
</style>
