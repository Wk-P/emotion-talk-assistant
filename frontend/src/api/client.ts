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
  user_message_id: string | null
  assistant_message_id: string | null
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
}

export interface HistoryMessageItem {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
  // Admin transcript only: the step that answered and what the program
  // decided that turn (missing for older replies).
  stage?: string | null
  flow_log?: { zh: string; ko: string }[] | null
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

// ---- Conversation cards (backend app/services/summary_card.py) ----

export interface SummaryCard {
  id: string
  /** review: shown when coming back after a long break; final: after ending. */
  kind: 'review' | 'final'
  /** plan is '' when no plan came up. */
  content: { summary: string; plan: string; kindness: string }
  /** Shown after this many user/assistant messages. */
  after_messages: number
  /** Final card: null until the user picks. */
  decision: 'saved' | 'discarded' | null
}

export async function listCards(sessionId: string) {
  const { data } = await api.get<SummaryCard[]>(`/api/session/${sessionId}/cards`)
  return data
}

/** The program decides whether a review card is due; null when it isn't. */
export async function requestReviewCard(sessionId: string) {
  const { data } = await api.post<SummaryCard | null>(`/api/session/${sessionId}/review-card`)
  return data
}

/** The ended conversation's card (written the first time). */
export async function requestFinalCard(sessionId: string) {
  const { data } = await api.post<SummaryCard>(`/api/session/${sessionId}/final-card`)
  return data
}

/** Keep the final card in "我的记录" or not. */
export async function decideCard(sessionId: string, cardId: string, save: boolean) {
  await api.post(`/api/session/${sessionId}/cards/${cardId}/decision`, { save })
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

// ---- 每日省察 (daily reflection questionnaire, backend app/api/reflections.py) ----

export interface ReflectionAnswers {
  helpful: string
  changed: string
  improve: string
}

export interface Reflection {
  id: string
  day: string // the writer's local date, YYYY-MM-DD
  language: Language
  answers: ReflectionAnswers
  created_at: string
  updated_at: string | null
}

export async function listMyReflections() {
  const { data } = await api.get<Reflection[]>('/api/reflections')
  return data
}

export async function saveReflection(day: string, language: Language, answers: ReflectionAnswers) {
  const { data } = await api.put<Reflection>(`/api/reflections/${day}`, {
    language,
    answers,
  })
  return data
}

export async function deleteReflection(id: string) {
  await api.delete(`/api/reflections/${id}`)
}

export interface AdminReflection extends Reflection {
  participant_label: string
}

export async function listAdminReflections(filter: { participant?: string; day_from?: string; day_to?: string } = {}) {
  const { data } = await api.get<AdminReflection[]>('/api/admin/reflections', { params: filter })
  return data
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

// ---- Advanced AI settings (backend app/api/ai_params.py) ----

export type AiParamName =
  | 'history_turns'
  | 'temperature'
  | 'top_p'
  | 'max_tokens'
  | 'presence_penalty'
  | 'frequency_penalty'
  | 'timeout_seconds'
  | 'max_retries'

/** `null` = not sent: the model's own default applies. */
export type AiParamValues = Record<AiParamName, number | null>

export interface AiParamsOverview {
  values: AiParamValues
  defaults: AiParamValues
  ranges: Record<AiParamName, { min: number; max: number; integer: boolean; required: boolean }>
  model: string
  effort: ReasoningEffort | null
}

export interface AiParamsRecommendation {
  values: AiParamValues
  reasons: Partial<Record<AiParamName, string>>
  /** false: the AI call failed and built-in values came back instead. */
  from_ai: boolean
}

export async function getAiParams() {
  const { data } = await api.get<AiParamsOverview>('/api/admin/ai-params')
  return data
}

export async function setAiParams(values: AiParamValues) {
  const { data } = await api.put<AiParamsOverview>('/api/admin/ai-params', values)
  return data
}

export async function recommendAiParams(language: string) {
  const { data } = await api.post<AiParamsRecommendation>('/api/admin/ai-params/recommend', { language })
  return data
}

// ---- AI model choice (backend app/api/ai_model.py) ----

export interface ModelCandidate {
  id: string
  released: string // YYYY-MM-DD
  usable: boolean
  error: string | null
  supports_effort: boolean
  /** Plain-language traits, translated under admin model.tags.* */
  tags: string[]
}

export type ReasoningEffort = 'low' | 'medium' | 'high'

export interface ModelOverview {
  current: string
  default: string
  chosen_here: boolean
  updated_at: string | null
  updated_by: string | null
  candidates: ModelCandidate[]
  checked_at: string
  recent_days: number
  /** `null` = OpenAI's default for the model. */
  effort: ReasoningEffort | null
}

export async function getModelOverview(refresh = false) {
  const { data } = await api.get<ModelOverview>('/api/admin/model', { params: refresh ? { refresh: true } : {} })
  return data
}

/** `null` goes back to the server's default model. */
export async function setModel(model: string | null) {
  const { data } = await api.put<ModelOverview>('/api/admin/model', { model })
  return data
}

/** `null` goes back to OpenAI's default for the model. */
export async function setEffort(effort: ReasoningEffort | null) {
  const { data } = await api.put<ModelOverview>('/api/admin/model/effort', { effort })
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
  // A saved-but-not-applied edit ("暂存"), if any.
  draft_content: string | null
  draft_updated_at: string | null
  draft_updated_by: string | null
}

export type PromptGroup = 'rules' | 'flow' | 'other' | 'system'

// One block on the admin page: built-in (rename / disable only) or added by
// an admin (also deletable). See backend app/prompts/registry.load_modules.
export interface PromptModuleItem {
  key: string
  group: PromptGroup
  built_in: boolean
  enabled: boolean
  names: Partial<Record<Language, string>>
  flow_key: string | null
  /** A conversation step (built-in or added as a step of its own), not a block attached to one. */
  is_stage: boolean
}

export interface PromptOverview {
  items: PromptItem[]
  modules: PromptModuleItem[]
  output_format: string
  // Built-in components admins deleted (can be restored).
  deleted: string[]
  // Most characters one block may hold.
  max_content_length: number
}

export interface PromptVersionItem {
  version: number
  content: string
  note: string | null
  created_at: string
  created_by: string | null
}

export interface PromptPreviewRequest {
  language: Language
  /** The stage to test: a built-in flow key, e.g. 'flow.explore'. */
  stage: string
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

export async function savePromptDraft(key: string, language: Language, content: string) {
  const { data } = await api.put<PromptItem>(`/api/admin/prompts/${key}/${language}/draft`, { content })
  return data
}

export async function deletePromptDraft(key: string, language: Language) {
  await api.delete(`/api/admin/prompts/${key}/${language}/draft`)
}

export async function previewPrompt(payload: PromptPreviewRequest) {
  const { data } = await api.post<PromptPreviewResponse>('/api/admin/prompts/preview', payload)
  return data
}

export async function createPromptModule(group: PromptGroup, name: string, flowKey?: string) {
  const { data } = await api.post<PromptModuleItem>('/api/admin/prompts/modules', {
    group,
    name,
    flow_key: flowKey ?? null,
  })
  return data
}

export async function updatePromptModule(
  key: string,
  change: { language?: Language; name?: string; enabled?: boolean },
) {
  const { data } = await api.patch<PromptModuleItem>(`/api/admin/prompts/modules/${key}`, change)
  return data
}

/** Admin-set flow settings (backend app/services/flow_config.py). */
export interface FlowConfig {
  /** Per step: [minimum, maximum] user turns. */
  limits: Record<string, [number, number]>
  /** How many recent messages the AI sees each turn. */
  history_turns: number
  /** [min, max] turns of the self-kindness step when self-criticism is weak. */
  weak_kindness: [number, number]
  /** Extra crisis words (built-ins always apply), "overwhelmed" words, self-criticism words. */
  keywords: Record<KeywordList, string[]>
  /** Reply shown with the crisis resources, by language; empty = built-in. */
  crisis_reply: Partial<Record<Language, string>>
  /** Self-criticism scoring, 0-100. */
  criticism: { up: number; down: number; strong: number }
  /** "Tell me what to do" jumps here (null = ignored). */
  to_action_step: string | null
  /** Steps where "tell me what to do" is not acted on. */
  to_action_skip: string[]
  /** Check with the user for one turn before jumping. */
  to_action_confirm: boolean
  end_today_enabled: boolean
  /** Crisis resources of this country are shown ('' = all). */
  crisis_country: string
  /** Which step "enough for today" leads to / answers an overwhelmed user /
   * answers the end button (null = none). The last two aren't walked through. */
  closing_step: string | null
  stabilize_step: string | null
  ending_step: string | null
  /** Steps marked safety-related (a warning on the admin pages). */
  safety_steps: string[]
}

export type KeywordList = 'crisis' | 'watch' | 'self_criticism'

export async function getFlowConfig() {
  const { data } = await api.get<FlowConfig & { defaults: FlowConfig }>('/api/admin/prompts/flow-config')
  return data
}

export async function saveFlowConfig(config: FlowConfig) {
  const { data } = await api.put<FlowConfig & { defaults: FlowConfig }>('/api/admin/prompts/flow-config', config)
  return data
}

/** The order conversations go through the steps (closing is always last). */
export async function saveFlowOrder(order: string[]) {
  const { data } = await api.put<{ order: string[] }>('/api/admin/prompts/flow-order', { order })
  return data
}

export async function deletePromptModule(key: string) {
  await api.delete(`/api/admin/prompts/modules/${key}`)
}

export async function restorePromptModule(key: string) {
  await api.post(`/api/admin/prompts/modules/${key}/restore`)
}

// ---- prompt tools (backend app/api/prompt_tools.py) ----

export interface PromptConflict {
  where: string
  problem: string
  suggestion: string
}

export async function checkPromptConflicts(language: Language) {
  const { data } = await api.post<PromptConflict[]>('/api/admin/prompt-tools/check', { language })
  return data
}

export interface TestScript {
  id: string
  name: string
  language: Language
  lines: string[]
}

export async function fetchTestScripts() {
  const { data } = await api.get<TestScript[]>('/api/admin/prompt-tools/scripts')
  return data
}

export async function saveTestScripts(scripts: TestScript[]) {
  const { data } = await api.put<TestScript[]>('/api/admin/prompt-tools/scripts', scripts)
  return data
}

export interface RunState {
  flow_state: Record<string, unknown>
  confirmed_context: Record<string, unknown>
  self_criticism_level: number
}

export interface RunMessage {
  role: 'user' | 'assistant'
  content: string
  meta?: Record<string, unknown>
}

export async function runTestTurn(payload: { language: Language; message: string; history: RunMessage[]; state?: RunState }) {
  const { data } = await api.post<{ reply_text: string; candidates: CandidateCard[]; stage: string | null; state: RunState }>(
    '/api/admin/prompt-tools/run-turn',
    payload,
  )
  return data
}

/** Verified crisis/support contacts (backend app/api/resources.py). */
export interface CrisisResourceItem {
  id: string
  country: string
  category: string
  name: Partial<Record<Language, string>>
  description: Partial<Record<Language, string>>
  contact: string
  url: string | null
  verified_at: string
}
export type CrisisResourceInput = Omit<CrisisResourceItem, 'id'>

export async function listCrisisResources() {
  const { data } = await api.get<CrisisResourceItem[]>('/api/admin/resources')
  return data
}

export async function saveCrisisResource(item: CrisisResourceInput, id?: string) {
  if (id) await api.put(`/api/admin/resources/${id}`, item)
  else await api.post('/api/admin/resources', item)
}

export async function deleteCrisisResource(id: string) {
  await api.delete(`/api/admin/resources/${id}`)
}
