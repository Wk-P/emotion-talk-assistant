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
import { useAuthStore } from '@/stores/auth'
import { getDeviceId } from '@/utils/device'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const items = ref<SessionHistoryItem[]>([])
const openId = ref<string | null>(null)
const openMessages = ref<HistoryMessageItem[]>([])
const confirmingClear = ref(false)

// Logged in: history is scoped to the account (works across devices). Not
// logged in: falls back to this browser's local device_id (see utils/device).
async function load() {
  items.value = await listHistory(auth.user ? undefined : getDeviceId())
}

async function toggle(sessionId: string) {
  if (openId.value === sessionId) {
    openId.value = null
    return
  }
  openMessages.value = await getSessionMessages(sessionId)
  openId.value = sessionId
}

async function doClear() {
  await clearHistory(auth.user ? undefined : getDeviceId())
  confirmingClear.value = false
  openId.value = null
  await load()
}

onMounted(load)
</script>

<template>
  <div class="history-view">
    <header class="header">
      <button type="button" @click="router.push('/chat')">← {{ t('history.back') }}</button>
      <h1>{{ t('history.title') }}</h1>
    </header>

    <p v-if="items.length === 0" class="empty">{{ t('history.empty') }}</p>

    <div v-for="item in items" :key="item.session_id" class="entry">
      <button type="button" class="entry-head" @click="toggle(item.session_id)">
        <span>{{ new Date(item.created_at).toLocaleString() }}</span>
        <span class="count">{{ t('history.messageCount', { n: item.message_count }) }}</span>
      </button>
      <div v-if="openId === item.session_id" class="messages">
        <p v-if="openMessages.length === 0" class="empty">{{ t('history.noMessages') }}</p>
        <div v-for="(m, i) in openMessages" :key="i" class="message" :class="m.role">
          {{ m.content }}
        </div>
      </div>
    </div>

    <div class="clear-zone">
      <button v-if="!confirmingClear" type="button" class="clear" @click="confirmingClear = true">
        {{ t('history.clear') }}
      </button>
      <div v-else class="confirm">
        <p>{{ t('history.clearConfirm') }}</p>
        <div class="confirm-actions">
          <button type="button" class="clear" @click="doClear">{{ t('history.clearConfirmYes') }}</button>
          <button type="button" @click="confirmingClear = false">{{ t('history.clearConfirmNo') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.history-view {
  max-width: 480px;
  margin: 0 auto;
  padding: 16px;
}
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.header button {
  border: none;
  background: none;
  color: #6c5ce7;
}
.empty {
  color: #888;
}
.entry {
  border: 1px solid #eee;
  border-radius: 10px;
  margin-bottom: 10px;
  overflow: hidden;
}
.entry-head {
  width: 100%;
  display: flex;
  justify-content: space-between;
  padding: 10px;
  background: #f7f6fb;
  border: none;
  font-size: 13px;
  color: #444;
}
.count {
  color: #888;
}
.messages {
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.message {
  font-size: 13px;
  padding: 6px 8px;
  border-radius: 8px;
  line-height: 1.5;
}
.message.user {
  background: #ece9fb;
  align-self: flex-end;
}
.message.assistant {
  background: #f2f2f2;
  align-self: flex-start;
}
.clear-zone {
  margin-top: 24px;
  border-top: 1px solid #eee;
  padding-top: 16px;
}
.clear {
  border: 1px solid #e0a0a0;
  color: #c0392b;
  background: #fff;
  border-radius: 8px;
  padding: 10px;
  width: 100%;
}
.confirm p {
  font-size: 13px;
  color: #555;
  margin-bottom: 8px;
}
.confirm-actions {
  display: flex;
  gap: 8px;
}
.confirm-actions button {
  flex: 1;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid #d8d3ea;
  background: #fff;
}
</style>
