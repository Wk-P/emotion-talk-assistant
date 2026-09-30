<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ConfirmationPayload, Language } from '@/api/client'
import AppMenu from '@/components/AppMenu.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import BottomToolbar from '@/components/BottomToolbar.vue'
import CandidateCardView from '@/components/cards/CandidateCardView.vue'
import ConsentDialog from '@/components/ConsentDialog.vue'
import { useSessionStore } from '@/stores/session'
import { buildTranscriptMarkdown, downloadTextFile } from '@/utils/transcript'

const { t } = useI18n()
const session = useSessionStore()
const draft = ref('')
const scrollEl = ref<HTMLElement | null>(null)

function exportConversation() {
  const content = buildTranscriptMarkdown(
    new Date().toISOString(),
    session.turns.map((turn) => ({ role: turn.role, content: turn.text, created_at: '' })),
    { title: t('app.title'), createdAt: t('history.title'), user: t('chat.you'), assistant: t('chat.assistant') },
  )
  downloadTextFile(`conversation-${new Date().toISOString().slice(0, 10)}.md`, content)
}

// Neither a resumed conversation nor an acknowledged new one — i.e. a fresh
// visit, or "new chat" from the sidebar (which resets the store). The notice
// dialog shows every time; nothing is stored until the first send.
const needsAck = computed(() => !session.sessionId && !session.pending)

function onAcknowledge(lang: Language) {
  session.begin(lang)
  // Opening: deterministic, no LLM call, nothing stored.
  session.loadOpening()
}

onMounted(() => {
  if (!needsAck.value) session.loadOpening()
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
  <div class="chat-shell">
    <!-- >=960px: persistent nav replaces the header's dropdown menu. Kept in
         the DOM at all widths and toggled with CSS so there's no layout
         flash while resizing. -->
    <AppSidebar class="wide-only" />

    <div class="chat-view">
      <header class="chat-header">
        <span class="title">{{ t('app.title') }}</span>
        <div class="header-actions">
          <button
            v-if="session.turns.length > 0"
            type="button"
            class="btn-text export-btn"
            @click="exportConversation"
          >
            {{ t('chat.export') }}
          </button>
          <AppMenu class="narrow-only" />
        </div>
      </header>

      <div ref="scrollEl" class="turns">
        <TransitionGroup name="turn" tag="div" class="turns-inner">
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

          <div v-if="session.sending" key="typing" class="turn assistant">
            <div class="bubble typing" role="status" :aria-label="t('chat.assistant')">
              <span class="dot" />
              <span class="dot" />
              <span class="dot" />
            </div>
          </div>
        </TransitionGroup>

        <Transition name="turn">
          <div v-if="session.error" class="error-banner">
            <span>{{ t('chat.sendError') }}</span>
            <button type="button" class="btn-danger" @click="session.retry()">{{ t('chat.retry') }}</button>
          </div>
        </Transition>
      </div>

      <div class="footer">
        <BottomToolbar />

        <form class="composer" @submit.prevent="submit">
          <input
            v-model="draft"
            :placeholder="t('chat.placeholder')"
            :disabled="session.sending || needsAck"
            autocomplete="off"
          />
          <button type="submit" class="btn-primary send-btn" :disabled="session.sending || needsAck || !draft.trim()">
            <span v-if="!session.sending">{{ t('chat.send') }}</span>
            <span v-else class="spinner" aria-hidden="true" />
          </button>
        </form>
      </div>
    </div>

    <ConsentDialog v-if="needsAck" @start="onAcknowledge" />
  </div>
</template>

<style scoped>
.chat-shell {
  display: flex;
  height: 100dvh;
  background: var(--surface);
}
.wide-only {
  display: none;
}
.chat-view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* >=960px: real desktop layout — sidebar + a chat column that uses the
   extra width instead of floating a phone-width card in empty space. */
@media (min-width: 960px) {
  .wide-only {
    display: flex;
  }
  .narrow-only {
    display: none;
  }
  .chat-view {
    max-width: 760px;
    margin: 0 auto;
  }
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}
.chat-header .title {
  font-weight: 700;
  font-size: 15px;
  letter-spacing: -0.01em;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.export-btn {
  font-size: 12.5px;
  padding: 6px 8px;
}
.turns {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
.turns-inner {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.turn-enter-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s ease;
}
.turn-enter-from {
  opacity: 0;
  transform: translateY(10px) scale(0.98);
}
.turn-leave-active {
  transition: opacity 0.15s ease;
  position: absolute;
}
.turn-leave-to {
  opacity: 0;
}
.turn-move {
  transition: transform 0.2s ease;
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
  padding: 11px 15px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.55;
  white-space: pre-wrap;
  box-shadow: var(--shadow-sm);
}
.turn.user .bubble {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 6px 16px rgba(108, 92, 231, 0.25);
}
.turn.assistant .bubble {
  background: var(--bg);
  color: var(--text);
  border-bottom-left-radius: 4px;
}
.bubble.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 13px 16px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
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
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: 13px;
}
.error-banner .btn-danger {
  padding: 4px 10px;
  flex-shrink: 0;
  background: var(--surface);
}
.footer {
  border-top: 1px solid var(--border);
  background: var(--surface);
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
.composer {
  display: flex;
  gap: 8px;
  padding: 10px 12px 12px;
}
.composer input {
  flex: 1;
  padding: 11px 16px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg);
}
.composer input:disabled {
  opacity: 0.6;
}
.composer button.send-btn {
  min-width: 64px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
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
