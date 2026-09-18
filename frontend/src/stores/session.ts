import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { CandidateCard, ConfirmationPayload, Language } from '@/api/client'
import { endSession, sendChat, startSession, updateConsent, updateLanguage } from '@/api/client'
import { getDeviceId } from '@/utils/device'

export interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
  candidates?: CandidateCard[]
  riskLevel?: 'none' | 'watch' | 'crisis'
}

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref<string | null>(null)
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

  async function begin(lang: Language) {
    language.value = lang
    const res = await startSession(lang, getDeviceId())
    sessionId.value = res.session_id
    turns.value = []
    answeredTurnIndices.value = new Set()
  }

  async function send(message?: string, confirmation?: ConfirmationPayload, opts?: { skipBubble?: boolean }) {
    if (!sessionId.value || sending.value) return
    error.value = null
    if (message && !opts?.skipBubble) turns.value.push({ role: 'user', text: message })
    sending.value = true
    try {
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

  async function switchLanguage(lang: Language) {
    if (!sessionId.value || lang === language.value) return
    language.value = lang // optimistic — UI chrome switches immediately
    await updateLanguage(sessionId.value, lang)
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

  return {
    sessionId,
    language,
    turns,
    sending,
    consent,
    answeredTurnIndices,
    error,
    begin,
    send,
    retry,
    switchLanguage,
    markAnswered,
    setConsent,
    finish,
  }
})
