import type { Language } from '@/api/client'

// Two separate choices:
//  - the interface language (zh / ko / en), and
//  - the conversation language (zh / ko only — the AI talks in Chinese or
//    Korean; English is an interface language only).
// Picking Chinese or Korean for the interface also sets the conversation
// language; picking English leaves the conversation language as it was.
export type UiLang = Language | 'en'

const UI_KEY = 'emotion-ai-lang'
const CHAT_KEY = 'emotion-ai-chat-lang'

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null // localStorage unavailable (private mode, etc.)
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // ignore — worst case the choice just doesn't persist across visits
  }
}

// Only fall back to the browser's language when the visitor has never
// picked one themselves.
export function detectLang(): UiLang {
  const stored = read(UI_KEY)
  if (stored === 'zh' || stored === 'ko' || stored === 'en') return stored
  const nav = navigator.language.toLowerCase()
  if (nav.startsWith('ko')) return 'ko'
  if (nav.startsWith('zh')) return 'zh'
  return nav.startsWith('en') ? 'en' : 'zh'
}

export function saveLang(lang: UiLang): void {
  write(UI_KEY, lang)
  if (lang !== 'en') write(CHAT_KEY, lang)
}

/** The language conversations are held in. */
export function detectChatLang(): Language {
  const stored = read(CHAT_KEY)
  if (stored === 'zh' || stored === 'ko') return stored
  const ui = detectLang()
  return ui === 'en' ? 'zh' : ui
}

export function saveChatLang(lang: Language): void {
  write(CHAT_KEY, lang)
}

/** Conversation language implied by an interface language. */
export function chatLangFor(ui: string): Language {
  return ui === 'ko' ? 'ko' : ui === 'zh' ? 'zh' : detectChatLang()
}
