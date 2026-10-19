<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import LanguageSwitch from '@/components/LanguageSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'

// The admin side's own sidebar: same shape as AppSidebar, admin sections
// only. Its color comes from the admin palette (html.admin-area, main.css).
const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const session = useSessionStore()

const sections = [
  { tab: 'conversations', label: 'admin.tabConversations' },
  { tab: 'users', label: 'admin.tabUsers' },
  { tab: 'records', label: 'admin.tabRecords' },
  { tab: 'reflections', label: 'admin.tabReflections' },
  { tab: 'prompts', label: 'admin.tabPrompts' },
  { tab: 'guide', label: 'admin.tabGuide' },
]

function logout() {
  auth.signOut(() => {
    session.reset()
    return router.push('/login')
  })
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <img class="logo" src="/emotion-talk.png" alt="" />
      <span>{{ t('app.title') }}</span>
      <span class="badge">{{ t('admin.badge') }}</span>
    </div>

    <nav class="side-nav">
      <RouterLink v-for="s in sections" :key="s.tab" :to="`/admin/${s.tab}`">{{ t(s.label) }}</RouterLink>
    </nav>

    <LanguageSwitch class="sidebar-lang" show-label />

    <div class="account">
      <RouterLink to="/" class="btn-outline to-user">{{ t('admin.toUserSite') }}</RouterLink>
      <div v-if="auth.user" class="email">{{ auth.user.username }}</div>
      <button type="button" class="btn-text" @click="logout">{{ t('toolbar.logout') }}</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 16px;
  border-right: 1px solid var(--border);
  background: var(--bg);
  overflow-y: auto;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 14px;
}
.logo {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  box-shadow: var(--shadow-sm);
}
.badge {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}
.side-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.side-nav a {
  padding: 9px 10px;
  border-radius: var(--radius-sm);
  font-size: 13.5px;
  color: var(--text);
  text-decoration: none;
}
.side-nav a:hover {
  background: var(--accent-soft);
  color: var(--accent);
}
.side-nav a.router-link-active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}
.account {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.to-user {
  margin-bottom: 8px;
  padding: 8px 12px;
  font-size: 13.5px;
  text-align: center;
  text-decoration: none;
}
.email {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 2px;
}
.sidebar-lang {
  margin: 12px 0 4px;
}
</style>
