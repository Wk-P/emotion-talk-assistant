<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  getAiParams,
  recommendAiParams,
  setAiParams,
  type AiParamName,
  type AiParamsOverview,
  type AiParamValues,
} from '@/api/client'

// The numbers sent with every chat call (backend app/services/ai_params.py):
// how many recent messages the AI sees, sampling, answer length, timeout.
// Optional ones can be left unset so the model's own default applies.
// "AI 推荐" asks the model in use to fill in values with a reason each;
// nothing changes until the admin saves.
const { t, locale } = useI18n()

const GROUPS: { key: string; fields: AiParamName[] }[] = [
  { key: 'memory', fields: ['history_turns'] },
  { key: 'style', fields: ['temperature', 'top_p', 'presence_penalty', 'frequency_penalty'] },
  { key: 'length', fields: ['max_tokens'] },
  { key: 'connection', fields: ['timeout_seconds', 'max_retries'] },
]

const overview = ref<AiParamsOverview | null>(null)
const draft = ref<AiParamValues | null>(null)
const reasons = ref<Partial<Record<AiParamName, string>>>({})
const loading = ref(true)
const saving = ref(false)
const recommending = ref(false)
const error = ref('')
const flash = ref('')

const dirty = computed(
  () => !!overview.value && !!draft.value && JSON.stringify(overview.value.values) !== JSON.stringify(draft.value),
)

function show(msg: string) {
  flash.value = msg
  setTimeout(() => (flash.value = ''), 5000)
}

async function load() {
  try {
    overview.value = await getAiParams()
    draft.value = { ...overview.value.values }
  } catch {
    error.value = t('advanced.loadFailed')
  } finally {
    loading.value = false
  }
}

function step(name: AiParamName) {
  const r = overview.value!.ranges[name]
  return r.integer ? 1 : 0.05
}

// Fit a typed value to the field's range; empty input keeps the old value.
function setValue(name: AiParamName, raw: string) {
  const r = overview.value!.ranges[name]
  const n = Number(raw)
  if (raw.trim() === '' || Number.isNaN(n)) return
  const v = Math.min(r.max, Math.max(r.min, n))
  draft.value![name] = r.integer ? Math.round(v) : Math.round(v * 100) / 100
}

// Where an optional field starts when switched on: OpenAI's own defaults.
const START: Partial<Record<AiParamName, number>> = {
  temperature: 1,
  top_p: 1,
  max_tokens: 4000,
  presence_penalty: 0,
  frequency_penalty: 0,
}

function toggleSet(name: AiParamName, on: boolean) {
  draft.value![name] = on ? (overview.value!.defaults[name] ?? START[name] ?? overview.value!.ranges[name].min) : null
}

async function recommend() {
  recommending.value = true
  error.value = ''
  try {
    const rec = await recommendAiParams(locale.value)
    draft.value = { ...rec.values }
    reasons.value = rec.reasons
    show(rec.from_ai ? t('advanced.recommended') : t('advanced.recommendFallback'))
  } catch {
    error.value = t('advanced.recommendFallback')
  } finally {
    recommending.value = false
  }
}

async function save() {
  if (!draft.value) return
  saving.value = true
  error.value = ''
  try {
    overview.value = await setAiParams(draft.value)
    draft.value = { ...overview.value.values }
    show(t('advanced.saved'))
  } catch {
    error.value = t('advanced.saveFailed')
  } finally {
    saving.value = false
  }
}

function undo() {
  draft.value = { ...overview.value!.values }
  reasons.value = {}
}

function resetAll() {
  draft.value = { ...overview.value!.defaults }
  reasons.value = {}
}

onMounted(load)
</script>

<template>
  <section class="advanced">
    <div class="head">
      <div>
        <h2>{{ t('advanced.title') }}</h2>
        <p class="desc">{{ t('advanced.desc') }}</p>
        <p v-if="overview" class="muted">
          {{
            t('advanced.current', {
              model: overview.model,
              effort: overview.effort ? t(`model.effort.${overview.effort}`) : t('advanced.effortDefault'),
            })
          }}
        </p>
      </div>
      <button type="button" class="btn-primary" :disabled="loading || recommending || saving" @click="recommend">
        {{ recommending ? t('advanced.recommending') : t('advanced.recommend') }}
      </button>
    </div>

    <p v-if="loading" class="muted">…</p>
    <template v-else-if="overview && draft">
      <div v-for="g in GROUPS" :key="g.key" class="group">
        <h3>{{ t(`advanced.groups.${g.key}`) }}</h3>
        <div v-for="name in g.fields" :key="name" class="field" :class="{ changed: draft[name] !== overview.values[name] }">
          <div class="row">
            <span class="label">{{ t(`advanced.fields.${name}.label`) }}</span>
            <template v-if="overview.ranges[name].required || draft[name] !== null">
              <input
                type="range"
                :min="overview.ranges[name].min"
                :max="overview.ranges[name].max"
                :step="step(name)"
                :value="draft[name]"
                @input="setValue(name, ($event.target as HTMLInputElement).value)"
              />
              <input
                type="number"
                class="num"
                :min="overview.ranges[name].min"
                :max="overview.ranges[name].max"
                :step="step(name)"
                :value="draft[name]"
                @change="setValue(name, ($event.target as HTMLInputElement).value)"
              />
              <span class="unit">{{ t(`advanced.fields.${name}.unit`) }}</span>
            </template>
            <span v-else class="muted">{{ t('advanced.notSent') }}</span>
            <label v-if="!overview.ranges[name].required" class="toggle">
              <input
                type="checkbox"
                :checked="draft[name] !== null"
                @change="toggleSet(name, ($event.target as HTMLInputElement).checked)"
              />
              {{ t('advanced.setIt') }}
            </label>
          </div>
          <p class="hint">
            {{ t(`advanced.fields.${name}.hint`) }}
            <span class="muted">
              ·
              {{
                t('advanced.defaultIs', {
                  value: overview.defaults[name] ?? t('advanced.notSent'),
                })
              }}
              · {{ overview.ranges[name].min }}–{{ overview.ranges[name].max }}
            </span>
          </p>
          <p v-if="reasons[name]" class="reason">{{ t('advanced.reason') }}{{ reasons[name] }}</p>
        </div>
      </div>

      <div class="foot">
        <button type="button" class="btn-primary" :disabled="!dirty || saving" @click="save">
          {{ saving ? t('advanced.saving') : t('advanced.save') }}
        </button>
        <button type="button" class="btn-text" :disabled="!dirty || saving" @click="undo">{{ t('advanced.undo') }}</button>
        <button type="button" class="btn-text" :disabled="saving" @click="resetAll">{{ t('advanced.resetAll') }}</button>
        <span v-if="flash" class="flash">{{ flash }}</span>
      </div>
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<style scoped>
.advanced {
  margin-bottom: 28px;
  padding: 20px 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
}
.head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
h2 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
}
h3 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 700;
}
.desc {
  margin: 0 0 4px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}
.muted {
  font-size: 12.5px;
  color: var(--text-muted);
}
.group {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
}
.field {
  padding: 10px 12px;
  margin-bottom: 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}
.field.changed {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}
.label {
  min-width: 180px;
  font-size: 14px;
  font-weight: 600;
}
input[type='range'] {
  flex: 1 1 160px;
  max-width: 280px;
}
.num {
  width: 80px;
  padding: 4px 6px;
}
.unit {
  font-size: 13px;
  color: var(--text-muted);
}
.toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  font-size: 12.5px;
}
.hint {
  margin: 6px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
}
.reason {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--accent);
}
.foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  margin-top: 16px;
}
.flash {
  font-size: 13px;
  font-weight: 600;
  color: #1c8a4a;
}
.error {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--danger);
}
</style>
