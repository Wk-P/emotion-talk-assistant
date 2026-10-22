import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Language, Persona } from '@/api/client'
import {
  endSession,
  getSessionMessages,
  errorStatus,
  listPersonas,
  rateReply,
  setSessionPersona,
  setAuthToken,
  streamChat,
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
  riskLevel?: 'none' | 'watch' | 'crisis'
  /** Assistant replies: the 0-5 rating given beside it. */
  rating?: number | null
  /** The reply is still being written. */
  streaming?: boolean
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
  // Set when the last send() failed (network/API error) so the UI can show a
  // retry affordance instead of silently doing nothing.
  const error = ref<string | null>(null)
  const lastFailedSend = ref<{ message?: string; end?: boolean } | null>(null)
  // The user chose "结束对话" (or reopened one they had ended): the AI's
  // closing reply is shown and no further messages can be sent.
  const ended = ref(false)
  // How many user/assistant messages the backend has for this conversation
  // as far as we know — sync() asks only for what came after them.
  const serverCount = ref(0)
  // Speaking styles to pick from (backend app/services/agent_config.py) and
  // the one this conversation uses (null = the default).
  const personas = ref<Persona[]>([])
  const defaultPersona = ref<string | null>(null)
  const persona = ref<string | null>(null)

  async function loadPersonas() {
    if (personas.value.length) return
    const res = await listPersonas().catch(() => null)
    if (!res) return
    personas.value = res.personas
    defaultPersona.value = res.default
  }

  // Later replies use the new persona; a chat not started yet sends it on
  // its first message.
  async function choosePersona(id: string | null) {
    persona.value = id
    if (sessionId.value && !ended.value) await setSessionPersona(sessionId.value, id).catch(() => {})
  }

  async function rate(turn: ChatTurn, rating: number | null) {
    if (!turn.id) return
    const before = turn.rating
    turn.rating = rating
    await rateReply(turn.id, rating).catch(() => {
      turn.rating = before
    })
  }

  function begin(lang: Language) {
    reset()
    language.value = lang
    pending.value = true
  }

  // Re-opens a past conversation instead of starting a new one — the
  // backend chat endpoint accepts further messages against an existing
  // session_id unless the user ended it, so this only needs to rehydrate
  // local state from the stored history.
  async function resume(id: string, lang: Language, isEnded = false, personaId: string | null = null) {
    const messages = await getSessionMessages(id)
    pending.value = false
    ended.value = isEnded
    sessionId.value = id
    language.value = lang
    persona.value = personaId
    turns.value = messages
      .filter((m): m is typeof m & { role: 'user' | 'assistant' } => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({ id: m.id, role: m.role, text: m.content, rating: m.rating ?? null }))
    serverCount.value = turns.value.length
    error.value = null
    lastFailedSend.value = null
  }

  // `end`: the "结束对话" button — the AI's closing reply, then the
  // conversation is locked.
  async function send(message?: string, opts?: { skipBubble?: boolean; end?: boolean }) {
    if ((!sessionId.value && !pending.value) || sending.value || ended.value) return
    if (!message && !opts?.end) return
    error.value = null
    syncSeq++
    let bubble: ChatTurn | undefined
    if (message && !opts?.skipBubble) turns.value.push({ role: 'user', text: message })
    if (message) bubble = [...turns.value].reverse().find((t) => t.role === 'user' && !t.id && t.text === message)
    sending.value = true
    // Pushed on the first piece, so the typing dots show until then.
    let reply: ChatTurn | undefined
    // The reactive copy in `turns`, so writing to it updates the page.
    const ensureReply = (): ChatTurn => {
      if (!reply) {
        turns.value.push({ role: 'assistant', text: '', streaming: true, rating: null })
        reply = turns.value[turns.value.length - 1]!
      }
      return reply
    }
    try {
      if (!sessionId.value) {
        const started = await startSession(language.value)
        sessionId.value = started.session_id
        pending.value = false
        if (persona.value) await setSessionPersona(started.session_id, persona.value)
      }
      const res = await streamChat(sessionId.value, { message, end: opts?.end }, (piece) => {
        ensureReply().text += piece
      })
      if (bubble && res.user_message_id) bubble.id = res.user_message_id
      const done = ensureReply()
      done.id = res.assistant_message_id
      done.text = done.text.trim()
      done.riskLevel = res.risk_level
      done.streaming = false
      lastFailedSend.value = null
      if (opts?.end) ended.value = true
      // This device already shows the turn; just catch up on the count.
      void catchUp(sessionId.value, false)
    } catch (e) {
      // A half-written reply was not saved: drop it, the retry writes it again.
      if (reply) turns.value = turns.value.filter((t) => t !== reply)
      const status = errorStatus(e)
      if (status === 401) {
        setAuthToken(null)
        window.location.assign(`/login?redirect=${encodeURIComponent(window.location.pathname)}`)
        return
      }
      // 409: this conversation was already ended (e.g. in another tab).
      if (status === 409) {
        ended.value = true
        return
      }
      // Keep the user's bubble (their intent was real) but surface a retry.
      // 503 = the backend is fine but the AI provider call failed.
      error.value = status === 503 ? 'ai_unavailable' : 'send_failed'
      lastFailedSend.value = { message, end: opts?.end }
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
        if (m.role === 'user' || m.role === 'assistant')
          turns.value.push({ id: m.id, role: m.role, text: m.content, rating: m.rating ?? null })
      }
    }
    serverCount.value = res.total
    if (res.ended) ended.value = true
  }

  async function retry() {
    if (!lastFailedSend.value) return
    const { message, end } = lastFailedSend.value
    lastFailedSend.value = null
    // The bubble for this message (if any) is already in `turns` from the
    // failed attempt — don't push a second copy.
    await send(message, { skipBubble: true, end })
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
  // is locked. Never purges the turns.
  async function endConversation() {
    if (!sessionId.value || sending.value || ended.value) return
    await send(undefined, { end: true })
  }

  // Drops the in-memory reference to the current session without calling the
  // backend — used after clearing history, which may delete the session
  // that's currently open in ChatView. Without this, the next message send
  // would 404 ("session not found") against an id that no longer exists.
  function reset() {
    sessionId.value = null
    pending.value = false
    persona.value = null
    turns.value = []
    consent.value = {}
    error.value = null
    lastFailedSend.value = null
    ended.value = false
    serverCount.value = 0
  }

  return {
    sessionId,
    pending,
    language,
    turns,
    sending,
    consent,
    error,
    ended,
    endConversation,
    begin,
    resume,
    send,
    sync,
    retry,
    setConsent,
    finish,
    reset,
    personas,
    defaultPersona,
    persona,
    loadPersonas,
    choosePersona,
    rate,
  }
})
