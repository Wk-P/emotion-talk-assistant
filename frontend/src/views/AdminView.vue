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
// Doubles as "selected session" for the >=1024px master-detail layout and
// "expanded session" for the narrow accordion — the two layouts share this
// one piece of state on purpose (see the style block) rather than each
// layout inventing its own, since "one thing open at a time" is exactly
// what both actually mean.
const openId = ref<string | null>(null)
const openMessages = ref<HistoryMessageItem[]>([])
const loading = ref(true)
const exporting = ref(false)
const confirmingDeleteSession = ref<string | null>(null)
// Collapsed by default only once there's more than one participant — with
// just one or two, expanding everything up front saves a click.
const collapsedGroups = ref<Set<string>>(new Set())

const users = ref<AdminUserItem[]>([])
// Starts false, not true: switchTab() below used to gate its first fetch on
// `!usersLoading`, and since this hadn't loaded yet that read as "already in
// flight" — the very first switch to this tab silently fetched nothing.
const usersLoading = ref(false)
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

const selectedSession = computed(() => items.value.find((i) => i.session_id === openId.value) ?? null)

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
  <div class="admin-view">
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

      <!-- >=1024px: left column below is the list half of a master-detail
           split (see .conv-layout); <1024px: it's the whole page and each
           entry expands its own transcript inline (see .messages.inline). -->
      <div class="conv-layout">
        <div class="conv-list">
          <div v-for="group in groups" :key="group.label" class="group">
            <button type="button" class="group-head" @click="toggleGroup(group.label)">
              <span class="group-label">{{ group.label }}</span>
              <span class="group-meta">
                {{ t('admin.groupMeta', { sessions: group.sessionCount, messages: group.messageCount }) }}
              </span>
              <span class="chevron" :class="{ collapsed: collapsedGroups.has(group.label) }">▾</span>
            </button>

            <TransitionGroup v-if="!collapsedGroups.has(group.label)" name="entry" tag="div" class="group-sessions">
              <div v-for="item in group.sessions" :key="item.session_id" class="entry" :class="{ selected: openId === item.session_id }">
                <div class="entry-row">
                  <button type="button" class="entry-head" @click="toggle(item.session_id)">
                    <span>{{ new Date(item.created_at).toLocaleString() }}</span>
                    <span class="count">{{ t('history.messageCount', { n: item.message_count }) }}</span>
                  </button>
                  <button
                    v-if="confirmingDeleteSession !== item.session_id"
                    type="button"
                    class="btn-danger entry-delete"
                    @click="confirmingDeleteSession = item.session_id"
                  >
                    {{ t('admin.deleteSession') }}
                  </button>
                </div>
                <div v-if="confirmingDeleteSession === item.session_id" class="confirm-row">
                  <span>{{ t('admin.deleteSessionConfirm') }}</span>
                  <button type="button" class="btn-danger" @click="doDeleteSession(item.session_id)">
                    {{ t('history.clearConfirmYes') }}
                  </button>
                  <button type="button" class="btn-outline" @click="confirmingDeleteSession = null">
                    {{ t('history.clearConfirmNo') }}
                  </button>
                </div>
                <Transition name="expand">
                  <div v-if="openId === item.session_id" class="messages inline">
                    <div v-for="(m, i) in openMessages" :key="i" class="message" :class="m.role">
                      {{ m.content }}
                    </div>
                  </div>
                </Transition>
              </div>
            </TransitionGroup>
          </div>
        </div>

        <div class="conv-detail">
          <template v-if="selectedSession">
            <div class="detail-header">
              <span class="detail-participant">{{ selectedSession.participant_label }}</span>
              <span>{{ new Date(selectedSession.created_at).toLocaleString() }}</span>
            </div>
            <div class="messages">
              <div v-for="(m, i) in openMessages" :key="i" class="message" :class="m.role">
                {{ m.content }}
              </div>
            </div>
          </template>
          <p v-else class="detail-placeholder">{{ t('admin.selectPrompt') }}</p>
        </div>
      </div>
    </template>

    <template v-else>
      <p v-if="!usersLoading && users.length === 0" class="empty">{{ t('admin.usersEmpty') }}</p>

      <!-- >=1024px: a real table — user rows are what genuinely benefits
           from tabular alignment (email/role/status/sessions/date/actions
           as real columns), which no amount of widening a stacked card
           actually gives you. <1024px keeps the card list below instead;
           a table forces horizontal scrolling on a narrow screen. -->
      <table v-if="users.length > 0" class="users-table">
        <thead>
          <tr>
            <th>{{ t('admin.colEmail') }}</th>
            <th>{{ t('admin.colRole') }}</th>
            <th>{{ t('admin.colStatus') }}</th>
            <th>{{ t('admin.colSessions') }}</th>
            <th>{{ t('admin.colCreated') }}</th>
            <th>{{ t('admin.colActions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td class="cell-email">{{ user.email }}</td>
            <td><span class="badge" :class="user.role">{{ t(`admin.role.${user.role}`) }}</span></td>
            <td>
              <span v-if="!user.email_verified" class="badge warn">{{ t('admin.unverified') }}</span>
              <span v-if="!user.is_active" class="badge danger">{{ t('admin.disabled') }}</span>
            </td>
            <td>{{ user.session_count }}</td>
            <td>{{ new Date(user.created_at).toLocaleDateString() }}</td>
            <td class="cell-actions">
              <template v-if="confirmingDeleteUser === user.id">
                <span class="confirm-inline">{{ t('admin.deleteUserConfirm') }}</span>
                <button type="button" class="btn-danger" @click="doDeleteUser(user.id)">{{ t('history.clearConfirmYes') }}</button>
                <button type="button" class="btn-outline" @click="confirmingDeleteUser = null">{{ t('history.clearConfirmNo') }}</button>
              </template>
              <template v-else>
                <button v-if="isSuperadmin && user.role === 'user'" type="button" class="btn-outline" @click="promote(user)">
                  {{ t('admin.promote') }}
                </button>
                <button v-if="isSuperadmin && user.role === 'admin'" type="button" class="btn-outline" @click="demote(user)">
                  {{ t('admin.demote') }}
                </button>
                <button type="button" class="btn-outline" @click="toggleActive(user)">
                  {{ user.is_active ? t('admin.disable') : t('admin.enable') }}
                </button>
                <button type="button" class="btn-danger" @click="confirmingDeleteUser = user.id">
                  {{ t('admin.deleteUser') }}
                </button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="user-cards">
        <div v-for="user in users" :key="user.id" class="user-row">
          <div class="user-main">
            <div class="user-email">{{ user.email }}</div>
            <div class="user-meta">
              <span class="badge" :class="user.role">{{ t(`admin.role.${user.role}`) }}</span>
              <span v-if="!user.email_verified" class="badge warn">{{ t('admin.unverified') }}</span>
              <span v-if="!user.is_active" class="badge danger">{{ t('admin.disabled') }}</span>
              <span>{{ t('admin.userSessions', { n: user.session_count }) }}</span>
              <span>{{ new Date(user.created_at).toLocaleDateString() }}</span>
            </div>
          </div>
          <div class="user-actions">
            <button v-if="isSuperadmin && user.role === 'user'" type="button" class="btn-outline" @click="promote(user)">
              {{ t('admin.promote') }}
            </button>
            <button v-if="isSuperadmin && user.role === 'admin'" type="button" class="btn-outline" @click="demote(user)">
              {{ t('admin.demote') }}
            </button>
            <button type="button" class="btn-outline" @click="toggleActive(user)">
              {{ user.is_active ? t('admin.disable') : t('admin.enable') }}
            </button>
            <button
              v-if="confirmingDeleteUser !== user.id"
              type="button"
              class="btn-danger"
              @click="confirmingDeleteUser = user.id"
            >
              {{ t('admin.deleteUser') }}
            </button>
          </div>
          <div v-if="confirmingDeleteUser === user.id" class="confirm-row">
            <span>{{ t('admin.deleteUserConfirm') }}</span>
            <button type="button" class="btn-danger" @click="doDeleteUser(user.id)">
              {{ t('history.clearConfirmYes') }}
            </button>
            <button type="button" class="btn-outline" @click="confirmingDeleteUser = null">
              {{ t('history.clearConfirmNo') }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.admin-view {
  padding: 16px;
}
@media (min-width: 640px) {
  .admin-view {
    padding: 24px 32px;
  }
}
.header {
  margin-bottom: 14px;
}
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
}
.tabs button {
  flex: 1;
}
.tabs button.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
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

/* ---- Conversations: master-detail on wide, plain list on narrow ---- */
.conv-detail {
  display: none;
}
@media (min-width: 1024px) {
  .conv-layout {
    display: flex;
    align-items: flex-start;
    gap: 20px;
  }
  .conv-list {
    width: 360px;
    flex-shrink: 0;
    max-height: 72vh;
    overflow-y: auto;
    padding-right: 4px;
  }
  /* The detail pane renders the same transcript instead — showing it twice
     would just be confusing, not "using the space". */
  .messages.inline {
    display: none;
  }
  .conv-detail {
    display: block;
    flex: 1;
    min-width: 0;
    position: sticky;
    top: 16px;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 16px;
    max-height: 72vh;
    overflow-y: auto;
    background: var(--bg);
  }
  .entry.selected .entry-head {
    background: var(--accent-soft);
  }
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--border);
}
.detail-participant {
  font-family: ui-monospace, monospace;
  color: var(--accent);
}
.detail-placeholder {
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
  padding: 40px 0;
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
.entry-row {
  display: flex;
}
.entry-row .entry-head {
  flex: 1;
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
.entry-delete {
  border-radius: 0;
  border-left: 1px solid var(--danger-border);
}
.count {
  color: var(--text-muted);
}
.confirm-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--danger-soft);
  font-size: 12.5px;
  color: var(--danger);
}
.confirm-row span {
  flex: 1;
}
.confirm-row button {
  padding: 5px 10px;
  font-size: 12px;
}
.messages {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--bg);
}
.conv-detail .messages {
  padding: 0;
  /* The detail pane itself (its border/background) fills whatever width
     the page has, same as everywhere else now — but a chat bubble
     stretching to 85% of a 2000px-wide pane stops being a "message" and
     starts being a text block, so the transcript column specifically
     stays a readable width, centered in that full-width pane. */
  max-width: 760px;
  margin: 0 auto;
}
.message {
  font-size: 13px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  line-height: 1.5;
  max-width: 85%;
}
.message.user {
  background: var(--accent-soft);
  align-self: flex-end;
}
.message.assistant {
  background: var(--surface);
  align-self: flex-start;
}
.conv-detail .message.assistant {
  background: var(--surface);
}

/* ---- Users: real table on wide, cards on narrow ---- */
.users-table {
  display: none;
}
.user-cards {
  display: block;
}
@media (min-width: 1024px) {
  .users-table {
    display: table;
    width: 100%;
    border-collapse: separate;
    border-spacing: 0 8px;
    margin-bottom: 10px;
  }
  .user-cards {
    display: none;
  }
  .users-table th {
    text-align: left;
    font-size: 11.5px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    padding: 0 12px 6px;
  }
  .users-table td {
    background: var(--bg);
    padding: 12px;
    font-size: 13px;
    vertical-align: middle;
  }
  .users-table tr td:first-child {
    border-top-left-radius: var(--radius-md);
    border-bottom-left-radius: var(--radius-md);
  }
  .users-table tr td:last-child {
    border-top-right-radius: var(--radius-md);
    border-bottom-right-radius: var(--radius-md);
  }
  .cell-email {
    font-weight: 600;
    word-break: break-all;
  }
  .cell-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }
  .cell-actions button {
    padding: 6px 10px;
    font-size: 12px;
  }
  .confirm-inline {
    font-size: 12px;
    color: var(--danger);
  }
}

.user-row {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  margin-bottom: 10px;
}
@media (min-width: 640px) {
  .user-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }
  .user-main {
    margin-bottom: 0;
    flex: 1;
    min-width: 0;
  }
  .user-actions {
    flex-shrink: 0;
  }
  .user-row .confirm-row {
    flex-basis: 100%;
  }
}
.user-main {
  margin-bottom: 10px;
}
.user-email {
  font-weight: 600;
  font-size: 13.5px;
  word-break: break-all;
}
.user-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
.badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: var(--bg);
  color: var(--text-muted);
}
.badge.admin,
.badge.superadmin {
  background: var(--accent-soft);
  color: var(--accent);
}
.badge.warn {
  background: #fff4e0;
  color: #a15c00;
}
.badge.danger {
  background: var(--danger-soft);
  color: var(--danger);
}
.user-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.user-actions button {
  padding: 6px 10px;
  font-size: 12px;
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
