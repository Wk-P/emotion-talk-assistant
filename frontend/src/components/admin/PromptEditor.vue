<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import FlowOrderEditor from './FlowOrderEditor.vue'
import ModelPicker from './ModelPicker.vue'
import PromptTools from './PromptTools.vue'
import {
  createPromptModule,
  deletePromptModule,
  errorStatus,
  listPromptVersions,
  listPrompts,
  previewPrompt,
  savePrompt,
  updatePromptModule,
  type CandidateCard,
  type Language,
  type PromptGroup,
  type PromptItem,
  type PromptModuleItem,
  type PromptVersionItem,
} from '@/api/client'
import { formatDateTime } from '@/utils/time'
import { usePhone } from '@/utils/phone'

const { t } = useI18n()

// The language being *edited* — independent of the UI locale, since a
// researcher may well read the admin UI in Chinese while tuning the Korean
// prompt.
const lang = ref<Language>('zh')
const items = ref<PromptItem[]>([])
const modules = ref<PromptModuleItem[]>([])
const loading = ref(true)
const selectedKey = ref<string>('rules.role_scope')
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

// The list is grouped the way documents/03_技术文档/指导意见2.md is: the common
// principles (one per prompt-composition area), then the flows (each followed
// by the blocks admins added to it), then admins' own "其他" blocks. The
// backend sends `modules` already in this order.
const GROUPS: PromptGroup[] = ['rules', 'flow', 'other', 'system']
// Every step (built-in or admin-added), in the admins' order.
const FLOW_KEYS = computed(() => modules.value.filter((m) => m.is_stage).map((m) => m.key))
// Steps with no text in the language being edited (flagged by the order editor).
const emptyStageKeys = computed(() =>
  langItems.value.filter((i) => FLOW_KEYS.value.includes(i.key) && !i.content.trim()).map((i) => i.key),
)

// "编辑问法" on a step card: select it and bring the editor into view.
const editorEl = ref<HTMLElement | null>(null)
// One part of the settings at a time, instead of everything stacked.
type Section = 'model' | 'flow' | 'prompts' | 'tools'
const SECTIONS: Section[] = ['model', 'flow', 'prompts', 'tools']
const section = ref<Section>('prompts')
// Narrow screens: the block list and the editor are two screens; this is
// whether the editor one is showing. Wide screens show both side by side.
const narrowDetail = ref(false)
function openBlock(key: string) {
  selectedKey.value = key
  narrowDetail.value = true
  if (window.matchMedia('(max-width: 1023px)').matches) nextTick(() => window.scrollTo({ top: 0 }))
}

async function editStep(key: string) {
  section.value = 'prompts'
  narrowDetail.value = true
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

// ---- Adding / renaming / turning off / deleting blocks ----
const addingGroup = ref<PromptGroup | null>(null)
const newName = ref('')
const newFlowKey = ref('flow.listen')
const moduleBusy = ref(false)
const moduleError = ref('')

function startAdd(group: PromptGroup) {
  addingGroup.value = group
  newName.value = ''
  newFlowKey.value = FLOW_KEYS.value[0] ?? 'flow.listen'
  moduleError.value = ''
}

async function addModule() {
  const name = newName.value.trim()
  if (!addingGroup.value || !name || moduleBusy.value) return
  moduleBusy.value = true
  moduleError.value = ''
  try {
    const created = await createPromptModule(
      addingGroup.value,
      name,
      addingGroup.value === 'flow' ? newFlowKey.value : undefined,
    )
    addingGroup.value = null
    await load()
    selectedKey.value = created.key
  } catch {
    moduleError.value = t('prompts.actionFailed')
  } finally {
    moduleBusy.value = false
  }
}

function replaceModule(updated: PromptModuleItem) {
  modules.value = modules.value.map((m) => (m.key === updated.key ? updated : m))
}

const renaming = ref(false)
const renameValue = ref('')
function startRename() {
  if (!currentModule.value) return
  renameValue.value = currentModule.value.names[lang.value] ?? nameOf(currentModule.value.key)
  renaming.value = true
  moduleError.value = ''
}

async function saveRename() {
  if (!currentModule.value || moduleBusy.value) return
  moduleBusy.value = true
  moduleError.value = ''
  try {
    replaceModule(await updatePromptModule(currentModule.value.key, { language: lang.value, name: renameValue.value }))
    renaming.value = false
  } catch {
    moduleError.value = t('prompts.actionFailed')
  } finally {
    moduleBusy.value = false
  }
}

async function toggleEnabled() {
  if (!currentModule.value || moduleBusy.value) return
  moduleBusy.value = true
  moduleError.value = ''
  try {
    replaceModule(await updatePromptModule(currentModule.value.key, { enabled: !currentModule.value.enabled }))
  } catch {
    moduleError.value = t('prompts.actionFailed')
  } finally {
    moduleBusy.value = false
  }
}

const confirmingRemove = ref(false)
async function removeModule() {
  const m = currentModule.value
  if (!m || m.built_in || moduleBusy.value) return
  moduleBusy.value = true
  moduleError.value = ''
  try {
    await deletePromptModule(m.key)
    confirmingRemove.value = false
    const next = { ...drafts.value }
    for (const l of ['zh', 'ko'] as Language[]) delete next[draftId(m.key, l)]
    drafts.value = next
    selectedKey.value = m.group === 'flow' && m.flow_key ? m.flow_key : 'rules.role_scope'
    await load()
  } catch (e) {
    moduleError.value = errorStatus(e) === 409 ? t('prompts.stageHasBlocks') : t('prompts.actionFailed')
  } finally {
    moduleBusy.value = false
  }
}

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
// A step written in three boxes (backend app/prompts/stages.py SLOT_*): the
// text is stored and sent as one piece with these headings.
const SLOT_HEADS = ['【这一步要达成什么】', '【示例问题】', '【这一步不要做什么】']
function parseSlots(text: string): string[] | null {
  const at = SLOT_HEADS.map((h) => text.indexOf(h))
  if (at.some((i) => i < 0) || at[0]! > 0 || !(at[0]! < at[1]! && at[1]! < at[2]!)) return null
  return SLOT_HEADS.map((h, i) => {
    let part = text.slice(at[i]! + h.length, i < 2 ? at[i + 1] : undefined)
    if (part.startsWith('\n')) part = part.slice(1)
    if (i < 2 && part.endsWith('\n\n')) part = part.slice(0, -2)
    return part
  })
}
const joinSlots = (parts: string[]) => SLOT_HEADS.map((h, i) => `${h}\n${parts[i] ?? ''}`).join('\n\n')
const slots = computed(() => (currentModule.value?.is_stage ? parseSlots(draft.value) : null))
function setSlot(i: number, value: string) {
  const parts = [...(slots.value ?? ['', '', ''])]
  parts[i] = value
  draft.value = joinSlots(parts)
}
function toSlots() {
  draft.value = joinSlots([draft.value.trim(), '', ''])
}
const SLOT_KEYS = ['goal', 'examples', 'avoid'] as const
// The program's own add-ons stay folded away unless asked for.
const showSystem = ref(false)
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
  renaming.value = false
  confirmingRemove.value = false
  moduleError.value = ''
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
    />

    <!-- Narrow: stacked. >=1024px: list | editor, test panel below.
         >=1360px: full-width three-column workspace — list | editor | a
         sticky, full-height test chat on the right. -->
    <div v-if="!loading && section === 'prompts'" class="workspace" :class="{ detail: narrowDetail }">
      <nav class="block-list">
        <template v-for="g in groupedItems" :key="g.group">
          <div class="group-title">
            {{ t(`prompts.groups.${g.group}.name`) }}
            <span class="group-hint">{{ t(`prompts.groups.${g.group}.hint`) }}</span>
            <button v-if="g.group === 'system'" type="button" class="btn-text fold-btn" @click="showSystem = !showSystem">
              {{ showSystem ? t('prompts.foldSystem') : t('prompts.unfoldSystem', { n: g.entries.length }) }}
            </button>
          </div>
          <button
            v-for="{ module: m, item } in g.group === 'system' && !showSystem ? [] : g.entries"
            :key="m.key"
            type="button"
            class="block"
            :class="{ selected: m.key === selectedKey, child: !m.is_stage && m.group === 'flow', off: !m.enabled }"
            @click="openBlock(m.key)"
          >
            <span class="block-name">{{ nameOf(m.key) }}</span>
            <span class="block-tags">
              <span v-if="!m.enabled" class="badge">{{ t('prompts.disabledBadge') }}</span>
              <span v-if="isDirty(item)" class="badge warn">{{ t('prompts.unsaved') }}</span>
              <span v-if="!m.built_in && !item.content.trim()" class="badge">{{ t('prompts.emptyBadge') }}</span>
              <span v-else-if="!m.built_in" class="badge accent">{{ t('prompts.customBadge') }}</span>
              <span v-else class="badge" :class="{ accent: item.version > 0 }">
                {{ item.version > 0 ? t('prompts.modified') : t('prompts.default') }}
              </span>
            </span>
          </button>

          <form v-if="addingGroup === g.group" class="add-form" @submit.prevent="addModule">
            <div class="add-title">{{ t('prompts.addTitle') }}</div>
            <input v-model="newName" maxlength="40" :placeholder="t('prompts.namePlaceholder')" />
            <label v-if="g.group === 'flow'" class="add-flow">
              <span>{{ t('prompts.belongsTo') }}</span>
              <select v-model="newFlowKey">
                <option v-for="fk in FLOW_KEYS" :key="fk" :value="fk">{{ nameOf(fk) }}</option>
              </select>
            </label>
            <div class="add-actions">
              <button type="button" class="btn-text" @click="addingGroup = null">{{ t('prompts.cancel') }}</button>
              <button type="submit" class="btn-primary" :disabled="!newName.trim() || moduleBusy">{{ t('prompts.create') }}</button>
            </div>
          </form>
          <button v-else-if="g.group !== 'system'" type="button" class="add-btn" @click="startAdd(g.group)">{{ t('prompts.add') }}</button>
        </template>
      </nav>

      <section v-if="current" ref="editorEl" class="editor panel">
        <button type="button" class="btn-text back-btn" @click="narrowDetail = false">← {{ t('prompts.backToList') }}</button>
        <h2 class="panel-title">{{ nameOf(current.key) }}</h2>
        <p v-if="currentModule" class="panel-desc">{{ descOf(currentModule) }}</p>

        <div v-if="currentModule" class="module-actions">
          <template v-if="renaming">
            <form class="rename-form" @submit.prevent="saveRename">
              <input v-model="renameValue" maxlength="40" />
              <button type="submit" class="btn-primary" :disabled="moduleBusy">{{ t('prompts.renameSave') }}</button>
              <button type="button" class="btn-text" @click="renaming = false">{{ t('prompts.cancel') }}</button>
            </form>
            <p class="hint">{{ t('prompts.renameHint', { lang: lang === 'zh' ? '中文' : '한국어' }) }}</p>
          </template>
          <template v-else-if="confirmingRemove">
            <span class="remove-text">{{ t('prompts.removeConfirm', { name: nameOf(currentModule.key) }) }}</span>
            <button type="button" class="btn-text" @click="confirmingRemove = false">{{ t('prompts.cancel') }}</button>
            <button type="button" class="btn-danger" :disabled="moduleBusy" @click="removeModule">
              {{ t('prompts.removeYes') }}
            </button>
          </template>
          <template v-else>
            <button v-if="!phone" type="button" class="btn-outline small" @click="startRename">{{ t('prompts.rename') }}</button>
            <button type="button" class="btn-outline small" :disabled="moduleBusy" @click="toggleEnabled">
              {{ currentModule.enabled ? t('prompts.disable') : t('prompts.enable') }}
            </button>
            <button
              v-if="!currentModule.built_in"
              type="button"
              class="btn-outline small danger"
              @click="confirmingRemove = true"
            >
              {{ t('prompts.remove') }}
            </button>
          </template>
          <span v-if="moduleError" class="error">{{ moduleError }}</span>
        </div>
        <p v-if="currentModule && !currentModule.enabled" class="off-note">{{ t('prompts.disabledNote') }}</p>
        <p v-else-if="currentModule && !currentModule.built_in && !current.content.trim()" class="off-note">
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

        <div v-if="phone" class="ro-text">{{ draft }}</div>
        <div v-else-if="slots" class="slots">
          <label v-for="(k, i) in SLOT_KEYS" :key="k" class="slot">
            <span class="slot-title">{{ t(`prompts.slots.${k}.title`) }}</span>
            <span class="slot-hint">{{ t(`prompts.slots.${k}.hint`) }}</span>
            <textarea
              :value="slots[i]"
              class="content slot-text"
              spellcheck="false"
              @input="setSlot(i, ($event.target as HTMLTextAreaElement).value)"
            />
          </label>
        </div>
        <template v-else>
          <textarea v-model="draft" class="content" spellcheck="false" />
          <button v-if="currentModule?.is_stage" type="button" class="btn-text to-slots" @click="toSlots">
            {{ t('prompts.slots.convert') }}
          </button>
        </template>

        <div class="save-row">
          <input v-model="note" class="note-input" maxlength="200" :placeholder="t('prompts.notePlaceholder')" />
          <button type="button" class="btn-primary" :disabled="!dirty || saving || !draft.trim()" @click="save">
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
    grid-template-columns: 240px minmax(0, 1fr);
    gap: 24px;
  }
  .test {
    grid-column: 1 / -1;
    height: 640px;
  }
  .block-list {
    position: sticky;
    top: calc(var(--site-header-h) + 24px);
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
.block-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.group-title {
  margin: 14px 2px 2px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text);
}
.group-title:first-child {
  margin-top: 0;
}
.group-hint {
  display: block;
  font-weight: 400;
  color: var(--text-muted);
  font-size: 11.5px;
  line-height: 1.5;
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

.block.child {
  margin-left: 16px;
}
.block.off .block-name {
  color: var(--text-muted);
  text-decoration: line-through;
}
.add-btn {
  align-self: flex-start;
  border: 1px dashed var(--border);
  background: transparent;
  color: var(--accent);
  border-radius: var(--radius-md);
  padding: 8px 14px;
  font-size: 12.5px;
  font-weight: 600;
}
.add-btn:not(:disabled):hover {
  border-color: var(--accent);
  transform: none;
}
.add-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--accent);
  border-radius: var(--radius-md);
  background: var(--accent-soft);
}
.add-title {
  font-size: 12.5px;
  font-weight: 700;
}
.add-form input,
.add-form select,
.rename-form input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface);
}
.add-flow {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
}
.add-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}
.add-actions .btn-primary {
  padding: 7px 16px;
  font-size: 13px;
}

/* ---- Editor ---- */
.module-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.module-actions .small {
  padding: 6px 12px;
  font-size: 12.5px;
}
.module-actions .danger {
  color: var(--danger);
  border-color: var(--danger-border);
}
.rename-form {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  width: 100%;
}
.rename-form input {
  flex: 1;
  min-width: 160px;
}
.rename-form .btn-primary {
  padding: 7px 14px;
  font-size: 13px;
}
.remove-text {
  font-size: 13px;
  color: var(--danger);
}
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
.phone .secondary-row,
.phone .secondary-row + .hint,
.phone .versions,
.phone .add-btn,
.phone .add-form {
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
.back-btn {
  display: none;
  padding: 0;
  margin-bottom: 10px;
  font-size: 14px;
}
/* Narrow: list, or editor + test chat — never both stacked. */
@media (max-width: 1023px) {
  .back-btn {
    display: inline-block;
  }
  .workspace:not(.detail) .editor,
  .workspace:not(.detail) .test,
  .workspace.detail .block-list {
    display: none;
  }
}
.slots {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.slot {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.slot-title {
  font-weight: 700;
  font-size: 14px;
}
.slot-hint {
  font-size: 12.5px;
  color: var(--text-muted);
}
.content.slot-text {
  min-height: 140px;
  height: auto;
  field-sizing: content;
  max-height: 520px;
}
.to-slots {
  align-self: flex-start;
  margin-top: 6px;
  font-size: 13px;
}
.fold-btn {
  display: block;
  margin-top: 4px;
  padding: 0;
  font-size: 12.5px;
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
