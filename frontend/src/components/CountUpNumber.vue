<script setup lang="ts">
/** CountUpNumber — renders a number that counts up to its value. */
import { useCountUp } from '@/composables/useCountUp'

const props = withDefaults(defineProps<{
  value: number
  duration?: number
}>(), {
  duration: 900,
})

const display = useCountUp(() => props.value, props.duration)
</script>

<template>
  <span class="count-up">{{ display }}</span>
</template>

<style scoped>
.count-up {
  font-variant-numeric: tabular-nums;
}
</style>
