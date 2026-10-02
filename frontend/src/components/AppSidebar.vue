<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { listHistory, type SessionHistoryItem } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const session = useSessionStore()

const recent = ref<SessionHistoryItem[]>([])

async function loadRecent() {
  recent.value = await listHistory()
}

async function openConversation(item: SessionHistoryItem) {
  if (item.session_id === session.sessionId) return
  await session.resume(item.session_id, item.language)
  router.push('/')
}

async function newChat() {
  session.reset()
  router.push('/')
  await loadRecent()
}

function logout() {
  // Clear the open chat too — it belongs to the account being signed out.
  auth.signOut(() => {
    session.reset()
    return router.push('/')
  })
}

// A new chat only exists once its first message has gone through — refresh
// after that send finishes, instead of waiting for a reload.
watch(
  () => session.sending,
  (sending) => {
    const id = session.sessionId
    if (!sending && id && !recent.value.some((item) => item.session_id === id)) loadRecent()
  },
)

onMounted(loadRecent)
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <img class="logo" src="/emotion-talk.png" :alt="t('app.title')" />
      <span>{{ t('app.title') }}</span>
    </div>

    <button type="button" class="btn-primary new-chat" @click="newChat">{{ t('sidebar.newChat') }}</button>

    <div class="recent">
      <div class="recent-label">{{ t('sidebar.recent') }}</div>
      <p v-if="recent.length === 0" class="recent-empty">{{ t('sidebar.recentEmpty') }}</p>
      <button
        v-for="item in recent"
        :key="item.session_id"
        type="button"
        class="recent-item"
        :class="{ active: item.session_id === session.sessionId }"
        :title="new Date(item.created_at).toLocaleString()"
        @click="openConversation(item)"
      >
        {{ new Date(item.created_at).toLocaleString() }}
      </button>
    </div>

    <nav class="side-nav">
      <button type="button" @click="router.push('/reflection')">{{ t('reflection.title') }}</button>
      <button type="button" @click="router.push('/history')">{{ t('toolbar.history') }}</button>
      <button type="button" @click="router.push('/records')">{{ t('toolbar.records') }}</button>
      <button type="button" @click="router.push('/help')">{{ t('toolbar.help') }}</button>
      <button type="button" @click="router.push('/privacy')">{{ t('privacy.title') }}</button>
      <button type="button" @click="router.push('/contact')">{{ t('contact.title') }}</button>
      <button v-if="auth.user && auth.user.role !== 'user'" type="button" @click="router.push('/admin')">
        {{ t('admin.entry') }}
      </button>
    </nav>

    <div class="account">
      <button v-if="!auth.user" type="button" class="btn-outline" @click="router.push('/login')">
        {{ t('toolbar.login') }}
      </button>
      <template v-else>
        <div class="email">{{ auth.user.username }}</div>
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
.recent {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
}
.recent-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 4px 10px 6px;
}
.recent-empty {
  font-size: 12.5px;
  color: var(--text-muted);
  padding: 0 10px;
}
.recent-item {
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}
.recent-item:hover {
  background: var(--accent-soft);
  color: var(--accent);
  transform: none;
}
.recent-item.active {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}
.side-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
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
