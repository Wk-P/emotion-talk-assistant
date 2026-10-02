import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { CandidateCard, ConfirmationPayload, Language } from '@/api/client'
import {
  endSession,
  getSessionMessages,
  errorStatus,
  saveRecord,
  sendChat,
  updateSessionLanguage,
  startSession,
  updateConsent,
} from '@/api/client'
import type { RecordDraft } from '@/utils/fieldLabels'

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
  // The user chose "结束对话" (or reopened one they had ended): the AI's
  // closing reply is shown and no further messages can be sent.
  const ended = ref(false)

  function begin(lang: Language) {
    reset()
    language.value = lang
    pending.value = true
  }

  // Re-opens a past conversation instead of starting a new one — the
  // backend chat endpoint accepts further messages against an existing
  // session_id unless the user ended it, so this only needs to rehydrate
  // local state from the stored history.
  // Replayed turns never carry candidate cards (history only stores
  // role/content), so they render as plain bubbles, same as a live reply
  // once its card has been confirmed.
  async function resume(id: string, lang: Language, isEnded = false) {
    const messages = await getSessionMessages(id)
    pending.value = false
    ended.value = isEnded
    sessionId.value = id
    language.value = lang
    turns.value = messages
      .filter((m): m is typeof m & { role: 'user' | 'assistant' } => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ role: m.role, text: m.content }))
    answeredTurnIndices.value = new Set()
    recordDrafts.value = new Map()
    savedTurns.value = new Set()
    error.value = null
    lastFailedSend.value = null
  }

  async function send(message?: string, confirmation?: ConfirmationPayload, opts?: { skipBubble?: boolean }) {
    if ((!sessionId.value && !pending.value) || sending.value || ended.value) return
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
      if (confirmation?.card_type === 'end') ended.value = true
    } catch (e) {
      // 409: this conversation was already ended (e.g. in another tab).
      if (errorStatus(e) === 409) {
        ended.value = true
        return
      }
      // Keep the user's bubble (their intent was real) but surface a retry
      // affordance instead of leaving the UI silently stuck on "...".
      // 503 = the backend is fine but the AI provider call failed.
      error.value = errorStatus(e) === 503 ? 'ai_unavailable' : 'send_failed'
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

  // The user switched the UI language. An ongoing conversation continues in
  // the new language from the next reply on (nothing already said is
  // re-translated); a chat that hasn't started yet just remembers the choice
  // for when the user does send something.
  async function setLanguage(lang: Language) {
    if (language.value === lang) return
    language.value = lang
    if (sessionId.value && !ended.value) await updateSessionLanguage(sessionId.value, lang)
  }

  function markAnswered(turnIndex: number) {
    answeredTurnIndices.value = new Set(answeredTurnIndices.value).add(turnIndex)
  }

  // Confirmed cards the user may keep in "my records", keyed by turn index,
  // and which of them they actually saved. Nothing is saved unless the user
  // taps save — records are never written implicitly.
  const recordDrafts = ref<Map<number, RecordDraft>>(new Map())
  const savedTurns = ref<Set<number>>(new Set())
  const savingTurn = ref<number | null>(null)

  function offerRecord(turnIndex: number, draft: RecordDraft) {
    recordDrafts.value = new Map(recordDrafts.value).set(turnIndex, draft)
  }

  async function saveTurnRecord(turnIndex: number) {
    const draft = recordDrafts.value.get(turnIndex)
    if (!draft || !sessionId.value || savingTurn.value !== null || savedTurns.value.has(turnIndex)) return
    savingTurn.value = turnIndex
    try {
      // Tapping "save" is the user's explicit consent to keep this record
      // (the backend refuses to save without it).
      if (!consent.value.emotion_records) await setConsent('emotion_records', true)
      await saveRecord(sessionId.value, draft.recordType, draft.payload)
      savedTurns.value = new Set(savedTurns.value).add(turnIndex)
    } finally {
      savingTurn.value = null
    }
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

  // "结束对话": the AI writes a short closing reply (no question, no
  // cards), then the conversation is locked. Never purges the turns.
  async function endConversation() {
    if (!sessionId.value || sending.value || ended.value) return
    await send(undefined, { card_type: 'end' })
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
    recordDrafts.value = new Map()
    savedTurns.value = new Set()
    error.value = null
    lastFailedSend.value = null
    ended.value = false
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
    ended,
    endConversation,
    begin,
    resume,
    send,
    retry,
    markAnswered,
    setLanguage,
    recordDrafts,
    savedTurns,
    savingTurn,
    offerRecord,
    saveTurnRecord,
    setConsent,
    finish,
    reset,
  }
})
