import type { Language } from '@/api/client'

const STORAGE_KEY = 'emotion-ai-lang'

// Only fall back to the browser's language when the visitor has never
// picked one themselves — components that call this on every mount (e.g.
// OnboardingView) would otherwise stomp on an explicit choice each time.
export function detectLang(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'zh' || stored === 'ko') return stored
  } catch {
    // localStorage unavailable (private mode, etc.) — fall through to detection
  }
  return navigator.language.toLowerCase().startsWith('ko') ? 'ko' : 'zh'
}

export function saveLang(lang: Language): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // ignore — worst case the choice just doesn't persist across visits
  }
}
