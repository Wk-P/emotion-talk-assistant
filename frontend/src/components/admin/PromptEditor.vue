<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  listPromptVersions,
  listPrompts,
  previewPrompt,
  savePrompt,
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
const outputFormat = ref('')
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
    outputFormat.value = data.output_format
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
}
const testIntent = ref<PreviewIntent>('vent')
const testSelfKindness = ref(false)
const testTurns = ref<TestTurn[]>([])
const testInput = ref('')
const testSending = ref(false)
const testError = ref('')
const testSystemPrompt = ref('')

const draftOverrides = computed(() => {
  const out: Record<string, string> = {}
  for (const item of langItems.value) {
    if (isDirty(item)) out[item.key] = drafts.value[draftId(item.key, item.language)]!
  }
  return out
})
const draftCount = computed(() => Object.keys(draftOverrides.value).length)

watch(lang, () => clearTest())

async function sendTest() {
  const message = testInput.value.trim()
  if (!message || testSending.value) return
  testSending.value = true
  testError.value = ''
  try {
    const res = await previewPrompt({
      language: lang.value,
      intent: testIntent.value,
      self_kindness: testSelfKindness.value,
      overrides: draftOverrides.value,
      history: testTurns.value,
      message,
    })
    testTurns.value = [...testTurns.value, { role: 'user', content: message }, { role: 'assistant', content: res.reply_text }]
    testSystemPrompt.value = res.system_prompt
    testInput.value = ''
  } catch {
    testError.value = t('prompts.testFailed')
  } finally {
    testSending.value = false
  }
}

function clearTest() {
  testTurns.value = []
  testSystemPrompt.value = ''
  testError.value = ''
}

onMounted(load)
</script>

<template>
  <div class="prompt-editor">
    <p class="intro">{{ t('prompts.intro') }}</p>

    <div class="lang-switch">
      <button type="button" class="btn-outline" :class="{ active: lang === 'zh' }" @click="lang = 'zh'">中文</button>
      <button type="button" class="btn-outline" :class="{ active: lang === 'ko' }" @click="lang = 'ko'">한국어</button>
    </div>

    <div v-if="!loading" class="layout">
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
              {{ item.version > 0 ? `v${item.version}` : t('prompts.default') }}
            </span>
          </span>
        </button>
      </nav>

      <section v-if="current" class="editor">
        <h2 class="editor-title">{{ t(`prompts.keys.${current.key}.name`) }}</h2>
        <p class="editor-desc">{{ t(`prompts.keys.${current.key}.desc`) }}</p>
        <p class="editor-meta">
          <template v-if="current.version > 0">
            {{ t('prompts.inEffect', { v: current.version }) }}
            · {{ current.updated_by ?? '—' }}
            · {{ current.updated_at ? new Date(current.updated_at).toLocaleString() : '' }}
          </template>
          <template v-else>{{ t('prompts.usingDefault') }}</template>
        </p>

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
              <span class="badge accent">v{{ v.version }}</span>
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

        <details class="locked">
          <summary>{{ t('prompts.lockedTitle') }}</summary>
          <p class="muted">{{ t('prompts.lockedDesc') }}</p>
          <pre>{{ outputFormat }}</pre>
        </details>
      </section>
    </div>

    <section v-if="!loading" class="test">
      <h2 class="editor-title">{{ t('prompts.testTitle') }}</h2>
      <p class="editor-desc">
        {{ t('prompts.testDesc') }}
        <strong v-if="draftCount > 0">{{ t('prompts.testDrafts', { n: draftCount }) }}</strong>
      </p>
      <div class="test-controls">
        <select v-model="testIntent">
          <option value="vent">{{ t('prompts.intent.vent') }}</option>
          <option value="organize">{{ t('prompts.intent.organize') }}</option>
          <option value="stabilize">{{ t('prompts.intent.stabilize') }}</option>
          <option value="method">{{ t('prompts.intent.method') }}</option>
        </select>
        <label class="check">
          <input v-model="testSelfKindness" type="checkbox" />
          {{ t('prompts.forceSelfKindness') }}
        </label>
        <button type="button" class="btn-text" :disabled="testTurns.length === 0" @click="clearTest">
          {{ t('prompts.testClear') }}
        </button>
      </div>
      <div class="test-log">
        <p v-if="testTurns.length === 0" class="muted">{{ t('prompts.testEmpty') }}</p>
        <div v-for="(m, i) in testTurns" :key="i" class="message" :class="m.role">{{ m.content }}</div>
      </div>
      <div class="save-row">
        <input
          v-model="testInput"
          class="note-input"
          :placeholder="t('chat.placeholder')"
          :disabled="testSending"
          @keydown.enter.prevent="sendTest"
        />
        <button type="button" class="btn-primary" :disabled="testSending || !testInput.trim()" @click="sendTest">
          {{ testSending ? '…' : t('chat.send') }}
        </button>
      </div>
      <p v-if="testError" class="error">{{ testError }}</p>
      <details v-if="testSystemPrompt" class="locked">
        <summary>{{ t('prompts.testSystemPrompt') }}</summary>
        <pre>{{ testSystemPrompt }}</pre>
      </details>
    </section>
  </div>
</template>

<style scoped>
.intro {
  font-size: 12.5px;
  color: var(--text-muted);
  line-height: 1.5;
  margin: 0 0 12px;
}
.lang-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.lang-switch button {
  padding: 7px 16px;
  font-size: 13px;
}
.layout {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
@media (min-width: 1024px) {
  .layout {
    flex-direction: row;
    align-items: flex-start;
  }
  .block-list {
    width: 280px;
    flex-shrink: 0;
    position: sticky;
    top: 16px;
  }
}
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
  padding: 10px 12px;
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
.editor {
  flex: 1;
  min-width: 0;
}
.editor-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 4px;
}
.editor-desc {
  font-size: 12.5px;
  color: var(--text-muted);
  margin: 0 0 6px;
  line-height: 1.5;
}
.editor-meta {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 10px;
}
.content {
  width: 100%;
  min-height: 360px;
  resize: vertical;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.6;
  font-family: ui-monospace, 'SF Mono', Menlo, monospace;
}
.save-row {
  display: flex;
  gap: 8px;
  margin-top: 10px;
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
  margin-top: 6px;
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
  margin-top: 12px;
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
.locked {
  margin-top: 16px;
}
.test {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}
.test-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 8px 0 10px;
  font-size: 13px;
}
.test-controls select {
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface);
  color: var(--text);
}
.check {
  display: flex;
  align-items: center;
  gap: 5px;
}
.test-log {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px;
  min-height: 120px;
  max-height: 480px;
  overflow-y: auto;
  background: var(--bg);
  border-radius: var(--radius-md);
}
.message {
  font-size: 13px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  line-height: 1.5;
  max-width: 85%;
  white-space: pre-wrap;
}
.message.user {
  background: var(--accent-soft);
  align-self: flex-end;
}
.message.assistant {
  background: var(--surface);
  align-self: flex-start;
}
</style>
