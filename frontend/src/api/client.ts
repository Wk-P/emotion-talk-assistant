import axios from 'axios'

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

export type Language = 'zh' | 'ko'

export interface CandidateItem {
  id: string
  label: string
  description?: string
  contact?: string
  url?: string
  verified_at?: string
}

export interface CandidateCard {
  type: string
  items: CandidateItem[]
  fields?: Record<string, unknown> | null
}

export interface ChatResponse {
  reply_text: string
  candidates: CandidateCard[]
  risk_level: 'none' | 'watch' | 'crisis'
}

export interface ConfirmationPayload {
  card_type: string
  selected_labels?: string[]
  custom_text?: string
  fields?: Record<string, unknown>
}

export async function startSession(language: Language, deviceId?: string) {
  const { data } = await api.post<{ session_id: string; language: Language }>('/api/session/start', {
    language,
    device_id: deviceId ?? null,
  })
  return data
}

export interface SessionHistoryItem {
  session_id: string
  language: Language
  created_at: string
  ended_at: string | null
  message_count: number
}

export interface HistoryMessageItem {
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}

export async function listHistory(deviceId?: string) {
  const { data } = await api.get<SessionHistoryItem[]>('/api/session/history', {
    params: deviceId ? { device_id: deviceId } : {},
  })
  return data
}

export async function getSessionMessages(sessionId: string) {
  const { data } = await api.get<HistoryMessageItem[]>(`/api/session/${sessionId}/messages`)
  return data
}

export async function clearHistory(deviceId?: string) {
  await api.delete('/api/session/history', { params: deviceId ? { device_id: deviceId } : {} })
}

export async function sendChat(sessionId: string, message?: string, confirmation?: ConfirmationPayload) {
  const { data } = await api.post<ChatResponse>('/api/chat', {
    session_id: sessionId,
    message: message ?? null,
    confirmation: confirmation ?? null,
  })
  return data
}

export async function updateLanguage(sessionId: string, language: Language) {
  const { data } = await api.put<{ session_id: string; language: Language }>(
    `/api/session/${sessionId}/language`,
    { language },
  )
  return data
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

export async function listRecords(sessionId: string) {
  const { data } = await api.get<SavedRecord[]>(`/api/records/${sessionId}`)
  return data
}

export async function deleteRecord(recordId: string) {
  await api.delete(`/api/records/${recordId}`)
}

export interface Resource {
  id: string
  country: string
  category: string
  name: Record<string, string>
  description: Record<string, string>
  contact: string
  url: string | null
  verified_at: string
}

export async function listResources() {
  const { data } = await api.get<Resource[]>('/api/resources')
  return data
}

export interface AuthUser {
  id: string
  email: string
  email_verified: boolean
}

export async function register(email: string, password: string) {
  const { data } = await api.post<{ message: string }>('/api/auth/register', { email, password })
  return data
}

export async function verifyEmail(token: string) {
  const { data } = await api.post<{ message: string }>('/api/auth/verify-email', { token })
  return data
}

export async function login(email: string, password: string) {
  const { data } = await api.post<{ access_token: string; user: AuthUser }>('/api/auth/login', { email, password })
  return data
}

export async function forgotPassword(email: string) {
  const { data } = await api.post<{ message: string }>('/api/auth/forgot-password', { email })
  return data
}

export async function resetPassword(token: string, newPassword: string) {
  const { data } = await api.post<{ message: string }>('/api/auth/reset-password', {
    token,
    new_password: newPassword,
  })
  return data
}

export async function fetchMe() {
  const { data } = await api.get<AuthUser>('/api/auth/me')
  return data
}
