<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'

const props = withDefaults(
  defineProps<{
    id?: string
    length?: number
    invalid?: boolean
    ariaDescribedby?: string
    disabled?: boolean
  }>(),
  {
    length: 8,
    invalid: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  input: []
}>()

const model = defineModel<string>({ default: '' })

function sanitize(raw: string): string {
  return raw.replace(/[^a-zA-Z0-9]/g, '').toUpperCase()
}

function toSlots(value: string, len: number): string[] {
  const clean = sanitize(value)
  return Array.from({ length: len }, (_, i) => clean[i] ?? '')
}

const slots = ref<string[]>(toSlots(model.value, props.length))
const inputRefs = ref<(HTMLInputElement | null)[]>([])

function setInputRef(el: unknown, index: number) {
  inputRefs.value[index] = el as HTMLInputElement | null
}

function syncDomValues() {
  for (let i = 0; i < props.length; i++) {
    const el = inputRefs.value[i]
    if (el && el.value !== (slots.value[i] ?? '')) {
      el.value = slots.value[i] ?? ''
    }
  }
}

function commitSlots() {
  model.value = slots.value.join('')
  syncDomValues()
  emit('input')
}

function focusSlot(index: number) {
  const clamped = Math.max(0, Math.min(index, props.length - 1))
  nextTick(() => {
    const el = inputRefs.value[clamped]
    if (!el) return
    el.focus()
    el.select()
  })
}

watch(
  () => [model.value, props.length] as const,
  ([nextModel, nextLen]) => {
    if (slots.value.length !== nextLen || sanitize(nextModel) !== slots.value.join('')) {
      slots.value = toSlots(nextModel, nextLen)
      nextTick(syncDomValues)
    }
  },
)

function distributeFrom(startIndex: number, chars: string) {
  const start = chars.length >= props.length ? 0 : startIndex
  for (let offset = 0; offset < chars.length && start + offset < props.length; offset++) {
    slots.value[start + offset] = chars[offset] ?? ''
  }
  commitSlots()
  const nextEmpty = slots.value.findIndex((c, idx) => idx > start && c === '')
  if (start + chars.length < props.length) {
    focusSlot(start + chars.length)
  } else if (nextEmpty !== -1) {
    focusSlot(nextEmpty)
  } else {
    focusSlot(props.length - 1)
  }
}

function processRawInput(index: number, raw: string, typedData?: string | null) {
  const prevChar = slots.value[index] ?? ''
  const clean = sanitize(raw)

  if (clean.length === 0) {
    slots.value[index] = ''
    commitSlots()
    return
  }

  if (clean.length === 1) {
    slots.value[index] = clean
    commitSlots()
    if (index < props.length - 1) focusSlot(index + 1)
    return
  }

  const singleTyped = typedData ? sanitize(typedData) : ''
  if (singleTyped.length === 1 && clean.length === 2 && prevChar) {
    slots.value[index] = singleTyped
    commitSlots()
    if (index < props.length - 1) focusSlot(index + 1)
    return
  }
  if (!typedData && clean.length === 2 && prevChar && (clean[0] === prevChar || clean[1] === prevChar)) {
    const replacement = clean[0] === prevChar ? clean[1]! : clean[0]!
    slots.value[index] = replacement
    commitSlots()
    if (index < props.length - 1) focusSlot(index + 1)
    return
  }

  distributeFrom(index, clean)
}

function handleInput(index: number, event: Event) {
  const inputEvent = event as InputEvent
  if (inputEvent.isComposing) return
  const target = event.target as HTMLInputElement
  processRawInput(index, target.value, inputEvent.data)
}

function handleCompositionEnd(index: number, event: CompositionEvent) {
  const target = event.target as HTMLInputElement
  processRawInput(index, target.value, event.data)
}

function handleKeydown(index: number, event: KeyboardEvent) {
  if (event.key === 'Backspace') {
    event.preventDefault()
    if (slots.value[index]) {
      slots.value[index] = ''
      commitSlots()
    } else if (index > 0) {
      slots.value[index - 1] = ''
      commitSlots()
      focusSlot(index - 1)
    }
  } else if (event.key === 'Delete') {
    event.preventDefault()
    if (slots.value[index]) {
      slots.value[index] = ''
      commitSlots()
    }
  } else if (event.key === 'ArrowLeft') {
    event.preventDefault()
    if (index > 0) focusSlot(index - 1)
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    if (index < props.length - 1) focusSlot(index + 1)
  } else if (event.key === 'Home') {
    event.preventDefault()
    focusSlot(0)
  } else if (event.key === 'End') {
    event.preventDefault()
    focusSlot(props.length - 1)
  } else if (event.key === ' ') {
    event.preventDefault()
  }
}

function handlePaste(index: number, event: ClipboardEvent) {
  event.preventDefault()
  const text = sanitize(event.clipboardData?.getData('text') ?? '')
  if (!text) return
  const firstEmpty = slots.value.findIndex(c => c === '')
  const start = text.length >= props.length ? 0 : (firstEmpty !== -1 && firstEmpty < index ? firstEmpty : index)
  distributeFrom(start, text)
}

function handleClick(index: number) {
  if (!slots.value[index]) {
    const firstEmpty = slots.value.findIndex(c => c === '')
    if (firstEmpty !== -1 && firstEmpty < index) {
      focusSlot(firstEmpty)
      return
    }
  }
  inputRefs.value[index]?.select()
}

function handleFocus(index: number) {
  inputRefs.value[index]?.select()
}
</script>

<template>
  <div
    class="invite-code-boxes"
    :class="{ 'is-invalid': invalid }"
    :style="{ '--code-length': length }"
    role="group"
    :aria-describedby="ariaDescribedby"
  >
    <input
      v-for="(char, index) in slots"
      :id="index === 0 ? id : undefined"
      :key="index"
      :ref="el => setInputRef(el, index)"
      :value="char"
      class="code-box"
      :class="{ 'is-filled': !!char }"
      type="text"
      inputmode="text"
      :maxlength="length"
      autocomplete="off"
      autocapitalize="characters"
      autocorrect="off"
      spellcheck="false"
      :disabled="disabled"
      :aria-label="`邀请码第 ${index + 1} 位`"
      :aria-invalid="invalid"
      @input="handleInput(index, $event)"
      @compositionend="handleCompositionEnd(index, $event)"
      @keydown="handleKeydown(index, $event)"
      @paste="handlePaste(index, $event)"
      @click="handleClick(index)"
      @focus="handleFocus(index)"
    />
  </div>
</template>

<style scoped>
.invite-code-boxes {
  display: grid;
  grid-template-columns: repeat(var(--code-length, 8), minmax(0, 1fr));
  gap: 8px;
  width: 100%;
}

.code-box {
  width: 100%;
  min-width: 0;
  height: 48px;
  padding: 0;
  text-align: center;
  font-family: var(--font-mono);
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  text-transform: uppercase;
  caret-color: var(--color-primary);
  color: var(--color-ink-primary);
  background: var(--color-surface-base);
  border: 1.5px solid var(--color-border-hairline);
  border-radius: var(--rounded-md);
  outline: none;
  transition:
    border-color var(--duration-fast) ease,
    box-shadow var(--duration-base) var(--ease-out),
    background-color var(--duration-fast) ease,
    transform var(--duration-fast) var(--ease-out);
}

.code-box.is-filled {
  background: var(--color-surface-raised);
  border-color: var(--color-border-strong);
}

.code-box:hover:not(:disabled):not(:focus) {
  border-color: var(--color-border-strong);
}

.code-box:focus,
.code-box:focus-visible {
  outline: none;
  background: var(--color-surface-raised);
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(26, 86, 50, 0.16);
  transform: translateY(-1px);
}

.invite-code-boxes.is-invalid .code-box {
  border-color: var(--color-destructive);
  background: var(--color-destructive-tint);
}

.invite-code-boxes.is-invalid .code-box:focus,
.invite-code-boxes.is-invalid .code-box:focus-visible {
  box-shadow: 0 0 0 3px rgba(197, 48, 48, 0.16);
}

.code-box:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

@media (max-width: 420px) {
  .invite-code-boxes {
    gap: 5px;
  }

  .code-box {
    height: 42px;
    font-size: 16px;
    border-radius: var(--rounded-sm);
  }
}

@media (prefers-reduced-motion: reduce) {
  .code-box:focus,
  .code-box:focus-visible {
    transform: none;
  }
}
</style>
