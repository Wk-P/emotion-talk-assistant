<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const session = useSessionStore()

// "终止对话" first asks save or delete; delete asks once more, since it
// also removes what the user saved to "我的记录" from this conversation.
const step = ref<'idle' | 'ask' | 'confirmDelete'>('idle')
const deleting = ref(false)
const failed = ref(false)

function close() {
  step.value = 'idle'
  failed.value = false
}

function skipQuestion() {
  if (session.sending) return
  session.send(undefined, { card_type: 'skip' })
}

function anotherQuestion() {
  if (session.sending) return
  // Sent into the conversation, so it follows the conversation's language
  // (zh/ko), not the interface language.
  session.send(session.language === 'ko' ? '다른 질문으로 해주세요' : '换一个问题')
}

async function endConversation() {
  close()
  await session.endConversation()
}

async function discardConversation() {
  failed.value = false
  deleting.value = true
  try {
    await session.discardConversation()
    step.value = 'idle'
  } catch {
    failed.value = true
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <nav v-if="step === 'ask'" class="toolbar confirm" role="alertdialog" :aria-label="t('toolbar.endConfirm')">
    <span class="confirm-text">{{ t('toolbar.endConfirm') }}</span>
    <div class="confirm-actions">
      <button type="button" class="btn-primary" :disabled="session.sending" @click="endConversation">
        {{ t('toolbar.endSave') }}
      </button>
      <button type="button" class="btn-danger" :disabled="session.sending" @click="step = 'confirmDelete'">
        {{ t('toolbar.endDelete') }}
      </button>
      <button type="button" class="btn-outline" @click="close">{{ t('toolbar.endNo') }}</button>
    </div>
  </nav>
  <nav v-else-if="step === 'confirmDelete'" class="toolbar confirm" role="alertdialog" :aria-label="t('toolbar.deleteConfirm')">
    <span class="confirm-text">
      {{ t('toolbar.deleteConfirm') }}
      <template v-if="session.savedTurns.size > 0">{{ t('toolbar.deleteRecords', { n: session.savedTurns.size }) }}</template>
    </span>
    <span v-if="failed" class="confirm-text error">{{ t('toolbar.deleteFailed') }}</span>
    <div class="confirm-actions">
      <button type="button" class="btn-danger" :disabled="session.sending || deleting" @click="discardConversation">
        {{ deleting ? t('toolbar.deleting') : t('toolbar.deleteYes') }}
      </button>
      <button type="button" class="btn-outline" :disabled="deleting" @click="step = 'ask'; failed = false">
        {{ t('toolbar.deleteBack') }}
      </button>
    </div>
  </nav>
  <nav v-else class="toolbar">
    <button type="button" class="btn-outline" :disabled="session.sending" @click="anotherQuestion">
      {{ t('toolbar.another') }}
    </button>
    <button type="button" class="btn-outline" :disabled="session.sending" @click="skipQuestion">
      {{ t('toolbar.skip') }}
    </button>
    <button type="button" class="btn-outline end-btn" :disabled="session.sending" @click="step = 'ask'">
      {{ t('toolbar.end') }}
    </button>
  </nav>
</template>

<style scoped>
/* Small chips above the composer, not full-width buttons. */
.toolbar {
  display: flex;
  gap: 6px;
  padding: 4px 0 2px;
  overflow-x: auto;
  scrollbar-width: none;
}
.toolbar button {
  flex: 0 0 auto;
  padding: 5px 12px;
  font-size: 13px;
  border-radius: 999px;
}
.end-btn {
  color: var(--danger);
  border-color: var(--danger-border);
}
.end-btn:not(:disabled):hover {
  background: var(--danger-soft);
  border-color: var(--danger);
  color: var(--danger);
}
/* Not scrollable like the chip row: that clipped the buttons' shadow and
   bottom edge. All three buttons share one size and shape. */
.toolbar.confirm {
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
  overflow: visible;
  padding: 8px 0 4px;
}
.confirm-text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text);
}
.confirm-text.error {
  color: var(--danger);
}
.confirm-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.toolbar.confirm .confirm-actions button {
  flex: 1 1 0;
  min-width: 88px;
  padding: 8px 12px;
  font-size: 14px;
  line-height: 1.3;
  border: 1px solid transparent;
  border-radius: 999px;
  box-shadow: none;
}
.toolbar.confirm .confirm-actions .btn-outline {
  border-color: var(--border);
}
.toolbar.confirm .confirm-actions .btn-danger {
  border-color: var(--danger-border);
}
</style>
