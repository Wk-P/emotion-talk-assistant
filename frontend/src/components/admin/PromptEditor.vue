<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  listPromptVersions,
  listPrompts,
  previewPrompt,
  savePrompt,
  type CandidateCard,
  type Language,
  type PreviewIntent,
  type PromptItem,
  type PromptVersionItem,
} from '@/api/client'

const { t } = useI18n()

// The language being *edited* — independent of the UI locale, since a
// researcher may well read the admin UI in Chinese while tuning the Korean
// prompt.
const lang = ref<Language>('zh')
const items = ref<PromptItem[]>([])
const loading = ref(true)
const selectedKey = ref<string>('role_rules')
// Unsaved edits, keyed `${key}|${lang}` — kept across block/language
// switches so moving around never silently throws work away.
const drafts = ref<Record<string, string>>({})
const note = ref('')
const saving = ref(false)
const error = ref('')
const savedFlash = ref(false)

const versions = ref<PromptVersionItem[]>([])
const showVersions = ref(false)

const draftId = (key: string, l: Language) => `${key}|${l}`

const langItems = computed(() => items.value.filter((i) => i.language === lang.value))
const current = computed(() => langItems.value.find((i) => i.key === selectedKey.value) ?? null)

const draft = computed({
  get: () => (current.value ? (drafts.value[draftId(current.value.key, lang.value)] ?? current.value.content) : ''),
  set: (value: string) => {
    if (!current.value) return
    drafts.value = { ...drafts.value, [draftId(current.value.key, lang.value)]: value }
  },
})

function isDirty(item: PromptItem) {
  const d = drafts.value[draftId(item.key, item.language)]
  return d !== undefined && d !== item.content
}

const dirty = computed(() => (current.value ? isDirty(current.value) : false))
const draftIsDefault = computed(() => current.value !== null && draft.value === current.value.default_content)

async function load() {
  loading.value = true
  try {
    const data = await listPrompts()
    items.value = data.items
  } finally {
    loading.value = false
  }
}

async function loadVersions() {
  if (!current.value) return
  versions.value = await listPromptVersions(current.value.key, lang.value)
}

watch([selectedKey, lang], () => {
  error.value = ''
  note.value = ''
  if (showVersions.value) loadVersions()
})

async function toggleVersions() {
  showVersions.value = !showVersions.value
  if (showVersions.value) await loadVersions()
}

function errorMessage(e: unknown): string {
  const status = (e as { response?: { status?: number } }).response?.status
  if (status === 409) return t('prompts.conflict')
  if (status === 400) return t('prompts.unchanged')
  return t('prompts.saveFailed')
}

async function save() {
  if (!current.value || !dirty.value || !draft.value.trim()) return
  saving.value = true
  error.value = ''
  try {
    const updated = await savePrompt(current.value.key, lang.value, draft.value, note.value)
    const idx = items.value.findIndex((i) => i.key === updated.key && i.language === updated.language)
    if (idx !== -1) items.value[idx] = updated
    const next = { ...drafts.value }
    delete next[draftId(updated.key, updated.language)]
    drafts.value = next
    note.value = ''
    savedFlash.value = true
    setTimeout(() => (savedFlash.value = false), 2000)
    if (showVersions.value) await loadVersions()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

function discard() {
  if (!current.value) return
  const next = { ...drafts.value }
  delete next[draftId(current.value.key, lang.value)]
  drafts.value = next
}

function loadDefault() {
  if (!current.value) return
  draft.value = current.value.default_content
  note.value = t('prompts.noteResetDefault')
}

function loadVersion(v: PromptVersionItem) {
  draft.value = v.content
  note.value = t('prompts.noteRollback', { v: v.version })
}

// ---- Test panel ----
interface TestTurn {
  role: 'user' | 'assistant'
  content: string
  candidates?: CandidateCard[]
}
const INTENTS: PreviewIntent[] = ['vent', 'organize', 'stabilize', 'method']
const testIntent = ref<PreviewIntent>('vent')
const testSelfKindness = ref(false)
const testTurns = ref<TestTurn[]>([])
const testInput = ref('')
const testSending = ref(false)
const testError = ref('')
const testSystemPrompt = ref('')
const showSystemPrompt = ref(false)
const testLogEl = ref<HTMLElement | null>(null)

const draftOverrides = computed(() => {
  const out: Record<string, string> = {}
  for (const item of langItems.value) {
    if (isDirty(item)) out[item.key] = drafts.value[draftId(item.key, item.language)]!
  }
  return out
})
const draftCount = computed(() => Object.keys(draftOverrides.value).length)

watch(lang, () => clearTest())

function scrollTestLog() {
  nextTick(() => testLogEl.value?.scrollTo({ top: testLogEl.value.scrollHeight, behavior: 'smooth' }))
}
watch(() => testTurns.value.length, scrollTestLog)
watch(testSending, scrollTestLog)

// Candidate cards come back either as selectable items or as a fields form
// (seb_summary / plan_form) — shown read-only here, just so the researcher
// sees what the model proposed.
function candidateLines(card: CandidateCard): string[] {
  if (card.items?.length) return card.items.map((i) => i.label)
  return Object.entries(card.fields ?? {})
    .filter(([, v]) => v !== null && v !== '')
    .map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`)
}

async function sendTest() {
  const message = testInput.value.trim()
  if (!message || testSending.value) return
  const history = testTurns.value.map(({ role, content }) => ({ role, content }))
  testTurns.value = [...testTurns.value, { role: 'user', content: message }]
  testInput.value = ''
  testSending.value = true
  testError.value = ''
  try {
    const res = await previewPrompt({
      language: lang.value,
      intent: testIntent.value,
      self_kindness: testSelfKindness.value,
      overrides: draftOverrides.value,
      history,
      message,
    })
    testTurns.value = [...testTurns.value, { role: 'assistant', content: res.reply_text, candidates: res.candidates }]
    testSystemPrompt.value = res.system_prompt
  } catch {
    // Put the message back so it can be resent as-is.
    testTurns.value = testTurns.value.slice(0, -1)
    testInput.value = message
    testError.value = t('prompts.testFailed')
  } finally {
    testSending.value = false
  }
}

function clearTest() {
  testTurns.value = []
  testSystemPrompt.value = ''
  showSystemPrompt.value = false
  testError.value = ''
}

onMounted(load)
</script>

<template>
  <div class="prompt-editor">
    <div class="toolbar">
      <div class="steps">
        <div class="steps-title">{{ t('prompts.stepsTitle') }}</div>
        <ol>
          <li>{{ t('prompts.step1') }}</li>
          <li>{{ t('prompts.step2') }}</li>
          <li>{{ t('prompts.step3') }}</li>
        </ol>
      </div>
      <div class="lang-pick">
        <span class="lang-label">{{ t('prompts.langLabel') }}</span>
        <div class="segmented" role="radiogroup" :aria-label="t('prompts.langLabel')">
          <button type="button" role="radio" :aria-checked="lang === 'zh'" :class="{ on: lang === 'zh' }" @click="lang = 'zh'">
            中文
          </button>
          <button type="button" role="radio" :aria-checked="lang === 'ko'" :class="{ on: lang === 'ko' }" @click="lang = 'ko'">
            한국어
          </button>
        </div>
      </div>
    </div>

    <!-- Narrow: stacked. >=1024px: list | editor, test panel below.
         >=1360px: full-width three-column workspace — list | editor | a
         sticky, full-height test chat on the right. -->
    <div v-if="!loading" class="workspace">
      <nav class="block-list">
        <button
          v-for="item in langItems"
          :key="item.key"
          type="button"
          class="block"
          :class="{ selected: item.key === selectedKey }"
          @click="selectedKey = item.key"
        >
          <span class="block-name">{{ t(`prompts.keys.${item.key}.name`) }}</span>
          <span class="block-tags">
            <span v-if="isDirty(item)" class="badge warn">{{ t('prompts.unsaved') }}</span>
            <span class="badge" :class="{ accent: item.version > 0 }">
              {{ item.version > 0 ? t('prompts.modified') : t('prompts.default') }}
            </span>
          </span>
        </button>
      </nav>

      <section v-if="current" class="editor panel">
        <h2 class="panel-title">{{ t(`prompts.keys.${current.key}.name`) }}</h2>
        <p class="panel-desc">{{ t(`prompts.keys.${current.key}.desc`) }}</p>
        <p class="editor-meta">
          <template v-if="current.version > 0">
            {{ t('prompts.inEffect', { v: current.version }) }}
            · {{ current.updated_by ?? '—' }}
            · {{ current.updated_at ? new Date(current.updated_at).toLocaleString() : '' }}
          </template>
          <template v-else>{{ t('prompts.usingDefault') }}</template>
        </p>

        <details class="tips" open>
          <summary>{{ t('prompts.tipsTitle') }}</summary>
          <ul>
            <li>{{ t('prompts.tip1') }}</li>
            <li>{{ t('prompts.tip2') }}</li>
            <li>{{ t('prompts.tip3') }}</li>
          </ul>
        </details>

        <textarea v-model="draft" class="content" spellcheck="false" />

        <div class="save-row">
          <input v-model="note" class="note-input" maxlength="200" :placeholder="t('prompts.notePlaceholder')" />
          <button type="button" class="btn-primary" :disabled="!dirty || saving || !draft.trim()" @click="save">
            {{ saving ? t('prompts.saving') : t('prompts.save') }}
          </button>
        </div>
        <div class="secondary-row">
          <button type="button" class="btn-text" :disabled="!dirty" @click="discard">{{ t('prompts.discard') }}</button>
          <button type="button" class="btn-text" :disabled="draftIsDefault" @click="loadDefault">
            {{ t('prompts.loadDefault') }}
          </button>
          <button type="button" class="btn-text" @click="toggleVersions">
            {{ showVersions ? t('prompts.hideHistory') : t('prompts.showHistory') }}
          </button>
          <span v-if="savedFlash" class="flash">{{ t('prompts.saved') }}</span>
          <span v-if="error" class="error">{{ error }}</span>
        </div>
        <p class="hint">{{ t('prompts.saveHint') }}</p>

        <div v-if="showVersions" class="versions">
          <p v-if="versions.length === 0" class="muted">{{ t('prompts.noHistory') }}</p>
          <div v-for="v in versions" :key="v.version" class="version">
            <div class="version-head">
              <span class="badge accent">{{ t('prompts.versionBadge', { v: v.version }) }}</span>
              <span class="muted">{{ new Date(v.created_at).toLocaleString() }} · {{ v.created_by ?? '—' }}</span>
              <button type="button" class="btn-text" @click="loadVersion(v)">{{ t('prompts.loadVersion') }}</button>
            </div>
            <div v-if="v.note" class="version-note">{{ v.note }}</div>
            <details>
              <summary>{{ t('prompts.viewContent') }}</summary>
              <pre>{{ v.content }}</pre>
            </details>
          </div>
        </div>

        <p class="safety-note">🔒 {{ t('prompts.safetyNote') }}</p>
      </section>

      <aside class="test panel">
        <header class="test-head">
          <div>
            <h2 class="panel-title">{{ t('prompts.testTitle') }}</h2>
            <p class="panel-desc">{{ t('prompts.testDesc') }}</p>
          </div>
          <button type="button" class="ghost-btn" :disabled="testTurns.length === 0" @click="clearTest">
            {{ t('prompts.testClear') }}
          </button>
        </header>

        <div class="test-options">
          <div class="option-label">{{ t('prompts.testFlow') }}</div>
          <div class="chips" role="radiogroup">
            <button
              v-for="intent in INTENTS"
              :key="intent"
              type="button"
              role="radio"
              class="chip"
              :class="{ on: testIntent === intent }"
              :aria-checked="testIntent === intent"
              @click="testIntent = intent"
            >
              {{ t(`prompts.intent.${intent}`) }}
            </button>
          </div>
          <button
            type="button"
            role="switch"
            class="switch-row"
            :aria-checked="testSelfKindness"
            @click="testSelfKindness = !testSelfKindness"
          >
            <span class="switch" :class="{ on: testSelfKindness }"><span class="knob" /></span>
            <span>{{ t('prompts.forceSelfKindness') }}</span>
          </button>
          <div v-if="draftCount > 0" class="draft-banner">
            <span class="draft-dot" />
            {{ t('prompts.testDrafts', { n: draftCount }) }}
          </div>
        </div>

        <div ref="testLogEl" class="test-log">
          <div v-if="testTurns.length === 0 && !testSending" class="test-empty">
            <div class="test-empty-icon">💬</div>
            <p>{{ t('prompts.testEmpty') }}</p>
          </div>
          <div v-for="(m, i) in testTurns" :key="i" class="turn" :class="m.role">
            <div class="bubble">{{ m.content }}</div>
            <div v-for="(card, ci) in m.candidates ?? []" :key="ci" class="candidates">
              <span class="candidates-label">{{ t('prompts.candidates') }}</span>
              <span v-for="(line, li) in candidateLines(card)" :key="li" class="candidate">{{ line }}</span>
            </div>
          </div>
          <div v-if="testSending" class="turn assistant">
            <div class="bubble typing" role="status">
              <span class="dot" />
              <span class="dot" />
              <span class="dot" />
            </div>
          </div>
        </div>

        <div v-if="testError" class="test-error">{{ testError }}</div>

        <template v-if="testSystemPrompt">
          <button type="button" class="sp-toggle" @click="showSystemPrompt = !showSystemPrompt">
            <span class="chevron" :class="{ open: showSystemPrompt }">▸</span>
            {{ showSystemPrompt ? t('prompts.hideSystemPrompt') : t('prompts.testSystemPrompt') }}
          </button>
          <pre v-if="showSystemPrompt" class="sp-body">{{ testSystemPrompt }}</pre>
        </template>

        <form class="composer" @submit.prevent="sendTest">
          <input
            v-model="testInput"
            :placeholder="t('chat.placeholder')"
            :disabled="testSending"
            autocomplete="off"
          />
          <button type="submit" class="send-btn" :disabled="testSending || !testInput.trim()" :aria-label="t('chat.send')">
            <span v-if="!testSending">{{ t('chat.send') }}</span>
            <span v-else class="spinner" aria-hidden="true" />
          </button>
        </form>
      </aside>
    </div>
  </div>
</template>

<style scoped>
/* ---- Top toolbar ---- */
.toolbar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 20px;
}
@media (min-width: 1024px) {
  .toolbar {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    gap: 32px;
    margin-bottom: 28px;
  }
}
.steps {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
  max-width: 880px;
}
.steps-title {
  font-weight: 700;
  color: var(--text);
  margin-bottom: 2px;
}
.steps ol {
  margin: 0;
  padding-left: 20px;
}
.lang-pick {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.lang-label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-muted);
}
.segmented {
  display: inline-flex;
  flex-shrink: 0;
  padding: 3px;
  border-radius: 999px;
  background: var(--bg);
  border: 1px solid var(--border);
}
.segmented button {
  border: none;
  background: transparent;
  padding: 7px 18px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}
.segmented button.on {
  background: var(--surface);
  color: var(--accent);
  box-shadow: var(--shadow-sm);
}
.segmented button:not(:disabled):hover {
  transform: none;
  color: var(--accent);
}

/* ---- Workspace grid ---- */
.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
@media (min-width: 1024px) {
  .workspace {
    grid-template-columns: 240px minmax(0, 1fr);
    gap: 24px;
  }
  .test {
    grid-column: 1 / -1;
    height: 640px;
  }
  .block-list {
    position: sticky;
    top: 24px;
  }
}
@media (min-width: 1360px) {
  .workspace {
    grid-template-columns: 260px minmax(0, 1fr) minmax(380px, 440px);
    gap: 28px;
  }
  .test {
    grid-column: auto;
    position: sticky;
    top: 24px;
    height: calc(100dvh - 48px);
    max-height: 960px;
  }
}

.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
}
@media (min-width: 1024px) {
  .panel {
    padding: 24px 28px;
  }
}
.panel-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 4px;
}
.panel-desc {
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
}

/* ---- Block list ---- */
.block-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.block {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  font-size: 13px;
  text-align: left;
  color: var(--text);
}
.block.selected {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.block-name {
  font-weight: 600;
}
.block-tags {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

/* ---- Editor ---- */
.editor {
  min-width: 0;
}
.editor-meta {
  font-size: 12px;
  color: var(--text-muted);
  margin: 10px 0 14px;
}
.content {
  width: 100%;
  min-height: 360px;
  resize: vertical;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
  font-size: 13px;
  line-height: 1.7;
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
}
@media (min-width: 1360px) {
  .content {
    height: clamp(360px, calc(100dvh - 580px), 900px);
  }
}
.tips {
  margin: 0 0 12px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  font-size: 12.5px;
  line-height: 1.6;
}
.tips ul {
  margin: 6px 0 0;
  padding-left: 18px;
  color: var(--text);
}
.safety-note {
  margin: 20px 0 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
}
.save-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.save-row .btn-primary {
  padding: 10px 18px;
  font-size: 14px;
  flex-shrink: 0;
}
.note-input {
  flex: 1;
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
}
.secondary-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
}
.btn-text:disabled {
  color: var(--text-muted);
  opacity: 0.6;
}
.hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 4px 0 0;
}
.flash {
  font-size: 12.5px;
  color: #1c8a4a;
  font-weight: 600;
}
.error {
  font-size: 12.5px;
  color: var(--danger);
}
.muted {
  font-size: 12px;
  color: var(--text-muted);
}
.badge {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: var(--bg);
  color: var(--text-muted);
}
.badge.accent {
  background: var(--accent-soft);
  color: var(--accent);
}
.badge.warn {
  background: #fff4e0;
  color: #a15c00;
}
.versions {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.version {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
}
.version-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.version-head .btn-text {
  margin-left: auto;
}
.version-note {
  font-size: 12.5px;
  margin-top: 6px;
}
details {
  margin-top: 6px;
  font-size: 12.5px;
}
summary {
  cursor: pointer;
  color: var(--accent);
}
pre {
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg);
  border-radius: var(--radius-sm);
  padding: 10px;
  font-size: 12px;
  line-height: 1.55;
  max-height: 360px;
  overflow: auto;
}

/* ---- Test chat ---- */
.test {
  display: flex;
  flex-direction: column;
  min-height: 560px;
  padding: 0;
  overflow: hidden;
}
.test-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--border);
}
.ghost-btn {
  flex-shrink: 0;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-muted);
  border-radius: 999px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
}
.ghost-btn:not(:disabled):hover {
  color: var(--danger);
  border-color: var(--danger-border);
}
.ghost-btn:disabled {
  opacity: 0.45;
}
.test-options {
  padding: 14px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-bottom: 1px solid var(--border);
}
.option-label {
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 12.5px;
  font-weight: 500;
}
.chip:not(:disabled):hover {
  border-color: var(--accent);
  color: var(--accent);
}
.chip.on {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
  box-shadow: 0 4px 12px rgba(108, 92, 231, 0.25);
}
.switch-row {
  display: flex;
  align-items: center;
  gap: 10px;
  border: none;
  background: none;
  padding: 2px 0;
  font-size: 12.5px;
  color: var(--text);
  text-align: left;
}
.switch-row:not(:disabled):hover {
  transform: none;
}
.switch {
  position: relative;
  flex-shrink: 0;
  width: 34px;
  height: 20px;
  border-radius: 999px;
  background: var(--border);
  transition: background 0.18s ease;
}
.switch.on {
  background: var(--accent);
}
.knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(31, 35, 51, 0.2);
  transition: transform 0.18s ease;
}
.switch.on .knob {
  transform: translateX(14px);
}
.draft-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: #fff4e0;
  color: #a15c00;
  font-size: 12px;
  font-weight: 500;
}
.draft-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.test-log {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: linear-gradient(var(--surface), var(--bg));
}
.test-empty {
  margin: auto;
  text-align: center;
  color: var(--text-muted);
  font-size: 12.5px;
  max-width: 240px;
  line-height: 1.6;
}
.test-empty-icon {
  font-size: 26px;
  margin-bottom: 6px;
  opacity: 0.7;
}
.turn {
  display: flex;
  flex-direction: column;
  gap: 6px;
  animation: fade-up 0.25s ease;
}
.turn.user {
  align-items: flex-end;
}
.turn.assistant {
  align-items: flex-start;
}
.bubble {
  max-width: 88%;
  padding: 10px 14px;
  border-radius: 16px;
  font-size: 13.5px;
  line-height: 1.55;
  white-space: pre-wrap;
  box-shadow: var(--shadow-sm);
}
.turn.user .bubble {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 6px 16px rgba(108, 92, 231, 0.25);
}
.turn.assistant .bubble {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
}
.bubble.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 15px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: bounce 1.2s infinite ease-in-out;
}
.dot:nth-child(2) {
  animation-delay: 0.15s;
}
.dot:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-4px);
    opacity: 1;
  }
}
.candidates {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 5px;
  max-width: 88%;
}
.candidates-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  margin-right: 2px;
}
.candidate {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px dashed var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12px;
}
.test-error {
  margin: 0 20px 10px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: var(--danger-soft);
  color: var(--danger);
  font-size: 12.5px;
}
.sp-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  border: none;
  border-top: 1px solid var(--border);
  background: var(--surface);
  padding: 10px 20px;
  font-size: 12px;
  font-weight: 500;
  color: var(--accent);
  text-align: left;
}
.sp-toggle:not(:disabled):hover {
  transform: none;
  background: var(--accent-soft);
}
.chevron {
  display: inline-block;
  transition: transform 0.18s ease;
}
.chevron.open {
  transform: rotate(90deg);
}
.sp-body {
  margin: 0;
  border-radius: 0;
  max-height: 240px;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
}
.composer {
  display: flex;
  gap: 8px;
  padding: 12px 14px 14px;
  border-top: 1px solid var(--border);
  background: var(--surface);
}
.composer input {
  flex: 1;
  min-width: 0;
  padding: 11px 16px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg);
  font-size: 13.5px;
}
.composer input:disabled {
  opacity: 0.6;
}
.send-btn {
  min-width: 64px;
  border: none;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 13.5px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 16px rgba(108, 92, 231, 0.28);
}
.send-btn:not(:disabled):hover {
  background: var(--accent-hover);
}
.send-btn:disabled {
  opacity: 0.5;
  box-shadow: none;
}
.spinner {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-top-color: #fff;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
