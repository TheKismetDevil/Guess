<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useId } from 'vue'
import type { LeaderboardSort } from '@/types/leaderboard'

const model = defineModel<LeaderboardSort>({ required: true })
const emit = defineEmits<{ change: [] }>()
const options: { value: LeaderboardSort; label: string }[] = [
  { value: 'total_points', label: '按总分排行' },
  { value: 'avg_points', label: '按场均排行' },
]
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const open = ref(false)
const activeIndex = ref(0)
const id = `leaderboard-sort-${useId()}`
const selectedIndex = computed(() => options.findIndex(option => option.value === model.value))
const selectedLabel = computed(() => options[selectedIndex.value]?.label ?? options[0]!.label)

function openMenu(index = selectedIndex.value) {
  activeIndex.value = Math.max(0, index)
  open.value = true
}
function choose(index: number) {
  const option = options[index]
  if (!option) return
  open.value = false
  trigger.value?.focus()
  if (model.value !== option.value) {
    model.value = option.value
    emit('change')
  }
}
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Tab') { open.value = false; return }
  if (event.key === 'Escape') {
    if (open.value) { event.preventDefault(); open.value = false }
    return
  }
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(event.key)) return
  event.preventDefault()
  if (event.key === 'Home' || event.key === 'End') {
    openMenu(event.key === 'Home' ? 0 : options.length - 1)
  } else if (!open.value) {
    openMenu()
  } else if (event.key === 'Enter' || event.key === ' ') {
    choose(activeIndex.value)
  } else {
    activeIndex.value = (activeIndex.value + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length
  }
}
function onOutsidePointer(event: PointerEvent) {
  if (!root.value?.contains(event.target as Node)) open.value = false
}
function onFocusout(event: FocusEvent) {
  if (!root.value?.contains(event.relatedTarget as Node | null)) open.value = false
}
onMounted(() => document.addEventListener('pointerdown', onOutsidePointer))
onUnmounted(() => document.removeEventListener('pointerdown', onOutsidePointer))
</script>

<template>
  <div ref="root" class="sort-control" @focusout="onFocusout">
    <span :id="`${id}-label`" class="sort-label">排序方式</span>
    <div class="sort-dropdown">
      <button ref="trigger" type="button" class="sort-trigger" :class="{ 'is-open': open }"
        role="combobox" aria-haspopup="listbox" :aria-expanded="open"
        :aria-controls="`${id}-list`" :aria-labelledby="`${id}-label ${id}-value`"
        :aria-activedescendant="open ? `${id}-option-${activeIndex}` : undefined"
        @click="open ? open = false : openMenu()" @keydown="onKeydown">
        <span :id="`${id}-value`">{{ selectedLabel }}</span>
        <svg class="sort-chevron" :class="{ rotated: open }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9" /></svg>
      </button>
      <Transition name="sort-menu">
        <ul v-if="open" :id="`${id}-list`" class="sort-options" role="listbox" :aria-labelledby="`${id}-label`" @pointerdown.prevent>
          <li v-for="(option, index) in options" :id="`${id}-option-${index}`" :key="option.value"
            role="option" :aria-selected="model === option.value" class="sort-option"
            :class="{ selected: model === option.value, active: activeIndex === index }"
            @pointerenter="activeIndex = index" @click="choose(index)">
            <span>{{ option.label }}</span>
            <svg v-if="model === option.value" class="sort-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="5 12 10 17 19 7" /></svg>
          </li>
        </ul>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.sort-control { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 600; }
.sort-label { color: var(--color-ink-secondary); white-space: nowrap; }
.sort-dropdown { position: relative; }
.sort-trigger { display: flex; align-items: center; justify-content: space-between; gap: 18px; min-width: 156px; min-height: 42px; padding: 10px 14px; border: 1px solid var(--color-border-strong); border-radius: var(--rounded-md); background: var(--color-surface-raised); box-shadow: var(--shadow-sm); color: var(--color-ink-primary); font: inherit; transition: border-color var(--duration-fast) ease, box-shadow var(--duration-fast) ease; }
.sort-trigger:hover, .sort-trigger.is-open { border-color: var(--color-primary); }
.sort-trigger.is-open { box-shadow: 0 0 0 3px rgba(26, 86, 50, 0.1); }
.sort-chevron { flex-shrink: 0; width: 18px; height: 18px; color: var(--color-primary); transition: transform var(--duration-fast) ease; }
.sort-chevron.rotated { transform: rotate(180deg); }
.sort-options { position: absolute; z-index: 300; left: 0; top: calc(100% + 8px); min-width: 100%; padding: 6px; margin: 0; list-style: none; border: 1px solid var(--color-border-hairline); border-radius: var(--rounded-lg); background: var(--color-surface-raised); box-shadow: var(--shadow-xl); transform-origin: top center; }
.sort-option { display: flex; align-items: center; justify-content: space-between; gap: 18px; min-height: 42px; padding: 10px 12px; border-radius: var(--rounded-sm); white-space: nowrap; font-size: 14px; font-weight: 500; color: var(--color-ink-primary); cursor: pointer; transition: background var(--duration-fast) ease; }
.sort-option.selected { background: var(--color-primary-tint); color: var(--color-primary); font-weight: 700; }
.sort-option.active { background: var(--color-primary-tint-strong); }
.sort-check { width: 16px; height: 16px; flex-shrink: 0; color: var(--color-primary); }
.sort-menu-enter-active, .sort-menu-leave-active { transition: opacity var(--duration-fast) ease, transform var(--duration-fast) ease; }
.sort-menu-enter-from, .sort-menu-leave-to { opacity: 0; transform: translateY(-4px); }
@media (prefers-reduced-motion: reduce) { .sort-chevron, .sort-menu-enter-active, .sort-menu-leave-active { transition: none; } }
</style>
