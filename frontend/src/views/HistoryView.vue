<script setup lang="ts">
import SiteFooter from '@/components/SiteFooter.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  clearHistory,
  deleteSession,
  getSessionMessages,
  listHistory,
  type HistoryMessageItem,
  type SessionHistoryItem,
} from '@/api/client'
import { useSessionStore } from '@/stores/session'
import { buildTranscriptMarkdown, downloadTextFile } from '@/utils/transcript'

const { t } = useI18n()
const router = useRouter()
const session = useSessionStore()

const items = ref<SessionHistoryItem[]>([])
const openId = ref<string | null>(null)
const openMessages = ref<HistoryMessageItem[]>([])
const confirmingClear = ref(false)
const selected = computed(() => items.value.find((i) => i.session_id === openId.value) ?? null)

async function load() {
  items.value = await listHistory()
  // Wide screens show a detail pane — open the newest conversation so it
  // isn't an empty half-page on arrival.
  if (!openId.value && items.value[0] && isWide()) {
    await toggle(items.value[0].session_id)
  }
}

const isWide = () => window.matchMedia('(min-width: 1024px)').matches

async function toggle(sessionId: string) {
  if (openId.value === sessionId) {
    // Wide: the list is a selector for the detail pane, so re-clicking the
    // selected entry keeps it open instead of blanking the pane.
    if (!isWide()) openId.value = null
    return
  }
  openMessages.value = await getSessionMessages(sessionId)
  openId.value = sessionId
}

async function continueConversation(item: SessionHistoryItem) {
  await session.resume(item.session_id, item.language, !!item.ended_at)
  router.push('/')
}

async function exportConversation(item: SessionHistoryItem) {
  const messages = openId.value === item.session_id ? openMessages.value : await getSessionMessages(item.session_id)
  const content = buildTranscriptMarkdown(item.created_at, messages, {
    title: t('app.title'),
    createdAt: t('history.title'),
    user: t('chat.you'),
    assistant: t('chat.assistant'),
  })
  downloadTextFile(`conversation-${item.created_at.slice(0, 10)}.md`, content)
}

// One conversation at a time; the open chat is dropped if it was this one.
const confirmingDelete = ref<string | null>(null)
async function doDelete(item: SessionHistoryItem) {
  await deleteSession(item.session_id)
  confirmingDelete.value = null
  if (openId.value === item.session_id) openId.value = null
  if (session.sessionId === item.session_id) session.reset()
  await load()
}

async function doClear() {
  await clearHistory()
  confirmingClear.value = false
  openId.value = null
  // Clearing history deletes every session, including whichever one is
  // still open in ChatView — drop that reference too so the next message
  // send doesn't 404 against a session id that no longer exists.
  session.reset()
  await load()
}

onMounted(load)
</script>

<template>
  <div class="history-view">
    <SiteHeader />
    <main class="page-body">
    <div class="page-full">

      <h1 class="page-title">{{ t('history.title') }}</h1>

      <p v-if="items.length === 0" class="empty">{{ t('history.empty') }}</p>

      <!-- >=1024px: list on the left, the selected conversation on the right.
           Narrower: each entry expands its own transcript inline. -->
      <div class="hist-layout">
      <div class="hist-list">
      <TransitionGroup name="entry" tag="div">
        <div v-for="item in items" :key="item.session_id" class="entry" :class="{ selected: openId === item.session_id }">
          <button type="button" class="entry-head" @click="toggle(item.session_id)">
            <span>{{ new Date(item.created_at).toLocaleString() }}</span>
            <span class="count">{{ t('history.messageCount', { n: item.message_count }) }}</span>
          </button>
          <div class="entry-actions">
            <button type="button" class="btn-outline" @click="continueConversation(item)">
              {{ t('history.continue') }}
            </button>
            <button type="button" class="btn-outline" @click="exportConversation(item)">
              {{ t('history.export') }}
            </button>
            <button type="button" class="btn-outline danger" @click="confirmingDelete = item.session_id">
              {{ t('history.delete') }}
            </button>
          </div>
          <div v-if="confirmingDelete === item.session_id" class="delete-confirm entry-confirm">
            <span>{{ t('history.deleteConfirm') }}</span>
            <button type="button" class="btn-danger" @click="doDelete(item)">{{ t('history.deleteYes') }}</button>
            <button type="button" class="btn-outline" @click="confirmingDelete = null">{{ t('history.clearConfirmNo') }}</button>
          </div>
          <Transition name="expand">
            <div v-if="openId === item.session_id" class="messages inline">
              <p v-if="openMessages.length === 0" class="empty">{{ t('history.noMessages') }}</p>
              <div v-for="(m, i) in openMessages" :key="i" class="message" :class="m.role">
                {{ m.content }}
              </div>
            </div>
          </Transition>
        </div>
      </TransitionGroup>

      <div class="clear-zone">
        <button v-if="!confirmingClear" type="button" class="btn-danger clear" @click="confirmingClear = true">
          {{ t('history.clear') }}
        </button>
        <div v-else class="confirm">
          <p>{{ t('history.clearConfirm') }}</p>
          <div class="confirm-actions">
            <button type="button" class="btn-danger" @click="doClear">{{ t('history.clearConfirmYes') }}</button>
            <button type="button" class="btn-outline" @click="confirmingClear = false">{{ t('history.clearConfirmNo') }}</button>
          </div>
        </div>
      </div>
      </div>

      <div v-if="items.length > 0" class="hist-detail">
        <template v-if="selected">
          <div class="detail-header">
            <span class="detail-date">{{ new Date(selected.created_at).toLocaleString() }}</span>
            <div class="detail-actions">
              <button type="button" class="btn-primary" @click="continueConversation(selected)">
                {{ t('history.continue') }}
              </button>
              <button type="button" class="btn-outline" @click="exportConversation(selected)">
                {{ t('history.export') }}
              </button>
              <button type="button" class="btn-outline danger" @click="confirmingDelete = selected.session_id">
                {{ t('history.delete') }}
              </button>
            </div>
            <div v-if="confirmingDelete === selected.session_id" class="delete-confirm">
              <span>{{ t('history.deleteConfirm') }}</span>
              <button type="button" class="btn-danger" @click="doDelete(selected)">{{ t('history.deleteYes') }}</button>
              <button type="button" class="btn-outline" @click="confirmingDelete = null">{{ t('history.clearConfirmNo') }}</button>
            </div>
          </div>
          <div class="messages">
            <p v-if="openMessages.length === 0" class="empty">{{ t('history.noMessages') }}</p>
            <div v-for="(m, i) in openMessages" :key="i" class="message" :class="m.role">
              {{ m.content }}
            </div>
          </div>
        </template>
        <p v-else class="detail-placeholder">{{ t('history.selectHint') }}</p>
      </div>
      </div>
    </div>
  </main>
    <SiteFooter />
  </div>
</template>

<style scoped>
.page-title {
  margin-bottom: 20px;
}
.empty {
  color: var(--text-muted);
  font-size: 14px;
}
.entry {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  margin-bottom: 10px;
  overflow: hidden;
}
.entry-head {
  width: 100%;
  display: flex;
  justify-content: space-between;
  padding: 12px;
  background: var(--bg);
  border: none;
  font-size: 13px;
  color: var(--text);
}
.count {
  color: var(--text-muted);
}
.entry-actions {
  display: flex;
  gap: 8px;
  padding: 0 12px 10px;
}
.entry-actions button {
  flex: 1;
  padding: 6px 8px;
  font-size: 12.5px;
}
.page-full {
  width: 100%;
}
.hist-detail {
  display: none;
}
@media (min-width: 1024px) {
  .hist-layout {
    display: flex;
    align-items: flex-start;
    gap: 24px;
  }
  .hist-list {
    width: clamp(320px, 28vw, 420px);
    flex-shrink: 0;
  }
  /* The detail pane shows the transcript and the actions instead. */
  .messages.inline,
  .entry-actions {
    display: none;
  }
  .entry.selected {
    border-color: var(--accent);
  }
  .entry.selected .entry-head {
    background: var(--accent-soft);
  }
  .hist-detail {
    display: block;
    flex: 1;
    min-width: 0;
    position: sticky;
    top: calc(var(--site-header-h) + 24px);
    max-height: calc(100dvh - var(--site-header-h) - 48px);
    overflow-y: auto;
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: var(--bg);
  }
  .hist-detail .messages {
    padding: 20px 24px;
    gap: 10px;
  }
  .hist-detail .message {
    max-width: 70%;
    font-size: 14px;
    padding: 9px 13px;
  }
  .hist-detail .message.assistant {
    background: var(--surface);
    border: 1px solid var(--border);
  }
}
.detail-header {
  position: sticky;
  top: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.detail-date {
  font-size: 14px;
  font-weight: 600;
}
.btn-outline.danger {
  color: var(--danger);
  border-color: var(--danger-border);
}
.delete-confirm {
  flex-basis: 100%;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--danger-soft);
  font-size: 13px;
  color: var(--danger);
}
.delete-confirm button {
  padding: 5px 12px;
  font-size: 12.5px;
}
.entry-confirm {
  margin: 0 12px 10px;
}
.detail-actions {
  display: flex;
  gap: 8px;
}
.detail-actions button {
  padding: 7px 14px;
  font-size: 13px;
}
.detail-placeholder {
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
  padding: 60px 0;
}
.messages {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
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
  background: var(--bg);
  align-self: flex-start;
}
.clear-zone {
  margin-top: 24px;
  border-top: 1px solid var(--border);
  padding-top: 16px;
}
.clear {
  width: 100%;
}
.confirm p {
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.confirm-actions {
  display: flex;
  gap: 8px;
}
.confirm-actions button {
  flex: 1;
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
  max-height: 400px;
}
</style>
