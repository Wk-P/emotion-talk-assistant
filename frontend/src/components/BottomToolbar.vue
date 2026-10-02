<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const session = useSessionStore()

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
</script>

<template>
  <nav class="toolbar">
    <button type="button" class="btn-outline" :disabled="session.sending" @click="anotherQuestion">
      {{ t('toolbar.another') }}
    </button>
    <button type="button" class="btn-outline" :disabled="session.sending" @click="skipQuestion">
      {{ t('toolbar.skip') }}
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
</style>
