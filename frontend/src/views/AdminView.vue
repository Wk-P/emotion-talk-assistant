<script setup lang="ts">
import SiteFooter from '@/components/SiteFooter.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  createAdminUser,
  deleteAdminSession,
  deleteAdminUser,
  exportAdminFile,
  exportAdminSessions,
  getAdminSessionMessages,
  getAdminSessionRecords,
  listAdminSessions,
  errorStatus,
  listAdminUsers,
  MIN_PASSWORD_LENGTH,
  resetAdminUserPassword,
  setAdminUserActive,
  setAdminUserRole,
  type AdminRecordItem,
  type AdminSessionFilter,
  type AdminSessionItem,
  type AdminUserFilter,
  type AdminUserItem,
  type ExportFormat,
  type HistoryMessageItem,
  type Language,
  type UserRole,
  USERNAME_PATTERN,
} from '@/api/client'
import AdminReflections from '@/components/admin/AdminReflections.vue'
import ModelPicker from '@/components/admin/ModelPicker.vue'
import PromptEditor from '@/components/admin/PromptEditor.vue'
import PromptTools from '@/components/admin/PromptTools.vue'
import AdminGuide from '@/components/admin/AdminGuide.vue'
import { useAuthStore } from '@/stores/auth'
import { fieldLabel, fieldText, recordTypeLabel } from '@/utils/fieldLabels'
import { displayDay, displayDayStart, formatDate, formatDateTime } from '@/utils/time'

const { t, te, locale } = useI18n()
const auth = useAuthStore()

const tab = ref<'conversations' | 'users' | 'reflections' | 'prompts' | 'guide'>('conversations')

const items = ref<AdminSessionItem[]>([])
// Doubles as "selected session" for the >=1024px master-detail layout and
// "expanded session" for the narrow accordion — the two layouts share this
// one piece of state on purpose (see the style block) rather than each
// layout inventing its own, since "one thing open at a time" is exactly
// what both actually mean.
const openId = ref<string | null>(null)
const openMessages = ref<HistoryMessageItem[]>([])
const openRecords = ref<AdminRecordItem[]>([])
const loading = ref(true)
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

// ---- Filters ----
// Every field is optional; '' / null means "don't filter on this".
const convFilter = reactive({
  participant: '',
  language: '' as Language | '',
  dateFrom: '', // YYYY-MM-DD from <input type="date">, local time
  dateTo: '',
  minMessages: null as number | null,
})
const userFilter = reactive({
  q: '',
  role: '' as UserRole | '',
  status: '' as NonNullable<AdminUserFilter['status']> | '',
})

// Dates are picked as Korea-time days (like every time shown on the site),
// so turn them into exact instants here rather than letting the server
// guess; "to" is inclusive in the UI, so it becomes the start of the next day.

function sessionQuery(): AdminSessionFilter {
  const f: AdminSessionFilter = {}
  if (convFilter.participant.trim()) f.participant = convFilter.participant.trim()
  if (convFilter.language) f.language = convFilter.language
  if (convFilter.dateFrom) f.created_from = displayDayStart(convFilter.dateFrom)
  if (convFilter.dateTo) f.created_to = displayDayStart(convFilter.dateTo, 1)
  if (convFilter.minMessages && convFilter.minMessages > 0) f.min_messages = convFilter.minMessages
  return f
}

function userQuery(): AdminUserFilter {
  const f: AdminUserFilter = {}
  if (userFilter.q.trim()) f.q = userFilter.q.trim()
  if (userFilter.role) f.role = userFilter.role
  if (userFilter.status) f.status = userFilter.status
  return f
}

const convFiltered = computed(() => Object.keys(sessionQuery()).length > 0)
const usersFiltered = computed(() => Object.keys(userQuery()).length > 0)

function resetConvFilter() {
  Object.assign(convFilter, { participant: '', language: '', dateFrom: '', dateTo: '', minMessages: null })
}
function resetUserFilter() {
  Object.assign(userFilter, { q: '', role: '', status: '' })
}

// Typing in a search box shouldn't fire a request per keystroke.
function debounced(fn: () => void, ms = 300) {
  let timer: ReturnType<typeof setTimeout> | undefined
  return () => {
    clearTimeout(timer)
    timer = setTimeout(fn, ms)
  }
}
watch(convFilter, debounced(() => load()))
watch(userFilter, debounced(() => loadUsers()))

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
    items.value = await listAdminSessions(sessionQuery())
    if (openId.value && !items.value.some((i) => i.session_id === openId.value)) openId.value = null
  } finally {
    loading.value = false
  }
}

async function toggle(sessionId: string) {
  if (openId.value === sessionId) {
    openId.value = null
    return
  }
  const item = items.value.find((i) => i.session_id === sessionId)
  ;[openMessages.value, openRecords.value] = await Promise.all([
    getAdminSessionMessages(sessionId),
    item && item.record_count > 0 ? getAdminSessionRecords(sessionId) : Promise.resolve([]),
  ])
  openId.value = sessionId
}

// One format choice drives every export button on the page (all / filtered /
// one participant / one user). Remembered per browser.
const EXPORT_FORMATS: ExportFormat[] = ['json', 'pdf', 'docx', 'md', 'txt']
const exportFormat = ref<ExportFormat>(
  (() => {
    try {
      const saved = localStorage.getItem('emotion-talk-export-format') as ExportFormat | null
      return saved && EXPORT_FORMATS.includes(saved) ? saved : 'json'
    } catch {
      return 'json'
    }
  })(),
)
watch(exportFormat, (f) => {
  try {
    localStorage.setItem('emotion-talk-export-format', f)
  } catch {
    // storage unavailable — the choice just isn't remembered
  }
})

function download(blob: Blob, name: string, ext: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `emotion-ai-${name}-${displayDay()}.${ext}`
  a.click()
  URL.revokeObjectURL(url)
}

// Which export is running: 'all', a participant label, or a user id — so
// only the clicked button shows the busy state.
const exportingKey = ref<string | null>(null)

async function runExport(key: string, filter: AdminSessionFilter, name: string) {
  if (exportingKey.value) return
  exportingKey.value = key
  try {
    const format = exportFormat.value
    if (format === 'json') {
      const data = await exportAdminSessions(filter)
      download(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }), name, 'json')
    } else {
      download(await exportAdminFile(filter, format, locale.value as 'zh' | 'ko' | 'en'), name, format)
    }
  } finally {
    exportingKey.value = null
  }
}

function doExport() {
  return runExport('all', sessionQuery(), convFiltered.value ? 'export-filtered' : 'export')
}

// Single-participant export keeps the other active filters (language, dates…)
// so it matches the group as shown.
// Account IDs may contain characters that don't belong in a file name
// (older ones are email addresses).
const fileSafe = (s: string) => s.replace(/[^A-Za-z0-9_.-]+/g, '_')

function exportParticipant(label: string) {
  return runExport(label, { ...sessionQuery(), participant: label, participant_exact: true }, fileSafe(label))
}

function exportUser(user: AdminUserItem) {
  return runExport(user.id, { user_id: user.id }, fileSafe(user.username))
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
    users.value = await listAdminUsers(userQuery())
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

// ---- Account management (no email: admins create accounts and reset
// forgotten passwords, then pass the password on in person) ----
const showCreate = ref(false)
const newUser = reactive({ username: '', password: '', role: 'user' as UserRole })
const creating = ref(false)
const createError = ref('')
const accountFlash = ref('')

function flash(message: string) {
  accountFlash.value = message
  setTimeout(() => {
    if (accountFlash.value === message) accountFlash.value = ''
  }, 5000)
}

async function doCreateUser() {
  creating.value = true
  createError.value = ''
  try {
    const created = await createAdminUser(newUser.username, newUser.password, newUser.role)
    flash(t('admin.account.created', { id: created.username }))
    Object.assign(newUser, { username: '', password: '', role: 'user' })
    showCreate.value = false
    await loadUsers()
  } catch (e) {
    const status = errorStatus(e)
    createError.value =
      status === 409 ? t('auth.usernameTaken') : status === 422 ? t('admin.account.invalid') : t('admin.account.failed')
  } finally {
    creating.value = false
  }
}

const resettingUser = ref<string | null>(null)
const resetPassword = ref('')
const resetError = ref('')

function startReset(user: AdminUserItem) {
  resettingUser.value = user.id
  resetPassword.value = ''
  resetError.value = ''
  confirmingDeleteUser.value = null
}

async function doResetPassword(user: AdminUserItem) {
  resetError.value = ''
  try {
    await resetAdminUserPassword(user.id, resetPassword.value)
    resettingUser.value = null
    flash(t('admin.account.resetDone', { id: user.username }))
  } catch (e) {
    resetError.value = errorStatus(e) === 422 ? t('auth.passwordHint') : t('admin.account.failed')
  }
}

async function doDeleteUser(userId: string) {
  await deleteAdminUser(userId)
  confirmingDeleteUser.value = null
  await loadUsers()
}

function switchTab(next: 'conversations' | 'users' | 'reflections' | 'prompts' | 'guide') {
  tab.value = next
  if (next === 'users' && users.value.length === 0 && !usersLoading.value && !usersFiltered.value) loadUsers()
}

onMounted(load)
</script>

<template>
  <div class="admin-view">
    <SiteHeader />
    <main class="page-body">

    <h1 class="page-title">{{ t('admin.title') }}</h1>
    <p class="note">{{ t('admin.note') }}</p>

    <div class="tabs">
      <button type="button" class="btn-outline" :class="{ active: tab === 'conversations' }" @click="switchTab('conversations')">
        {{ t('admin.tabConversations') }}
      </button>
      <button type="button" class="btn-outline" :class="{ active: tab === 'users' }" @click="switchTab('users')">
        {{ t('admin.tabUsers') }}
      </button>
      <button type="button" class="btn-outline" :class="{ active: tab === 'reflections' }" @click="switchTab('reflections')">
        {{ t('admin.tabReflections') }}
      </button>
      <button type="button" class="btn-outline" :class="{ active: tab === 'prompts' }" @click="switchTab('prompts')">
        {{ t('admin.tabPrompts') }}
      </button>
      <button type="button" class="btn-outline" :class="{ active: tab === 'guide' }" @click="switchTab('guide')">
        {{ t('admin.tabGuide') }}
      </button>
    </div>

    <template v-if="tab === 'conversations'">
      <div class="filters">
        <label class="filter-field grow">
          <span>{{ t('admin.filter.participant') }}</span>
          <input v-model="convFilter.participant" type="search" :placeholder="t('admin.filter.participantPlaceholder')" />
        </label>
        <label class="filter-field">
          <span>{{ t('admin.filter.language') }}</span>
          <select v-model="convFilter.language">
            <option value="">{{ t('admin.filter.all') }}</option>
            <option value="zh">中文</option>
            <option value="ko">한국어</option>
          </select>
        </label>
        <label class="filter-field">
          <span>{{ t('admin.filter.dateFrom') }}</span>
          <input v-model="convFilter.dateFrom" type="date" :max="convFilter.dateTo || undefined" />
        </label>
        <label class="filter-field">
          <span>{{ t('admin.filter.dateTo') }}</span>
          <input v-model="convFilter.dateTo" type="date" :min="convFilter.dateFrom || undefined" />
        </label>
        <label class="filter-field narrow">
          <span>{{ t('admin.filter.minMessages') }}</span>
          <input v-model.number="convFilter.minMessages" type="number" min="1" placeholder="—" />
        </label>
        <button v-if="convFiltered" type="button" class="btn-text filter-reset" @click="resetConvFilter">
          {{ t('admin.filter.reset') }}
        </button>
      </div>

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

      <div v-if="!loading && items.length > 0" class="export-row">
      <label class="export-format">
        <span>{{ t('admin.exportFormat') }}</span>
        <select v-model="exportFormat">
          <option v-for="f in EXPORT_FORMATS" :key="f" :value="f">{{ t(`admin.formats.${f}`) }}</option>
        </select>
      </label>
      <button
        type="button"
        class="btn-outline export-btn"
        :disabled="exportingKey !== null"
        @click="doExport"
      >
        {{
          exportingKey === 'all'
            ? t('admin.exporting')
            : convFiltered
              ? t('admin.exportFiltered', { n: items.length })
              : t('admin.export')
        }}
      </button>
      </div>

      <p v-if="!loading && items.length === 0" class="empty">
        {{ convFiltered ? t('admin.filter.noMatch') : t('admin.empty') }}
      </p>

      <!-- >=1024px: left column below is the list half of a master-detail
           split (see .conv-layout); <1024px: it's the whole page and each
           entry expands its own transcript inline (see .messages.inline). -->
      <div class="conv-layout">
        <div class="conv-list">
          <div v-for="group in groups" :key="group.label" class="group">
            <div class="group-head-row">
              <button type="button" class="group-head" @click="toggleGroup(group.label)">
                <span class="group-label">{{ group.label }}</span>
                <span class="group-meta">
                  {{ t('admin.groupMeta', { sessions: group.sessionCount, messages: group.messageCount }) }}
                </span>
                <span class="chevron" :class="{ collapsed: collapsedGroups.has(group.label) }">▾</span>
              </button>
              <button
                type="button"
                class="btn-outline group-export"
                :disabled="exportingKey !== null"
                :title="t('admin.exportPersonHint')"
                @click="exportParticipant(group.label)"
              >
                {{ exportingKey === group.label ? t('admin.exporting') : t('admin.exportPerson') }}
              </button>
            </div>

            <TransitionGroup v-if="!collapsedGroups.has(group.label)" name="entry" tag="div" class="group-sessions">
              <div v-for="item in group.sessions" :key="item.session_id" class="entry" :class="{ selected: openId === item.session_id }">
                <div class="entry-row">
                  <button type="button" class="entry-head" @click="toggle(item.session_id)">
                    <span>{{ formatDateTime(item.created_at) }}</span>
                    <span class="count">
                      {{ t('history.messageCount', { n: item.message_count }) }}
                      <span v-if="item.record_count > 0" class="record-badge">
                        {{ t('admin.recordCount', { n: item.record_count }) }}
                      </span>
                    </span>
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
                    <div v-if="openRecords.length > 0" class="saved-records">
                      <div class="saved-records-title">{{ t('admin.savedRecords') }}</div>
                      <div v-for="rec in openRecords" :key="rec.id" class="saved-record">
                        <div class="saved-record-type">{{ recordTypeLabel(t, te, rec.record_type) }}</div>
                        <div v-for="(value, key) in rec.payload" :key="key" class="saved-record-line">
                          <span class="saved-record-key">{{ fieldLabel(t, te, String(key)) }}</span>
                          {{ fieldText(value) }}
                        </div>
                      </div>
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
              <span>{{ formatDateTime(selectedSession.created_at) }}</span>
            </div>
            <div class="messages">
              <div v-for="(m, i) in openMessages" :key="i" class="message" :class="m.role">
                {{ m.content }}
              </div>
              <div v-if="openRecords.length > 0" class="saved-records">
                <div class="saved-records-title">{{ t('admin.savedRecords') }}</div>
                <div v-for="rec in openRecords" :key="rec.id" class="saved-record">
                  <div class="saved-record-type">{{ recordTypeLabel(t, te, rec.record_type) }}</div>
                  <div v-for="(value, key) in rec.payload" :key="key" class="saved-record-line">
                    <span class="saved-record-key">{{ fieldLabel(t, te, String(key)) }}</span>
                    {{ fieldText(value) }}
                  </div>
                </div>
              </div>
            </div>
          </template>
          <p v-else class="detail-placeholder">{{ t('admin.selectPrompt') }}</p>
        </div>
      </div>
    </template>

    <template v-else-if="tab === 'prompts'">
      <ModelPicker />
      <PromptEditor />
      <PromptTools />
    </template>

    <AdminGuide v-else-if="tab === 'guide'" />

    <AdminReflections v-else-if="tab === 'reflections'" />

    <template v-else>
      <div class="account-bar">
        <button type="button" class="btn-primary" @click="showCreate = !showCreate">
          {{ showCreate ? t('admin.account.cancel') : t('admin.account.create') }}
        </button>
        <span v-if="accountFlash" class="account-flash" role="status">{{ accountFlash }}</span>
      </div>
      <form v-if="showCreate" class="create-form" @submit.prevent="doCreateUser">
        <p class="create-hint">{{ t('admin.account.createHint') }}</p>
        <div class="create-fields">
          <label class="filter-field grow">
            <span>{{ t('auth.username') }}</span>
            <input
              v-model="newUser.username"
              required
              :pattern="USERNAME_PATTERN"
              :title="t('auth.usernameRules')"
              :placeholder="t('auth.usernameRules')"
              autocomplete="off"
              autocapitalize="off"
              spellcheck="false"
            />
          </label>
          <label class="filter-field grow">
            <span>{{ t('admin.account.initialPassword') }}</span>
            <input
              v-model="newUser.password"
              type="text"
              required
              :minlength="MIN_PASSWORD_LENGTH"
              :placeholder="t('auth.passwordHint')"
              autocomplete="off"
            />
          </label>
          <label v-if="isSuperadmin" class="filter-field">
            <span>{{ t('admin.colRole') }}</span>
            <select v-model="newUser.role">
              <option value="user">{{ t('admin.role.user') }}</option>
              <option value="admin">{{ t('admin.role.admin') }}</option>
            </select>
          </label>
          <button type="submit" class="btn-primary create-submit" :disabled="creating">
            {{ creating ? t('admin.account.creating') : t('admin.account.submit') }}
          </button>
        </div>
        <p v-if="createError" class="create-error">{{ createError }}</p>
      </form>

      <div class="filters">
        <label class="filter-field grow">
          <span>{{ t('auth.username') }}</span>
          <input v-model="userFilter.q" type="search" :placeholder="t('admin.filter.idPlaceholder')" />
        </label>
        <label v-if="isSuperadmin" class="filter-field">
          <span>{{ t('admin.colRole') }}</span>
          <select v-model="userFilter.role">
            <option value="">{{ t('admin.filter.all') }}</option>
            <option value="user">{{ t('admin.role.user') }}</option>
            <option value="admin">{{ t('admin.role.admin') }}</option>
            <option v-if="isSuperadmin" value="superadmin">{{ t('admin.role.superadmin') }}</option>
          </select>
        </label>
        <label class="filter-field">
          <span>{{ t('admin.colStatus') }}</span>
          <select v-model="userFilter.status">
            <option value="">{{ t('admin.filter.all') }}</option>
            <option value="active">{{ t('admin.filter.statusActive') }}</option>
            <option value="disabled">{{ t('admin.disabled') }}</option>
          </select>
        </label>
        <button v-if="usersFiltered" type="button" class="btn-text filter-reset" @click="resetUserFilter">
          {{ t('admin.filter.reset') }}
        </button>
      </div>

      <p v-if="!usersLoading && users.length === 0" class="empty">
        {{ usersFiltered ? t('admin.filter.noMatch') : t('admin.usersEmpty') }}
      </p>

      <!-- >=1024px: a real table — user rows are what genuinely benefits
           from tabular alignment (ID/role/status/sessions/date/actions
           as real columns), which no amount of widening a stacked card
           actually gives you. <1024px keeps the card list below instead;
           a table forces horizontal scrolling on a narrow screen. -->
      <table v-if="users.length > 0" class="users-table">
        <thead>
          <tr>
            <th>{{ t('auth.username') }}</th>
            <th>{{ t('admin.colRole') }}</th>
            <th>{{ t('admin.colStatus') }}</th>
            <th>{{ t('admin.colSessions') }}</th>
            <th>{{ t('admin.colCreated') }}</th>
            <th>{{ t('admin.colActions') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id" :class="{ protected: user.role === 'superadmin' }">
            <td class="cell-email">{{ user.username }}</td>
            <td><span class="badge" :class="user.role">{{ t(`admin.role.${user.role}`) }}</span></td>
            <td>
              <span v-if="!user.is_active" class="badge danger">{{ t('admin.disabled') }}</span>
            </td>
            <td>{{ user.session_count }}</td>
            <td>{{ formatDate(user.created_at) }}</td>
            <td class="cell-actions">
              <template v-if="resettingUser === user.id">
                <form class="reset-inline" @submit.prevent="doResetPassword(user)">
                  <input
                    v-model="resetPassword"
                    type="text"
                    required
                    :minlength="MIN_PASSWORD_LENGTH"
                    :placeholder="t('admin.account.newPassword')"
                    autocomplete="off"
                  />
                  <button type="submit" class="btn-primary">{{ t('admin.account.save') }}</button>
                  <button type="button" class="btn-outline" @click="resettingUser = null">
                    {{ t('history.clearConfirmNo') }}
                  </button>
                  <span v-if="resetError" class="create-error">{{ resetError }}</span>
                </form>
              </template>
              <template v-else-if="confirmingDeleteUser === user.id">
                <span class="confirm-inline">{{ t('admin.deleteUserConfirm') }}</span>
                <button type="button" class="btn-danger" @click="doDeleteUser(user.id)">{{ t('history.clearConfirmYes') }}</button>
                <button type="button" class="btn-outline" @click="confirmingDeleteUser = null">{{ t('history.clearConfirmNo') }}</button>
              </template>
              <template v-else>
                <button
                  v-if="user.session_count > 0 && (user.role !== 'superadmin' || user.id === auth.user?.id)"
                  type="button"
                  class="btn-outline"
                  :disabled="exportingKey !== null"
                  @click="exportUser(user)"
                >
                  {{ exportingKey === user.id ? t('admin.exporting') : t('admin.exportUser') }}
                </button>
                <template v-if="user.role === 'superadmin'">
                  <button v-if="user.id === auth.user?.id" type="button" class="btn-outline" @click="startReset(user)">
                    {{ t('admin.account.resetPassword') }}
                  </button>
                  <span class="protected-note">{{ user.id === auth.user?.id ? t('admin.protectedSelfNote') : t('admin.protectedNote') }}</span>
                </template>
                <template v-else>
                <button v-if="isSuperadmin && user.role === 'user'" type="button" class="btn-outline" @click="promote(user)">
                  {{ t('admin.promote') }}
                </button>
                <button v-if="isSuperadmin && user.role === 'admin'" type="button" class="btn-outline" @click="demote(user)">
                  {{ t('admin.demote') }}
                </button>
                <button type="button" class="btn-outline" @click="startReset(user)">
                  {{ t('admin.account.resetPassword') }}
                </button>
                <button type="button" class="btn-outline" @click="toggleActive(user)">
                  {{ user.is_active ? t('admin.disable') : t('admin.enable') }}
                </button>
                <button type="button" class="btn-danger" @click="confirmingDeleteUser = user.id">
                  {{ t('admin.deleteUser') }}
                </button>
                </template>
              </template>
            </td>
          </tr>
        </tbody>
      </table>

      <div class="user-cards">
        <div v-for="user in users" :key="user.id" class="user-row" :class="{ protected: user.role === 'superadmin' }">
          <div class="user-main">
            <div class="user-email">{{ user.username }}</div>
            <div class="user-meta">
              <span class="badge" :class="user.role">{{ t(`admin.role.${user.role}`) }}</span>
              <span v-if="!user.is_active" class="badge danger">{{ t('admin.disabled') }}</span>
              <span>{{ t('admin.userSessions', { n: user.session_count }) }}</span>
              <span>{{ formatDate(user.created_at) }}</span>
            </div>
          </div>
          <div class="user-actions">
            <button
              v-if="user.session_count > 0 && (user.role !== 'superadmin' || user.id === auth.user?.id)"
              type="button"
              class="btn-outline"
              :disabled="exportingKey !== null"
              @click="exportUser(user)"
            >
              {{ exportingKey === user.id ? t('admin.exporting') : t('admin.exportUser') }}
            </button>
            <template v-if="user.role === 'superadmin'">
              <button v-if="user.id === auth.user?.id" type="button" class="btn-outline" @click="startReset(user)">
                {{ t('admin.account.resetPassword') }}
              </button>
              <span class="protected-note">{{ user.id === auth.user?.id ? t('admin.protectedSelfNote') : t('admin.protectedNote') }}</span>
            </template>
            <template v-else>
            <button v-if="isSuperadmin && user.role === 'user'" type="button" class="btn-outline" @click="promote(user)">
              {{ t('admin.promote') }}
            </button>
            <button v-if="isSuperadmin && user.role === 'admin'" type="button" class="btn-outline" @click="demote(user)">
              {{ t('admin.demote') }}
            </button>
            <button type="button" class="btn-outline" @click="startReset(user)">
              {{ t('admin.account.resetPassword') }}
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
            </template>
          </div>
          <form v-if="resettingUser === user.id" class="confirm-row reset-inline" @submit.prevent="doResetPassword(user)">
            <input
              v-model="resetPassword"
              type="text"
              required
              :minlength="MIN_PASSWORD_LENGTH"
              :placeholder="t('admin.account.newPassword')"
              autocomplete="off"
            />
            <button type="submit" class="btn-primary">{{ t('admin.account.save') }}</button>
            <button type="button" class="btn-outline" @click="resettingUser = null">
              {{ t('history.clearConfirmNo') }}
            </button>
            <span v-if="resetError" class="create-error">{{ resetError }}</span>
          </form>
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
  </main>
    <SiteFooter />
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
  /* Narrow screens: one row that scrolls sideways instead of wrapping. */
  overflow-x: auto;
  scrollbar-width: none;
}
.tabs button {
  flex: 1 0 auto;
  white-space: nowrap;
}
.tabs button.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}
.page-title {
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
.export-row {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px;
  margin-bottom: 20px;
}
.export-format {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
}
.export-format select {
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13.5px;
  color: var(--text);
}
.export-btn {
  flex: 1;
  min-width: 200px;
}
.account-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.account-bar .btn-primary {
  padding: 9px 16px;
  font-size: 13.5px;
}
.account-flash {
  font-size: 13px;
  font-weight: 600;
  color: #1c8a4a;
}
.create-form {
  padding: 14px;
  margin-bottom: 14px;
  border: 1px solid var(--accent);
  border-radius: var(--radius-md);
  background: var(--accent-soft);
}
.create-hint {
  margin: 0 0 10px;
  font-size: 12.5px;
  color: var(--text-muted);
  line-height: 1.5;
}
.create-fields {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px 12px;
}
.create-submit {
  padding: 8px 18px;
  font-size: 13.5px;
}
.create-error {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: var(--danger);
}
.reset-inline {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.reset-inline input {
  width: 160px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px 12px;
  padding: 12px 14px;
  margin-bottom: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}
.filter-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
  min-width: 130px;
}
.filter-field.grow {
  flex: 1 1 200px;
}
.filter-field.narrow {
  min-width: 0;
  width: 110px;
}
.filter-field input,
.filter-field select {
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
  color: var(--text);
}
.filter-reset {
  align-self: flex-end;
  padding-bottom: 8px;
}
@media (max-width: 639px) {
  .filter-field {
    flex: 1 1 calc(50% - 6px);
    min-width: 0;
  }
  .filter-field.grow {
    flex-basis: 100%;
  }
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
    top: calc(var(--site-header-h) + 16px);
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
.group-head-row {
  display: flex;
  gap: 6px;
  align-items: stretch;
}
.group-export {
  flex-shrink: 0;
  padding: 6px 12px;
  font-size: 12px;
}
.group-head {
  flex: 1;
  min-width: 0;
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
}
/* The transcript uses the pane's full width; only each bubble is capped so
   a long reply still reads as a message rather than a text block. */
.conv-detail .message {
  max-width: 70%;
}
.record-badge {
  margin-left: 6px;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 11px;
  font-weight: 600;
}
.saved-records {
  align-self: stretch;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
}
.saved-records-title {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.saved-record {
  padding: 10px 12px;
  margin-bottom: 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
  line-height: 1.6;
}
.saved-record-type {
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 4px;
}
.saved-record-key {
  color: var(--text-muted);
  margin-right: 6px;
}
.saved-record-key::after {
  content: '：';
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
.protected-note {
  font-size: 12.5px;
  color: var(--text-muted);
}
tr.protected,
.user-row.protected {
  background: var(--accent-soft);
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
/* Kept last on purpose: these wide-screen overrides must come after the
   base .tabs/.page-title rules above, or those win on order.
   Wide: full width edge to edge, with real vertical breathing room —
   generous top/bottom page padding and a clear header → tabs → content
   rhythm instead of everything stacked tight against the top. */
@media (min-width: 1024px) {
  .page-title {
    margin-bottom: 8px;
  }
  .note {
    font-size: 13px;
    margin-bottom: 24px;
  }
  .tabs {
    gap: 4px;
    margin-bottom: 32px;
    padding-bottom: 0;
    border-bottom: 1px solid var(--border);
  }
  /* Underline tabs rather than three stretched buttons across a 2000px row. */
  .tabs button {
    flex: 0 0 auto;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    background: transparent;
    padding: 12px 20px;
    margin-bottom: -1px;
    font-weight: 600;
    color: var(--text-muted);
  }
  .tabs button:not(:disabled):hover {
    transform: none;
    color: var(--accent);
  }
  .tabs button.active,
  .tabs button.active:hover {
    background: transparent;
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
}
@media (min-width: 1600px) {
  .admin-view {
    padding: 40px 64px 72px;
  }
}
</style>
