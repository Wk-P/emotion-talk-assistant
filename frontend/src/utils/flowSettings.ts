import { computed, ref } from 'vue'
import { getFlowConfig, saveFlowConfig, type FlowConfig } from '@/api/client'

// The flow settings (backend app/services/flow_config.py), shared by the
// "对话组件" and "对话流程" admin pages so an unsaved change on one page is
// still there, and saved together, when the admin switches to the other.

const savedConfig = ref<FlowConfig | null>(null)
const defaults = ref<FlowConfig | null>(null)
const config = ref<FlowConfig | null>(null)
const clone = (c: FlowConfig): FlowConfig => JSON.parse(JSON.stringify(c))

const dirty = computed(
  () => !!config.value && !!savedConfig.value && JSON.stringify(config.value) !== JSON.stringify(savedConfig.value),
)

function take(data: FlowConfig & { defaults: FlowConfig }) {
  const { defaults: d, ...current } = data
  defaults.value = d
  savedConfig.value = current
  config.value = clone(current)
}

let loading: Promise<void> | null = null
function load(force = false): Promise<void> {
  if (config.value && !force) return Promise.resolve()
  loading ??= getFlowConfig()
    .then(take)
    .finally(() => (loading = null))
  return loading
}

async function save() {
  if (!config.value) return
  take(await saveFlowConfig(config.value))
}

function discard() {
  if (savedConfig.value) config.value = clone(savedConfig.value)
}

function resetToDefaults() {
  if (defaults.value) config.value = clone(defaults.value)
}

/** After a step is deleted: drop every setting that pointed at it, so the
 * next save isn't refused. Saves at once when something changed. */
async function forgetStep(key: string) {
  for (const c of [config.value, savedConfig.value]) {
    if (!c) continue
    delete c.limits[key]
    if (c.to_action_step === key) c.to_action_step = null
    for (const r of ['closing_step', 'stabilize_step', 'ending_step'] as const) if (c[r] === key) c[r] = null
    c.safety_steps = c.safety_steps.filter((k) => k !== key)
  }
  // Store the saved settings without it; unsaved edits stay unsaved.
  if (!savedConfig.value) return
  const draft = config.value
  try {
    take(await saveFlowConfig(savedConfig.value))
  } finally {
    if (draft) config.value = draft
  }
}

export function useFlowSettings() {
  return { config, defaults, dirty, load, save, discard, resetToDefaults, forgetStep }
}
