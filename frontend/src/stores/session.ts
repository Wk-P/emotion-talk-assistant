import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { CandidateCard, ConfirmationPayload, Language, SummaryCard } from '@/api/client'
import {
  decideCard,
  deleteSession,
  endSession,
  getSessionMessages,
  errorStatus,
  listCards,
  requestFinalCard,
  requestReviewCard,
  sendChat,
  updateSessionLanguage,
  startSession,
  syncSession,
  updateConsent,
} from '@/api/client'

export interface ChatTurn {
  // The stored message's id; a turn just typed has none until the reply
  // comes back. Sync uses it so a message is never shown twice.
  id?: string
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
  // How many user/assistant messages the backend has for this conversation
  // as far as we know — sync() asks only for what came after them.
  const serverCount = ref(0)
  // Set after the user ended a conversation and chose to delete it; the
  // chat page says so until a new conversation starts.
  const deletedNotice = ref(false)
  // Conversation cards shown so far (backend app/services/summary_card.py).
  const cards = ref<SummaryCard[]>([])
  // After "结束对话": the final card's steps ('card'), then whether to keep
  // the conversation ('conversation'); 'done' (or null for a conversation
  // ended earlier) shows the ended panel.
  const endFlow = ref<'card' | 'conversation' | 'done' | null>(null)

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
  // role/content), so they render as plain bubbles; the conversation cards
  // come back separately.
  async function resume(id: string, lang: Language, isEnded = false) {
    const [messages, shown] = await Promise.all([getSessionMessages(id), listCards(id).catch(() => [])])
    pending.value = false
    ended.value = isEnded
    sessionId.value = id
    language.value = lang
    turns.value = messages
      .filter((m): m is typeof m & { role: 'user' | 'assistant' } => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ id: m.id, role: m.role, text: m.content }))
    serverCount.value = turns.value.length
    answeredTurnIndices.value = new Set()
    cards.value = shown
    // Ended here earlier but the final card was never answered: pick up there.
    const final = shown.find((c) => c.kind === 'final')
    endFlow.value = isEnded && final && !final.decision ? 'card' : null
    error.value = null
    lastFailedSend.value = null
    lastReviewCheck = 0
    if (!isEnded) void checkReview()
  }

  // Coming back to a conversation: the backend decides whether a review
  // card is due (4 hours since the last message, 4 rounds since the last
  // card). Asked on opening it and whenever the page comes back into view.
  let lastReviewCheck = 0
  async function checkReview() {
    const id = sessionId.value
    if (!id || ended.value || sending.value || Date.now() - lastReviewCheck < 60_000) return
    lastReviewCheck = Date.now()
    const card = await requestReviewCard(id).catch(() => null)
    if (card && sessionId.value === id && !cards.value.some((c) => c.id === card.id)) cards.value = [...cards.value, card]
  }

  // The final card, written by the backend the first time it's asked for.
  async function loadFinalCard(): Promise<SummaryCard> {
    const existing = cards.value.find((c) => c.kind === 'final')
    if (existing) return existing
    const card = await requestFinalCard(sessionId.value!)
    if (!cards.value.some((c) => c.id === card.id)) cards.value = [...cards.value, card]
    return card
  }

  async function decideFinalCard(save: boolean) {
    const card = cards.value.find((c) => c.kind === 'final')
    if (!card || !sessionId.value) return
    await decideCard(sessionId.value, card.id, save)
    cards.value = cards.value.map((c) =>
      c.id === card.id ? { ...c, decision: save ? 'saved' : 'discarded', content: save ? c.content : { summary: '', plan: '', kindness: '' } } : c,
    )
  }

  async function send(message?: string, confirmation?: ConfirmationPayload, opts?: { skipBubble?: boolean }) {
    if ((!sessionId.value && !pending.value) || sending.value || ended.value) return
    error.value = null
    syncSeq++
    let bubble: ChatTurn | undefined
    if (message && !opts?.skipBubble) turns.value.push({ role: 'user', text: message })
    if (message) bubble = [...turns.value].reverse().find((t) => t.role === 'user' && !t.id && t.text === message)
    sending.value = true
    try {
      if (!sessionId.value) {
        const started = await startSession(language.value)
        sessionId.value = started.session_id
        pending.value = false
      }
      const res = await sendChat(sessionId.value, message, confirmation)
      if (bubble && res.user_message_id) bubble.id = res.user_message_id
      turns.value.push({
        id: res.assistant_message_id ?? undefined,
        role: 'assistant',
        text: res.reply_text,
        candidates: res.candidates,
        riskLevel: res.risk_level,
      })
      lastFailedSend.value = null
      if (confirmation?.card_type === 'end') {
        ended.value = true
        endFlow.value = 'card'
      }
      // This device already shows the turn; just catch up on the count
      // (a card confirmation may be stored as a user message too).
      void catchUp(sessionId.value, false)
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

  // Picks up messages sent from another device (or tab) into the open
  // conversation. Polled by ChatView while the page is visible.
  async function sync() {
    if (!sessionId.value || sending.value || error.value || catchingUp > 0) return
    await catchUp(sessionId.value, true)
  }

  // Bumped by every send: a poll that started before it is stale (it would
  // re-add the turn this device just showed) and must be dropped.
  let syncSeq = 0
  // Catch-ups in flight; a poll waits until the count is up to date, or it
  // would ask from the old count and show this device's own turn again.
  let catchingUp = 0

  async function catchUp(id: string, show: boolean) {
    const seq = syncSeq
    catchingUp++
    const res = await syncSession(id, serverCount.value)
      .catch(() => null)
      .finally(() => catchingUp--)
    // Dropped if the user sent, switched or reset meanwhile.
    if (!res || sessionId.value !== id) return
    if (show && (sending.value || seq !== syncSeq)) return
    if (show) {
      const known = new Set(turns.value.map((t) => t.id).filter(Boolean))
      for (const m of res.messages) {
        if (known.has(m.id)) continue
        if (m.role === 'user' || m.role === 'assistant') turns.value.push({ id: m.id, role: m.role, text: m.content })
      }
    }
    serverCount.value = res.total
    if (res.ended) ended.value = true
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

  async function setConsent(category: string, granted: boolean) {
    if (!sessionId.value) return
    const res = await updateConsent(sessionId.value, category, granted)
    consent.value = res.consent
  }

  async function finish() {
    if (!sessionId.value) return
    await endSession(sessionId.value)
  }

  // "结束对话": the AI writes a short closing reply, then the conversation
  // is locked and the final card follows (endFlow). Never purges the turns.
  async function endConversation() {
    if (!sessionId.value || sending.value || ended.value) return
    await send(undefined, { card_type: 'end' })
  }

  // End flow → "不保存（删除对话）": removes the whole conversation (what
  // was saved to "我的记录" stays).
  async function discardConversation() {
    if (sending.value) return
    if (sessionId.value) await deleteSession(sessionId.value)
    reset()
    deletedNotice.value = true
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
    cards.value = []
    endFlow.value = null
    lastReviewCheck = 0
    error.value = null
    lastFailedSend.value = null
    ended.value = false
    serverCount.value = 0
    deletedNotice.value = false
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
    discardConversation,
    deletedNotice,
    begin,
    resume,
    send,
    sync,
    retry,
    markAnswered,
    setLanguage,
    cards,
    endFlow,
    checkReview,
    loadFinalCard,
    decideFinalCard,
    setConsent,
    finish,
    reset,
  }
})
