<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import {
  getAdminSessionMessages,
  listAdminSessions,
  type AdminSessionItem,
  type HistoryMessageItem,
} from '@/api/client'

const { t } = useI18n()
const router = useRouter()

const items = ref<AdminSessionItem[]>([])
const openId = ref<string | null>(null)
const openMessages = ref<HistoryMessageItem[]>([])
const loading = ref(true)

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

onMounted(load)
</script>

<template>
  <div class="history-view">
    <header class="header">
      <button type="button" class="btn-back" @click="router.push('/')"><span class="arrow">&lt;</span> {{ t('admin.back') }}</button>
    </header>

    <h1 class="page-title">{{ t('admin.title') }}</h1>
    <p class="note">{{ t('admin.note') }}</p>

    <p v-if="!loading && items.length === 0" class="empty">{{ t('admin.empty') }}</p>

    <TransitionGroup name="entry" tag="div">
      <div v-for="item in items" :key="item.session_id" class="entry">
        <button type="button" class="entry-head" @click="toggle(item.session_id)">
          <span class="participant">{{ item.participant_label }}</span>
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
  margin: 0 0 20px;
  line-height: 1.5;
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
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--bg);
  border: none;
  font-size: 13px;
  color: var(--text);
}
.participant {
  font-weight: 600;
  color: var(--accent);
  font-family: ui-monospace, monospace;
  font-size: 12px;
}
.count {
  color: var(--text-muted);
  flex-shrink: 0;
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
