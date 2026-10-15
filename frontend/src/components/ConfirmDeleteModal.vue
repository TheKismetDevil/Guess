<script setup lang="ts">
/**
 * ConfirmDeleteModal — Reusable destructive confirmation dialog.
 *
 * Usage:
 *   <ConfirmDeleteModal
 *     v-if="showModal"
 *     title="删除比赛"
 *     :item-name="raceName"
 *     :loading="isDeleting"
 *     @confirm="handleDelete"
 *     @cancel="showModal = false"
 *   />
 */

const props = withDefaults(defineProps<{
  title?: string
  itemName: string
  message?: string
  loading?: boolean
  confirmText?: string
  loadingText?: string
}>(), {
  title: '确认删除',
  message: '确定删除「{name}」？此操作不可撤销。',
  loading: false,
  confirmText: '确认删除',
  loadingText: '删除中…',
})

const titleId = 'confirm-delete-title'

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

function displayMessage(): string {
  return props.message.replace('{name}', props.itemName)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && !props.loading) {
    emit('cancel')
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      class="modal-overlay ui-anim-overlay"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
      @keydown="onKeydown"
      @click.self="emit('cancel')"
    >
      <div class="modal-content ui-anim-dialog">
        <h2 :id="titleId" class="modal-title">{{ title }}</h2>

        <p class="modal-message">
          {{ displayMessage() }}
        </p>

        <div class="modal-actions">
          <button
            class="ui-btn ui-btn--ghost"
            :disabled="loading"
            @click="emit('cancel')"
          >
            取消
          </button>
          <button
            class="ui-btn ui-btn--danger-solid"
            :disabled="loading"
            @click="emit('confirm')"
          >
            <span v-if="loading" class="ui-spinner"></span>
            {{ loading ? loadingText : confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(13, 30, 18, 0.5);
  padding: var(--spacing-4, 16px);
}

.modal-content {
  background: var(--color-surface-raised, #FFFFFF);
  border-radius: var(--rounded-xl, 20px);
  padding: var(--spacing-6, 24px);
  max-width: 400px;
  width: 100%;
}

.modal-title {
  font-family: var(--font-display, 'Barlow Condensed', system-ui, sans-serif);
  font-size: var(--text-heading, 24px);
  font-weight: 700;
  color: var(--color-ink-primary, #1A2E1A);
  margin: 0 0 var(--spacing-3, 12px);
}

.modal-message {
  font-size: var(--text-body, 16px);
  color: var(--color-ink-secondary, #4A5A4A);
  line-height: 1.6;
  margin: 0 0 var(--spacing-6, 24px);
}

.modal-actions {
  display: flex;
  gap: var(--spacing-3, 12px);
  justify-content: flex-end;
}
</style>
