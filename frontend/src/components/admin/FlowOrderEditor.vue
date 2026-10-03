<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  createPromptModule,
  getFlowConfig,
  saveFlowConfig,
  saveFlowOrder,
  updatePromptModule,
  type FlowConfig,
  type PromptModuleItem,
} from '@/api/client'

// The order every conversation goes through its steps (backend
// app/services/flow.py), and the flow settings (app/services/flow_config.py):
// admins drag the cards (or use ↑ ↓ on touch screens), turn steps off, add
// steps of their own, set each step's turn limits, edit the purpose buttons
// and how much history the AI sees, and jump to a step's wording in the
// editor below. Closing is always last; "calming down" and the end-button
// reply are not part of the sequence.
const props = defineProps<{
  modules: PromptModuleItem[]
  nameOf: (key: string) => string
  // Steps with no text in the language being edited.
  emptyKeys: string[]
}>()
const emit = defineEmits<{ edit: [key: string]; reload: [] }>()

const { t, te } = useI18n()

const CLOSING = 'flow.closing'
const STABILIZATION = 'flow.stabilization'
const ENDING = 'flow.ending'
const PURPOSE = 'flow.purpose'
// Steps that end on something the user does: only a maximum applies.
const MAX_ONLY = new Set(['flow.listen', 'flow.self_check'])
const DEFAULT_ORDER = [
  'flow.listen',
  'flow.purpose',
  'flow.explore',
  'flow.self_check',
  'flow.self_kindness',
  'flow.regulate',
  'flow.act',
]

const saved = computed(() =>
  props.modules.filter((m) => m.is_stage && ![CLOSING, STABILIZATION, ENDING].includes(m.key)).map((m) => m.key),
)
const order = ref<string[]>([])
watch(saved, (v) => (order.value = [...v]), { immediate: true })

// ---- Flow settings: turn limits, purpose buttons, history length ----
const savedConfig = ref<FlowConfig | null>(null)
const defaults = ref<FlowConfig | null>(null)
const config = ref<FlowConfig | null>(null)
const clone = (c: FlowConfig): FlowConfig => JSON.parse(JSON.stringify(c))
async function loadConfig() {
  const data = await getFlowConfig()
  const { defaults: d, ...current } = data
  defaults.value = d
  savedConfig.value = current
  config.value = clone(current)
}
onMounted(() => loadConfig().catch(() => (error.value = t('flowOrder.failed'))))

function limitsOf(key: string): [number, number] {
  const c = config.value
  if (!c) return [1, 8]
  if (!c.limits[key]) c.limits[key] = [...(defaults.value?.limits[key] ?? [1, 8])] as [number, number]
  return c.limits[key]!
}
function setLimit(key: string, which: 0 | 1, value: number) {
  const l = limitsOf(key)
  l[which] = Math.max(1, Math.min(50, Math.round(value) || 1))
  if (l[0] > l[1]) l[which === 0 ? 1 : 0] = l[which]
}

function addPurpose() {
  config.value?.purposes.push({ id: `p${Date.now().toString(36)}`, labels: { zh: '', ko: '' }, jump: null })
}
function removePurpose(i: number) {
  config.value?.purposes.splice(i, 1)
}
// A purpose button can only jump to a step after "confirm the purpose".
const jumpTargets = computed(() => {
  const i = order.value.indexOf(PURPOSE)
  return i < 0 ? [] : order.value.slice(i + 1)
})
const purposeProblem = computed(() => {
  const c = config.value
  if (!c) return ''
  if (!c.purposes.length) return t('flowOrder.purposes.needOne')
  if (c.purposes.some((p) => !Object.values(p.labels).some((v) => v?.trim()))) return t('flowOrder.purposes.needLabel')
  return ''
})

const configDirty = computed(
  () => !!config.value && !!savedConfig.value && JSON.stringify(config.value) !== JSON.stringify(savedConfig.value),
)
const dirty = computed(() => order.value.join() !== saved.value.join() || configDirty.value)

const byKey = (key: string) => props.modules.find((m) => m.key === key)
const enabled = (key: string) => byKey(key)?.enabled ?? true
const custom = (key: string) => !byKey(key)?.built_in

// Step numbers count only the steps that will actually run.
const numbers = computed(() => {
  let n = 0
  return Object.fromEntries(order.value.map((k) => [k, enabled(k) ? ++n : 0]))
})
const closingNumber = computed(() => order.value.filter(enabled).length + 1)

function endsText(key: string): string {
  const id = `flowOrder.ends.${key.replace('flow.', '')}`
  return custom(key) || !te(id) ? t('flowOrder.ends.custom') : t(id)
}

// ---- Reordering: drag on desktop, ↑ ↓ everywhere ----
const dragging = ref<string | null>(null)
// Only the ⠿ handle starts a drag, so the inputs inside a card stay usable.
const armed = ref<string | null>(null)
function onDragStart(key: string, e: DragEvent) {
  dragging.value = key
  e.dataTransfer?.setData('text/plain', key)
  if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
}
function onDragOver(key: string) {
  const from = dragging.value
  if (!from || from === key) return
  const list = order.value.filter((k) => k !== from)
  list.splice(order.value.indexOf(key), 0, from)
  order.value = list
}
function move(key: string, delta: number) {
  const i = order.value.indexOf(key)
  const j = i + delta
  if (j < 0 || j >= order.value.length) return
  const list = [...order.value]
  ;[list[i], list[j]] = [list[j]!, list[i]!]
  order.value = list
}

// ---- Warnings: orders that technically work but probably aren't meant ----
const warnings = computed(() => {
  const live = order.value.filter(enabled)
  const pos = (k: string) => live.indexOf(k)
  const out: string[] = []
  if (live.length && live[0] !== 'flow.listen' && pos('flow.listen') > 0) out.push(t('flowOrder.warn.listenFirst'))
  if (pos('flow.self_kindness') >= 0 && pos('flow.self_check') > pos('flow.self_kindness'))
    out.push(t('flowOrder.warn.checkBeforeKindness'))
  if (pos('flow.act') >= 0 && pos('flow.explore') > pos('flow.act')) out.push(t('flowOrder.warn.actBeforeExplore'))
  if (!live.length) out.push(t('flowOrder.warn.noneOn'))
  for (const k of live) if (props.emptyKeys.includes(k)) out.push(t('flowOrder.warn.empty', { name: props.nameOf(k) }))
  return out
})

// ---- Saving ----
const busy = ref(false)
const error = ref('')
const flash = ref('')
function flashMessage(msg: string) {
  flash.value = msg
  setTimeout(() => (flash.value = ''), 6000)
}

async function save() {
  if (purposeProblem.value) {
    error.value = purposeProblem.value
    return
  }
  busy.value = true
  error.value = ''
  try {
    if (order.value.join() !== saved.value.join()) await saveFlowOrder(order.value)
    if (configDirty.value && config.value) {
      const res = await saveFlowConfig(config.value)
      const { defaults: d, ...current } = res
      defaults.value = d
      savedConfig.value = current
      config.value = clone(current)
    }
    emit('reload')
    flashMessage(t('flowOrder.saved'))
  } catch {
    error.value = t('flowOrder.failed')
  } finally {
    busy.value = false
  }
}

function resetDefault() {
  order.value = [...DEFAULT_ORDER.filter((k) => saved.value.includes(k)), ...saved.value.filter((k) => !DEFAULT_ORDER.includes(k))]
  if (defaults.value) config.value = clone(defaults.value)
}

function discardAll() {
  order.value = [...saved.value]
  if (savedConfig.value) config.value = clone(savedConfig.value)
}

async function toggle(key: string) {
  busy.value = true
  error.value = ''
  try {
    await updatePromptModule(key, { enabled: !enabled(key) })
    emit('reload')
  } catch {
    error.value = t('flowOrder.failed')
  } finally {
    busy.value = false
  }
}

// ---- Adding a step of one's own ----
const adding = ref(false)
const newName = ref('')
async function addStep() {
  const name = newName.value.trim()
  if (!name || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const created = await createPromptModule('flow', name)
    adding.value = false
    newName.value = ''
    emit('reload')
    emit('edit', created.key)
    flashMessage(t('flowOrder.added', { name }))
  } catch {
    error.value = t('flowOrder.failed')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="flow-order">
    <header class="head">
      <div>
        <h2>{{ t('flowOrder.title') }}</h2>
        <p class="desc">{{ t('flowOrder.desc') }}</p>
      </div>
    </header>

    <ol class="howto">
      <li>{{ t('flowOrder.how1') }}</li>
      <li>{{ t('flowOrder.how2') }}</li>
      <li>{{ t('flowOrder.how3') }}</li>
      <li>{{ t('flowOrder.how4') }}</li>
    </ol>

    <TransitionGroup name="card" tag="ol" class="cards">
      <li
        v-for="(key, i) in order"
        :key="key"
        class="card"
        :class="{ off: !enabled(key), dragging: dragging === key }"
        :draggable="armed === key"
        @dragstart="onDragStart(key, $event)"
        @dragover.prevent="onDragOver(key)"
        @drop.prevent
        @dragend="dragging = null; armed = null"
      >
        <span
          class="grip"
          :title="t('flowOrder.dragHint')"
          aria-hidden="true"
          @mousedown="armed = key"
          @mouseup="armed = null"
          >⠿</span
        >
        <span class="num" :class="{ off: !enabled(key) }">{{ enabled(key) ? numbers[key] : '–' }}</span>
        <div class="body">
          <div class="name">
            {{ nameOf(key) }}
            <span v-if="custom(key)" class="badge accent">{{ t('flowOrder.customBadge') }}</span>
            <span v-if="!enabled(key)" class="badge">{{ t('flowOrder.skippedBadge') }}</span>
          </div>
          <div class="ends">{{ endsText(key) }}</div>
          <div v-if="config && key !== PURPOSE" class="limits">
            <label v-if="!MAX_ONLY.has(key)">
              {{ t('flowOrder.minTurns') }}
              <input
                type="number"
                min="1"
                max="50"
                :value="limitsOf(key)[0]"
                @change="setLimit(key, 0, Number(($event.target as HTMLInputElement).value))"
              />
            </label>
            <label>
              {{ t('flowOrder.maxTurns') }}
              <input
                type="number"
                min="1"
                max="50"
                :value="limitsOf(key)[1]"
                @change="setLimit(key, 1, Number(($event.target as HTMLInputElement).value))"
              />
            </label>
            <span class="limits-hint">{{ t('flowOrder.turnsHint') }}</span>
          </div>
          <div v-if="config && key === PURPOSE" class="purposes">
            <div class="purposes-title">{{ t('flowOrder.purposes.title') }}</div>
            <p class="limits-hint">{{ t('flowOrder.purposes.hint') }}</p>
            <div v-for="(p, pi) in config.purposes" :key="p.id" class="purpose-row">
              <input v-model="p.labels.zh" maxlength="40" :placeholder="t('flowOrder.purposes.zh')" />
              <input v-model="p.labels.ko" maxlength="40" :placeholder="t('flowOrder.purposes.ko')" />
              <select v-model="p.jump">
                <option :value="null">{{ t('flowOrder.purposes.noJump') }}</option>
                <option v-for="k in jumpTargets" :key="k" :value="k">{{ t('flowOrder.purposes.jumpTo', { name: nameOf(k) }) }}</option>
              </select>
              <button
                type="button"
                class="icon-btn"
                :aria-label="t('flowOrder.purposes.remove')"
                :disabled="config.purposes.length <= 1"
                @click="removePurpose(pi)"
              >
                ✕
              </button>
            </div>
            <button v-if="config.purposes.length < 8" type="button" class="btn-text small" @click="addPurpose">
              {{ t('flowOrder.purposes.add') }}
            </button>
          </div>
        </div>
        <div class="actions">
          <button
            type="button"
            class="icon-btn"
            :disabled="i === 0"
            :aria-label="t('flowOrder.up', { name: nameOf(key) })"
            @click="move(key, -1)"
          >
            ↑
          </button>
          <button
            type="button"
            class="icon-btn"
            :disabled="i === order.length - 1"
            :aria-label="t('flowOrder.down', { name: nameOf(key) })"
            @click="move(key, 1)"
          >
            ↓
          </button>
          <button type="button" class="btn-text small" @click="emit('edit', key)">{{ t('flowOrder.edit') }}</button>
          <button type="button" class="btn-text small" :disabled="busy" @click="toggle(key)">
            {{ enabled(key) ? t('flowOrder.skip') : t('flowOrder.unskip') }}
          </button>
        </div>
      </li>
    </TransitionGroup>

    <div class="card fixed">
      <span class="grip placeholder" aria-hidden="true">🔒</span>
      <span class="num">{{ closingNumber }}</span>
      <div class="body">
        <div class="name">{{ nameOf(CLOSING) }}</div>
        <div class="ends">{{ t('flowOrder.closingNote') }}</div>
      </div>
      <div class="actions">
        <button type="button" class="btn-text small" @click="emit('edit', CLOSING)">{{ t('flowOrder.edit') }}</button>
      </div>
    </div>
    <p class="aside">
      {{ t('flowOrder.stabilizationNote', { name: nameOf(STABILIZATION) }) }}
      <button type="button" class="btn-text small" @click="emit('edit', STABILIZATION)">{{ t('flowOrder.edit') }}</button>
    </p>
    <p class="aside">
      {{ t('flowOrder.endingNote', { name: nameOf(ENDING) }) }}
      <button type="button" class="btn-text small" @click="emit('edit', ENDING)">{{ t('flowOrder.edit') }}</button>
    </p>

    <div v-if="config" class="history">
      <label>
        {{ t('flowOrder.history.label') }}
        <input
          type="number"
          min="2"
          max="60"
          :value="config.history_turns"
          @change="config.history_turns = Math.max(2, Math.min(60, Math.round(Number(($event.target as HTMLInputElement).value)) || 12))"
        />
        {{ t('flowOrder.history.unit') }}
      </label>
      <span class="limits-hint">{{ t('flowOrder.history.hint') }}</span>
    </div>

    <ul v-if="warnings.length" class="warnings" role="status">
      <li v-for="w in warnings" :key="w">⚠️ {{ w }}</li>
    </ul>

    <form v-if="adding" class="add" @submit.prevent="addStep">
      <label>
        <span>{{ t('flowOrder.addLabel') }}</span>
        <input v-model="newName" maxlength="40" :placeholder="t('flowOrder.addPlaceholder')" />
      </label>
      <p class="hint">{{ t('flowOrder.addHint') }}</p>
      <div class="row">
        <button type="button" class="btn-text" @click="adding = false">{{ t('prompts.cancel') }}</button>
        <button type="submit" class="btn-primary" :disabled="!newName.trim() || busy">{{ t('flowOrder.addConfirm') }}</button>
      </div>
    </form>

    <div class="foot">
      <button v-if="!adding" type="button" class="btn-outline" @click="adding = true">{{ t('flowOrder.add') }}</button>
      <button type="button" class="btn-text" @click="resetDefault">{{ t('flowOrder.resetDefault') }}</button>
      <span v-if="flash" class="flash">{{ flash }}</span>
    </div>

    <div v-if="dirty" class="unsaved" role="status">
      <span>{{ t('flowOrder.unsaved') }}</span>
      <button type="button" class="btn-text" :disabled="busy" @click="discardAll">{{ t('flowOrder.discard') }}</button>
      <button type="button" class="btn-primary" :disabled="busy" @click="save">{{ t('flowOrder.save') }}</button>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<style scoped>
.flow-order {
  margin-bottom: 20px;
  padding: 20px 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
}
h2 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
}
.desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}
.howto {
  margin: 12px 0 14px;
  padding: 10px 14px 10px 30px;
  border-radius: var(--radius-md);
  background: var(--accent-soft);
  font-size: 13px;
  line-height: 1.8;
}
.cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}
.card.dragging {
  border-color: var(--accent);
  background: var(--accent-soft);
  opacity: 0.85;
}
.card.off {
  opacity: 0.6;
}
.card.fixed {
  margin-top: 8px;
  border-style: dashed;
  cursor: default;
}
.grip {
  flex-shrink: 0;
  cursor: grab;
  font-size: 18px;
  color: var(--text-muted);
  user-select: none;
}
.grip.placeholder {
  font-size: 13px;
}
.num {
  display: grid;
  flex-shrink: 0;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  font-weight: 700;
}
.num.off {
  background: var(--border);
  color: var(--text-muted);
}
.body {
  flex: 1;
  min-width: 0;
}
.name {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
}
.ends {
  margin-top: 2px;
  font-size: 12.5px;
  line-height: 1.5;
  color: var(--text-muted);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}
.icon-btn {
  width: 30px;
  height: 30px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
}
.icon-btn:disabled {
  opacity: 0.35;
  cursor: default;
}
.small {
  padding: 4px 8px;
  font-size: 12.5px;
}
.badge {
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--border);
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text-muted);
}
.badge.accent {
  background: var(--accent-soft);
  color: var(--accent);
}
.aside {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin: 10px 0 0;
  font-size: 12.5px;
  color: var(--text-muted);
}
.warnings {
  margin: 12px 0 0;
  padding: 10px 14px;
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-md);
  background: var(--danger-soft);
  font-size: 13px;
  line-height: 1.7;
  list-style: none;
}
.add {
  margin-top: 12px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.add label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}
.add input {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
}
.hint {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--text-muted);
}
.row {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
.foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 14px;
  margin-top: 14px;
}
.flash {
  font-size: 13px;
  font-weight: 600;
  color: #1c8a4a;
}
.unsaved {
  position: sticky;
  bottom: 12px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  margin-top: 14px;
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
.error {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--danger);
}
.limits,
.history {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 12px;
  margin-top: 6px;
  font-size: 12.5px;
}
.limits input,
.history input {
  width: 56px;
  margin-left: 4px;
  padding: 3px 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
}
.history {
  margin-top: 14px;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
}
.limits-hint {
  font-size: 12px;
  color: var(--text-muted);
}
.purposes {
  margin-top: 8px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  cursor: default;
}
.purposes-title {
  font-size: 13px;
  font-weight: 600;
}
.purpose-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr auto;
  gap: 6px;
  margin-top: 6px;
}
.purpose-row input,
.purpose-row select {
  min-width: 0;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
  font-size: 12.5px;
}
.card-move {
  transition: transform 0.2s ease;
}
@media (max-width: 640px) {
  .card {
    flex-wrap: wrap;
  }
  .purpose-row {
    grid-template-columns: 1fr auto;
  }
  .actions {
    width: 100%;
  }
}
</style>
