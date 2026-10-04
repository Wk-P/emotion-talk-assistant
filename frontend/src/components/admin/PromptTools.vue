<script setup lang="ts">
// Whole-prompt checks for admins (backend app/api/prompt_tools.py): a
// contradiction check, and saved test conversations rerun after an edit,
// shown next to the previous run.
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  checkPromptConflicts,
  errorStatus,
  fetchTestScripts,
  runTestTurn,
  saveTestScripts,
  type Language,
  type PromptConflict,
  type RunMessage,
  type RunState,
  type TestScript,
} from '@/api/client'

const { t, te } = useI18n()

// ---- contradiction check ----
const checkLang = ref<Language>('zh')
const checking = ref(false)
const conflicts = ref<PromptConflict[] | null>(null)
const checkError = ref('')

async function runCheck() {
  checking.value = true
  checkError.value = ''
  conflicts.value = null
  try {
    conflicts.value = await checkPromptConflicts(checkLang.value)
  } catch (e) {
    checkError.value = errorStatus(e) === 503 ? t('tools.aiUnavailable') : t('tools.failed')
  } finally {
    checking.value = false
  }
}

// ---- test conversations ----
interface RunLine {
  user: string
  reply: string
  stage: string | null
  cards: string[]
}
const scripts = ref<TestScript[]>([])
const selectedId = ref('')
const editing = ref(false)
const editText = ref('')
const editName = ref('')
const running = ref(false)
const runError = ref('')
const current = ref<RunLine[]>([])
const previous = ref<RunLine[]>([])

const selected = computed(() => scripts.value.find((s) => s.id === selectedId.value) ?? null)
const LAST_RUN_KEY = 'emotion-talk-test-run'

function stageName(key: string | null) {
  if (!key) return ''
  const k = `prompts.keys.flow.${key.replace('flow.', '')}.name`
  return te(k) ? t(k) : key
}

function loadPrevious() {
  try {
    previous.value = JSON.parse(localStorage.getItem(`${LAST_RUN_KEY}.${selectedId.value}`) ?? '[]')
  } catch {
    previous.value = []
  }
  current.value = []
}

function select(id: string) {
  selectedId.value = id
  editing.value = false
  loadPrevious()
}

onMounted(async () => {
  try {
    scripts.value = await fetchTestScripts()
    if (scripts.value[0]) select(scripts.value[0].id)
  } catch {
    runError.value = t('tools.failed')
  }
})

function startEdit() {
  if (!selected.value) return
  editName.value = selected.value.name
  editText.value = selected.value.lines.join('\n')
  editing.value = true
}

function addScript() {
  const s: TestScript = { id: `s${Date.now()}`, name: t('tools.newScript'), language: 'zh', lines: [] }
  scripts.value = [...scripts.value, s]
  select(s.id)
  startEdit()
}

async function persist(next: TestScript[]) {
  try {
    scripts.value = await saveTestScripts(next)
  } catch {
    runError.value = t('tools.failed')
  }
}

async function saveEdit() {
  const lines = editText.value.split('\n').map((l) => l.trim()).filter(Boolean)
  if (!selected.value || !lines.length || !editName.value.trim()) return
  await persist(scripts.value.map((s) => (s.id === selectedId.value ? { ...s, name: editName.value.trim(), lines } : s)))
  editing.value = false
}

async function removeScript() {
  if (!selected.value || !confirm(t('tools.removeConfirm'))) return
  await persist(scripts.value.filter((s) => s.id !== selectedId.value))
  if (scripts.value[0]) select(scripts.value[0].id)
}

async function runScript() {
  const s = selected.value
  if (!s || running.value) return
  running.value = true
  runError.value = ''
  // What was on screen becomes "last time" once a new run starts.
  if (current.value.length) previous.value = current.value
  current.value = []
  const history: RunMessage[] = []
  let state: RunState | undefined
  try {
    for (const line of s.lines) {
      const r = await runTestTurn({ language: s.language, message: line, history, state })
      current.value.push({ user: line, reply: r.reply_text, stage: r.stage, cards: r.candidates.map((c) => c.type) })
      history.push({ role: 'user', content: line }, { role: 'assistant', content: r.reply_text, meta: { candidates: r.candidates } })
      state = r.state
    }
    try {
      localStorage.setItem(`${LAST_RUN_KEY}.${s.id}`, JSON.stringify(current.value))
    } catch {
      // storage unavailable — the comparison just won't survive a reload
    }
  } catch (e) {
    runError.value = errorStatus(e) === 503 ? t('tools.aiUnavailable') : t('tools.failed')
  } finally {
    running.value = false
  }
}
</script>

<template>
  <section class="tools panel">
    <h2 class="panel-title">{{ t('tools.title') }}</h2>
    <p class="panel-desc">{{ t('tools.desc') }}</p>

    <div class="tool">
      <h3>{{ t('tools.checkTitle') }}</h3>
      <p class="hint">{{ t('tools.checkDesc') }}</p>
      <div class="row">
        <select v-model="checkLang">
          <option value="zh">中文</option>
          <option value="ko">한국어</option>
        </select>
        <button type="button" class="btn-primary" :disabled="checking" @click="runCheck">
          {{ checking ? t('tools.checking') : t('tools.check') }}
        </button>
      </div>
      <p v-if="checkError" class="error">{{ checkError }}</p>
      <p v-else-if="conflicts && !conflicts.length" class="ok">{{ t('tools.noConflicts') }}</p>
      <ol v-else-if="conflicts" class="conflicts">
        <li v-for="(c, i) in conflicts" :key="i">
          <div class="where">{{ c.where }}</div>
          <div>{{ c.problem }}</div>
          <div v-if="c.suggestion" class="suggest">{{ t('tools.suggestion') }}{{ c.suggestion }}</div>
        </li>
      </ol>
    </div>

    <div class="tool">
      <h3>{{ t('tools.runTitle') }}</h3>
      <p class="hint">{{ t('tools.runDesc') }}</p>
      <div class="chips">
        <button
          v-for="s in scripts"
          :key="s.id"
          type="button"
          class="chip"
          :class="{ on: s.id === selectedId }"
          @click="select(s.id)"
        >
          {{ s.name }}
        </button>
        <button type="button" class="chip add" @click="addScript">{{ t('tools.addScript') }}</button>
      </div>

      <template v-if="selected">
        <div v-if="editing" class="edit">
          <input v-model="editName" maxlength="60" :placeholder="t('tools.namePlaceholder')" />
          <select v-model="selected.language">
            <option value="zh">中文</option>
            <option value="ko">한국어</option>
          </select>
          <textarea v-model="editText" rows="8" :placeholder="t('tools.linesPlaceholder')" />
          <div class="row">
            <button type="button" class="btn-text danger" @click="removeScript">{{ t('tools.remove') }}</button>
            <button type="button" class="btn-outline" @click="editing = false">{{ t('tools.cancel') }}</button>
            <button type="button" class="btn-primary" @click="saveEdit">{{ t('tools.save') }}</button>
          </div>
        </div>
        <div v-else class="row">
          <span class="hint">{{ t('tools.lineCount', { n: selected.lines.length }) }}</span>
          <button type="button" class="btn-outline" :disabled="running" @click="startEdit">{{ t('tools.edit') }}</button>
          <button type="button" class="btn-primary" :disabled="running || !selected.lines.length" @click="runScript">
            {{ running ? t('tools.running', { done: current.length, all: selected.lines.length }) : t('tools.run') }}
          </button>
        </div>
      </template>
      <p v-if="runError" class="error">{{ runError }}</p>

      <div v-if="current.length || previous.length" class="compare">
        <div v-for="(col, ci) in [current, previous]" :key="ci" class="col">
          <h4>{{ ci === 0 ? t('tools.thisRun') : t('tools.lastRun') }}</h4>
          <p v-if="!col.length" class="hint">{{ t('tools.noRun') }}</p>
          <div v-for="(l, i) in col" :key="i" class="turn">
            <div class="u">{{ l.user }}</div>
            <div class="a">
              <span class="stage">{{ stageName(l.stage) }}</span>
              {{ l.reply }}
              <span v-for="c in l.cards" :key="c" class="card-tag">{{ t('tools.card') }} {{ c }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
}
.panel-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 4px;
}
.panel-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
}
.tools {
  margin-top: 20px;
}
.tool {
  border-top: 1px solid var(--border);
  padding-top: 16px;
  margin-top: 16px;
}
.tool h3 {
  font-size: 15px;
  margin: 0 0 4px;
}
.hint {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 10px;
}
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.row select,
.edit input,
.edit select,
.edit textarea {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font: inherit;
  font-size: 14px;
}
.error {
  color: var(--danger);
  font-size: 13px;
}
.ok {
  color: #1c8a4a;
  font-size: 14px;
}
.conflicts {
  margin: 12px 0 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  font-size: 14px;
  line-height: 1.6;
}
.where {
  font-weight: 700;
}
.suggest {
  color: var(--text-muted);
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}
.chip {
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--surface);
  font-size: 13px;
  cursor: pointer;
}
.chip.on {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
}
.chip.add {
  border-style: dashed;
  color: var(--text-muted);
}
.edit {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.edit .row {
  justify-content: flex-end;
}
.danger {
  color: var(--danger);
  margin-right: auto;
}
.compare {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  margin-top: 14px;
}
@media (min-width: 900px) {
  .compare {
    grid-template-columns: 1fr 1fr;
  }
}
.col h4 {
  margin: 0 0 8px;
  font-size: 14px;
}
.turn {
  margin-bottom: 10px;
  font-size: 13.5px;
  line-height: 1.6;
}
.u {
  background: var(--bg);
  border-radius: 12px;
  padding: 6px 10px;
  margin-bottom: 4px;
}
.a {
  padding: 0 4px;
}
.stage,
.card-tag {
  display: inline-block;
  font-size: 11.5px;
  padding: 1px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  margin-right: 6px;
}
.card-tag {
  margin: 0 0 0 6px;
  background: var(--bg);
  color: var(--text-muted);
}
</style>
