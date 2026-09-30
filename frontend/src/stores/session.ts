import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { CandidateCard, ConfirmationPayload, Language } from '@/api/client'
import { endSession, getOpening, getSessionMessages, sendChat, startSession, updateConsent } from '@/api/client'

export interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
  candidates?: CandidateCard[]
  riskLevel?: 'none' | 'watch' | 'crisis'
}

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref<string | null>(null)
  // A new chat is open but nothing has been sent yet, so no session exists
  // on the backend — like ChatGPT, the conversation is only created on the
  // first send (see send()). Starting and walking away leaves no record.
  const pending = ref(false)
  const language = ref<Language>('zh')
  const turns = ref<ChatTurn[]>([])
  const sending = ref(false)
  const consent = ref<Record<string, boolean>>({})
  // Indices into `turns` whose candidate card(s) have already been acted on —
  // used to lock those cards so a second tap can't resend the same choice.
  const answeredTurnIndices = ref<Set<number>>(new Set())
  // Set when the last send() failed (network/API error) so the UI can show a
  // retry affordance instead of silently doing nothing.
  const error = ref<string | null>(null)
  const lastFailedSend = ref<{ message?: string; confirmation?: ConfirmationPayload } | null>(null)

  function begin(lang: Language) {
    reset()
    language.value = lang
    pending.value = true
  }

  // Shows the disclaimer + intent question without creating anything.
  async function loadOpening() {
    if (sessionId.value || turns.value.length > 0) return
    sending.value = true
    try {
      const res = await getOpening(language.value)
      turns.value.push({ role: 'assistant', text: res.reply_text, candidates: res.candidates, riskLevel: res.risk_level })
    } finally {
      sending.value = false
    }
  }

  // Re-opens a past conversation instead of starting a new one — the
  // backend chat endpoint already accepts further messages against an
  // existing session_id (there is no "closed" state that blocks it), so
  // this only needs to rehydrate local state from the stored history.
  // Replayed turns never carry candidate cards (history only stores
  // role/content), so they render as plain bubbles, same as a live reply
  // once its card has been confirmed.
  async function resume(id: string, lang: Language) {
    const messages = await getSessionMessages(id)
    pending.value = false
    sessionId.value = id
    language.value = lang
    turns.value = messages
      .filter((m): m is typeof m & { role: 'user' | 'assistant' } => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, text: m.content }))
    answeredTurnIndices.value = new Set()
    error.value = null
    lastFailedSend.value = null
  }

  async function send(message?: string, confirmation?: ConfirmationPayload, opts?: { skipBubble?: boolean }) {
    if ((!sessionId.value && !pending.value) || sending.value) return
    error.value = null
    if (message && !opts?.skipBubble) turns.value.push({ role: 'user', text: message })
    sending.value = true
    try {
      if (!sessionId.value) {
        const started = await startSession(language.value)
        sessionId.value = started.session_id
        pending.value = false
      }
      const res = await sendChat(sessionId.value, message, confirmation)
      turns.value.push({
        role: 'assistant',
        text: res.reply_text,
        candidates: res.candidates,
        riskLevel: res.risk_level,
      })
      lastFailedSend.value = null
    } catch {
      // Keep the user's bubble (their intent was real) but surface a retry
      // affordance instead of leaving the UI silently stuck on "...".
      error.value = 'send_failed'
      lastFailedSend.value = { message, confirmation }
    } finally {
      sending.value = false
    }
  }

  async function retry() {
    if (!lastFailedSend.value) return
    const { message, confirmation } = lastFailedSend.value
    lastFailedSend.value = null
    // The bubble for this message (if any) is already in `turns` from the
    // failed attempt — don't push a second copy.
    await send(message, confirmation, { skipBubble: true })
  }

  function markAnswered(turnIndex: number) {
    answeredTurnIndices.value = new Set(answeredTurnIndices.value).add(turnIndex)
  }

  async function setConsent(category: string, granted: boolean) {
    if (!sessionId.value) return
    const res = await updateConsent(sessionId.value, category, granted)
    consent.value = res.consent
  }

  async function finish() {
    if (!sessionId.value) return
    await endSession(sessionId.value)
  }

  // Drops the in-memory reference to the current session without calling the
  // backend — used after clearing history, which may delete the session
  // that's currently open in ChatView. Without this, the next message send
  // would 404 ("session not found") against an id that no longer exists.
  function reset() {
    sessionId.value = null
    pending.value = false
    turns.value = []
    consent.value = {}
    answeredTurnIndices.value = new Set()
    error.value = null
    lastFailedSend.value = null
  }

  return {
    sessionId,
    pending,
    language,
    turns,
    sending,
    consent,
    answeredTurnIndices,
    error,
    begin,
    loadOpening,
    resume,
    send,
    retry,
    markAnswered,
    setConsent,
    finish,
    reset,
  }
})
