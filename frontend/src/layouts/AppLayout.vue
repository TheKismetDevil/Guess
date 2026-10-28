<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/authStore'
import BrandMark from '@/components/BrandMark.vue'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const isAdminDropdownOpen = ref(false)
const scrollContainer = ref<HTMLElement | null>(null)
const isScrolled = ref(false)

const userInitial = computed(() => authStore.user?.username?.charAt(0).toUpperCase() ?? '')

interface AdminNavItem {
  to: string
  label: string
}

const adminNavItems: AdminNavItem[] = [
  { to: '/admin/horses', label: '马匹管理' },
  { to: '/admin/invite-codes', label: '用户管理' }
]

function toggleAdminDropdown() {
  isAdminDropdownOpen.value = !isAdminDropdownOpen.value
}

function closeAdminDropdown() {
  isAdminDropdownOpen.value = false
}

function handleLogout() {
  authStore.logout()
  router.push('/')
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isAdminDropdownOpen.value) {
    closeAdminDropdown()
  }
}

function handleClickOutside(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.admin-dropdown-area')) {
    closeAdminDropdown()
  }
}

function handleScroll() {
  isScrolled.value = (scrollContainer.value?.scrollTop ?? 0) > 8
}

/** The old page has left and the new one is not painted yet — start it at the top. */
function resetScroll() {
  if (scrollContainer.value) scrollContainer.value.scrollTop = 0
  isScrolled.value = false
}

watch(() => route.fullPath, () => {
  closeAdminDropdown()
})

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
  scrollContainer.value?.addEventListener('scroll', handleScroll, { passive: true })
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
  scrollContainer.value?.removeEventListener('scroll', handleScroll)
})

/** Normalize route path for consistent matching */
function normalizedPath(path: string): string {
  return path.replace(/\/+$/, '') || '/'
}

function isAdminItemActive(item: AdminNavItem): boolean {
  const currentPath = normalizedPath(route.path)
  const itemPath = normalizedPath(item.to)
  if (itemPath === '/admin') {
    return currentPath === '/admin'
  }
  return currentPath.startsWith(itemPath)
}

const isAdminSectionActive = computed(() => route.path.startsWith('/admin'))
</script>

<template>
  <div class="app-layout">
    <!-- Desktop Header (≥768px) -->
    <header class="desktop-header" :class="{ 'is-scrolled': isScrolled }">
      <div class="header-inner">
        <router-link to="/" class="logo" aria-label="Guess 首页">
          <span class="logo-badge"><BrandMark :size="22" /></span>
          <span class="logo-text">Guess</span>
          <span class="logo-sub">赛马竞猜</span>
        </router-link>

        <nav class="nav-links">
          <router-link to="/" class="nav-link">首页</router-link>
          <router-link to="/leaderboard" class="nav-link">排行榜</router-link>

          <!-- Admin Dropdown (desktop) -->
          <div v-if="authStore.isAdmin" class="admin-dropdown-area">
            <button
              class="nav-link admin-dropdown-trigger"
              :class="{ 'dropdown-open': isAdminDropdownOpen, 'section-active': isAdminSectionActive }"
              @click.stop="toggleAdminDropdown"
              :aria-expanded="isAdminDropdownOpen"
              aria-haspopup="true"
            >
              管理
              <svg class="chevron-icon" :class="{ open: isAdminDropdownOpen }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            <transition name="dropdown-fade">
              <nav v-if="isAdminDropdownOpen" class="admin-dropdown" role="menu">
                <router-link
                  v-for="item in adminNavItems"
                  :key="item.to"
                  :to="item.to"
                  class="admin-dropdown-item"
                  :class="{ active: isAdminItemActive(item) }"
                  role="menuitem"
                  @click="closeAdminDropdown"
                >
                  <svg class="dropdown-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <template v-if="item.to === '/admin/horses'">
                      <path d="M18 4h-3a3 3 0 0 0-3 3v0a3 3 0 0 0 3 3h3a3 3 0 0 0 3-3v0a3 3 0 0 0-3-3z" />
                      <path d="M6 4h3a3 3 0 0 1 3 3v0a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v0a3 3 0 0 1 3-3z" />
                      <path d="M18 14h-3a3 3 0 0 0-3 3v0a3 3 0 0 0 3 3h3a3 3 0 0 0 3-3v0a3 3 0 0 0-3-3z" />
                      <path d="M6 14h3a3 3 0 0 1 3 3v0a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v0a3 3 0 0 1 3-3z" />
                    </template>
                    <template v-else>
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </template>
                  </svg>
                  {{ item.label }}
                </router-link>
              </nav>
            </transition>
          </div>
        </nav>

        <div class="user-area">
          <template v-if="authStore.isLoggedIn">
            <span class="user-chip">
              <span class="avatar" aria-hidden="true">{{ userInitial }}</span>
              <span class="username">{{ authStore.user?.username }}</span>
              <span v-if="authStore.isAdmin" class="role-tag">管理员</span>
            </span>
            <button class="logout-btn" @click="handleLogout">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              退出
            </button>
          </template>
          <router-link v-else to="/login" class="login-btn">登录</router-link>
        </div>
      </div>
    </header>

    <!-- Scroll Container -->
    <div ref="scrollContainer" class="scroll-container">
      <!-- Main Content -->
      <main class="main-content">
        <RouterView v-slot="{ Component, route: viewRoute }">
          <Transition name="page" mode="out-in" @before-enter="resetScroll">
            <component :is="Component" :key="viewRoute.path" />
          </Transition>
        </RouterView>
      </main>
    </div>

    <!-- Mobile Bottom Nav (<768px) -->
    <nav class="mobile-bottom-nav" aria-label="主导航">
      <router-link to="/" class="nav-item">
        <span class="nav-icon-wrap">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
        </span>
        <span class="nav-label">首页</span>
      </router-link>

      <router-link to="/leaderboard" class="nav-item">
        <span class="nav-icon-wrap">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5C7 4 6 7 6 9z" />
            <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5C17 4 18 7 18 9z" />
            <path d="M4 22h16" />
            <path d="M10 22V14h4v8" />
            <path d="M12 14c-1.5 0-3-2-3-4V7c0-1.1.9-2 2-2h2a2 2 0 0 1 2 2v3c0 2-1.5 4-3 4z" />
          </svg>
        </span>
        <span class="nav-label">排行榜</span>
      </router-link>

      <!-- Admin Dropdown (mobile) -->
      <div v-if="authStore.isAdmin" class="admin-dropdown-area mobile-dropdown-area">
        <button
          class="nav-item"
          :class="{ 'active-dropdown': isAdminDropdownOpen || isAdminSectionActive }"
          @click.stop="toggleAdminDropdown"
          :aria-expanded="isAdminDropdownOpen"
          aria-haspopup="true"
          type="button"
        >
          <span class="nav-icon-wrap">
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
            </svg>
          </span>
          <span class="nav-label">管理</span>
        </button>

        <transition name="dropdown-fade">
          <nav v-if="isAdminDropdownOpen" class="admin-dropdown mobile-dropdown" role="menu">
            <router-link
              v-for="item in adminNavItems"
              :key="item.to"
              :to="item.to"
              class="admin-dropdown-item"
              :class="{ active: isAdminItemActive(item) }"
              role="menuitem"
              @click="closeAdminDropdown"
            >
              <svg class="dropdown-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <template v-if="item.to === '/admin/horses'">
                  <path d="M18 4h-3a3 3 0 0 0-3 3v0a3 3 0 0 0 3 3h3a3 3 0 0 0 3-3v0a3 3 0 0 0-3-3z" />
                  <path d="M6 4h3a3 3 0 0 1 3 3v0a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v0a3 3 0 0 1 3-3z" />
                  <path d="M18 14h-3a3 3 0 0 0-3 3v0a3 3 0 0 0 3 3h3a3 3 0 0 0 3-3v0a3 3 0 0 0-3-3z" />
                  <path d="M6 14h3a3 3 0 0 1 3 3v0a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3v0a3 3 0 0 1 3-3z" />
                </template>
                <template v-else>
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </template>
              </svg>
              {{ item.label }}
            </router-link>
          </nav>
        </transition>
      </div>

      <!-- Auth (mobile) -->
      <!-- Login button -->
      <router-link v-if="!authStore.isLoggedIn" to="/login" class="nav-item auth-nav-item">
        <span class="nav-icon-wrap">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
            <polyline points="10 17 15 12 10 7" />
            <line x1="15" y1="12" x2="3" y2="12" />
          </svg>
        </span>
        <span class="nav-label">登录</span>
      </router-link>
      <!-- Logout button -->
      <div v-else class="nav-item auth-nav-item logout-nav-item" @click="handleLogout">
        <span class="nav-icon-wrap">
          <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </span>
        <span class="nav-label">退出</span>
      </div>
    </nav>
  </div>
</template>

<style scoped>
/* =========================================
   Desktop Header (≥768px)
   ========================================= */

.desktop-header {
  display: none;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: var(--header-height);
  background: var(--gradient-brand);
  color: #fff;
  z-index: 100;
  transition: box-shadow var(--duration-base) ease;
}

/* Thin gold "finish line" under the header */
.desktop-header::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(212, 184, 74, 0.85) 20%, rgba(212, 184, 74, 0.85) 80%, transparent);
  opacity: 0.7;
}

.desktop-header.is-scrolled {
  box-shadow: 0 10px 24px -14px rgba(13, 58, 31, 0.6);
}

.header-inner {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: 0 var(--spacing-4);
  height: 100%;
  display: flex;
  align-items: center;
  gap: var(--spacing-8);
}

.logo {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  color: #fff;
  text-decoration: none;
  white-space: nowrap;
}

.logo-badge {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18);
  transition: transform var(--duration-slow) var(--ease-spring), background var(--duration-fast) ease;
}

.logo:hover .logo-badge {
  transform: rotate(-14deg) scale(1.08);
  background: rgba(255, 255, 255, 0.16);
}

.logo-text {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.logo-sub {
  padding: 1px 8px;
  border-radius: var(--rounded-full);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.78);
  background: rgba(255, 255, 255, 0.08);
}

.nav-links {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
}

.nav-link {
  position: relative;
  padding: var(--spacing-2) var(--spacing-3);
  border-radius: var(--rounded-sm);
  color: rgba(255, 255, 255, 0.78);
  font-size: var(--text-body-sm);
  transition: background var(--duration-fast) ease, color var(--duration-fast) ease;
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

/* Gold underline that grows under the active link */
.nav-link::after {
  content: '';
  position: absolute;
  left: var(--spacing-3);
  right: var(--spacing-3);
  bottom: 2px;
  height: 2px;
  border-radius: 2px;
  background: var(--gradient-gold);
  transform: scaleX(0);
  transition: transform var(--duration-slow) var(--ease-out);
}

.nav-link:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}

.nav-link.router-link-active,
.nav-link.router-link-exact-active,
.nav-link.section-active {
  color: #fff;
  font-weight: 600;
}

.nav-link.router-link-active::after,
.nav-link.router-link-exact-active::after,
.nav-link.section-active::after {
  transform: scaleX(1);
}

/* Admin Dropdown Trigger - desktop */
.admin-dropdown-trigger {
  position: relative;
}

.admin-dropdown-trigger.dropdown-open {
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.chevron-icon {
  width: 12px;
  height: 12px;
  transition: transform var(--duration-base) var(--ease-out);
}

.chevron-icon.open {
  transform: rotate(180deg);
}

.user-area {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
}

.user-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: 3px 10px 3px 3px;
  border-radius: var(--rounded-full);
  background: rgba(255, 255, 255, 0.08);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14);
}

.avatar {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--color-primary-dark);
  background: var(--gradient-gold);
}

.username {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: #fff;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-tag {
  padding: 0 6px;
  border-radius: var(--rounded-full);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-accent-light);
  box-shadow: inset 0 0 0 1px rgba(212, 184, 74, 0.5);
}

.login-btn {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: var(--spacing-1) var(--spacing-5);
  border-radius: var(--rounded-full);
  background: var(--gradient-gold);
  color: #fff;
  font-size: var(--text-body-sm);
  font-weight: 600;
  text-decoration: none;
  box-shadow: 0 6px 14px -8px rgba(0, 0, 0, 0.6);
  transition: transform var(--duration-fast) var(--ease-out), filter var(--duration-fast) ease;
}

.login-btn:hover {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.login-btn:active {
  transform: scale(0.96);
}

.logout-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: var(--spacing-1) var(--spacing-3);
  border-radius: var(--rounded-full);
  background: transparent;
  color: rgba(255, 255, 255, 0.8);
  font-size: var(--text-body-sm);
  border: 1px solid rgba(255, 255, 255, 0.2);
  cursor: pointer;
  transition: background var(--duration-fast) ease, color var(--duration-fast) ease;
  min-height: 32px;
}

.logout-btn svg {
  width: 14px;
  height: 14px;
}

.logout-btn:hover {
  background: rgba(255, 255, 255, 0.14);
  color: #fff;
}

/* =========================================
   Admin Dropdown (desktop & mobile)
   ========================================= */

.admin-dropdown-area {
  position: relative;
}

.admin-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  min-width: 180px;
  max-height: 360px;
  overflow-y: auto;
  background: #fff;
  border-radius: var(--rounded-md);
  box-shadow: var(--shadow-xl);
  border: 1px solid var(--color-border-hairline);
  padding: var(--spacing-1);
  z-index: 200;
  transform-origin: top left;
}

.mobile-dropdown-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  position: relative;
}

.mobile-dropdown-area .nav-item {
  flex: 1;
  width: 100%;
  padding: 0;
  margin: 0;
  background: none;
  border: none;
  cursor: pointer;
  font-family: inherit;
}

.mobile-dropdown {
  position: absolute;
  top: auto;
  bottom: calc(100% + 10px);
  left: 50%;
  transform: translateX(-50%);
  transform-origin: bottom center;
  min-width: 200px;
  z-index: 200;
  isolation: isolate;
}

.admin-dropdown-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-2) var(--spacing-3);
  border-radius: var(--rounded-sm);
  color: var(--color-ink-primary);
  font-size: var(--text-body-sm);
  text-decoration: none;
  transition: background var(--duration-fast) ease, color var(--duration-fast) ease, padding var(--duration-base) var(--ease-out);
}

.admin-dropdown-item:hover {
  background: var(--color-surface-base);
  color: var(--color-primary);
  padding-left: var(--spacing-4);
}

.admin-dropdown-item.active {
  background: var(--color-primary-tint);
  color: var(--color-primary);
  font-weight: 600;
}

.dropdown-item-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

/* Dropdown transition */
.dropdown-fade-enter-active,
.dropdown-fade-leave-active {
  transition: opacity var(--duration-base) ease, transform var(--duration-base) var(--ease-out);
}

.dropdown-fade-enter-from,
.dropdown-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.96);
}

.mobile-dropdown.dropdown-fade-enter-from,
.mobile-dropdown.dropdown-fade-leave-to {
  transform: translateX(-50%) translateY(6px) scale(0.96);
}

/* =========================================
   Main Content + page transition
   ========================================= */

.main-content {
  min-height: calc(100dvh - var(--bottom-nav-height) - env(safe-area-inset-bottom, 0));
  padding-bottom: calc(var(--bottom-nav-height) + env(safe-area-inset-bottom, 0));
}

/* Opacity only: a transform on the page root would turn it into the
   containing block for the page's position:fixed FAB / scroll hints. */
.page-enter-active {
  transition: opacity var(--duration-base) var(--ease-out);
}

.page-leave-active {
  transition: opacity 120ms ease;
}

.page-enter-from,
.page-leave-to {
  opacity: 0;
}

@media (min-width: 768px) {
  .main-content {
    min-height: calc(100vh - var(--header-height));
    padding-bottom: 0;
    max-width: var(--max-width);
    margin: 0 auto;
    padding-left: var(--spacing-4);
    padding-right: var(--spacing-4);
  }
}

/* =========================================
   Mobile Bottom Nav (<768px)
   ========================================= */

.mobile-bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: calc(var(--bottom-nav-height) + env(safe-area-inset-bottom, 0px));
  padding-bottom: env(safe-area-inset-bottom, 0px);
  display: flex;
  align-items: stretch;
  background: rgba(255, 255, 255, 0.86);
  -webkit-backdrop-filter: saturate(180%) blur(16px);
  backdrop-filter: saturate(180%) blur(16px);
  border-top: 1px solid rgba(212, 220, 208, 0.8);
  box-shadow: 0 -8px 24px -18px rgba(13, 58, 31, 0.35);
  z-index: 100;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  color: var(--color-ink-secondary);
  text-decoration: none;
  font-size: 10px;
  font-weight: 500;
  -webkit-tap-highlight-color: transparent;
  transition: color var(--duration-fast) ease;
}

.nav-icon-wrap {
  position: relative;
  display: grid;
  place-items: center;
  width: 52px;
  height: 28px;
}

/* Pill behind the active icon */
.nav-icon-wrap::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: var(--rounded-full);
  background: var(--color-primary-tint-strong);
  opacity: 0;
  transform: scaleX(0.4);
  transition: opacity var(--duration-base) ease, transform var(--duration-slow) var(--ease-spring);
}

.nav-item:hover {
  color: var(--color-primary);
}

.nav-item:active .nav-icon {
  transform: scale(0.88);
}

.nav-item.router-link-active,
.nav-item.router-link-exact-active,
.mobile-dropdown-area .nav-item.active-dropdown {
  color: var(--color-primary);
  font-weight: 600;
}

.nav-item.router-link-active .nav-icon-wrap::before,
.nav-item.router-link-exact-active .nav-icon-wrap::before,
.nav-item.active-dropdown .nav-icon-wrap::before {
  opacity: 1;
  transform: scaleX(1);
}

.nav-icon {
  position: relative;
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  transition: transform var(--duration-fast) var(--ease-spring);
}

.nav-label {
  line-height: 1;
}

/* Auth nav item — clickable bottom tab */
.auth-nav-item {
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}

/* =========================================
   Responsive
   ========================================= */

/* Desktop: scroll container is a fixed composited layer */
@media (min-width: 768px) {
  .scroll-container {
    position: fixed;
    top: var(--header-height);
    left: 0;
    right: 0;
    bottom: 0;
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  .desktop-header {
    display: block;
  }

  .mobile-bottom-nav {
    display: none;
  }
}

/* Mobile: scroll container fills the viewport with bottom-nav offset.
   Must use overflow-y: auto so getScrollContainer() finds a proper
   scrolling element for auto-scroll during drag operations. */
@media (max-width: 767px) {
  .scroll-container {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: calc(var(--bottom-nav-height) + env(safe-area-inset-bottom, 0px));
    overflow-y: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-gutter: stable;
  }
}

/* =========================================
   Reduced Motion
   ========================================= */

@media (prefers-reduced-motion: reduce) {
  .dropdown-fade-enter-active,
  .dropdown-fade-leave-active,
  .page-enter-active,
  .page-leave-active {
    transition: none;
  }
}
</style>
