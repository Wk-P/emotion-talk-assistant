<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  clearHistory,
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

async function load() {
  items.value = await listHistory()
}

async function toggle(sessionId: string) {
  if (openId.value === sessionId) {
    openId.value = null
    return
  }
  openMessages.value = await getSessionMessages(sessionId)
  openId.value = sessionId
}

async function continueConversation(item: SessionHistoryItem) {
  await session.resume(item.session_id, item.language)
  router.push('/chat')
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
    <div class="page-inner-wide">
      <header class="header">
        <button type="button" class="btn-back" @click="router.push('/chat')"><span class="arrow">&lt;</span> {{ t('history.back') }}</button>
      </header>

      <h1 class="page-title">{{ t('history.title') }}</h1>

      <p v-if="items.length === 0" class="empty">{{ t('history.empty') }}</p>

      <TransitionGroup name="entry" tag="div">
        <div v-for="item in items" :key="item.session_id" class="entry">
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
          </div>
          <Transition name="expand">
            <div v-if="openId === item.session_id" class="messages">
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
  </div>
</template>

<style scoped>
.history-view {
  padding: 16px;
}
@media (min-width: 640px) {
  .history-view {
    padding: 32px;
  }
}
.header {
  margin-bottom: 14px;
}
.page-title {
  font-size: 17px;
  font-weight: 700;
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
