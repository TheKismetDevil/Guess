<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

interface Props {
  name: string
  date: string
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})

const emit = defineEmits<{
  save: [{ name: string; date: string }]
}>()

const isEditing = ref(false)
const editName = ref('')
const nameInput = ref<HTMLInputElement | null>(null)

function enterEdit() {
  if (props.disabled) return
  editName.value = props.name
  isEditing.value = true
  nextTick(() => nameInput.value?.focus())
}

function cancelEdit() {
  isEditing.value = false
}

function submitEdit() {
  const trimmed = editName.value.trim()
  if (!trimmed) {
    cancelEdit()
    return
  }
  emit('save', { name: trimmed, date: props.date.slice(0, 10) })
  isEditing.value = false
}

function handleNameKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    submitEdit()
  } else if (e.key === 'Escape') {
    cancelEdit()
  }
}

watch(
  () => props.name,
  () => {
    if (!isEditing.value) editName.value = props.name
  },
)
</script>

<template>
  <div class="race-header-editor">
    <template v-if="isEditing">
      <div class="edit-row">
        <input
          ref="nameInput"
          v-model="editName"
          type="text"
          class="edit-input name-input"
          placeholder="比赛名称"
          @keydown="handleNameKeydown"
          @blur="submitEdit"
        />
      </div>
    </template>
    <template v-else>
      <div class="display-row" @dblclick="enterEdit">
        <h1 class="race-name">{{ name }}</h1>
        <button
          class="edit-btn"
          type="button"
          aria-label="编辑比赛信息"
          :disabled="disabled"
          @click="enterEdit"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 20h9" /><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
          </svg>
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.race-header-editor {
  flex: 1;
  min-width: 0;
}

.display-row {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1, 4px);
  position: relative;
  padding-right: 32px;
  cursor: pointer;
}

.race-name {
  font-family: var(--font-display, 'Barlow Condensed', system-ui, sans-serif);
  font-size: var(--text-heading, 24px);
  font-weight: 600;
  color: inherit;
  margin: 0;
  line-height: 1.25;
  word-break: break-word;
}

.race-date {
  font-size: var(--text-body, 16px);
  color: var(--color-ink-secondary, #4A5A4A);
  margin: 0;
}

.edit-btn {
  position: absolute;
  top: 6px;
  right: 0;
  background: transparent;
  border: none;
  color: inherit;
  opacity: 0.75;
  transition: opacity var(--duration-fast) ease, background var(--duration-fast) ease, transform var(--duration-fast) var(--ease-spring);
  font-size: var(--text-body, 16px);
  cursor: pointer;
  padding: 4px;
  min-width: 28px;
  min-height: 28px;
  border-radius: var(--rounded-sm, 6px);
}

.edit-btn:hover:not(:disabled) {
  opacity: 1;
  background: rgba(255, 255, 255, 0.14);
  transform: rotate(-12deg) scale(1.1);
}

.edit-btn svg {
  display: block;
  width: 18px;
  height: 18px;
}

.edit-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.edit-row {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2, 8px);
}

.edit-input {
  padding: 8px 12px;
  border: 1px solid var(--color-border-strong, #A8B8A4);
  border-radius: var(--rounded-sm, 6px);
  font-size: var(--text-body, 16px);
  color: var(--color-ink-primary, #1A2E1A);
  background: var(--color-surface-raised, #FFFFFF);
  display: block;
  width: 100%;
  box-sizing: border-box;
}

.edit-input:focus {
  outline: 2px solid var(--color-accent-light, #D4B84A);
  outline-offset: 2px;
}

.name-input {
  font-family: var(--font-display, 'Barlow Condensed', system-ui, sans-serif);
  font-size: var(--text-heading, 24px);
  font-weight: 600;
}

@media (max-width: 767px) {
  .race-name {
    font-size: var(--text-subheading, 18px);
  }

  .name-input {
    font-size: var(--text-subheading, 18px);
  }
}
</style>
