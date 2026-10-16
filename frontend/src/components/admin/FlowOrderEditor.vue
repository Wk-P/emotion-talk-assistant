<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePhone } from '@/utils/phone'
import { useFlowSettings } from '@/utils/flowSettings'
import CrisisResourcesEditor from './CrisisResourcesEditor.vue'
import {
  deletePromptModule,
  errorStatus,
  saveFlowOrder,
  updatePromptModule,
  type KeywordList,
  type PromptModuleItem,
} from '@/api/client'

// "对话流程": the order a conversation goes through its steps (backend
// app/services/flow.py). The steps in use are a line of cards; between any
// two, admins put in a step that isn't in use (new components are made on
// the "对话组件" page). Taking a step
// out, moving it and putting it back save at once. The program rules a
// conversation follows (app/services/flow_config.py) are folded below and
// saved with the save bar. No drag and drop: it flickered in Safari.
const props = defineProps<{
  modules: PromptModuleItem[]
  nameOf: (key: string) => string
  // Steps with no text in the language being edited.
  emptyKeys: string[]
}>()
const emit = defineEmits<{ edit: [key: string]; reload: []; components: [] }>()

const { t, te } = useI18n()
const phone = usePhone()
const { config, defaults, dirty, load, save, discard, resetToDefaults, forgetStep } = useFlowSettings()

const PURPOSE = 'flow.purpose'
// Steps that answer only when something happens (admin-chosen), not in order.
const TRIGGER_ROLES = ['stabilize_step', 'ending_step'] as const

// Every step, in use or not (the order the backend stores). Nothing is fixed.
const saved = computed(() => props.modules.filter((m) => m.is_stage).map((m) => m.key))
const order = ref<string[]>([])
watch(saved, (v) => (order.value = [...v]), { immediate: true })

const byKey = (key: string) => props.modules.find((m) => m.key === key)
const enabled = (key: string) => byKey(key)?.enabled ?? true
const custom = (key: string) => !byKey(key)?.built_in
const triggered = (key: string) => TRIGGER_ROLES.some((r) => config.value?.[r] === key)
const isSafety = (key: string) => !!config.value?.safety_steps.includes(key)
// The line: steps walked through in order (trigger-only steps are below).
const inLine = (key: string) => enabled(key)
// Every component is shown on the line, trigger-only ones too (marked).
const lineKeys = computed(() => order.value)
const live = computed(() => order.value.filter(inLine))
const unused = computed(() => order.value.filter((k) => !enabled(k)))
const roleOfKey = (key: string) => TRIGGER_ROLES.find((r) => config.value?.[r] === key) ?? null
function clearRole(key: string) {
  const r = roleOfKey(key)
  if (r && config.value) config.value[r] = null
}
// Position among the steps in use.
const liveIndex = computed(() => Object.fromEntries(live.value.map((k, i) => [k, i])) as Record<string, number>)

onMounted(() => load().catch(() => (error.value = t('flowOrder.failed'))))

const busy = ref(false)
const error = ref('')
const flash = ref('')
function done(msg: string) {
  flash.value = msg
  setTimeout(() => (flash.value = ''), 4000)
}
async function run(action: () => Promise<unknown>, okMsg?: string) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await action()
    if (okMsg) done(okMsg)
  } catch (e) {
    error.value = errorStatus(e) === 409 ? t('prompts.stageHasBlocks') : t('flowOrder.failed')
    order.value = [...saved.value]
  } finally {
    busy.value = false
  }
}

// What happens in a step, in one line.
function endsText(key: string): string {
  const id = `flowOrder.ends.${key.replace('flow.', '')}`
  return custom(key) || !te(id) ? t('flowOrder.ends.custom') : t(id)
}
// Add-ons shown on a step's card.
function addons(key: string): string[] {
  const c = config.value
  if (!c) return []
  const out: string[] = []
  if (c.card_steps.seb_summary === key) out.push(t('flowUi.addon.summary'))
  if (c.card_steps.plan_form === key) out.push(t('flowUi.addon.plan'))
  if (c.closing_step === key) out.push(t('comp.role.closing_step'))
  return out
}

// ---- Ordering (saved at once) ----
// Put `key` at position `pos` among the steps in use; steps not in use keep
// their place in the stored order.
function placed(base: string[], key: string, pos: number): string[] {
  const rest = base.filter((k) => k !== key)
  const liveRest = rest.filter((k) => k === key || inLine(k))
  const at = pos < liveRest.length ? rest.indexOf(liveRest[pos]!) : liveRest.length ? rest.indexOf(liveRest.at(-1)!) + 1 : rest.length
  rest.splice(at, 0, key)
  return rest
}
async function commit(next: string[]) {
  order.value = next
  await saveFlowOrder(next)
  emit('reload')
}
function move(key: string, delta: number) {
  const i = live.value.indexOf(key)
  if (i + delta < 0 || i + delta >= live.value.length) return
  run(() => commit(placed(order.value, key, i + delta)), t('flowUi.orderSaved'))
}
function moveTo(key: string, pos: number) {
  run(() => commit(placed(order.value, key, pos)), t('flowUi.orderSaved'))
}

// ---- Taking out (or back in, in place), putting in, deleting ----
function setOn(key: string, on: boolean) {
  run(async () => {
    await updatePromptModule(key, { enabled: on })
    emit('reload')
  }, t(on ? 'flowUi.putIn' : 'flowUi.takenOut', { name: props.nameOf(key) }))
}

// The gap a step is being put into: before live[slot] (live.length = at the end).
const slot = ref<number | null>(null)
function openSlot(i: number) {
  slot.value = slot.value === i ? null : i
}
function putIn(key: string, pos: number) {
  run(async () => {
    // Order first: the step is still off, so the position counts the others.
    await saveFlowOrder((order.value = placed(order.value, key, pos)))
    await updatePromptModule(key, { enabled: true })
    slot.value = null
    emit('reload')
  }, t('flowUi.putIn', { name: props.nameOf(key) }))
}
const confirmingDelete = ref<string | null>(null)
function remove(key: string) {
  if (confirmingDelete.value !== key) {
    confirmingDelete.value = key
    return
  }
  const name = props.nameOf(key)
  run(async () => {
    await deletePromptModule(key)
    confirmingDelete.value = null
    await forgetStep(key)
    emit('reload')
  }, t('comp.deleted', { name }))
}

// ---- Warnings: orders that work but probably aren't meant ----
const warnings = computed(() => {
  const pos = (k: string) => live.value.indexOf(k)
  const out: string[] = []
  if (live.value.length && live.value[0] !== 'flow.listen' && pos('flow.listen') > 0) out.push(t('flowOrder.warn.listenFirst'))
  if (pos('flow.self_kindness') >= 0 && pos('flow.self_check') > pos('flow.self_kindness'))
    out.push(t('flowOrder.warn.checkBeforeKindness'))
  if (pos('flow.act') >= 0 && pos('flow.explore') > pos('flow.act')) out.push(t('flowOrder.warn.actBeforeExplore'))
  if (!live.value.length) out.push(t('flowOrder.warn.noneOn'))
  return out
})

// ---- Program rules (saved with the save bar) ----
const KEYWORD_LISTS: KeywordList[] = ['crisis', 'watch', 'self_criticism']
const CARD_TYPES = ['seb_summary', 'plan_form'] as const
const newWord = ref<Record<KeywordList, string>>({ crisis: '', watch: '', self_criticism: '' })
const ruleSteps = computed(() => live.value.filter((k) => k !== PURPOSE))
const clampPct = (v: number, low = 0) => Math.max(low, Math.min(100, Math.round(v) || 0))
function addWord(list: KeywordList) {
  const c = config.value
  const words = newWord.value[list].split(/[,，、\n]/).map((w) => w.trim()).filter(Boolean)
  if (!c || !words.length) return
  c.keywords[list] = [...new Set([...c.keywords[list], ...words.map((w) => w.slice(0, 40))])]
  newWord.value[list] = ''
}
function resetWords(list: KeywordList) {
  if (config.value && defaults.value) config.value.keywords[list] = [...defaults.value.keywords[list]]
}
function setWeak(which: 0 | 1, value: number) {
  const l = config.value?.weak_kindness
  if (!l) return
  l[which] = Math.max(1, Math.min(50, Math.round(value) || 1))
  if (l[0] > l[1]) l[which === 0 ? 1 : 0] = l[which]
}
function saveRules() {
  run(save, t('flowOrder.saved'))
}

// Puts the rules back to defaults as an unsaved change: nothing is lost
// until the admin presses save (and "undo" still brings it back).
function resetRules() {
  resetToDefaults()
  done(t('flowUi.resetDraft'))
}
</script>

<template>
  <section class="flow">
    <header class="intro">
      <h2>{{ t('flowUi.title') }}</h2>
      <p>{{ t('flowUi.desc') }}</p>
    </header>

    <ol class="line">
      <li class="node start">
        <span class="dot">▶</span>
        <span class="node-text">{{ t('flowUi.start') }}</span>
      </li>

      <!-- Every step in its stored place; ones taken out stay visible, greyed. -->
      <template v-for="key in lineKeys" :key="key">
        <li v-if="inLine(key)" class="gap">
          <button type="button" class="gap-btn" :class="{ open: slot === liveIndex[key]! }" :aria-label="t('flowUi.insertHere')" @click="openSlot(liveIndex[key]!)">
            ＋<span class="gap-label">{{ t('flowUi.insertHere') }}</span>
          </button>
          <div v-if="slot === liveIndex[key]!" class="picker">
            <template v-if="unused.length">
              <div class="picker-title">{{ t('flowUi.pickUnused') }}</div>
              <div class="chips">
                <button v-for="k in unused" :key="k" type="button" class="chip-btn" :disabled="busy" @click="putIn(k, liveIndex[key]!)">
                  {{ nameOf(k) }}
                </button>
              </div>
            </template>
            <p v-else class="what">{{ t('flowUi.noneToInsert') }}</p>
            <button type="button" class="btn-text small to-lib" @click="emit('components')">{{ t('flowUi.makeNew') }}</button>
          </div>
        </li>

        <li class="step" :class="{ off: !enabled(key) }">
          <span class="num">{{ enabled(key) ? liveIndex[key]! + 1 : '–' }}</span>
          <div class="step-card">
            <div class="step-head">
              <h3>{{ nameOf(key) }}</h3>
              <span v-if="!enabled(key)" class="tag">{{ t('flowUi.outBadge') }}</span>
              <span v-if="isSafety(key)" class="tag safety">🛡 {{ t('flowUi.safetyStep') }}</span>
              <span v-if="custom(key)" class="tag accent">{{ t('flowOrder.customBadge') }}</span>
              <span v-for="a in addons(key)" :key="a" class="tag addon">{{ a }}</span>
              <span v-if="triggered(key)" class="tag addon">{{ t(`comp.role.${roleOfKey(key)}`) }}</span>
            </div>
            <p class="what">{{ enabled(key) ? endsText(key) : t('flowUi.outHint') }}</p>
            <p v-if="triggered(key)" class="what">{{ t('flowUi.triggeredHint', { when: t(`flowUi.roleWhen.${roleOfKey(key)}`) }) }}</p>
            <p v-if="isSafety(key)" class="warn">⚠️ {{ t('comp.safetyGeneric') }}</p>
            <p v-if="enabled(key) && emptyKeys.includes(key)" class="warn">⚠️ {{ t('comp.noPrompt') }}</p>

            <div v-if="confirmingDelete === key" class="confirm">
              <span>{{ t('comp.deleteConfirm', { name: nameOf(key) }) }}</span>
              <button type="button" class="btn-text small" @click="confirmingDelete = null">{{ t('prompts.cancel') }}</button>
              <button type="button" class="btn-danger small" :disabled="busy" @click="remove(key)">{{ t('prompts.removeYes') }}</button>
            </div>
            <div v-else-if="enabled(key)" class="step-actions">
              <button type="button" class="icon-btn" :disabled="busy || liveIndex[key] === 0" :aria-label="t('flowOrder.up', { name: nameOf(key) })" @click="move(key, -1)">↑</button>
              <button type="button" class="icon-btn" :disabled="busy || liveIndex[key] === live.length - 1" :aria-label="t('flowOrder.down', { name: nameOf(key) })" @click="move(key, 1)">↓</button>
              <select class="pos" :value="liveIndex[key]" :disabled="busy" :aria-label="t('flowOrder.moveTo', { name: nameOf(key) })" @change="moveTo(key, Number(($event.target as HTMLSelectElement).value))">
                <option v-for="(_, n) in live" :key="n" :value="n">{{ t('flowOrder.position', { n: n + 1 }) }}</option>
              </select>
              <span class="spacer" />
              <button type="button" class="btn-text small" @click="emit('edit', key)">{{ t('comp.editPrompt') }}</button>
              <button type="button" class="btn-outline small" :disabled="busy" @click="setOn(key, false)">{{ t('flowUi.takeOut') }}</button>
              <button v-if="triggered(key)" type="button" class="btn-outline small" :disabled="phone" @click="clearRole(key)">{{ t('flowUi.toLine') }}</button>
              <button type="button" class="btn-text small danger" @click="remove(key)">{{ t('comp.delete') }}</button>
            </div>
            <div v-else class="step-actions">
              <span class="spacer" />
              <button type="button" class="btn-text small" @click="emit('edit', key)">{{ t('comp.editPrompt') }}</button>
              <button type="button" class="btn-outline small" :disabled="busy" @click="setOn(key, true)">{{ t('flowUi.putBackHere') }}</button>
              <button type="button" class="btn-text small danger" @click="remove(key)">{{ t('comp.delete') }}</button>
            </div>
          </div>
        </li>
      </template>

      <!-- Gap at the end -->
      <li class="gap">
        <button type="button" class="gap-btn" :class="{ open: slot === live.length }" :aria-label="t('flowUi.insertHere')" @click="openSlot(live.length)">
          ＋<span class="gap-label">{{ t('flowUi.insertHere') }}</span>
        </button>
        <div v-if="slot === live.length" class="picker">
          <template v-if="unused.length">
            <div class="picker-title">{{ t('flowUi.pickUnused') }}</div>
            <div class="chips">
              <button v-for="k in unused" :key="k" type="button" class="chip-btn" :disabled="busy" @click="putIn(k, live.length)">
                {{ nameOf(k) }}
              </button>
            </div>
          </template>
          <p v-else class="what">{{ t('flowUi.noneToInsert') }}</p>
          <button type="button" class="btn-text small to-lib" @click="emit('components')">{{ t('flowUi.makeNew') }}</button>
        </div>
      </li>

    </ol>

    <p v-if="flash" class="flash" role="status">{{ flash }}</p>
    <p v-if="error" class="error">{{ error }}</p>
    <ul v-if="warnings.length" class="warnings" role="status">
      <li v-for="w in warnings" :key="w">⚠️ {{ w }}</li>
    </ul>

    <!-- Steps used when something happens, chosen by the admins. -->
    <section v-if="config" class="special">
      <h3>{{ t('flowUi.specialTitle') }}</h3>
      <p class="what">{{ t('flowUi.roleDesc') }}</p>
      <div v-for="r in TRIGGER_ROLES" :key="r" class="special-item" :class="{ off: !config[r] || !enabled(config[r]!) }">
        <label class="rule">
          <strong>{{ t(`flowUi.roleWhen.${r}`) }}</strong>
          <select v-model="config[r]" :disabled="phone">
            <option :value="null">{{ t(`flowUi.roleNone.${r}`) }}</option>
            <option
              v-for="k in order"
              :key="k"
              :value="k"
              :disabled="[...TRIGGER_ROLES, 'closing_step' as const].some((o) => o !== r && config![o] === k)"
            >
              {{ nameOf(k) }}
            </option>
          </select>
        </label>
        <p v-if="!config[r]" class="warn">⚠️ {{ t(`flowUi.roleOffWarn.${r}`) }}</p>
      </div>
      <p v-if="dirty" class="what">{{ t('flowUi.roleUnsaved') }}</p>
    </section>

    <!-- Program rules, folded -->
    <details v-if="config" class="fold">
      <summary>{{ t('flowUi.advanced') }}<span class="fold-hint">{{ t('flowUi.advancedHint') }}</span></summary>
      <div class="fold-body">
        <div class="group">
          <div class="group-title">{{ t('flowOrder.rules.cards.title') }}</div>
          <p class="what">{{ t('flowOrder.rules.cards.hint') }}</p>
          <label v-for="c in CARD_TYPES" :key="c" class="rule">
            {{ t(`flowOrder.rules.cards.${c}`) }}
            <select v-model="config.card_steps[c]" :disabled="phone">
              <option :value="null">{{ t('flowOrder.rules.never') }}</option>
              <option
                v-for="k in ruleSteps"
                :key="k"
                :value="k"
                :disabled="CARD_TYPES.some((o) => o !== c && config!.card_steps[o] === k)"
              >
                {{ nameOf(k) }}
              </option>
            </select>
          </label>
          <label class="rule">
            {{ t('flowOrder.rules.summaryMin') }}
            <input type="number" min="1" max="20" :disabled="phone" :value="config.summary_min_turns" @change="config.summary_min_turns = Math.max(1, Math.min(20, Math.round(Number(($event.target as HTMLInputElement).value)) || 3))" />
            {{ t('flowOrder.rules.summaryUnit') }}
          </label>
        </div>
        <div class="group">
          <div class="group-title">{{ t('flowOrder.rules.requests.title') }}</div>
          <label class="rule">
            {{ t('flowOrder.rules.requests.toAction') }}
            <select v-model="config.to_action_step" :disabled="phone">
              <option :value="null">{{ t('flowOrder.rules.requests.ignore') }}</option>
              <option v-for="k in ruleSteps" :key="k" :value="k">{{ t('flowUi.goTo', { name: nameOf(k) }) }}</option>
            </select>
          </label>
          <label class="rule">
            {{ t('flowUi.closingStep') }}
            <select v-model="config.closing_step" :disabled="phone">
              <option :value="null">{{ t('flowUi.closingNone') }}</option>
              <option
                v-for="k in lineKeys"
                :key="k"
                :value="k"
              >
                {{ nameOf(k) }}
              </option>
            </select>
          </label>
          <label v-if="config.closing_step" class="rule">
            <input v-model="config.end_today_enabled" type="checkbox" class="check" :disabled="phone" />
            {{ t('flowOrder.rules.requests.endToday', { name: nameOf(config.closing_step) }) }}
          </label>
        </div>
        <div class="group">
          <div class="group-title">{{ t('flowUi.other') }}</div>
          <label class="rule">
            {{ t('flowOrder.history.label') }}
            <input type="number" min="2" max="60" :disabled="phone" :value="config.history_turns" @change="config.history_turns = Math.max(2, Math.min(60, Math.round(Number(($event.target as HTMLInputElement).value)) || 12))" />
            {{ t('flowOrder.history.unit') }}
          </label>
          <p class="what">{{ t('flowOrder.history.hint') }}</p>
          <div class="rule">
            {{ t('flowOrder.rules.weakKindness', { name: nameOf('flow.self_kindness') }) }}
            <label>{{ t('flowOrder.minTurns') }}<input type="number" min="1" max="50" :disabled="phone" :value="config.weak_kindness[0]" @change="setWeak(0, Number(($event.target as HTMLInputElement).value))" /></label>
            <label>{{ t('flowOrder.maxTurns') }}<input type="number" min="1" max="50" :disabled="phone" :value="config.weak_kindness[1]" @change="setWeak(1, Number(($event.target as HTMLInputElement).value))" /></label>
          </div>
        </div>
      </div>
    </details>

    <!-- Safety, folded -->
    <details v-if="config" class="fold">
      <summary>{{ t('flowUi.safety') }}<span class="fold-hint">{{ t('flowUi.safetyHint') }}</span></summary>
      <div class="fold-body">
        <div v-for="list in KEYWORD_LISTS" :key="list" class="group">
          <div class="group-title">{{ t(`flowOrder.rules.words.${list}.title`) }}</div>
          <p class="what">{{ t(`flowOrder.rules.words.${list}.hint`) }}</p>
          <div class="chips">
            <span v-for="(w, wi) in config.keywords[list]" :key="w" class="word">
              {{ w }}
              <button v-if="!phone" type="button" :aria-label="t('flowOrder.rules.removeWord', { word: w })" @click="config.keywords[list].splice(wi, 1)">✕</button>
            </span>
            <span v-if="!config.keywords[list].length" class="what">{{ t('flowOrder.rules.noWords') }}</span>
          </div>
          <form v-if="!phone" class="word-add" @submit.prevent="addWord(list)">
            <input v-model="newWord[list]" :placeholder="t('flowOrder.rules.addPlaceholder')" />
            <button type="submit" class="btn-text small" :disabled="!newWord[list].trim()">{{ t('flowOrder.rules.addWord') }}</button>
            <button type="button" class="btn-text small" @click="resetWords(list)">{{ t('flowOrder.rules.resetWords') }}</button>
          </form>
        </div>
        <div class="group">
          <div class="group-title">{{ t('flowOrder.rules.crisisReply') }}</div>
          <p class="what">{{ t('flowOrder.rules.crisisReplyHint') }}</p>
          <textarea v-model="config.crisis_reply.zh" rows="3" maxlength="1000" :disabled="phone" :placeholder="t('flowUi.zhText')" />
          <textarea v-model="config.crisis_reply.ko" rows="3" maxlength="1000" :disabled="phone" :placeholder="t('flowUi.koText')" />
          <label class="rule">
            {{ t('flowOrder.rules.crisisCountry') }}
            <input v-model="config.crisis_country" class="wide" maxlength="8" placeholder="KR" :disabled="phone" />
            <span class="what">{{ t('flowOrder.rules.crisisCountryHint') }}</span>
          </label>
        </div>
        <div class="group">
          <div class="group-title">{{ t('flowOrder.rules.criticism.title') }}</div>
          <p class="what">{{ t('flowOrder.rules.criticism.hint') }}</p>
          <div class="rule">
            <label v-for="k in ['up', 'down', 'strong'] as const" :key="k">
              {{ t(`flowOrder.rules.criticism.${k}`) }}
              <input type="number" :min="k === 'strong' ? 1 : 0" max="100" :disabled="phone" :value="config.criticism[k]" @change="config.criticism[k] = clampPct(Number(($event.target as HTMLInputElement).value), k === 'strong' ? 1 : 0)" />
            </label>
          </div>
        </div>
        <CrisisResourcesEditor />
      </div>
    </details>

    <div class="foot">
      <button type="button" class="btn-text" @click="resetRules">{{ t('flowUi.reset') }}</button>
    </div>

    <div v-if="dirty" class="unsaved" role="status">
      <span>{{ t('flowOrder.unsaved') }}</span>
      <button type="button" class="btn-text" :disabled="busy" @click="discard">{{ t('flowOrder.discard') }}</button>
      <button type="button" class="btn-primary" :disabled="busy" @click="saveRules">{{ t('flowOrder.save') }}</button>
    </div>
  </section>
</template>

<style scoped>
.flow {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.intro h2 {
  margin: 0 0 4px;
  font-size: 17px;
}
.intro p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text-muted);
}
h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}
.what {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}

/* ---- The line of steps ---- */
.line {
  position: relative;
  margin: 0;
  padding: 0;
  list-style: none;
}
/* The vertical line through the numbers. */
.line::before {
  content: '';
  position: absolute;
  top: 14px;
  bottom: 40px;
  left: 15px;
  width: 2px;
  background: var(--border);
}
.node,
.step {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 14px;
}
.node.start {
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}
.dot,
.num {
  z-index: 1;
  display: grid;
  flex-shrink: 0;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  font-size: 14px;
  font-weight: 700;
}
.dot {
  background: var(--bg);
  border: 2px solid var(--border);
  font-size: 11px;
  color: var(--text-muted);
}
.num {
  margin-top: 12px;
  background: var(--accent);
  color: #fff;
  box-shadow: 0 0 0 4px var(--surface);
}
.step.off .num {
  background: var(--border);
  color: var(--text-muted);
}
.step.off .step-card,
.special-item.off {
  background: var(--bg);
  box-shadow: none;
  border-style: dashed;
}
.step.off h3,
.special-item.off h3 {
  color: var(--text-muted);
}
.tag.safety {
  border-color: #f0c98a;
  background: #fff7e8;
  color: #9a5b00;
}
.special {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid #f0c98a;
  border-radius: var(--radius-lg);
}
.special-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}
.step-card {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}
.step-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.tag {
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg);
  font-size: 11.5px;
  color: var(--text-muted);
}
.tag.accent {
  border-color: transparent;
  background: var(--accent-soft);
  color: var(--accent);
}
.tag.addon {
  border-color: var(--accent);
  background: var(--surface);
  color: var(--accent);
}
.warn {
  margin: 0;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  background: #fff4e0;
  color: #a15c00;
  font-size: 12.5px;
}
.step-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
.spacer {
  flex: 1;
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
.pos {
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
  font-size: 12.5px;
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

/* ---- Gaps between steps ---- */
.gap {
  position: relative;
  padding: 6px 0 6px 46px;
}
.gap-btn {
  position: absolute;
  top: 50%;
  left: 5px;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  width: 22px;
  height: 22px;
  padding: 0;
  transform: translateY(-50%);
  border: 1px dashed var(--accent);
  border-radius: 50%;
  background: var(--surface);
  color: var(--accent);
  font-size: 14px;
  line-height: 1;
  justify-content: center;
  cursor: pointer;
}
.gap:has(.picker) .gap-btn {
  top: 18px;
}
.gap-label {
  position: absolute;
  left: 32px;
  white-space: nowrap;
  font-size: 12.5px;
  opacity: 0;
  transition: opacity 0.15s;
}
.gap-btn:hover .gap-label,
.gap-btn:focus-visible .gap-label,
.gap-btn.open .gap-label {
  opacity: 1;
}
.gap-btn.open {
  border-style: solid;
  background: var(--accent);
  color: #fff;
}
.gap-btn.open .gap-label {
  color: var(--accent);
}
.gap:not(:has(.picker)) {
  min-height: 22px;
}
.picker {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 26px 0 4px;
  padding: 12px 14px;
  border: 1px solid var(--accent);
  border-radius: var(--radius-md);
  background: var(--accent-soft);
}
.picker-title {
  font-size: 12.5px;
  font-weight: 700;
}
.to-lib {
  align-self: flex-start;
  padding: 0;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip-btn {
  padding: 6px 12px;
  border: 1px solid var(--accent);
  border-radius: 999px;
  background: var(--surface);
  color: var(--accent);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}

/* ---- Below the line ---- */
.aside {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-muted);
}
.fold {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
}
.fold summary {
  padding: 14px 16px;
  font-size: 14.5px;
  font-weight: 700;
  cursor: pointer;
}
.fold-hint {
  display: block;
  margin-top: 2px;
  font-size: 12.5px;
  font-weight: 400;
  color: var(--text-muted);
}
.fold-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 0 16px 16px;
}
.group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}
.group-title {
  font-size: 13.5px;
  font-weight: 700;
}
.rule {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
}
.rule input,
.rule select {
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
}
.rule input[type='number'] {
  width: 56px;
}
.rule input.check {
  width: auto;
  margin: 0;
}
.word {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 4px 2px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
}
.word button {
  border: 0;
  background: none;
  color: var(--text-muted);
  cursor: pointer;
}
.word-add {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.word-add input {
  flex: 1;
  min-width: 160px;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
}
.group textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
  resize: vertical;
}
.warnings {
  margin: 0;
  padding: 10px 14px;
  border: 1px solid var(--danger-border);
  border-radius: var(--radius-md);
  background: var(--danger-soft);
  font-size: 13px;
  line-height: 1.7;
  list-style: none;
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
.foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.danger-text {
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
