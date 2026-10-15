<script setup lang="ts">
/**
 * RaceTags — the six race tags as chips. Grade and surface get their own
 * colours so G1s and dirt races are recognisable at a glance.
 */
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  race: {
    race_grade: string
    age_range: string
    sex_restriction: string
    country: string
    distance: string
    surface: string
  }
  onDark?: boolean
}>(), {
  onDark: false,
})

const gradeClass = computed(() => {
  switch (props.race.race_grade) {
    case 'G1': return 'grade-g1'
    case 'G2': return 'grade-g2'
    case 'G3': return 'grade-g3'
    case 'JPN1':
    case 'JPN2': return 'grade-jpn'
    case '自定义': return 'grade-custom'
    default: return ''
  }
})

const surfaceClass = computed(() => {
  switch (props.race.surface) {
    case '草地': return 'surface-turf'
    case '泥地': return 'surface-dirt'
    case '全天候': return 'surface-aw'
    default: return ''
  }
})
</script>

<template>
  <div class="race-tags" :class="{ 'on-dark': onDark }">
    <span class="ui-chip tag-grade" :class="gradeClass">{{ race.race_grade }}</span>
    <span class="ui-chip">{{ race.age_range }}</span>
    <span v-if="race.sex_restriction !== '无'" class="ui-chip">{{ race.sex_restriction }}</span>
    <span class="ui-chip">{{ race.country }}</span>
    <span class="ui-chip">{{ race.distance }}</span>
    <span class="ui-chip" :class="surfaceClass">
      <span class="surface-dot" aria-hidden="true"></span>{{ race.surface }}
    </span>
  </div>
</template>

<style scoped>
.race-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-grade {
  font-weight: 700;
  letter-spacing: 0.04em;
}

.grade-g1 {
  color: #FFFFFF;
  background: var(--gradient-gold);
  border-color: transparent;
  box-shadow: 0 2px 8px -3px rgba(184, 150, 12, 0.7);
}

.grade-g2 {
  color: #FFFFFF;
  background: var(--gradient-silver);
  border-color: transparent;
}

.grade-g3 {
  color: #FFFFFF;
  background: var(--gradient-bronze);
  border-color: transparent;
}

.grade-jpn {
  color: #FFFFFF;
  background: linear-gradient(135deg, #3A9C8F, #23756B);
  border-color: transparent;
}

.grade-custom {
  color: #5B3FA8;
  background: #F1ECFB;
  border-color: #DCD0F5;
}

.surface-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-ink-disabled);
}

.surface-turf .surface-dot { background: #3FA35F; }
.surface-dirt .surface-dot { background: #A0703F; }
.surface-aw .surface-dot { background: #6C7FA0; }

/* Translucent chips for the race-detail hero banner */
.on-dark .ui-chip:not(.grade-g1):not(.grade-g2):not(.grade-g3):not(.grade-jpn) {
  color: rgba(255, 255, 255, 0.92);
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.22);
}
</style>
