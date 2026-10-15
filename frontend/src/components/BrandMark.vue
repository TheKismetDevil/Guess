<script setup lang="ts">
/** BrandMark — gold horseshoe logo used in the header and auth pages. */
import { useId } from 'vue'

withDefaults(defineProps<{
  size?: number
}>(), {
  size: 28,
})

// Per-instance gradient id: a url(#id) that resolves to a copy inside a
// display:none header would not paint.
const gradientId = `brand-mark-gold-${useId()}`
</script>

<template>
  <svg
    class="brand-mark"
    :width="size"
    :height="size"
    viewBox="0 0 32 32"
    fill="none"
    aria-hidden="true"
  >
    <defs>
      <linearGradient :id="gradientId" x1="6" y1="4" x2="26" y2="28" gradientUnits="userSpaceOnUse">
        <stop offset="0" stop-color="#F1D77A" />
        <stop offset="0.55" stop-color="#C9A21A" />
        <stop offset="1" stop-color="#9C7E08" />
      </linearGradient>
    </defs>
    <path
      d="M9 5.5v10a7 7 0 0 0 14 0v-10"
      :stroke="`url(#${gradientId})`"
      stroke-width="5"
      stroke-linecap="round"
    />
    <g fill="#0D3A1F" opacity="0.55">
      <circle cx="9" cy="9.5" r="1" />
      <circle cx="9" cy="14.5" r="1" />
      <circle cx="23" cy="9.5" r="1" />
      <circle cx="23" cy="14.5" r="1" />
      <circle cx="11.6" cy="20.6" r="1" />
      <circle cx="20.4" cy="20.6" r="1" />
    </g>
  </svg>
</template>

<style scoped>
.brand-mark {
  flex-shrink: 0;
  display: block;
}
</style>
