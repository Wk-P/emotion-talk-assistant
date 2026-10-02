import axios from 'axios'

const AUTH_TOKEN_KEY = 'emotion-talk-auth-token'
const DEVICE_ID_KEY = 'emotion-talk-device-id'

// Only used when signed out — groups an anonymous visitor's sessions on this
// browser so history/records work without an account. Once they log in,
// user_id takes over and this is ignored server-side.
export function getDeviceId(): string {
  try {
    let id = localStorage.getItem(DEVICE_ID_KEY)
    if (!id) {
      id = crypto.randomUUID()
      localStorage.setItem(DEVICE_ID_KEY, id)
    }
    return id
  } catch {
    return crypto.randomUUID()
  }
}

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

export async function startSession(language: Language) {
  const { data } = await api.post<{ session_id: string; language: Language }>('/api/session/start', {
    language,
    device_id: getAuthToken() ? undefined : getDeviceId(),
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

// The opening shown on a new chat before anything is stored — the session
// itself is only created (startSession) on the user's first send.
export async function getOpening(language: Language) {
  const { data } = await api.get<ChatResponse>('/api/session/opening', { params: { language } })
  return data
}

export async function listHistory() {
  const params = getAuthToken() ? undefined : { device_id: getDeviceId() }
  const { data } = await api.get<SessionHistoryItem[]>('/api/session/history', { params })
  return data
}

export async function getSessionMessages(sessionId: string) {
  const { data } = await api.get<HistoryMessageItem[]>(`/api/session/${sessionId}/messages`)
  return data
}

export async function clearHistory() {
  const params = getAuthToken() ? undefined : { device_id: getDeviceId() }
  await api.delete('/api/session/history', { params })
}

export async function sendChat(sessionId: string, message?: string, confirmation?: ConfirmationPayload) {
  const { data } = await api.post<ChatResponse>('/api/chat', {
    session_id: sessionId,
    message: message ?? null,
    confirmation: confirmation ?? null,
  })
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

export interface OwnRecord extends SavedRecord {
  session_id: string
  session_created_at: string
}

// Same ownership rule as listHistory: the account when logged in, otherwise
// this browser's device id.
function ownerParams() {
  return getAuthToken() ? undefined : { device_id: getDeviceId() }
}

/** Every record the current user saved, across all their conversations. */
export async function listMyRecords() {
  const { data } = await api.get<OwnRecord[]>('/api/records', { params: ownerParams() })
  return data
}

export async function deleteRecord(recordId: string) {
  await api.delete(`/api/records/${recordId}`, { params: ownerParams() })
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
}

export interface AdminRecordItem {
  id: string
  record_type: string
  payload: Record<string, unknown>
  created_at: string
}

export async function getAdminSessionRecords(sessionId: string) {
  const { data } = await api.get<AdminRecordItem[]>(`/api/admin/sessions/${sessionId}/records`)
  return data
}

// Shared by the session list and export (backend app/api/admin.py
// SessionFilter): export always means "what the list currently shows".
// participant/user_id narrow it to one person for a single-user export.
export interface AdminSessionFilter {
  participant?: string
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
  lang: Language,
) {
  const { data } = await api.get<Blob>('/api/admin/export/file', {
    params: { ...filter, format, lang, tz_offset: new Date().getTimezoneOffset() },
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

// ---- Prompt editing (see backend app/api/prompts.py) ----

export interface PromptItem {
  key: string
  language: Language
  version: number // 0 = code default, nothing saved yet
  content: string
  default_content: string
  updated_at: string | null
  updated_by: string | null
}

export interface PromptOverview {
  items: PromptItem[]
  output_format: string
}

export interface PromptVersionItem {
  version: number
  content: string
  note: string | null
  created_at: string
  created_by: string | null
}

export type PreviewIntent = 'vent' | 'organize' | 'stabilize' | 'method'

export interface PromptPreviewRequest {
  language: Language
  intent: PreviewIntent
  self_kindness: boolean
  overrides: Record<string, string>
  history: { role: 'user' | 'assistant'; content: string }[]
  message: string
}

export interface PromptPreviewResponse {
  reply_text: string
  candidates: CandidateCard[]
  system_prompt: string
  prompt_versions: Record<string, number>
}

export async function listPrompts() {
  const { data } = await api.get<PromptOverview>('/api/admin/prompts')
  return data
}

export async function listPromptVersions(key: string, language: Language) {
  const { data } = await api.get<PromptVersionItem[]>(`/api/admin/prompts/${key}/${language}/versions`)
  return data
}

export async function savePrompt(key: string, language: Language, content: string, note?: string) {
  const { data } = await api.post<PromptItem>(`/api/admin/prompts/${key}/${language}`, { content, note: note || null })
  return data
}

export async function previewPrompt(payload: PromptPreviewRequest) {
  const { data } = await api.post<PromptPreviewResponse>('/api/admin/prompts/preview', payload)
  return data
}
