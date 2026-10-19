<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, provide, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppSidebar from '@/components/AppSidebar.vue'
import AdminSidebar from '@/components/admin/AdminSidebar.vue'

// The one shell for both sides — participant pages and the admin pages
// (/admin/…), which get their own sidebar and color (html.admin-area in
// main.css, set on <html> so dialogs teleported to <body> follow it). Wide screens (>=960px): the
// sidebar stays put on the left and only the content on the right changes.
// Narrow: a top bar with a menu button that slides the same sidebar in.
// The chat draws its own top bar (it has an export button there), so it gets
// openNav via inject and this bar is left out on that page.
const { t } = useI18n()
const route = useRoute()
const auth = useAuthStore()
const router = useRouter()

// Signed out (here or in another tab's expired token) while on a page that
// needs an account: the router guard only runs on navigation, so send them
// to the login page from here.
watch(
  () => auth.user,
  (user) => {
    if (!user && auth.ready && route.meta.requiresAuth) router.replace({ path: '/login' })
  },
)
const navOpen = ref(false)
const openNav = () => (navOpen.value = true)
provide('openNav', openNav)

const isAdmin = computed(() => route.path.startsWith('/admin'))
watch(isAdmin, (on) => document.documentElement.classList.toggle('admin-area', on), { immediate: true })
onBeforeUnmount(() => document.documentElement.classList.remove('admin-area'))

// The content area scrolls, not the window, so the router's scrollBehavior
// can't reach it: back to the top on each page, or to #anchor if given.
const contentEl = ref<HTMLElement | null>(null)
watch(
  () => route.fullPath,
  async (_, old) => {
    navOpen.value = false
    await nextTick()
    const target = route.hash ? document.querySelector(route.hash) : null
    if (target) target.scrollIntoView()
    else if (old !== undefined && contentEl.value) contentEl.value.scrollTop = 0
  },
)
</script>

<template>
  <div class="app-layout">
    <div v-if="navOpen" class="nav-backdrop" @click="navOpen = false" />
    <AdminSidebar v-if="isAdmin" class="layout-sidebar" :class="{ open: navOpen }" />
    <AppSidebar v-else class="layout-sidebar" :class="{ open: navOpen }" />

    <div ref="contentEl" class="layout-content">
      <header v-if="route.name !== 'chat'" class="layout-topbar">
        <button type="button" class="menu-btn" :aria-label="t('toolbar.menu')" @click="openNav">
          <span /><span /><span />
        </button>
        <span class="topbar-title">{{ t('app.title') }}</span>
        <span v-if="isAdmin" class="topbar-badge">{{ t('admin.badge') }}</span>
      </header>
      <!-- An admin on the participant side: say so, with the way back. -->
      <div v-if="!isAdmin && auth.user && auth.user.role !== 'user'" class="admin-hint" role="note">
        <span>{{ t('admin.viewingUserSite') }}</span>
        <RouterLink to="/admin">{{ t('admin.backToAdmin') }}</RouterLink>
      </div>
      <RouterView v-slot="{ Component }">
        <Transition name="route">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100dvh;
  background: var(--surface);
}
.layout-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.admin-hint {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 4px 12px;
  padding: 7px 16px;
  background: #e3f4f1;
  color: #0b5f56;
  font-size: 13px;
  text-align: center;
  flex-shrink: 0;
}
.admin-hint a {
  color: #0b7569;
  font-weight: 600;
}
.layout-topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 52px;
  padding: 8px 16px 8px 8px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: saturate(1.4) blur(10px);
  border-bottom: 1px solid var(--border);
}
.topbar-badge {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
}
.topbar-title {
  font-weight: 700;
  font-size: 15px;
}

/* Narrow: the sidebar is a drawer over the page. */
.layout-sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 60;
  width: min(280px, 85vw);
  transform: translateX(-100%);
  transition: transform 0.22s ease;
  box-shadow: var(--shadow-md);
}
.layout-sidebar.open {
  transform: none;
}
.nav-backdrop {
  position: fixed;
  inset: 0;
  z-index: 55;
  background: rgba(0, 0, 0, 0.3);
}
@media (prefers-reduced-motion: reduce) {
  .layout-sidebar {
    transition: none;
  }
}

/* Wide: the sidebar is part of the page and always there. */
@media (min-width: 960px) {
  .layout-sidebar {
    position: static;
    width: 240px;
    transform: none;
    box-shadow: none;
  }
  .nav-backdrop,
  .layout-topbar {
    display: none;
  }
}
</style>

<style>
/* The hamburger, shared with the chat's own top bar. */
.menu-btn {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border: none;
  border-radius: 10px;
  background: transparent;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.menu-btn:hover {
  background: var(--accent-soft);
}
.menu-btn span {
  width: 18px;
  height: 2px;
  border-radius: 1px;
  background: var(--text);
}
@media (min-width: 960px) {
  .menu-btn {
    display: none;
  }
}
</style>
