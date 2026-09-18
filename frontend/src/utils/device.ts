const STORAGE_KEY = 'emotion-talk-device-id'

// No login system (test phase): a random id persisted in localStorage lets
// the backend group a browser's past sessions into a history list without
// any account. It is not a secret and not tied to a real identity.
export function getDeviceId(): string {
  try {
    const existing = localStorage.getItem(STORAGE_KEY)
    if (existing) return existing
    const generated = crypto.randomUUID()
    localStorage.setItem(STORAGE_KEY, generated)
    return generated
  } catch {
    // localStorage unavailable (private mode, etc.) — fall back to a
    // per-load id; history just won't persist across reloads.
    return crypto.randomUUID()
  }
}
