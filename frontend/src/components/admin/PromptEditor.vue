<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AdvancedSettings from './AdvancedSettings.vue'
import ComponentLibrary from './ComponentLibrary.vue'
import FlowOrderEditor from './FlowOrderEditor.vue'
import ModelPicker from './ModelPicker.vue'
import PromptTools from './PromptTools.vue'
import {
  deletePromptDraft,
  listPromptVersions,
  listPrompts,
  previewPrompt,
  savePrompt,
  savePromptDraft,
  type CandidateCard,
  type Language,
  type PromptGroup,
  type PromptItem,
  type PromptModuleItem,
  type PromptVersionItem,
} from '@/api/client'
import { formatDateTime } from '@/utils/time'
import { usePhone } from '@/utils/phone'
import { PARTS, joinParts, partsEmpty, splitParts, type Part } from '@/utils/promptParts'

const { t } = useI18n()

// The language being *edited* — independent of the UI locale, since a
// researcher may well read the admin UI in Chinese while tuning the Korean
// prompt.
const lang = ref<Language>('zh')
const items = ref<PromptItem[]>([])
const modules = ref<PromptModuleItem[]>([])
const deletedKeys = ref<string[]>([])
const loading = ref(true)
const selectedKey = ref<string>('rules.role_scope')
// Unsaved edits, keyed `${key}|${lang}` — kept across block/language
// switches so moving around never silently throws work away.
const drafts = ref<Record<string, string>>({})
const note = ref('')
const saving = ref(false)
const savingDraft = ref(false)
const draftFlash = ref(false)
const maxLength = ref(1_000_000)
const error = ref('')
const savedFlash = ref(false)

const versions = ref<PromptVersionItem[]>([])
const showVersions = ref(false)

const draftId = (key: string, l: Language) => `${key}|${l}`

const langItems = computed(() => items.value.filter((i) => i.language === lang.value))

// The list is grouped the way documents/03_技术文档/指导意见2.md is: the common
// principles (one per prompt-composition area), then the flows (each followed
// by the blocks admins added to it), then admins' own "其他" blocks. The
// backend sends `modules` already in this order.
const GROUPS: PromptGroup[] = ['rules', 'flow', 'other', 'system']
// Every step (built-in or admin-added), in the admins' order.
const FLOW_KEYS = computed(() => modules.value.filter((m) => m.is_stage).map((m) => m.key))
// Steps with no text in the language being edited (flagged by the order editor).
const emptyStageKeys = computed(() =>
  langItems.value.filter((i) => FLOW_KEYS.value.includes(i.key) && partsEmpty(i.content)).map((i) => i.key),
)

// "编辑问法" on a step card: select it and bring the editor into view.
const editorEl = ref<HTMLElement | null>(null)
// One part of the settings at a time, instead of everything stacked.
type Section = 'model' | 'components' | 'flow' | 'prompts' | 'tools' | 'advanced'
const SECTIONS: Section[] = ['components', 'flow', 'prompts', 'model', 'advanced', 'tools']
const section = ref<Section>('components')
async function editStep(key: string) {
  section.value = 'prompts'
  selectedKey.value = key
  await nextTick()
  editorEl.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
const groupedItems = computed(() =>
  GROUPS.map((group) => ({
    group,
    entries: modules.value
      .filter((m) => m.group === group)
      .map((m) => ({ module: m, item: langItems.value.find((i) => i.key === m.key) }))
      .filter((e): e is { module: PromptModuleItem; item: PromptItem } => e.item !== undefined),
  })),
)
// One line per block for the dropdown: how it stands, so the admin sees
// what's changed without opening each one.
function optionLabel(m: PromptModuleItem, item: PromptItem): string {
  const tags: string[] = []
  if (isDirty(item)) tags.push(t('prompts.unsaved'))
  else if (item.draft_content !== null) tags.push(t('prompts.draftTag'))
  if (!m.enabled) tags.push(t('prompts.disabledBadge'))
  if (!m.built_in && partsEmpty(item.content)) tags.push(t('prompts.emptyBadge'))
  else if (m.built_in && item.version > 0) tags.push(t('prompts.modified'))
  const indent = !m.is_stage && m.group === 'flow' ? '　└ ' : ''
  return `${indent}${nameOf(m.key)}${tags.length ? `（${tags.join('·')}）` : ''}`
}
const current = computed(() => langItems.value.find((i) => i.key === selectedKey.value) ?? null)
const currentModule = computed(() => modules.value.find((m) => m.key === selectedKey.value) ?? null)

function moduleByKey(key: string) {
  return modules.value.find((m) => m.key === key)
}

// Name in the language being edited: an admin-set name first, then the
// built-in default, then (added blocks) the other language's name.
function nameOf(key: string): string {
  const m = moduleByKey(key)
  const own = m?.names[lang.value]?.trim()
  if (own) return own
  if (!m || m.built_in) return t(`prompts.keys.${key}.name`)
  return Object.values(m.names).find((n) => n?.trim()) ?? ''
}

function descOf(m: PromptModuleItem): string {
  if (m.built_in) return t(`prompts.keys.${m.key}.desc`)
  if (m.is_stage) return t('prompts.customDesc.stage')
  if (m.group === 'flow') return t('prompts.customDesc.flow', { flow: nameOf(m.flow_key ?? '') })
  return t(`prompts.customDesc.${m.group}`)
}

const draft = computed({
  get: () => (current.value ? (drafts.value[draftId(current.value.key, lang.value)] ?? baseline(current.value)) : ''),
  set: (value: string) => {
    if (!current.value) return
    drafts.value = { ...drafts.value, [draftId(current.value.key, lang.value)]: value }
  },
})

// What the editor would show with no local edits: the saved draft if
// there is one, else the text in use.
const baseline = (item: PromptItem) => item.draft_content ?? item.content

// Edited since the last 暂存 (or since load).
function isDirty(item: PromptItem) {
  const d = drafts.value[draftId(item.key, item.language)]
  return d !== undefined && d !== baseline(item)
}

const dirty = computed(() => (current.value ? isDirty(current.value) : false))
// Differs from the text in use — what 启用 would change.
const differsFromLive = computed(() => current.value !== null && draft.value !== current.value.content)
const tooLong = computed(() => draft.value.length > maxLength.value)

// A step is written in three boxes (目标 / 问法 / 示例); every other block is
// one box.
const split = computed(() => !!currentModule.value?.is_stage)
const draftParts = computed(() => splitParts(draft.value))
function setPart(part: Part, value: string) {
  draft.value = joinParts({ ...draftParts.value, [part]: value })
}
// A stored version, readable: each part under its label.
function readable(content: string): string {
  const p = splitParts(content)
  if (!p.ask.trim() && !p.example.trim()) return content
  return PARTS.filter((k) => p[k].trim())
    .map((k) => `〔${t(`prompts.parts.${k}`)}〕\n${p[k].trim()}`)
    .join('\n\n')
}
const phone = usePhone()

const draftIsDefault = computed(() => current.value !== null && draft.value === current.value.default_content)

// `silent`: refresh in place (after changing the step order or a step's
// on/off) without hiding the page.
async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const data = await listPrompts()
    items.value = data.items
    modules.value = data.modules
    deletedKeys.value = data.deleted
    maxLength.value = data.max_content_length ?? maxLength.value
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
  if (status === 422) return t('prompts.tooLong', { max: maxLength.value.toLocaleString() })
  // Tag the cause so a screenshot is enough to tell what happened.
  return `${t('prompts.saveFailed')} (${status ?? 'network'})`
}

function replaceItem(updated: PromptItem) {
  const idx = items.value.findIndex((i) => i.key === updated.key && i.language === updated.language)
  if (idx !== -1) items.value[idx] = updated
  const next = { ...drafts.value }
  delete next[draftId(updated.key, updated.language)]
  drafts.value = next
}

// 暂存: keep the edit on the server without putting it in use.
async function stash() {
  if (!current.value || !dirty.value || partsEmpty(draft.value) || tooLong.value) return
  savingDraft.value = true
  error.value = ''
  try {
    replaceItem(await savePromptDraft(current.value.key, lang.value, draft.value))
    draftFlash.value = true
    setTimeout(() => (draftFlash.value = false), 2000)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    savingDraft.value = false
  }
}

// 启用: publish what's in the editor (the saved draft goes with it).
async function save() {
  if (!current.value || !differsFromLive.value || partsEmpty(draft.value) || tooLong.value) return
  saving.value = true
  error.value = ''
  try {
    replaceItem(await savePrompt(current.value.key, lang.value, draft.value, note.value))
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

// Throw the saved draft away: back to the text in use.
async function dropDraft() {
  const item = current.value
  if (!item || item.draft_content === null) return
  error.value = ''
  try {
    await deletePromptDraft(item.key, item.language)
    replaceItem({ ...item, draft_content: null, draft_updated_at: null, draft_updated_by: null })
  } catch (e) {
    error.value = errorMessage(e)
  }
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
// One per flow the router can pick (vent and organize both map to the
// exploration flow, so only one of them is offered).
// In a real conversation the stage is chosen by the system; here the admin
// picks one to try.
const testStage = ref('flow.listen')
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
    // Unapplied text — typed here or 暂存'd — is what gets tried.
    const text = drafts.value[draftId(item.key, item.language)] ?? baseline(item)
    if (text !== item.content) out[item.key] = text
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
// — shown read-only here, just so the researcher sees what the model
// proposed (the chat itself never shows them).
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
      stage: testStage.value,
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

onMounted(() => load())
</script>

<template>
  <div class="prompt-editor" :class="{ phone }">
    <nav class="subtabs" role="tablist">
      <button
        v-for="s in SECTIONS"
        :key="s"
        type="button"
        role="tab"
        :aria-selected="section === s"
        :class="{ on: section === s }"
        @click="section = s"
      >
        {{ t(`prompts.sections.${s}`) }}
      </button>
    </nav>

    <p v-if="phone && section !== 'tools'" class="phone-note">{{ t('prompts.phoneNote') }}</p>

    <ModelPicker v-if="section === 'model'" />
    <AdvancedSettings v-else-if="section === 'advanced'" />
    <PromptTools v-else-if="section === 'tools'" />

    <div v-if="section === 'prompts'" class="toolbar">
      <details v-if="!phone" class="steps">
        <summary class="steps-title">{{ t('prompts.stepsTitle') }}</summary>
        <ol>
          <li>{{ t('prompts.step1') }}</li>
          <li>{{ t('prompts.step2') }}</li>
          <li>{{ t('prompts.step3') }}</li>
        </ol>
      </details>
      <label class="block-pick">
        <span class="lang-label">{{ t('prompts.pickLabel') }}</span>
        <select v-model="selectedKey">
          <optgroup v-for="g in groupedItems" :key="g.group" :label="t(`prompts.groups.${g.group}.name`)">
            <option v-for="{ module: m, item } in g.entries" :key="m.key" :value="m.key">{{ optionLabel(m, item) }}</option>
          </optgroup>
        </select>
      </label>
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

    <FlowOrderEditor
      v-if="!loading && section === 'flow'"
      :modules="modules"
      :name-of="nameOf"
      :empty-keys="emptyStageKeys"
      @edit="editStep"
      @reload="load(true)"
      @components="section = 'components'"
    />
    <ComponentLibrary
      v-if="!loading && section === 'components'"
      :modules="modules"
      :deleted="deletedKeys"
      :name-of="nameOf"
      :empty-keys="emptyStageKeys"
      @edit="editStep"
      @reload="load(true)"
    />

    <!-- Narrow: stacked. >=1024px: list | editor, test panel below.
         >=1360px: full-width three-column workspace — list | editor | a
         sticky, full-height test chat on the right. -->
    <div v-if="!loading && section === 'prompts'" class="workspace">

      <section v-if="current" ref="editorEl" class="editor panel">
        <h2 class="panel-title">{{ nameOf(current.key) }}</h2>
        <p v-if="currentModule" class="panel-desc">{{ descOf(currentModule) }}</p>

        <p v-if="currentModule && currentModule.group !== 'system'" class="manage-note">
          {{ t('prompts.manageElsewhere') }}
          <button type="button" class="btn-text" @click="section = 'components'">{{ t('flowUi.goComponents') }}</button>
        </p>
        <p v-if="currentModule && !currentModule.enabled" class="off-note">{{ t('prompts.disabledNote') }}</p>
        <p v-else-if="currentModule && !currentModule.built_in && partsEmpty(current.content)" class="off-note">
          {{ t('prompts.emptyNote') }}
        </p>
        <p class="editor-meta">
          <template v-if="current.version > 0">
            {{ t('prompts.inEffect', { v: current.version }) }}
            · {{ current.updated_by ?? '—' }}
            · {{ current.updated_at ? formatDateTime(current.updated_at) : '' }}
          </template>
          <template v-else>{{ t('prompts.usingDefault') }}</template>
        </p>

        <details v-if="!phone" class="tips">
          <summary>{{ t('prompts.tipsTitle') }}</summary>
          <ul>
            <li>{{ t('prompts.tip1') }}</li>
            <li>{{ t('prompts.tip2') }}</li>
            <li>{{ t('prompts.tip3') }}</li>
          </ul>
        </details>

        <template v-if="split">
          <div v-for="k in PARTS" :key="k" class="part">
            <label class="part-head" :for="`part-${k}`">
              <span class="part-name">{{ t(`prompts.parts.${k}`) }}</span>
              <span class="part-hint">{{ t(`prompts.parts.hint_${k}`) }}</span>
            </label>
            <div v-if="phone" class="ro-text">{{ draftParts[k] || '—' }}</div>
            <textarea
              v-else
              :id="`part-${k}`"
              class="content part-box"
              spellcheck="false"
              :placeholder="t(`prompts.parts.placeholder_${k}`)"
              :value="draftParts[k]"
              @input="setPart(k, ($event.target as HTMLTextAreaElement).value)"
            />
          </div>
        </template>
        <template v-else>
          <div v-if="phone" class="ro-text">{{ draft }}</div>
          <textarea v-else v-model="draft" class="content" spellcheck="false" />
        </template>

        <p class="char-count" :class="{ over: tooLong }">
          {{ t('prompts.charCount', { n: draft.length.toLocaleString(), max: maxLength.toLocaleString() }) }}
          <template v-if="tooLong"> · {{ t('prompts.tooLong', { max: maxLength.toLocaleString() }) }}</template>
        </p>
        <p v-if="current.draft_content !== null" class="draft-note">
          {{ t('prompts.draftPending', { who: current.draft_updated_by ?? '—', time: current.draft_updated_at ? formatDateTime(current.draft_updated_at) : '' }) }}
          <button type="button" class="btn-text" @click="dropDraft">{{ t('prompts.deleteDraft') }}</button>
        </p>

        <div class="save-row">
          <input v-model="note" class="note-input" maxlength="200" :placeholder="t('prompts.notePlaceholder')" />
          <button
            type="button"
            class="btn-outline"
            :disabled="!dirty || savingDraft || saving || partsEmpty(draft) || tooLong"
            @click="stash"
          >
            {{ savingDraft ? t('prompts.savingDraft') : t('prompts.saveDraft') }}
          </button>
          <button
            type="button"
            class="btn-primary"
            :disabled="!differsFromLive || saving || savingDraft || partsEmpty(draft) || tooLong"
            @click="save"
          >
            {{ saving ? t('prompts.saving') : t('prompts.save') }}
          </button>
        </div>
        <div class="secondary-row">
          <button type="button" class="btn-text" :disabled="!dirty" @click="discard">{{ t('prompts.discard') }}</button>
          <button
            v-if="currentModule?.built_in"
            type="button"
            class="btn-text"
            :disabled="draftIsDefault"
            @click="loadDefault"
          >
            {{ t('prompts.loadDefault') }}
          </button>
          <button type="button" class="btn-text" @click="toggleVersions">
            {{ showVersions ? t('prompts.hideHistory') : t('prompts.showHistory') }}
          </button>
          <span v-if="savedFlash" class="flash">{{ t('prompts.saved') }}</span>
          <span v-if="draftFlash" class="flash">{{ t('prompts.draftSaved') }}</span>
          <span v-if="error" class="error">{{ error }}</span>
        </div>
        <p class="hint">{{ t('prompts.saveHint') }}</p>

        <div v-if="showVersions" class="versions">
          <p v-if="versions.length === 0" class="muted">{{ t('prompts.noHistory') }}</p>
          <div v-for="v in versions" :key="v.version" class="version">
            <div class="version-head">
              <span class="badge accent">{{ t('prompts.versionBadge', { v: v.version }) }}</span>
              <span class="muted">{{ formatDateTime(v.created_at) }} · {{ v.created_by ?? '—' }}</span>
              <button type="button" class="btn-text" @click="loadVersion(v)">{{ t('prompts.loadVersion') }}</button>
            </div>
            <div v-if="v.note" class="version-note">{{ v.note }}</div>
            <details>
              <summary>{{ t('prompts.viewContent') }}</summary>
              <pre>{{ readable(v.content) }}</pre>
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
              v-for="stage in FLOW_KEYS"
              :key="stage"
              type="button"
              role="radio"
              class="chip"
              :class="{ on: testStage === stage }"
              :aria-checked="testStage === stage"
              @click="testStage = stage"
            >
              {{ nameOf(stage) }}
            </button>
          </div>
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
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.6;
}
/* Wide: the three steps side by side across the toolbar. */
@media (min-width: 1024px) {
  .steps ol {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 20px;
    padding-left: 0;
    list-style-position: inside;
  }
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
    grid-template-columns: minmax(0, 1fr);
    gap: 24px;
  }
  .test {
    grid-column: 1 / -1;
    height: 640px;
  }
}
@media (min-width: 1360px) {
  .workspace {
    grid-template-columns: minmax(0, 1fr) minmax(380px, 440px);
    gap: 28px;
  }
  .test {
    grid-column: auto;
    position: sticky;
    top: calc(var(--site-header-h) + 24px);
    height: calc(100dvh - var(--site-header-h) - 48px);
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

.block-pick {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}
.block-pick select {
  flex: 1;
  min-width: 0;
  max-width: 460px;
  padding: 9px 12px;
  font-size: 14px;
  font-weight: 600;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
}

/* ---- Editor ---- */
.off-note {
  margin: 10px 0 0;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  background: #fff4e0;
  color: #a15c00;
  font-size: 12.5px;
}
.editor {
  min-width: 0;
}
.manage-note {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin: 10px 0 0;
  font-size: 12.5px;
  color: var(--text-muted);
}
.manage-note .btn-text {
  padding: 0;
  font-size: 12.5px;
}
.editor-meta {
  font-size: 12px;
  color: var(--text-muted);
  margin: 10px 0 14px;
}
/* Phone: view only — everything that types or saves text is hidden. */
.phone-note {
  margin: 0 0 14px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 13.5px;
  line-height: 1.5;
}
.ro-text {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.7;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: var(--bg);
  overflow-wrap: anywhere;
}
.phone .save-row,
.phone .char-count,
.phone .secondary-row,
.phone .secondary-row + .hint,
.phone .versions {
  display: none;
}
.subtabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  margin-bottom: 16px;
  border-radius: 999px;
  background: var(--bg);
  border: 1px solid var(--border);
  overflow-x: auto;
  scrollbar-width: none;
}
.subtabs button {
  flex: 1 0 auto;
  padding: 7px 14px;
  border: 0;
  border-radius: 999px;
  background: transparent;
  color: var(--text-muted);
  font: inherit;
  font-size: 14px;
  white-space: nowrap;
  cursor: pointer;
}
.subtabs button.on {
  background: var(--surface);
  color: var(--accent);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
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
  /* Prose, mostly Chinese: a code font made Windows fall back to SimSun. */
  font-family: inherit;
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
.char-count {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-muted);
  text-align: right;
}
.char-count.over {
  color: var(--danger);
  font-weight: 600;
}
.draft-note {
  margin: 8px 0 0;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  font-size: 13px;
  line-height: 1.6;
}
.draft-note .btn-text {
  margin-left: 6px;
}
.save-row .btn-outline,
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
  padding: 0 16px;
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
.part {
  margin-bottom: 12px;
}
.part-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 8px;
  margin-bottom: 4px;
}
.part-name {
  padding: 1px 10px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 600;
  background: var(--accent-soft);
  color: var(--accent);
}
.part-hint {
  font-size: 12.5px;
  color: var(--text-muted);
}
.content.part-box {
  min-height: 160px;
  height: auto;
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
