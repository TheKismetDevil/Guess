<script setup lang="ts">
withDefaults(defineProps<{
  skeleton?: boolean
}>(), {
  skeleton: false,
})
</script>

<template>
  <div class="race-card" :class="{ 'is-skeleton': skeleton }">
    <!-- Skeleton mode: mirrors the HomePage card (date block + title + tags) -->
    <template v-if="skeleton">
      <div class="ui-skeleton date-skeleton"></div>
      <div class="card-body">
        <div class="ui-skeleton title-skeleton"></div>
        <div class="tags-skeleton">
          <div v-for="i in 5" :key="i" class="ui-skeleton tag-skeleton"></div>
        </div>
        <div class="ui-skeleton meta-skeleton"></div>
      </div>
      <div class="ui-skeleton badge-skeleton"></div>
    </template>

    <!-- Normal mode (content slot for future stories) -->
    <template v-else>
      <slot />
    </template>
  </div>
</template>

<style scoped>
.race-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
  background: var(--color-surface-raised);
  border: 1px solid var(--color-border-hairline);
  border-radius: var(--rounded-lg);
  padding: var(--spacing-4) var(--spacing-5);
}

.race-card.is-skeleton {
  pointer-events: none;
}

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  min-width: 0;
}

.date-skeleton {
  flex-shrink: 0;
  width: 64px;
  height: 68px;
  border-radius: var(--rounded-md);
}

.title-skeleton {
  width: 45%;
  max-width: 220px;
  height: 20px;
}

.tags-skeleton {
  display: flex;
  gap: 6px;
}

.tag-skeleton {
  width: 40px;
  height: 18px;
  border-radius: var(--rounded-full);
}

.meta-skeleton {
  width: 60%;
  max-width: 260px;
  height: 12px;
}

.badge-skeleton {
  flex-shrink: 0;
  width: 64px;
  height: 22px;
  border-radius: var(--rounded-full);
}

@media (max-width: 767px) {
  .race-card {
    padding: var(--spacing-3);
    gap: var(--spacing-3);
  }

  .date-skeleton {
    width: 54px;
  }

  .badge-skeleton {
    display: none;
  }
}
</style>
