<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { deleteSession, listHistory, type SessionHistoryItem } from '@/api/client'
import LanguageSwitch from '@/components/LanguageSwitch.vue'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'
import { displayDay, formatDateTime, toDate, DISPLAY_TIME_ZONE } from '@/utils/time'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()
const session = useSessionStore()

const recent = ref<SessionHistoryItem[]>([])

// Signed-out visitors have no history; a failed refresh keeps the old list.
async function loadRecent() {
  if (!auth.user) {
    recent.value = []
    return
  }
  recent.value = await listHistory().catch(() => recent.value)
}

// Today → "14:05"; earlier → the date. The full time is in the tooltip.
function shortTime(value: string): string {
  if (displayDay(value) === displayDay()) {
    return toDate(value).toLocaleTimeString(undefined, { timeZone: DISPLAY_TIME_ZONE, hour: '2-digit', minute: '2-digit' })
  }
  return toDate(value).toLocaleDateString(undefined, { timeZone: DISPLAY_TIME_ZONE, month: 'numeric', day: 'numeric' })
}

async function openConversation(item: SessionHistoryItem) {
  // Already open: just go back to it (it may be open behind another page).
  if (item.session_id !== session.sessionId) await session.resume(item.session_id, item.language, !!item.ended_at)
  router.push('/')
}

const confirmingDelete = ref<string | null>(null)
const deleteFailed = ref(false)
async function removeConversation(item: SessionHistoryItem) {
  deleteFailed.value = false
  try {
    await deleteSession(item.session_id)
  } catch {
    deleteFailed.value = true
    return
  }
  confirmingDelete.value = null
  if (session.sessionId === item.session_id) {
    session.reset()
    router.push('/')
  }
  await loadRecent()
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
    return router.push('/login')
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

// Keep the list current: a conversation started, ended or deleted here, a
// different account signed in, or one continued on another device.
watch(() => [session.sessionId, session.ended, session.deletedNotice, auth.user?.id], loadRecent)

function onVisible() {
  if (document.visibilityState === 'visible') loadRecent()
}
let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  loadRecent()
  timer = setInterval(onVisible, 15_000)
  document.addEventListener('visibilitychange', onVisible)
  window.addEventListener('focus', loadRecent)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisible)
  window.removeEventListener('focus', loadRecent)
})
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
      <div
        v-for="item in recent"
        :key="item.session_id"
        class="recent-row"
        :class="{ active: item.session_id === session.sessionId, confirming: confirmingDelete === item.session_id }"
      >
        <template v-if="confirmingDelete === item.session_id">
          <span class="recent-confirm">{{ deleteFailed ? t('toolbar.deleteFailed') : t('sidebar.deleteConfirm') }}</span>
          <button type="button" class="recent-yes" @click="removeConversation(item)">{{ t('history.deleteYes') }}</button>
          <button type="button" class="recent-no" @click="confirmingDelete = null; deleteFailed = false">{{ t('history.clearConfirmNo') }}</button>
        </template>
        <template v-else>
          <button
            type="button"
            class="recent-item"
            :title="formatDateTime(item.last_active_at)"
            @click="openConversation(item)"
          >
            <span class="recent-title">{{ item.title || t('sidebar.untitled') }}</span>
            <span class="recent-meta">
              {{ shortTime(item.last_active_at) }}
              <span v-if="item.ended_at" class="recent-ended">· {{ t('sidebar.ended') }}</span>
            </span>
          </button>
          <button
            type="button"
            class="recent-delete"
            :aria-label="t('history.delete')"
            :title="t('history.delete')"
            @click="confirmingDelete = item.session_id; deleteFailed = false"
          >
            ×
          </button>
        </template>
      </div>
    </div>

    <nav class="side-nav">
      <RouterLink to="/history">{{ t('toolbar.history') }}</RouterLink>
      <RouterLink to="/records">{{ t('toolbar.records') }}</RouterLink>
      <RouterLink to="/reflection">{{ t('reflection.title') }}</RouterLink>
      <RouterLink to="/help">{{ t('toolbar.help') }}</RouterLink>
      <RouterLink to="/privacy">{{ t('privacy.title') }}</RouterLink>
    </nav>

    <LanguageSwitch class="sidebar-lang" show-label />

    <div class="account">
      <button v-if="!auth.user" type="button" class="btn-outline" @click="router.push('/login')">
        {{ t('toolbar.login') }}
      </button>
      <template v-else>
        <RouterLink v-if="auth.user.role !== 'user'" to="/admin" class="btn-outline to-admin">{{ t('admin.entry') }}</RouterLink>
        <div class="email">{{ auth.user.username }}</div>
        <button type="button" class="btn-text" @click="logout">{{ t('toolbar.logout') }}</button>
      </template>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  flex-shrink: 0;
  overflow-y: auto;
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
  flex: 1 1 160px;
  min-height: 120px;
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
.recent-row {
  display: flex;
  align-items: center;
  gap: 2px;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}
.recent-row:hover,
.recent-row.active {
  background: var(--accent-soft);
}
.recent-row.confirming {
  flex-wrap: wrap;
  padding: 6px 8px;
  background: var(--danger-soft);
}
.recent-delete {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  font-size: 16px;
  line-height: 1;
  color: var(--text-muted);
  opacity: 0;
}
.recent-row:hover .recent-delete,
.recent-delete:focus-visible {
  opacity: 1;
}
.recent-delete:hover {
  color: var(--danger);
}
/* touch screens have no hover: keep it visible there */
@media (hover: none) {
  .recent-delete {
    opacity: 1;
  }
}
.recent-confirm {
  flex: 1 1 100%;
  line-height: 1.4;
  font-size: 12px;
  color: var(--danger);
}
.recent-yes,
.recent-no {
  border: none;
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  font-size: 12px;
}
.recent-yes {
  background: var(--danger);
  color: #fff;
}
.recent-no {
  background: var(--surface);
  color: var(--text);
}
.recent-item {
  flex: 1;
  min-width: 0;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  color: var(--text);
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.recent-title,
.recent-meta {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.recent-meta {
  font-size: 11px;
  font-weight: 400;
  color: var(--text-muted);
}
.recent-item:hover,
.recent-row.active .recent-item {
  color: var(--accent);
}
.recent-row.active .recent-title {
  font-weight: 600;
}
.side-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex-shrink: 0;
}
.side-nav a {
  padding: 9px 10px;
  border-radius: var(--radius-sm);
  font-size: 13.5px;
  color: var(--text);
  text-decoration: none;
}
.side-nav a:hover,
.side-nav a.router-link-active {
  background: var(--accent-soft);
  color: var(--accent);
}
.side-nav a.router-link-active {
  font-weight: 600;
}
.to-admin {
  margin-bottom: 8px;
  padding: 8px 12px;
  font-size: 13.5px;
  text-align: center;
  text-decoration: none;
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
.sidebar-lang {
  margin: 12px 0 4px;
}
</style>
