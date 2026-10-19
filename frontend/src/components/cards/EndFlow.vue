<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { SummaryCard } from '@/api/client'
import ConversationCard from '@/components/cards/ConversationCard.vue'
import { useSessionStore } from '@/stores/session'

// After "结束对话" and the AI's closing reply: the final card (save it to
// "我的记录" or not), then whether to keep the whole conversation.
const { t } = useI18n()
const session = useSessionStore()

const card = ref<SummaryCard | null>(null)
const writeFailed = ref(false)
const busy = ref(false)
const failed = ref(false)
const kept = ref(false)

async function load() {
  writeFailed.value = false
  try {
    card.value = await session.loadFinalCard()
  } catch {
    writeFailed.value = true
  }
}
onMounted(load)

function keep() {
  kept.value = true
  // Let "已保存" show for a moment before the ended panel takes over.
  window.setTimeout(() => (session.endFlow = 'done'), 1200)
}

async function remove() {
  if (busy.value) return
  busy.value = true
  failed.value = false
  try {
    await session.discardConversation()
  } catch {
    failed.value = true
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="end-flow">
    <template v-if="session.endFlow === 'card'">
      <div v-if="writeFailed" class="panel">
        <p class="note error">{{ t('chat.card.writeFailed') }}</p>
        <div class="actions">
          <button type="button" class="btn-primary" @click="load">{{ t('chat.retry') }}</button>
        </div>
      </div>
      <div v-else-if="!card" class="panel writing" role="status">
        <span class="spinner" aria-hidden="true" />{{ t('chat.card.writing') }}
      </div>
      <ConversationCard v-else :card="card" :decide="session.decideFinalCard" @done="session.endFlow = 'conversation'" />
    </template>

    <div v-else-if="session.endFlow === 'conversation'" class="panel" role="alertdialog" :aria-label="t('chat.endFlow.ask')">
      <template v-if="kept">
        <p class="result">✓ {{ t('chat.endFlow.saved') }}</p>
      </template>
      <template v-else>
        <p class="question">{{ t('chat.endFlow.ask') }}</p>
        <p class="note">{{ t('chat.endFlow.note') }}</p>
        <p v-if="failed" class="note error">{{ t('toolbar.deleteFailed') }}</p>
        <div class="actions">
          <button type="button" class="btn-primary" :disabled="busy" @click="keep">{{ t('chat.endFlow.save') }}</button>
          <button type="button" class="btn-danger" :disabled="busy" @click="remove">{{ t('chat.endFlow.delete') }}</button>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.end-flow {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}
.panel {
  box-sizing: border-box;
  width: 100%;
  max-width: 520px;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 12px);
  background: var(--surface);
  box-shadow: var(--shadow-md);
}
.writing {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: var(--text-muted);
}
.question {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.note {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
.note.error {
  margin-top: 4px;
  color: var(--danger);
}
.result {
  margin: 0;
  font-size: 14.5px;
  font-weight: 600;
  color: #1c8a4a;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}
.actions button {
  flex: 1 1 0;
  min-width: 120px;
  padding: 8px 14px;
  font-size: 14px;
  border: 1px solid transparent;
  border-radius: 999px;
}
.actions .btn-danger {
  border-color: var(--danger-border);
}
.spinner {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 2px solid var(--border);
  border-top-color: var(--text-muted);
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
