<script setup lang="ts">
import { onMounted } from 'vue'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/authStore'

const authStore = useAuthStore()

onMounted(() => {
  authStore.restoreSession()
})
</script>

<template>
  <!-- AppLayout owns the RouterView so it can animate page changes and
       reset its scroll container between pages. -->
  <AppLayout />
</template>
