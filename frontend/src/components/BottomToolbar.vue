<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const session = useSessionStore()

// "结束对话" asks once before locking the conversation.
const confirmingEnd = ref(false)

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
  confirmingEnd.value = false
  await session.endConversation()
}
</script>

<template>
  <nav v-if="confirmingEnd" class="toolbar confirm" role="alertdialog" :aria-label="t('toolbar.endConfirm')">
    <span class="confirm-text">{{ t('toolbar.endConfirm') }}</span>
    <button type="button" class="btn-outline" @click="confirmingEnd = false">{{ t('toolbar.endNo') }}</button>
    <button type="button" class="btn-danger" :disabled="session.sending" @click="endConversation">
      {{ t('toolbar.endYes') }}
    </button>
  </nav>
  <nav v-else class="toolbar">
    <button type="button" class="btn-outline" :disabled="session.sending" @click="anotherQuestion">
      {{ t('toolbar.another') }}
    </button>
    <button type="button" class="btn-outline" :disabled="session.sending" @click="skipQuestion">
      {{ t('toolbar.skip') }}
    </button>
    <button type="button" class="btn-outline end-btn" :disabled="session.sending" @click="confirmingEnd = true">
      {{ t('toolbar.end') }}
    </button>
  </nav>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px;
  padding: 10px 12px 0;
}
.toolbar button {
  flex: 1;
  padding: 8px 6px;
  font-size: 12.5px;
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
.toolbar.confirm {
  align-items: center;
  flex-wrap: wrap;
}
.confirm-text {
  flex: 1 1 100%;
  font-size: 13px;
  color: var(--text);
}
.toolbar.confirm button {
  flex: 0 0 auto;
  min-width: 96px;
}
</style>
