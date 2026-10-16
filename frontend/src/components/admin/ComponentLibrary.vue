<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePhone } from '@/utils/phone'
import { useFlowSettings } from '@/utils/flowSettings'
import {
  createPromptModule,
  deletePromptModule,
  errorStatus,
  updatePromptModule,
  type Language,
  type PromptModuleItem,
} from '@/api/client'

// "对话组件": every conversation step as a card of its own — create, rename,
// turn off, delete, how many turns it lasts — and the prompt blocks. Where the steps go is the
// "对话流程" page; what the AI says in them is the "提示词" page.
const props = defineProps<{
  modules: PromptModuleItem[]
  nameOf: (key: string) => string
  // Steps with no text in the language being edited.
  emptyKeys: string[]
}>()
const emit = defineEmits<{ edit: [key: string]; reload: [] }>()

const { t, te } = useI18n()
const phone = usePhone()
const { config, defaults, dirty, load, save, discard, forgetStep } = useFlowSettings()

const CLOSING = 'flow.closing'
const FIXED = [CLOSING, 'flow.stabilization', 'flow.ending']
// Steps that end on something the user does: only a maximum applies.
const MAX_ONLY = new Set(['flow.listen', 'flow.self_check'])
const NO_TURNS = new Set(['flow.purpose', ...FIXED])

const steps = computed(() => props.modules.filter((m) => m.is_stage && !FIXED.includes(m.key)))
const fixed = computed(() => FIXED.map((k) => props.modules.find((m) => m.key === k)).filter((m): m is PromptModuleItem => !!m))
// Position in the conversation, counting only the steps in use.
const positions = computed(() => {
  let n = 0
  return Object.fromEntries(steps.value.map((m) => [m.key, m.enabled ? ++n : 0]))
})

const error = ref('')
const flash = ref('')
const busy = ref(false)
function done(msg: string) {
  flash.value = msg
  setTimeout(() => (flash.value = ''), 4000)
}
onMounted(() => load().catch(() => (error.value = t('flowOrder.failed'))))

function summary(m: PromptModuleItem): string {
  const id = `prompts.keys.${m.key}.desc`
  return m.built_in && te(id) ? t(id) : t('comp.what.custom')
}

// ---- Turns ----
function limitsOf(key: string): [number, number] {
  return config.value?.limits[key] ?? defaults.value?.limits[key] ?? [1, 8]
}
function setLimit(key: string, which: 0 | 1, value: number) {
  const c = config.value!
  const l = (c.limits[key] = [...limitsOf(key)] as [number, number])
  l[which] = Math.max(1, Math.min(50, Math.round(value) || 1))
  if (l[0] > l[1]) l[which === 0 ? 1 : 0] = l[which]
}

// ---- Rename (both languages at once) ----
const renaming = ref<string | null>(null)
const names = ref<Record<Language, string>>({ zh: '', ko: '' })
function startRename(m: PromptModuleItem) {
  renaming.value = m.key
  names.value = { zh: m.names.zh ?? '', ko: m.names.ko ?? '' }
}
async function saveRename(m: PromptModuleItem) {
  busy.value = true
  error.value = ''
  try {
    for (const l of ['zh', 'ko'] as Language[]) {
      if ((m.names[l] ?? '') !== names.value[l].trim()) await updatePromptModule(m.key, { language: l, name: names.value[l].trim() })
    }
    renaming.value = null
    emit('reload')
  } catch {
    error.value = t('flowOrder.failed')
  } finally {
    busy.value = false
  }
}

// ---- Turn off / on, delete ----
async function toggle(m: PromptModuleItem) {
  busy.value = true
  error.value = ''
  try {
    await updatePromptModule(m.key, { enabled: !m.enabled })
    emit('reload')
    done(m.enabled ? t('comp.offDone', { name: props.nameOf(m.key) }) : t('comp.onDone', { name: props.nameOf(m.key) }))
  } catch {
    error.value = t('flowOrder.failed')
  } finally {
    busy.value = false
  }
}

const confirmingDelete = ref<string | null>(null)
async function remove(m: PromptModuleItem) {
  if (confirmingDelete.value !== m.key) {
    confirmingDelete.value = m.key
    return
  }
  const name = props.nameOf(m.key)
  busy.value = true
  error.value = ''
  try {
    await deletePromptModule(m.key)
    confirmingDelete.value = null
    await forgetStep(m.key)
    emit('reload')
    done(t('comp.deleted', { name }))
  } catch (e) {
    error.value = errorStatus(e) === 409 ? t('prompts.stageHasBlocks') : t('flowOrder.failed')
  } finally {
    busy.value = false
  }
}

// ---- New component ----
const creating = ref(false)
const newNames = ref<Record<Language, string>>({ zh: '', ko: '' })
async function create() {
  const zh = newNames.value.zh.trim()
  const ko = newNames.value.ko.trim()
  if (!(zh || ko) || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const created = await createPromptModule('flow', zh || ko)
    if (zh && ko) await updatePromptModule(created.key, { language: 'ko', name: ko })
    creating.value = false
    newNames.value = { zh: '', ko: '' }
    emit('reload')
    done(t('comp.created', { name: zh || ko }))
  } catch {
    error.value = t('flowOrder.failed')
  } finally {
    busy.value = false
  }
}

// ---- Prompt blocks: shared rules, blocks attached to a step, others ----
const blocks = computed(() => props.modules.filter((m) => !m.is_stage && m.group !== 'system'))
function blockWhere(m: PromptModuleItem): string {
  if (m.group === 'flow') return t('comp.blockOf', { name: props.nameOf(m.flow_key ?? '') })
  return t(`prompts.groups.${m.group}.name`)
}
const blockForm = ref<{ name: string; kind: 'rules' | 'flow' | 'other'; step: string } | null>(null)
function startBlock() {
  blockForm.value = { name: '', kind: 'rules', step: steps.value[0]?.key ?? 'flow.listen' }
}
async function createBlock() {
  const f = blockForm.value
  if (!f || !f.name.trim() || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await createPromptModule(f.kind, f.name.trim(), f.kind === 'flow' ? f.step : undefined)
    blockForm.value = null
    emit('reload')
    done(t('comp.created', { name: f.name.trim() }))
  } catch {
    error.value = t('flowOrder.failed')
  } finally {
    busy.value = false
  }
}

async function saveSettings() {
  busy.value = true
  error.value = ''
  try {
    await save()
    done(t('flowOrder.saved'))
  } catch {
    error.value = t('flowOrder.failed')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="library">
    <header class="intro">
      <h2>{{ t('comp.title') }}</h2>
      <p>{{ t('comp.desc') }}</p>
    </header>

    <!-- What's what on this page, in plain words. -->
    <details class="explain" open>
      <summary>{{ t('comp.explain.title') }}</summary>
      <div class="explain-body">
        <div class="kinds">
          <div class="kind">
            <div class="kind-name">🧩 {{ t('comp.explain.compName') }}</div>
            <p>{{ t('comp.explain.compWhat') }}</p>
          </div>
          <div class="kind">
            <div class="kind-name">📝 {{ t('comp.explain.blockName') }}</div>
            <p>{{ t('comp.explain.blockWhat') }}</p>
          </div>
        </div>
        <div class="assemble">
          <div class="assemble-title">{{ t('comp.explain.assembleTitle') }}</div>
          <div class="stack">
            <span class="layer">{{ t('comp.explain.layerRules') }}</span>
            <span class="plus-sign">＋</span>
            <span class="layer main">{{ t('comp.explain.layerStep') }}</span>
            <span class="plus-sign">＋</span>
            <span class="layer">{{ t('comp.explain.layerAttached') }}</span>
            <span class="plus-sign">＋</span>
            <span class="layer muted">{{ t('comp.explain.layerProgram') }}</span>
          </div>
        </div>
        <div class="which">
          <div class="assemble-title">{{ t('comp.explain.whichTitle') }}</div>
          <ul>
            <li>{{ t('comp.explain.which1') }}</li>
            <li>{{ t('comp.explain.which2') }}</li>
            <li>{{ t('comp.explain.which3') }}</li>
            <li>{{ t('comp.explain.which4') }}</li>
          </ul>
        </div>
        <p class="hint">{{ t('comp.explain.pages') }}</p>
      </div>
    </details>

    <!-- Steps -->
    <div class="grid">
      <article v-for="m in steps" :key="m.key" class="card" :class="{ off: !m.enabled }">
        <div class="card-head">
          <h3>{{ nameOf(m.key) }}</h3>
          <span v-if="m.enabled" class="tag on">{{ t('comp.inFlow', { n: positions[m.key] }) }}</span>
          <span v-else class="tag">{{ t('comp.notUsed') }}</span>
          <span v-if="!m.built_in" class="tag accent">{{ t('flowOrder.customBadge') }}</span>
        </div>
        <p class="what">{{ summary(m) }}</p>
        <p v-if="emptyKeys.includes(m.key)" class="warn">⚠️ {{ t('comp.noPrompt') }}</p>

        <div v-if="config && !NO_TURNS.has(m.key)" class="turns">
          <span class="turns-label">{{ t('comp.turns') }}</span>
          <label v-if="!MAX_ONLY.has(m.key)">
            {{ t('flowOrder.minTurns') }}
            <input type="number" min="1" max="50" :disabled="phone" :value="limitsOf(m.key)[0]" @change="setLimit(m.key, 0, Number(($event.target as HTMLInputElement).value))" />
          </label>
          <label>
            {{ t('flowOrder.maxTurns') }}
            <input type="number" min="1" max="50" :disabled="phone" :value="limitsOf(m.key)[1]" @change="setLimit(m.key, 1, Number(($event.target as HTMLInputElement).value))" />
          </label>
          <span class="unit">{{ t('comp.turnsUnit') }}</span>
        </div>

        <form v-if="renaming === m.key" class="rename" @submit.prevent="saveRename(m)">
          <label>中文<input v-model="names.zh" maxlength="40" :placeholder="nameOf(m.key)" /></label>
          <label>한국어<input v-model="names.ko" maxlength="40" /></label>
          <p class="hint">{{ t('comp.renameHint') }}</p>
          <div class="row">
            <button type="button" class="btn-text" @click="renaming = null">{{ t('prompts.cancel') }}</button>
            <button type="submit" class="btn-primary" :disabled="busy">{{ t('prompts.renameSave') }}</button>
          </div>
        </form>
        <div v-else-if="confirmingDelete === m.key" class="confirm">
          <span>{{ t('comp.deleteConfirm', { name: nameOf(m.key) }) }}</span>
          <button type="button" class="btn-text" @click="confirmingDelete = null">{{ t('prompts.cancel') }}</button>
          <button type="button" class="btn-danger" :disabled="busy" @click="remove(m)">{{ t('prompts.removeYes') }}</button>
        </div>
        <div v-else class="actions">
          <button type="button" class="btn-outline small" :disabled="busy" @click="toggle(m)">
            {{ m.enabled ? t('comp.turnOff') : t('comp.turnOn') }}
          </button>
          <button v-if="!phone" type="button" class="btn-text small" @click="startRename(m)">{{ t('prompts.rename') }}</button>
          <button v-if="!m.built_in && !phone" type="button" class="btn-text small danger" @click="remove(m)">{{ t('comp.delete') }}</button>
          <button type="button" class="btn-text small push" @click="emit('edit', m.key)">{{ t('comp.editPrompt') }}</button>
        </div>
      </article>

      <!-- New component -->
      <article v-if="!phone" class="card new" :class="{ open: creating }">
        <button v-if="!creating" type="button" class="new-btn" @click="creating = true">
          <span class="plus">＋</span>{{ t('comp.new') }}
        </button>
        <form v-else class="rename" @submit.prevent="create">
          <h3>{{ t('comp.new') }}</h3>
          <label>{{ t('comp.nameZh') }}<input v-model="newNames.zh" maxlength="40" :placeholder="t('flowOrder.addPlaceholder')" /></label>
          <label>{{ t('comp.nameKo') }}<input v-model="newNames.ko" maxlength="40" /></label>
          <p class="hint">{{ t('comp.newHint') }}</p>
          <div class="row">
            <button type="button" class="btn-text" @click="creating = false">{{ t('prompts.cancel') }}</button>
            <button type="submit" class="btn-primary" :disabled="busy || !(newNames.zh.trim() || newNames.ko.trim())">{{ t('flowOrder.addConfirm') }}</button>
          </div>
        </form>
      </article>
    </div>

    <!-- Prompt blocks -->
    <h3 class="sub">{{ t('comp.blocksTitle') }}</h3>
    <p class="sub-desc">{{ t('comp.blocksDesc') }}</p>
    <div class="grid">
      <article v-for="m in blocks" :key="m.key" class="card" :class="{ off: !m.enabled }">
        <div class="card-head">
          <h3>{{ nameOf(m.key) }}</h3>
          <span class="tag">{{ blockWhere(m) }}</span>
          <span v-if="!m.enabled" class="tag">{{ t('comp.notUsed') }}</span>
          <span v-if="!m.built_in" class="tag accent">{{ t('flowOrder.customBadge') }}</span>
        </div>
        <form v-if="renaming === m.key" class="rename" @submit.prevent="saveRename(m)">
          <label>中文<input v-model="names.zh" maxlength="40" :placeholder="nameOf(m.key)" /></label>
          <label>한국어<input v-model="names.ko" maxlength="40" /></label>
          <div class="row">
            <button type="button" class="btn-text" @click="renaming = null">{{ t('prompts.cancel') }}</button>
            <button type="submit" class="btn-primary" :disabled="busy">{{ t('prompts.renameSave') }}</button>
          </div>
        </form>
        <div v-else-if="confirmingDelete === m.key" class="confirm">
          <span>{{ t('comp.deleteConfirm', { name: nameOf(m.key) }) }}</span>
          <button type="button" class="btn-text" @click="confirmingDelete = null">{{ t('prompts.cancel') }}</button>
          <button type="button" class="btn-danger" :disabled="busy" @click="remove(m)">{{ t('prompts.removeYes') }}</button>
        </div>
        <div v-else class="actions">
          <button type="button" class="btn-outline small" :disabled="busy" @click="toggle(m)">
            {{ m.enabled ? t('comp.turnOff') : t('comp.turnOn') }}
          </button>
          <button v-if="!phone" type="button" class="btn-text small" @click="startRename(m)">{{ t('prompts.rename') }}</button>
          <button v-if="!m.built_in && !phone" type="button" class="btn-text small danger" @click="remove(m)">{{ t('comp.delete') }}</button>
          <button type="button" class="btn-text small push" @click="emit('edit', m.key)">{{ t('comp.editPrompt') }}</button>
        </div>
      </article>
      <article v-if="!phone" class="card new" :class="{ open: blockForm }">
        <button v-if="!blockForm" type="button" class="new-btn" @click="startBlock">
          <span class="plus">＋</span>{{ t('comp.newBlock') }}
        </button>
        <form v-else class="rename" @submit.prevent="createBlock">
          <h3>{{ t('comp.newBlock') }}</h3>
          <label>{{ t('comp.nameZh') }}<input v-model="blockForm.name" maxlength="40" :placeholder="t('prompts.namePlaceholder')" /></label>
          <label>
            {{ t('comp.blockKind') }}
            <select v-model="blockForm.kind">
              <option value="rules">{{ t('prompts.groups.rules.name') }}</option>
              <option value="flow">{{ t('comp.kindFlow') }}</option>
              <option value="other">{{ t('prompts.groups.other.name') }}</option>
            </select>
          </label>
          <label v-if="blockForm.kind === 'flow'">
            {{ t('prompts.belongsTo') }}
            <select v-model="blockForm.step">
              <option v-for="s in steps" :key="s.key" :value="s.key">{{ nameOf(s.key) }}</option>
            </select>
          </label>
          <div class="row">
            <button type="button" class="btn-text" @click="blockForm = null">{{ t('prompts.cancel') }}</button>
            <button type="submit" class="btn-primary" :disabled="busy || !blockForm.name.trim()">{{ t('flowOrder.addConfirm') }}</button>
          </div>
        </form>
      </article>
    </div>

    <!-- Fixed components -->
    <h3 class="sub">{{ t('comp.fixedTitle') }}</h3>
    <p class="sub-desc">{{ t('comp.fixedDesc') }}</p>
    <div class="grid">
      <article v-for="m in fixed" :key="m.key" class="card fixed" :class="{ off: !m.enabled }">
        <div class="card-head">
          <h3>{{ nameOf(m.key) }}</h3>
          <span class="tag safety">🛡 {{ t('flowUi.safetyStep') }}</span>
          <span v-if="!m.enabled" class="tag">{{ t('comp.notUsed') }}</span>
        </div>
        <p class="what">{{ summary(m) }}</p>
        <p class="warn">⚠️ {{ t(`comp.safetyWarn.${m.key.replace('flow.', '')}`) }}</p>
        <form v-if="renaming === m.key" class="rename" @submit.prevent="saveRename(m)">
          <label>中文<input v-model="names.zh" maxlength="40" :placeholder="nameOf(m.key)" /></label>
          <label>한국어<input v-model="names.ko" maxlength="40" /></label>
          <div class="row">
            <button type="button" class="btn-text" @click="renaming = null">{{ t('prompts.cancel') }}</button>
            <button type="submit" class="btn-primary" :disabled="busy">{{ t('prompts.renameSave') }}</button>
          </div>
        </form>
        <div v-else class="actions">
          <button type="button" class="btn-outline small" :disabled="busy" @click="toggle(m)">
            {{ m.enabled ? t('comp.turnOff') : t('comp.turnOn') }}
          </button>
          <button v-if="!phone" type="button" class="btn-text small" @click="startRename(m)">{{ t('prompts.rename') }}</button>
          <button type="button" class="btn-text small push" @click="emit('edit', m.key)">{{ t('comp.editPrompt') }}</button>
        </div>
      </article>
    </div>

    <p v-if="flash" class="flash" role="status">{{ flash }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <div v-if="dirty" class="unsaved" role="status">
      <span>{{ t('comp.unsaved') }}</span>
      <button type="button" class="btn-text" :disabled="busy" @click="discard">{{ t('flowOrder.discard') }}</button>
      <button type="button" class="btn-primary" :disabled="busy" @click="saveSettings">{{ t('flowOrder.save') }}</button>
    </div>
  </section>
</template>

<style scoped>
.library {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.intro h2 {
  margin: 0 0 4px;
  font-size: 17px;
}
.intro p,
.sub-desc {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text-muted);
}
.explain {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--accent-soft);
}
.explain summary {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
}
.explain-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 0 16px 16px;
  font-size: 13px;
  line-height: 1.6;
}
.kinds {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr));
  gap: 10px;
}
.kind {
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--surface);
}
.kind-name,
.assemble-title {
  font-weight: 700;
}
.kind p {
  margin: 4px 0 0;
  color: var(--text-muted);
}
.stack {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}
.layer {
  padding: 5px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
}
.layer.main {
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}
.layer.muted {
  border-style: dashed;
  color: var(--text-muted);
}
.plus-sign {
  color: var(--text-muted);
}
.which ul {
  margin: 4px 0 0;
  padding-left: 18px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr));
  gap: 12px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
}
.card.off {
  background: var(--bg);
}
.card.off h3 {
  color: var(--text-muted);
}
.card.fixed {
  border-color: #f0c98a;
}
.tag.safety {
  border-color: #f0c98a;
  background: #fff7e8;
  color: #9a5b00;
}
.card-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}
.card-head h3 {
  flex-basis: 100%;
}
.tag {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg);
  border: 1px solid var(--border);
  font-size: 11.5px;
  color: var(--text-muted);
}
.tag.on {
  background: #e7f6ec;
  border-color: #bfe5cb;
  color: #1c7a43;
}
.tag.accent {
  background: var(--accent-soft);
  border-color: transparent;
  color: var(--accent);
}
.what {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}
.warn {
  margin: 0;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: #fff4e0;
  color: #a15c00;
  font-size: 12.5px;
}
.turns {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  font-size: 13px;
}
.turns-label {
  font-weight: 600;
}
.turns input {
  width: 52px;
  margin-left: 4px;
  padding: 3px 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
}
.unit {
  color: var(--text-muted);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-top: auto;
  padding-top: 6px;
  border-top: 1px solid var(--border);
}
.push {
  margin-left: auto;
}
.small {
  padding: 5px 10px;
  font-size: 12.5px;
}
.danger {
  color: var(--danger);
}
.confirm {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--danger);
}
.rename {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
}
.rename label {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.rename input,
.rename select {
  min-width: 0;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
  font-size: 13px;
}
.row {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}
.hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
.card.new {
  border-style: dashed;
  background: transparent;
}
.card.new.open {
  border-style: solid;
  border-color: var(--accent);
  background: var(--surface);
}
.new-btn {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: 140px;
  border: 0;
  background: none;
  color: var(--accent);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.plus {
  font-size: 26px;
  line-height: 1;
}
.sub {
  margin: 10px 0 0;
}
.flash {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #1c8a4a;
}
.error {
  margin: 0;
  font-size: 13px;
  color: var(--danger);
}
.unsaved {
  position: sticky;
  bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 10px 14px;
  border: 1px solid var(--accent);
  border-radius: var(--radius-md);
  background: var(--surface);
  box-shadow: var(--shadow-md);
  font-size: 13px;
  font-weight: 600;
}
.unsaved span {
  flex: 1;
}
</style>
