<script setup lang="ts">
/**
 * AuthShell — shared frame for login / register / reset-password:
 * drifting backdrop, brand mark, title and a card for the form.
 * Form controls inside use the global ui-* primitives (ui.css).
 */
import BrandMark from '@/components/BrandMark.vue'

defineProps<{
  title: string
  subtitle?: string
}>()
</script>

<template>
  <div class="auth-page">
    <div class="auth-backdrop" aria-hidden="true">
      <span class="blob blob-green"></span>
      <span class="blob blob-gold"></span>
      <svg class="auth-track" viewBox="0 0 600 400" preserveAspectRatio="none">
        <path d="M-40 330 C 160 250, 420 260, 640 120" />
        <path d="M-40 360 C 160 280, 420 290, 640 150" />
      </svg>
    </div>

    <div class="auth-card">
      <div class="auth-brand">
        <span class="auth-badge"><BrandMark :size="30" /></span>
        <h1 class="auth-title">{{ title }}</h1>
        <p v-if="subtitle" class="auth-subtitle">{{ subtitle }}</p>
      </div>

      <slot />

      <div v-if="$slots.footer" class="auth-footer">
        <slot name="footer" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  position: relative;
  isolation: isolate;
  min-height: calc(100dvh - var(--header-height));
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-8) var(--spacing-4);
}

/* Fixed so the decoration spans the viewport rather than the centred
   content column. */
.auth-backdrop {
  position: fixed;
  inset: 0;
  overflow: hidden;
  z-index: -1;
  pointer-events: none;
}

.blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.55;
  animation: blob-drift 18s var(--ease-in-out) infinite alternate;
}

.blob-green {
  width: 420px;
  height: 420px;
  top: -120px;
  right: -80px;
  background: radial-gradient(circle, rgba(45, 122, 79, 0.45), transparent 70%);
}

.blob-gold {
  width: 360px;
  height: 360px;
  bottom: -140px;
  left: -100px;
  background: radial-gradient(circle, rgba(212, 184, 74, 0.45), transparent 70%);
  animation-delay: -9s;
}

@keyframes blob-drift {
  from { transform: translate(0, 0) scale(1); }
  to { transform: translate(-40px, 30px) scale(1.12); }
}

.auth-track {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.auth-track path {
  fill: none;
  stroke: rgba(26, 86, 50, 0.06);
  stroke-width: 18;
}

.auth-card {
  width: 100%;
  max-width: 420px;
  padding: var(--spacing-8);
  border-radius: var(--rounded-xl);
  background: rgba(255, 255, 255, 0.92);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(212, 220, 208, 0.8);
  box-shadow: var(--shadow-xl);
  animation: dialog-in var(--duration-slow) var(--ease-out) backwards;
}

.auth-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: var(--spacing-6);
  text-align: center;
}

.auth-badge {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  margin-bottom: var(--spacing-3);
  border-radius: 18px;
  background: var(--gradient-brand);
  box-shadow: 0 12px 24px -12px rgba(13, 58, 31, 0.8);
  animation: pop-in var(--duration-slow) var(--ease-spring) 150ms backwards;
}

.auth-title {
  font-family: var(--font-display);
  font-size: 34px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--color-ink-primary);
}

.auth-subtitle {
  margin-top: var(--spacing-1);
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
}

.auth-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-2);
  margin-top: var(--spacing-5);
  font-size: var(--text-body-sm);
  color: var(--color-ink-secondary);
}

.auth-footer :slotted(a) {
  color: var(--color-primary);
  font-weight: 600;
  text-decoration: none;
  background-image: linear-gradient(currentColor, currentColor);
  background-size: 0 1px;
  background-position: 0 100%;
  background-repeat: no-repeat;
  transition: background-size var(--duration-base) var(--ease-out);
}

.auth-footer :slotted(a:hover) {
  background-size: 100% 1px;
}

@media (max-width: 767px) {
  .auth-page {
    min-height: calc(100dvh - 2 * var(--bottom-nav-height) - env(safe-area-inset-bottom, 0px));
    padding: var(--spacing-6) var(--spacing-4);
  }

  .auth-card {
    padding: var(--spacing-6) var(--spacing-5);
  }
}

@media (prefers-reduced-motion: reduce) {
  .blob {
    animation: none;
  }
}
</style>
