<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import AppMenu from '@/components/AppMenu.vue'
import LanguageSwitch from '@/components/LanguageSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'

// Shared top bar for every page except the chat (which has its own sidebar
// shell): brand on the left, site navigation and account on the right. On
// narrow screens the navigation collapses into AppMenu, as in the chat.
const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const session = useSessionStore()

const links = [
  { to: '/', label: 'site.nav.chat' },
  { to: '/history', label: 'toolbar.history' },
  { to: '/records', label: 'toolbar.records' },
  { to: '/reflection', label: 'reflection.title' },
  { to: '/help', label: 'toolbar.help' },
  { to: '/privacy', label: 'privacy.title' },
]

function logout() {
  auth.signOut(() => {
    session.reset()
    return router.push('/')
  })
}
</script>

<template>
  <header class="site-header">
    <RouterLink to="/" class="site-brand">
      <img src="/emotion-talk.png" alt="" />
      <span>{{ t('app.title') }}</span>
    </RouterLink>

    <nav class="site-nav" :aria-label="t('toolbar.menu')">
      <RouterLink v-for="link in links" :key="link.to" :to="link.to" :class="{ exact: link.to === '/' }">
        {{ t(link.label) }}
      </RouterLink>
      <RouterLink v-if="auth.user && auth.user.role !== 'user'" to="/admin">{{ t('admin.entry') }}</RouterLink>
    </nav>

    <div class="site-account">
      <LanguageSwitch />
      <template v-if="auth.user">
        <span class="site-user">{{ auth.user.username }}</span>
        <button type="button" class="btn-text" @click="logout">{{ t('toolbar.logout') }}</button>
      </template>
      <RouterLink v-else to="/login" class="btn-outline site-login">{{ t('toolbar.login') }}</RouterLink>
    </div>

    <AppMenu class="site-menu" />
  </header>
</template>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 24px;
  height: var(--site-header-h);
  padding: 0 16px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: saturate(1.4) blur(10px);
  border-bottom: 1px solid var(--border);
}
@media (min-width: 640px) {
  .site-header {
    padding: 0 32px;
  }
}
.site-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  color: var(--text);
  font-size: 15px;
  font-weight: 700;
  text-decoration: none;
}
.site-brand img {
  width: 30px;
  height: 30px;
  border-radius: 8px;
}
.site-nav,
.site-account {
  display: none;
}
.site-menu {
  margin-left: auto;
}
@media (min-width: 960px) {
  .site-nav {
    display: flex;
    align-items: stretch;
    align-self: stretch;
    gap: 4px;
    flex: 1;
  }
  .site-nav a {
    display: flex;
    align-items: center;
    padding: 0 12px;
    border-bottom: 2px solid transparent;
    color: var(--text-muted);
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;
    transition:
      color 0.15s ease,
      border-color 0.15s ease;
  }
  .site-nav a:hover {
    color: var(--text);
  }
  /* "/" would match every route as a prefix — only highlight it exactly. */
  .site-nav a.router-link-active:not(.exact),
  .site-nav a.exact.router-link-exact-active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
  .site-account {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-shrink: 0;
  }
  .site-user {
    font-size: 13px;
    color: var(--text-muted);
  }
  .site-login {
    padding: 7px 16px;
    font-size: 13.5px;
    text-decoration: none;
  }
  .site-menu {
    display: none;
  }
}
</style>
