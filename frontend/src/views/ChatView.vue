<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CandidateCard, ConfirmationPayload, Language } from '@/api/client'
import AppMenu from '@/components/AppMenu.vue'
import AppSidebar from '@/components/AppSidebar.vue'
import BottomToolbar from '@/components/BottomToolbar.vue'
import CandidateCardView from '@/components/cards/CandidateCardView.vue'
import ConsentDialog from '@/components/ConsentDialog.vue'
import { useSessionStore } from '@/stores/session'
import { recordFromConfirmation } from '@/utils/fieldLabels'
import { buildTranscriptMarkdown, downloadTextFile } from '@/utils/transcript'
import { displayDay } from '@/utils/time'

const { t } = useI18n()
const session = useSessionStore()
const draft = ref('')
const scrollEl = ref<HTMLElement | null>(null)
const inputEl = ref<HTMLTextAreaElement | null>(null)

// Grows with the text up to a few lines, like ChatGPT's composer.
function autosize() {
  const el = inputEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}
watch(draft, () => nextTick(autosize))

// Enter sends on a keyboard; on phones Enter is a new line and the button
// sends. Never while an IME (Chinese/Korean input) is still composing.
const touchOnly = typeof window !== 'undefined' && window.matchMedia?.('(hover: none)').matches
function onKeydown(e: KeyboardEvent) {
  if (e.key !== 'Enter' || e.shiftKey || e.isComposing || e.keyCode === 229 || touchOnly) return
  e.preventDefault()
  submit()
}

function exportConversation() {
  const content = buildTranscriptMarkdown(
    new Date().toISOString(),
    session.turns.map((turn) => ({ role: turn.role, content: turn.text, created_at: '' })),
    { title: t('app.title'), createdAt: t('history.title'), user: t('chat.you'), assistant: t('chat.assistant') },
  )
  downloadTextFile(`conversation-${displayDay()}.md`, content)
}

// Neither a resumed conversation nor an acknowledged new one — i.e. a fresh
// visit, or "new chat" from the sidebar (which resets the store). The notice
// dialog shows every time; nothing is stored until the first send.
const needsAck = computed(() => !session.sessionId && !session.pending)

// Shown only until the user's first message — plain UI chrome, not a chat
// bubble, so it never reads as something the AI said (there is no canned
// AI reply any more; the first real reply comes from the model).
const showEmptyHint = computed(() => !needsAck.value && session.turns.length === 0 && !session.sending)


// Starting a chat no longer shows any canned message — the conversation is
// entirely AI-driven from the user's first real message on (only the crisis
// safety response, app/services/dialogue_state.py, is still fixed by code).
function onAcknowledge(lang: Language) {
  session.begin(lang)
}

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

function onCardConfirm(idx: number, card: CandidateCard, payload: ConfirmationPayload) {
  session.markAnswered(idx)
  const draft = recordFromConfirmation(card, payload)
  if (draft) session.offerRecord(idx, draft)
  session.send(undefined, payload)
}

const saveFailed = ref<number | null>(null)
async function saveRecordFor(idx: number) {
  saveFailed.value = null
  try {
    await session.saveTurnRecord(idx)
  } catch {
    saveFailed.value = idx
  }
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

      <div ref="scrollEl" class="turns" :lang="session.language === 'ko' ? 'ko' : 'zh-CN'">
        <div v-if="showEmptyHint" class="chat-empty">
          <!-- documents/02_内容与需求/首选提示题建议.md, verbatim and not edited: the welcome
               sentence plus the starter list, as plain text (no clickable options). -->
          <p class="chat-empty-hint">{{ t('chat.emptyHint') }}</p>
        </div>

        <TransitionGroup name="turn" tag="div" class="turns-inner">
          <div v-for="(turn, idx) in session.turns" :key="idx" class="turn" :class="turn.role">
            <div class="bubble">{{ turn.text }}</div>
            <CandidateCardView
              v-for="(card, cIdx) in turn.candidates ?? []"
              :key="cIdx"
              :card="card"
              :disabled="session.answeredTurnIndices.has(idx)"
              @confirm="(payload) => onCardConfirm(idx, card, payload)"
            />
            <div v-if="session.recordDrafts.has(idx)" class="save-record">
              <template v-if="session.savedTurns.has(idx)">
                <span class="saved">✓ {{ t('chat.recordSaved') }}</span>
                <RouterLink to="/records" class="btn-text">{{ t('chat.viewRecords') }}</RouterLink>
              </template>
              <template v-else>
                <button
                  type="button"
                  class="btn-outline save-btn"
                  :disabled="session.savingTurn !== null"
                  @click="saveRecordFor(idx)"
                >
                  {{ session.savingTurn === idx ? t('chat.recordSaving') : t('chat.saveRecord') }}
                </button>
                <span class="save-hint">{{ saveFailed === idx ? t('chat.recordSaveFailed') : t('chat.saveRecordHint') }}</span>
              </template>
            </div>
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
            <span>{{ session.error === 'ai_unavailable' ? t('chat.aiUnavailable') : t('chat.sendError') }}</span>
            <button type="button" class="btn-danger" @click="session.retry()">{{ t('chat.retry') }}</button>
          </div>
        </Transition>
      </div>

      <div v-if="session.ended" class="footer ended-panel">
        <p class="ended-title">{{ t('chat.endedTitle') }}</p>
        <p class="ended-hint">{{ t('chat.endedHint') }}</p>
        <div class="ended-actions">
          <button type="button" class="btn-primary" @click="session.reset()">{{ t('chat.newChat') }}</button>
          <RouterLink to="/reflection" class="btn-outline">{{ t('chat.writeReflection') }}</RouterLink>
        </div>
      </div>

      <div v-else class="footer">
        <!-- Only once there is a conversation to skip / end. -->
        <BottomToolbar v-if="session.turns.length > 0" />

        <form class="composer" @submit.prevent="submit">
          <div class="composer-box">
            <textarea
              ref="inputEl"
              :lang="session.language === 'ko' ? 'ko' : 'zh-CN'"
              v-model="draft"
              rows="1"
              :placeholder="t('chat.placeholder')"
              :disabled="session.sending || needsAck"
              autocomplete="off"
              enterkeyhint="send"
              @keydown="onKeydown"
            />
            <button
              type="submit"
              class="send-btn"
              :aria-label="t('chat.send')"
              :disabled="session.sending || needsAck || !draft.trim()"
            >
              <span v-if="session.sending" class="spinner" aria-hidden="true" />
              <svg v-else viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path d="M12 19V5M5 12l7-7 7 7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </div>
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

/* >=960px: real desktop layout — sidebar + a chat column that fills all
   the remaining width. Only the bubbles themselves are capped (see .bubble
   below), so a long reply still reads as a message, not a wall of text. */
@media (min-width: 960px) {
  .wide-only {
    display: flex;
  }
  .narrow-only {
    display: none;
  }
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 8px 8px 16px;
  min-height: 52px;
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
  padding: 8px 16px 24px;
}
/* Plain instructional text, not a chat bubble — there is no canned AI
   reply any more for it to be confused with. */
.chat-empty {
  max-width: 560px;
  margin: 15vh auto 0;
  padding: 0 16px;
  text-align: center;
}
.chat-empty-hint {
  margin: 0;
  font-size: 15px;
  line-height: 1.8;
  color: var(--text);
  /* keep the line breaks of the source text (the list of starters) */
  white-space: pre-line;
  text-align: left;
}
.save-record {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  max-width: 100%;
}
.save-btn {
  padding: 6px 14px;
  font-size: 12.5px;
  border-radius: 999px;
}
.save-hint {
  font-size: 11.5px;
  color: var(--text-muted);
}
.saved {
  font-size: 12.5px;
  font-weight: 600;
  color: #1c8a4a;
}
.turns-inner {
  display: flex;
  flex-direction: column;
  gap: 22px;
}
/* One centered reading column, as in ChatGPT. */
.turns-inner,
.error-banner,
.footer > * {
  width: 100%;
  max-width: 768px;
  margin-left: auto;
  margin-right: auto;
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
  font-size: 16px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--text);
}
/* The user's words in a soft grey bubble; the AI's reply as plain text
   across the column — ChatGPT's reading layout. */
.turn.user .bubble {
  max-width: 85%;
  padding: 9px 16px;
  border-radius: 20px;
  background: var(--bg);
}
.turn.assistant .bubble {
  max-width: 100%;
}
.bubble.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 27px;
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
  background: var(--surface);
  padding: 0 12px env(safe-area-inset-bottom, 0px);
}
.composer {
  padding: 6px 0 10px;
}
.composer-box {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 6px 6px 6px 16px;
  border-radius: 26px;
  border: 1px solid var(--border);
  background: var(--surface);
  box-shadow: var(--shadow-md);
}
.composer-box:focus-within {
  border-color: var(--accent);
}
.composer textarea {
  flex: 1;
  min-width: 0;
  /* 16px: below that iOS zooms the page when the field is focused. */
  font: inherit;
  font-size: 16px;
  line-height: 1.5;
  padding: 7px 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text);
  resize: none;
  max-height: 160px;
}
.composer textarea:disabled {
  opacity: 0.6;
}
.ended-panel {
  padding: 16px 16px 20px;
  text-align: center;
}
.ended-title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.ended-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-muted);
}
.ended-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}
.ended-actions > * {
  min-width: 140px;
  padding: 9px 16px;
  font-size: 14px;
  text-decoration: none;
  text-align: center;
}
.send-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: var(--text);
  color: var(--surface);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.send-btn:disabled {
  background: var(--border);
  color: var(--text-muted);
  cursor: default;
}
.spinner {
  width: 14px;
  height: 14px;
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

/* Wide-screen spacing — last in the file so it wins over the base rules
   above (same specificity). */
@media (min-width: 960px) {
  .chat-header {
    padding: 10px 16px 10px 24px;
  }
  .turns {
    padding: 16px 24px 32px;
  }
  .footer {
    padding: 0 24px;
  }
  .composer {
    padding-bottom: 16px;
  }
  .turn.user .bubble {
    max-width: 70%;
  }
}
</style>
