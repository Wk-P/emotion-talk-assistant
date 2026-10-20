import axios from 'axios'
import { DISPLAY_TZ_OFFSET } from '@/utils/time'

const AUTH_TOKEN_KEY = 'emotion-talk-auth-token'
export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY)
  } catch {
    return null
  }
}

export function setAuthToken(token: string | null) {
  try {
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token)
    else localStorage.removeItem(AUTH_TOKEN_KEY)
  } catch {
    // localStorage unavailable — token just won't survive a reload
  }
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
})

api.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Everything a participant does needs a login. If the token has expired or
// the account was disabled mid-use, drop it and send them to sign in again
// (then back to where they were) instead of leaving the page half-broken.
// Login itself is exempt: a 401 there just means a wrong password.
api.interceptors.response.use(undefined, (error) => {
  const url: string = error?.config?.url ?? ''
  if (error?.response?.status === 401 && !url.includes('/api/auth/login') && getAuthToken()) {
    setAuthToken(null)
    const here = window.location.pathname + window.location.search
    window.location.assign(`/login?redirect=${encodeURIComponent(here)}`)
  }
  return Promise.reject(error)
})

export type Language = 'zh' | 'ko'

export async function startSession(language: Language) {
  const { data } = await api.post<{ session_id: string; language: Language }>('/api/session/start', {
    language,
  })
  return data
}

export interface SessionHistoryItem {
  session_id: string
  language: Language
  created_at: string
  ended_at: string | null
  message_count: number
  last_active_at: string
  title: string
  /** The picked persona; null = the default. */
  persona?: string | null
}

export interface HistoryMessageItem {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
  /** Assistant replies: the 0-5 rating given beside it. */
  rating?: number | null
  // Admin transcript only: the persona that wrote an AI reply.
  persona?: string | null
}

/** Switch an ongoing conversation's language: later AI replies use it. */
export async function updateSessionLanguage(sessionId: string, language: Language) {
  await api.put(`/api/session/${sessionId}/language`, { language })
}

export async function listHistory() {
  const { data } = await api.get<SessionHistoryItem[]>('/api/session/history')
  return data
}

export async function getSessionMessages(sessionId: string) {
  const { data } = await api.get<HistoryMessageItem[]>(`/api/session/${sessionId}/messages`)
  return data
}

export interface SessionSync {
  messages: HistoryMessageItem[]
  total: number
  ended: boolean
}

/** What was said in a conversation after the first `after` messages (backend app/api/session.py sync_session). */
export async function syncSession(sessionId: string, after: number) {
  const { data } = await api.get<SessionSync>(`/api/session/${sessionId}/sync`, { params: { after } })
  return data
}

export async function clearHistory() {
  await api.delete('/api/session/history')
}

/** Delete one of your own conversations (what was saved to "我的记录" from it stays). */
export async function deleteSession(sessionId: string) {
  await api.delete(`/api/session/${sessionId}`)
}

export interface StreamDone {
  user_message_id: string | null
  assistant_message_id: string
  risk_level: 'none' | 'watch' | 'crisis'
}

/** Thrown by streamChat; `status` as for an axios error (503 = AI unavailable). */
export class StreamError extends Error {
  constructor(public status: number | undefined, message: string) {
    super(message)
  }
}

/**
 * One turn with the reply streamed (backend POST /api/chat/stream):
 * `onDelta` gets each piece as it is written. `end` = the "结束对话" button.
 */
export async function streamChat(
  sessionId: string,
  body: { message?: string; end?: boolean },
  onDelta: (text: string) => void,
): Promise<StreamDone> {
  const token = getAuthToken()
  const res = await fetch(`${api.defaults.baseURL}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ session_id: sessionId, message: body.message ?? null, end: !!body.end }),
  })
  if (!res.ok || !res.body) throw new StreamError(res.status, `stream failed: ${res.status}`)
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let cut: number
    while ((cut = buffer.indexOf('\n\n')) >= 0) {
      const block = buffer.slice(0, cut)
      buffer = buffer.slice(cut + 2)
      const event = /^event: (.*)$/m.exec(block)?.[1]
      const data = /^data: (.*)$/m.exec(block)?.[1]
      if (!event || data === undefined) continue
      const parsed = JSON.parse(data)
      if (event === 'delta') onDelta(parsed.text)
      else if (event === 'done') return parsed as StreamDone
      else if (event === 'error') throw new StreamError(503, parsed.reason)
    }
  }
  throw new StreamError(undefined, 'stream ended early')
}

/** The 0-5 rating beside an AI reply (null clears it). */
export async function rateReply(messageId: string, rating: number | null) {
  await api.put(`/api/chat/messages/${messageId}/rating`, { rating })
}

export interface Persona {
  id: string
  name: Partial<Record<Language, string>>
  intro: Partial<Record<Language, string>>
}

export async function listPersonas() {
  const { data } = await api.get<{ personas: Persona[]; default: string }>('/api/chat/personas')
  return data
}

export async function setSessionPersona(sessionId: string, persona: string | null) {
  await api.put(`/api/chat/sessions/${sessionId}/persona`, { persona })
}

export async function updateConsent(sessionId: string, category: string, granted: boolean) {
  const { data } = await api.put<{ consent: Record<string, boolean> }>(`/api/session/${sessionId}/consent`, {
    category,
    granted,
  })
  return data
}

export async function endSession(sessionId: string) {
  await api.post(`/api/session/${sessionId}/end`)
}

export interface SavedRecord {
  id: string
  record_type: string
  payload: Record<string, unknown>
  created_at: string
}

export async function saveRecord(sessionId: string, recordType: string, payload: Record<string, unknown>) {
  const { data } = await api.post<SavedRecord>('/api/records', {
    session_id: sessionId,
    record_type: recordType,
    payload,
  })
  return data
}

export interface OwnRecord extends SavedRecord {
  session_id: string
  /** null once that conversation was deleted (the record is kept). */
  session_created_at: string | null
  session_deleted: boolean
}

/** Every record the current user saved, across all their conversations. */
export async function listMyRecords() {
  const { data } = await api.get<OwnRecord[]>('/api/records')
  return data
}

export async function deleteRecord(recordId: string) {
  await api.delete(`/api/records/${recordId}`)
}

export type UserRole = 'user' | 'admin' | 'superadmin'

// ID + password accounts — no email anywhere. A forgotten password is reset
// by an admin (resetAdminUserPassword below).
export interface AuthUser {
  id: string
  username: string
  role: UserRole
}

interface TokenResponse {
  access_token: string
  user: AuthUser
}

// Same rules as the backend (app/services/auth.py).
export const USERNAME_PATTERN = '[A-Za-z0-9_.\\-]{3,32}'
export const MIN_PASSWORD_LENGTH = 8

export async function register(username: string, password: string) {
  const { data } = await api.post<TokenResponse>('/api/auth/register', { username, password })
  return data
}

export async function login(username: string, password: string) {
  const { data } = await api.post<TokenResponse>('/api/auth/login', { username, password })
  return data
}

/** HTTP status of a failed request, for picking a translated message. */
export function errorStatus(e: unknown): number | undefined {
  if (e instanceof StreamError) return e.status
  return (e as { response?: { status?: number } })?.response?.status
}

export async function fetchMe() {
  const { data } = await api.get<AuthUser>('/api/auth/me')
  return data
}

export interface AdminSessionItem {
  session_id: string
  participant_label: string
  language: Language
  created_at: string
  ended_at: string | null
  message_count: number
  record_count: number
  /** How many AI replies were rated (0-5), and the average. */
  rated_count: number
  avg_rating: number | null
}

export interface AdminRecordItem {
  id: string
  record_type: string
  payload: Record<string, unknown>
  created_at: string
}

export interface AdminUserRecord extends AdminRecordItem {
  participant_label: string
  session_id: string
  /** The participant deleted that conversation; the record stays. */
  session_deleted: boolean
}

/** Everything participants saved to "我的记录" (backend GET /api/admin/records). */
export async function listAdminRecords(
  filter: { participant?: string; record_type?: string; day_from?: string; day_to?: string } = {},
) {
  const { data } = await api.get<AdminUserRecord[]>('/api/admin/records', { params: filter })
  return data
}

export async function getAdminSessionRecords(sessionId: string) {
  const { data } = await api.get<AdminRecordItem[]>(`/api/admin/sessions/${sessionId}/records`)
  return data
}

// Shared by the session list and export (backend app/api/admin.py
// SessionFilter): export always means "what the list currently shows".
// participant/user_id narrow it to one person for a single-user export.
export interface AdminSessionFilter {
  participant?: string // account ID, partial match
  participant_exact?: boolean
  user_id?: string
  language?: Language
  created_from?: string // ISO datetime, inclusive
  created_to?: string // ISO datetime, exclusive
  min_messages?: number
}

export async function listAdminSessions(filter: AdminSessionFilter = {}) {
  const { data } = await api.get<AdminSessionItem[]>('/api/admin/sessions', { params: filter })
  return data
}

export async function getAdminSessionMessages(sessionId: string) {
  const { data } = await api.get<HistoryMessageItem[]>(`/api/admin/sessions/${sessionId}/messages`)
  return data
}

export interface AdminSessionExport {
  session_id: string
  participant_label: string
  language: Language
  created_at: string
  ended_at: string | null
  messages: HistoryMessageItem[]
  records: AdminRecordItem[]
}

export type ExportFormat = 'json' | 'pdf' | 'docx' | 'md' | 'txt'

/** A readable export document (everything but JSON), same filters as above. */
export async function exportAdminFile(
  filter: AdminSessionFilter,
  format: Exclude<ExportFormat, 'json'>,
  lang: Language | 'en', // labels follow the admin's interface language
) {
  const { data } = await api.get<Blob>('/api/admin/export/file', {
    params: { ...filter, format, lang, tz_offset: DISPLAY_TZ_OFFSET },
    responseType: 'blob',
  })
  return data
}

export async function exportAdminSessions(filter: AdminSessionFilter = {}) {
  const { data } = await api.get<AdminSessionExport[]>('/api/admin/export', { params: filter })
  return data
}

export async function deleteAdminSession(sessionId: string) {
  await api.delete(`/api/admin/sessions/${sessionId}`)
}

export interface AdminUserItem {
  id: string
  username: string
  role: UserRole
  is_active: boolean
  created_at: string
  session_count: number
}

export interface AdminUserFilter {
  q?: string
  role?: UserRole
  status?: 'active' | 'disabled'
}

export async function listAdminUsers(filter: AdminUserFilter = {}) {
  const { data } = await api.get<AdminUserItem[]>('/api/admin/users', { params: filter })
  return data
}

export async function createAdminUser(username: string, password: string, role: UserRole = 'user') {
  const { data } = await api.post<AdminUserItem>('/api/admin/users', { username, password, role })
  return data
}

export async function resetAdminUserPassword(userId: string, password: string) {
  const { data } = await api.post<AdminUserItem>(`/api/admin/users/${userId}/password`, { password })
  return data
}

export async function deleteAdminUser(userId: string) {
  await api.delete(`/api/admin/users/${userId}`)
}

export async function setAdminUserActive(userId: string, isActive: boolean) {
  const { data } = await api.patch<AdminUserItem>(`/api/admin/users/${userId}/active`, { is_active: isActive })
  return data
}

export async function setAdminUserRole(userId: string, role: UserRole) {
  const { data } = await api.patch<AdminUserItem>(`/api/admin/users/${userId}/role`, { role })
  return data
}
