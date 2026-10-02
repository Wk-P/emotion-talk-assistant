<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { Language } from '@/api/client'
import { saveLang } from '@/i18n/langPreference'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const session = useSessionStore()
const open = ref(false)
const toggleEl = ref<HTMLButtonElement | null>(null)
const panelPos = ref({ top: 0, left: 0 })
const PANEL_WIDTH = 220
const VIEWPORT_MARGIN = 8

// The panel is teleported to <body> (see template) so it isn't clipped by
// an ancestor's `overflow: hidden` — every top-level view gets that on wide
// screens for the floating-card look (see main.css), which would otherwise
// cut this dropdown off. Since it's no longer positioned relative to
// `.app-menu`, its coordinates are computed from the toggle button instead —
// and clamped to the viewport, since a right-aligned toggle on a narrow
// phone screen otherwise pushes `left: rect.right - 200` past the left edge
// with no matching clamp on the right, exactly the case that let this panel
// run off-screen when the account email was long enough to need the full
// panel width (see PANEL_WIDTH below).
async function toggle() {
  open.value = !open.value
  if (open.value) {
    await nextTick()
    const rect = toggleEl.value?.getBoundingClientRect()
    if (rect) {
      const maxLeft = window.innerWidth - PANEL_WIDTH - VIEWPORT_MARGIN
      const left = Math.min(Math.max(VIEWPORT_MARGIN, rect.right - PANEL_WIDTH), maxLeft)
      panelPos.value = { top: rect.bottom + 8, left }
    }
  }
}

function go(path: string) {
  open.value = false
  router.push(path)
}

function logout() {
  open.value = false
  // Clear the open chat too — it belongs to the account being signed out.
  auth.signOut(() => {
    session.reset()
    return router.push('/')
  })
}

function chooseLang(lang: Language) {
  locale.value = lang
  saveLang(lang)
}
</script>

<template>
  <div class="app-menu">
    <button
      ref="toggleEl"
      type="button"
      class="menu-toggle"
      :class="{ open }"
      :aria-expanded="open"
      :aria-label="t('toolbar.menu')"
      @click="toggle"
    >
      <span />
      <span />
      <span />
    </button>

    <Teleport to="body">
      <div v-if="open" class="app-menu-backdrop" @click="open = false" />
      <Transition name="menu-panel">
        <nav v-if="open" class="app-menu-panel" :style="{ top: panelPos.top + 'px', left: panelPos.left + 'px' }">
          <button type="button" class="app-menu-item" @click="go('/history')">{{ t('toolbar.history') }}</button>
          <button type="button" class="app-menu-item" @click="go('/records')">{{ t('toolbar.records') }}</button>
          <button type="button" class="app-menu-item" @click="go('/help')">{{ t('toolbar.help') }}</button>
          <button type="button" class="app-menu-item" @click="go('/privacy')">{{ t('privacy.title') }}</button>
          <button
            v-if="auth.user && auth.user.role !== 'user'"
            type="button"
            class="app-menu-item"
            @click="go('/admin')"
          >
            {{ t('admin.entry') }}
          </button>
          <div class="app-menu-divider" />
          <div class="app-menu-lang-row">
            <button
              type="button"
              class="app-menu-lang-btn"
              :class="{ active: locale === 'zh' }"
              @click="chooseLang('zh')"
            >
              中文
            </button>
            <button
              type="button"
              class="app-menu-lang-btn"
              :class="{ active: locale === 'ko' }"
              @click="chooseLang('ko')"
            >
              한국어
            </button>
          </div>
          <div class="app-menu-divider" />
          <button v-if="!auth.user" type="button" class="app-menu-item" @click="go('/login')">
            {{ t('toolbar.login') }}
          </button>
          <template v-else>
            <div class="app-menu-email">{{ auth.user.username }}</div>
            <button type="button" class="app-menu-item" @click="logout">{{ t('toolbar.logout') }}</button>
          </template>
        </nav>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.app-menu {
  position: relative;
}
.menu-toggle {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: none;
  background: transparent;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.menu-toggle:hover {
  background: var(--accent-soft);
}
.menu-toggle span {
  width: 18px;
  height: 2px;
  border-radius: 1px;
  background: var(--text);
  transition:
    transform 0.2s ease,
    opacity 0.2s ease;
}
.menu-toggle.open span:nth-child(1) {
  transform: translateY(6px) rotate(45deg);
}
.menu-toggle.open span:nth-child(2) {
  opacity: 0;
}
.menu-toggle.open span:nth-child(3) {
  transform: translateY(-6px) rotate(-45deg);
}
</style>

<style>
/* Unscoped: this panel and backdrop are teleported out of the component's
   DOM subtree, so Vue's scoped data-v attribute no longer reaches them. */
.app-menu-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
}
.app-menu-panel {
  position: fixed;
  z-index: 1001;
  width: 220px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: 6px;
  display: flex;
  flex-direction: column;
}
.app-menu-panel .app-menu-item {
  text-align: left;
  padding: 10px 12px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text);
}
.app-menu-panel .app-menu-item:hover {
  background: var(--accent-soft);
  color: var(--accent);
  transform: none;
}
.app-menu-panel .app-menu-email {
  padding: 6px 12px 2px;
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-menu-panel .app-menu-divider {
  height: 1px;
  background: var(--border);
  margin: 6px 4px;
}
.app-menu-lang-row {
  display: flex;
  gap: 6px;
  padding: 2px 4px;
}
.app-menu-lang-btn {
  flex: 1;
  padding: 7px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: none;
  font-size: 12.5px;
  color: var(--text-muted);
}
.app-menu-lang-btn.active {
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
  background: var(--accent-soft);
}
.menu-panel-enter-active,
.menu-panel-leave-active {
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
}
.menu-panel-enter-from,
.menu-panel-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.98);
}
</style>
