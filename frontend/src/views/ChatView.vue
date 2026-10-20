<script setup lang="ts">
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Language } from '@/api/client'
import BottomToolbar from '@/components/BottomToolbar.vue'
import ConsentDialog from '@/components/ConsentDialog.vue'
import { useSessionStore } from '@/stores/session'
import { buildTranscriptMarkdown, downloadTextFile } from '@/utils/transcript'
import { displayDay } from '@/utils/time'

const { t } = useI18n()
// Narrow screens: opens AppLayout's sidebar drawer.
const openNav = inject<() => void>('openNav', () => {})
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
    session.turns.map((turn) => ({ id: turn.id ?? '', role: turn.role, content: turn.text, created_at: '' })),
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
  nextTick(() => inputEl.value?.focus())
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

// Cross-device: while this page is visible, check every few seconds for
// messages sent from elsewhere, and at once when it comes back into view.
const SYNC_MS = 4000
let syncTimer: number | undefined
function syncNow() {
  if (document.visibilityState === 'visible') void session.sync()
}
function onReturn() {
  if (document.visibilityState === 'visible') void session.sync()
}
onMounted(() => {
  syncTimer = window.setInterval(syncNow, SYNC_MS)
  document.addEventListener('visibilitychange', onReturn)
  window.addEventListener('focus', onReturn)
})
onBeforeUnmount(() => {
  window.clearInterval(syncTimer)
  document.removeEventListener('visibilitychange', onReturn)
  window.removeEventListener('focus', onReturn)
})

function submit() {
  const text = draft.value.trim()
  if (!text || session.sending) return
  draft.value = ''
  session.send(text)
}

// Rating beside each AI reply: the local dev build only, for tuning.
const showRating = import.meta.env.DEV
const RATINGS = [0, 1, 2, 3, 4, 5]

// Dots until the reply's first piece arrives; then the reply itself grows.
const waiting = computed(() => session.sending && !session.turns[session.turns.length - 1]?.streaming)

const personaId = computed({
  get: () => session.persona ?? session.defaultPersona ?? '',
  set: (id: string) => void session.choosePersona(id),
})
function personaName(p: { name: Partial<Record<Language, string>> }) {
  return p.name[session.language] ?? p.name.zh ?? ''
}
onMounted(() => void session.loadPersonas())
</script>

<template>
  <div class="chat-shell">
    <div class="chat-view">
      <header class="chat-header">
        <button type="button" class="menu-btn" :aria-label="t('toolbar.menu')" @click="openNav">
          <span /><span /><span />
        </button>
        <span class="title">{{ t('app.title') }}</span>
        <div class="header-actions">
          <select
            v-if="session.personas.length && !session.ended && !needsAck"
            v-model="personaId"
            class="persona-select"
            :aria-label="t('chat.persona')"
            :title="t('chat.persona')"
          >
            <option v-for="p in session.personas" :key="p.id" :value="p.id">{{ personaName(p) }}</option>
          </select>
          <button
            v-if="session.turns.length > 0"
            type="button"
            class="btn-text export-btn"
            @click="exportConversation"
          >
            {{ t('chat.export') }}
          </button>
        </div>
      </header>

      <div ref="scrollEl" class="turns" :lang="session.language === 'ko' ? 'ko' : 'zh-CN'">
        <ConsentDialog v-if="needsAck" @start="onAcknowledge" />
        <div v-if="showEmptyHint" class="chat-empty">
          <!-- documents/02_内容与需求/首选提示题建议.md, verbatim and not edited: the welcome
               sentence plus the starter list, as plain text (no clickable options). -->
          <p class="chat-empty-hint">{{ t('chat.emptyHint') }}</p>
        </div>

        <TransitionGroup name="turn" tag="div" class="turns-inner">
          <div v-for="(turn, idx) in session.turns" :key="idx" class="turn" :class="turn.role">
            <div class="bubble">{{ turn.text }}</div>
            <div
              v-if="showRating && turn.role === 'assistant' && turn.id && !turn.streaming"
              class="rating"
              role="group"
              :aria-label="t('chat.rate')"
              :title="t('chat.rate')"
            >
              <button
                v-for="n in RATINGS"
                :key="n"
                type="button"
                :class="{ on: turn.rating === n }"
                :aria-pressed="turn.rating === n"
                @click="session.rate(turn, turn.rating === n ? null : n)"
              >
                {{ n }}
              </button>
            </div>
          </div>

          <div v-if="waiting" key="typing" class="turn assistant">
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

      <!-- No input until the notice is accepted, nothing to type into yet. -->
      <div v-if="needsAck" class="footer" />
      <div v-else-if="session.ended" class="footer ended-panel">
        <p class="ended-title">{{ t('chat.endedTitle') }}</p>
        <p class="ended-hint">{{ t('chat.endedHint') }}</p>
        <div class="ended-actions">
          <button type="button" class="btn-primary" @click="session.reset()">{{ t('chat.newChat') }}</button>
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

  </div>
</template>

<style scoped>
.chat-shell {
  display: flex;
  flex: 1;
  min-height: 0;
  background: var(--surface);
}
.chat-view {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}


.chat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 8px 8px 8px;
  min-height: 52px;
}
.chat-header .title {
  flex: 1;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: -0.01em;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.persona-select {
  font: inherit;
  font-size: 12.5px;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text);
  max-width: 140px;
}
.rating {
  display: flex;
  gap: 4px;
}
.rating button {
  width: 26px;
  height: 26px;
  padding: 0;
  font-size: 12px;
  border: 1px solid var(--border);
  border-radius: 50%;
  background: var(--surface);
  color: var(--text-muted);
  cursor: pointer;
}
.rating button.on {
  background: var(--text);
  border-color: var(--text);
  color: var(--surface);
}
.export-btn {
  font-size: 12.5px;
  padding: 6px 8px;
}
.turns {
  flex: 1;
  min-height: 0;
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
  flex-shrink: 0;
  background: var(--surface);
  padding: 0 12px env(safe-area-inset-bottom, 0px);
}
/* A soft top edge, so the footer reads as separate from the scrolling turns
   (not on the empty placeholder footer). */
.footer:not(:empty) {
  position: relative;
  z-index: 1;
  border-top: 1px solid var(--border);
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.05);
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
  flex-shrink: 0;
  padding: 16px 16px calc(28px + env(safe-area-inset-bottom, 0px));
  text-align: center;
}
.ended-title {
  margin: 0 auto 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.ended-hint {
  margin: 0 auto 12px;
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: border-box;
  border: 1px solid transparent;
  line-height: 1.3;
  min-width: 140px;
  padding: 9px 16px;
  font-size: 14px;
  text-decoration: none;
  text-align: center;
}
.ended-actions > .btn-outline {
  border-color: var(--border);
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
  .ended-panel {
    padding: 20px 24px 32px;
  }
  .composer {
    padding-bottom: 16px;
  }
  .turn.user .bubble {
    max-width: 70%;
  }
}
</style>
