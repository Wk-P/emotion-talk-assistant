<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  deleteAdminSession,
  deleteAdminUser,
  exportAdminSessions,
  getAdminSessionMessages,
  listAdminSessions,
  listAdminUsers,
  setAdminUserActive,
  setAdminUserRole,
  type AdminSessionItem,
  type AdminUserItem,
  type HistoryMessageItem,
} from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const tab = ref<'conversations' | 'users'>('conversations')

const items = ref<AdminSessionItem[]>([])
const openId = ref<string | null>(null)
const openMessages = ref<HistoryMessageItem[]>([])
const loading = ref(true)
const exporting = ref(false)
const confirmingDeleteSession = ref<string | null>(null)
// Collapsed by default only once there's more than one participant — with
// just one or two, expanding everything up front saves a click.
const collapsedGroups = ref<Set<string>>(new Set())

const users = ref<AdminUserItem[]>([])
const usersLoading = ref(true)
const confirmingDeleteUser = ref<string | null>(null)
const isSuperadmin = computed(() => auth.user?.role === 'superadmin')

interface ParticipantGroup {
  label: string
  sessionCount: number
  messageCount: number
  lastActive: string
  sessions: AdminSessionItem[]
}

const stats = computed(() => {
  const participants = new Set(items.value.map((i) => i.participant_label))
  const messageCount = items.value.reduce((sum, i) => sum + i.message_count, 0)
  return { participantCount: participants.size, sessionCount: items.value.length, messageCount }
})

// Sessions arrive sorted newest-first; group by participant while keeping
// each group's own sessions in that order, and order the groups themselves
// by their most recent session so active participants stay near the top.
const groups = computed<ParticipantGroup[]>(() => {
  const byLabel = new Map<string, AdminSessionItem[]>()
  for (const item of items.value) {
    const list = byLabel.get(item.participant_label) ?? []
    list.push(item)
    byLabel.set(item.participant_label, list)
  }
  return Array.from(byLabel.entries()).map(([label, sessions]) => ({
    label,
    sessionCount: sessions.length,
    messageCount: sessions.reduce((sum, s) => sum + s.message_count, 0),
    lastActive: sessions[0]?.created_at ?? '',
    sessions,
  }))
})

function toggleGroup(label: string) {
  const next = new Set(collapsedGroups.value)
  if (next.has(label)) next.delete(label)
  else next.add(label)
  collapsedGroups.value = next
}

async function load() {
  loading.value = true
  try {
    items.value = await listAdminSessions()
  } finally {
    loading.value = false
  }
}

async function toggle(sessionId: string) {
  if (openId.value === sessionId) {
    openId.value = null
    return
  }
  openMessages.value = await getAdminSessionMessages(sessionId)
  openId.value = sessionId
}

async function doExport() {
  exporting.value = true
  try {
    const data = await exportAdminSessions()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `emotion-ai-export-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  } finally {
    exporting.value = false
  }
}

async function doDeleteSession(sessionId: string) {
  await deleteAdminSession(sessionId)
  confirmingDeleteSession.value = null
  if (openId.value === sessionId) openId.value = null
  await load()
}

async function loadUsers() {
  usersLoading.value = true
  try {
    users.value = await listAdminUsers()
  } finally {
    usersLoading.value = false
  }
}

async function toggleActive(user: AdminUserItem) {
  const updated = await setAdminUserActive(user.id, !user.is_active)
  const idx = users.value.findIndex((u) => u.id === user.id)
  if (idx !== -1) users.value[idx] = updated
}

async function promote(user: AdminUserItem) {
  const updated = await setAdminUserRole(user.id, 'admin')
  const idx = users.value.findIndex((u) => u.id === user.id)
  if (idx !== -1) users.value[idx] = updated
}

async function demote(user: AdminUserItem) {
  const updated = await setAdminUserRole(user.id, 'user')
  const idx = users.value.findIndex((u) => u.id === user.id)
  if (idx !== -1) users.value[idx] = updated
}

async function doDeleteUser(userId: string) {
  await deleteAdminUser(userId)
  confirmingDeleteUser.value = null
  await loadUsers()
}

function switchTab(next: 'conversations' | 'users') {
  tab.value = next
  if (next === 'users' && users.value.length === 0 && !usersLoading.value) loadUsers()
}

onMounted(load)
</script>

<template>
  <div class="history-view">
    <header class="header">
      <button type="button" class="btn-back" @click="router.push('/')"><span class="arrow">&lt;</span> {{ t('admin.back') }}</button>
    </header>

    <h1 class="page-title">{{ t('admin.title') }}</h1>
    <p class="note">{{ t('admin.note') }}</p>

    <div class="tabs">
      <button type="button" class="btn-outline" :class="{ active: tab === 'conversations' }" @click="switchTab('conversations')">
        {{ t('admin.tabConversations') }}
      </button>
      <button type="button" class="btn-outline" :class="{ active: tab === 'users' }" @click="switchTab('users')">
        {{ t('admin.tabUsers') }}
      </button>
    </div>

    <template v-if="tab === 'conversations'">
    <div v-if="!loading && items.length > 0" class="stats">
      <div class="stat">
        <div class="stat-value">{{ stats.participantCount }}</div>
        <div class="stat-label">{{ t('admin.statParticipants') }}</div>
      </div>
      <div class="stat">
        <div class="stat-value">{{ stats.sessionCount }}</div>
        <div class="stat-label">{{ t('admin.statSessions') }}</div>
      </div>
      <div class="stat">
        <div class="stat-value">{{ stats.messageCount }}</div>
        <div class="stat-label">{{ t('admin.statMessages') }}</div>
      </div>
    </div>

    <button
      v-if="!loading && items.length > 0"
      type="button"
      class="btn-outline export-btn"
      :disabled="exporting"
      @click="doExport"
    >
      {{ exporting ? t('admin.exporting') : t('admin.export') }}
    </button>

    <p v-if="!loading && items.length === 0" class="empty">{{ t('admin.empty') }}</p>

    <div v-for="group in groups" :key="group.label" class="group">
      <button type="button" class="group-head" @click="toggleGroup(group.label)">
        <span class="group-label">{{ group.label }}</span>
        <span class="group-meta">
          {{ t('admin.groupMeta', { sessions: group.sessionCount, messages: group.messageCount }) }}
        </span>
        <span class="chevron" :class="{ collapsed: collapsedGroups.has(group.label) }">▾</span>
      </button>

      <TransitionGroup v-if="!collapsedGroups.has(group.label)" name="entry" tag="div" class="group-sessions">
        <div v-for="item in group.sessions" :key="item.session_id" class="entry">
          <button type="button" class="entry-head" @click="toggle(item.session_id)">
            <span>{{ new Date(item.created_at).toLocaleString() }}</span>
            <span class="count">{{ t('history.messageCount', { n: item.message_count }) }}</span>
          </button>
          <Transition name="expand">
            <div v-if="openId === item.session_id" class="messages">
              <div v-for="(m, i) in openMessages" :key="i" class="message" :class="m.role">
                {{ m.content }}
              </div>
            </div>
          </Transition>
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>

<style scoped>
.history-view {
  padding: 16px;
}
.header {
  margin-bottom: 14px;
}
.page-title {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 6px;
}
.note {
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 0 0 16px;
  line-height: 1.5;
}
.stats {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.stat {
  flex: 1;
  text-align: center;
  padding: 10px 6px;
  border-radius: var(--radius-md);
  background: var(--bg);
  border: 1px solid var(--border);
}
.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--accent);
}
.stat-label {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 2px;
}
.export-btn {
  width: 100%;
  margin-bottom: 20px;
}
.empty {
  color: var(--text-muted);
  font-size: 14px;
}
.group {
  margin-bottom: 14px;
}
.group-head {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--accent-soft);
}
.group-label {
  font-weight: 700;
  color: var(--accent);
  font-family: ui-monospace, monospace;
  font-size: 12.5px;
}
.group-meta {
  flex: 1;
  text-align: left;
  font-size: 12px;
  color: var(--text-muted);
}
.chevron {
  color: var(--accent);
  transition: transform 0.2s ease;
}
.chevron.collapsed {
  transform: rotate(-90deg);
}
.group-sessions {
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.entry {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.entry-head {
  width: 100%;
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--surface);
  border: none;
  font-size: 13px;
  color: var(--text);
}
.count {
  color: var(--text-muted);
}
.messages {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--bg);
}
.message {
  font-size: 13px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  line-height: 1.5;
}
.message.user {
  background: var(--accent-soft);
  align-self: flex-end;
}
.message.assistant {
  background: var(--surface);
  align-self: flex-start;
}
.entry-enter-active,
.entry-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}
.entry-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.entry-leave-to {
  opacity: 0;
}
.expand-enter-active,
.expand-leave-active {
  transition:
    opacity 0.18s ease,
    max-height 0.22s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 600px;
}
</style>
