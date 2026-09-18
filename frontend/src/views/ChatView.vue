<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { ConfirmationPayload } from '@/api/client'
import BottomToolbar from '@/components/BottomToolbar.vue'
import CandidateCardView from '@/components/cards/CandidateCardView.vue'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const router = useRouter()
const session = useSessionStore()
const draft = ref('')
const scrollEl = ref<HTMLElement | null>(null)

onMounted(() => {
  if (!session.sessionId) {
    router.replace('/')
    return
  }
  if (session.turns.length === 0) {
    // Kick off the flow — deterministic intent_options card, no LLM call.
    session.send()
  }
})

function scrollToBottom() {
  nextTick(() => {
    scrollEl.value?.scrollTo({ top: scrollEl.value.scrollHeight, behavior: 'smooth' })
  })
}

// Watch both: turns.length alone misses the moment the typing indicator
// appears/disappears (sending flips before the next turn is pushed), which
// left the indicator rendering below the fold with no scroll.
watch(() => session.turns.length, scrollToBottom)
watch(() => session.sending, scrollToBottom)

function submit() {
  const text = draft.value.trim()
  if (!text || session.sending) return
  draft.value = ''
  session.send(text)
}

function onCardConfirm(idx: number, payload: ConfirmationPayload) {
  session.markAnswered(idx)
  session.send(undefined, payload)
}
</script>

<template>
  <div class="chat-view">
    <header class="chat-header">{{ t('app.title') }}</header>

    <div ref="scrollEl" class="turns">
      <div v-for="(turn, idx) in session.turns" :key="idx" class="turn" :class="turn.role">
        <div class="bubble">{{ turn.text }}</div>
        <CandidateCardView
          v-for="(card, cIdx) in turn.candidates ?? []"
          :key="cIdx"
          :card="card"
          :disabled="session.answeredTurnIndices.has(idx)"
          @confirm="(payload) => onCardConfirm(idx, payload)"
        />
      </div>

      <div v-if="session.sending" class="turn assistant">
        <div class="bubble typing" role="status" :aria-label="t('chat.assistant')">
          <span class="dot" />
          <span class="dot" />
          <span class="dot" />
        </div>
      </div>

      <div v-if="session.error" class="error-banner">
        <span>{{ t('chat.sendError') }}</span>
        <button type="button" @click="session.retry()">{{ t('chat.retry') }}</button>
      </div>
    </div>

    <form class="composer" @submit.prevent="submit">
      <input
        v-model="draft"
        :placeholder="t('chat.placeholder')"
        :disabled="session.sending"
        autocomplete="off"
      />
      <button type="submit" class="send-btn" :disabled="session.sending || !draft.trim()">
        <span v-if="!session.sending">{{ t('chat.send') }}</span>
        <span v-else class="spinner" aria-hidden="true" />
      </button>
    </form>

    <BottomToolbar />
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100dvh;
  max-width: 480px;
  margin: 0 auto;
  background: #fff;
}
.chat-header {
  padding: 12px 16px;
  font-weight: 600;
  border-bottom: 1px solid #eee;
}
.turns {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.turn {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.turn.user {
  align-items: flex-end;
}
.turn.assistant {
  align-items: flex-start;
}
.bubble {
  max-width: 85%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
}
.turn.user .bubble {
  background: #6c5ce7;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.turn.assistant .bubble {
  background: #f1f0f7;
  color: #333;
  border-bottom-left-radius: 4px;
}
.bubble.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 16px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #9992b8;
  animation: bounce 1.2s infinite ease-in-out;
}
.dot:nth-child(2) {
  animation-delay: 0.15s;
}
.dot:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #fdecea;
  color: #b3261e;
  font-size: 13px;
}
.error-banner button {
  border: 1px solid #b3261e;
  color: #b3261e;
  background: #fff;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 12px;
  flex-shrink: 0;
}
.composer {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid #eee;
}
.composer input {
  flex: 1;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #d8d3ea;
  transition: opacity 0.15s ease;
}
.composer input:disabled {
  opacity: 0.6;
}
.composer button.send-btn {
  min-width: 64px;
  padding: 10px 16px;
  border-radius: 10px;
  border: none;
  background: #6c5ce7;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.15s ease;
}
.composer button.send-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.spinner {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: #fff;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
