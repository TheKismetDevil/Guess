<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  /** Opaque key from the API (`avatar_key`); falls back to the initial when missing or broken. */
  avatarKey?: string | null
  name: string
  size?: number
}>(), { avatarKey: null, size: 28 })

const failed = ref(false)
watch(() => props.avatarKey, () => { failed.value = false })

const src = computed(() => (props.avatarKey && !failed.value ? `/api/v1/avatars/${encodeURIComponent(props.avatarKey)}` : null))
const initial = computed(() => props.name.trim().charAt(0).toUpperCase() || '?')
</script>

<template>
  <span class="user-avatar" :style="{ '--avatar-size': `${size}px` }" aria-hidden="true">
    <img v-if="src" :src="src" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" @error="failed = true" />
    <template v-else>{{ initial }}</template>
  </span>
</template>

<style scoped>
.user-avatar {
  flex-shrink: 0;
  display: inline-grid;
  place-items: center;
  width: var(--avatar-size);
  height: var(--avatar-size);
  border-radius: 50%;
  overflow: hidden;
  font-family: var(--font-display);
  font-size: calc(var(--avatar-size) / 2);
  font-weight: 700;
  line-height: 1;
  color: var(--color-primary, #1A5632);
  background: var(--color-primary-tint, #EDF5EF);
}

.user-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
