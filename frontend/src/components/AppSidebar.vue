<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const session = useSessionStore()

function newChat() {
  session.reset()
  router.push('/')
}

function logout() {
  auth.logout()
  router.push('/')
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <img class="logo" src="/emotion-talk.png" :alt="t('app.title')" />
      <span>{{ t('app.title') }}</span>
    </div>

    <button type="button" class="btn-primary new-chat" @click="newChat">{{ t('sidebar.newChat') }}</button>

    <nav class="side-nav">
      <button type="button" @click="router.push('/history')">{{ t('toolbar.history') }}</button>
      <button type="button" @click="router.push('/records')">{{ t('toolbar.records') }}</button>
      <button type="button" @click="router.push('/help')">{{ t('toolbar.help') }}</button>
      <button v-if="auth.user && auth.user.role !== 'user'" type="button" @click="router.push('/admin')">
        {{ t('admin.entry') }}
      </button>
    </nav>

    <div class="account">
      <button v-if="!auth.user" type="button" class="btn-outline" @click="router.push('/login')">
        {{ t('toolbar.login') }}
      </button>
      <template v-else>
        <div class="email">{{ auth.user.email }}</div>
        <button type="button" class="btn-text" @click="logout">{{ t('toolbar.logout') }}</button>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px 16px;
  border-right: 1px solid var(--border);
  background: var(--bg);
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
.new-chat {
  width: 100%;
  font-size: 14px;
  padding: 10px 14px;
}
.side-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.side-nav button {
  text-align: left;
  padding: 9px 10px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  font-size: 13.5px;
  color: var(--text);
}
.side-nav button:hover {
  background: var(--accent-soft);
  color: var(--accent);
  transform: none;
}
.account {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.account .btn-outline {
  width: 100%;
}
.email {
  font-size: 12px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding: 0 2px;
}
</style>
