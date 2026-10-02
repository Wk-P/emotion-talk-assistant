<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { errorStatus, getModelOverview, setModel, type ModelOverview } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

// Which OpenAI model answers every conversation. Candidates are the chat
// models OpenAI released in the last ~3 months, each test-called by the
// server. Any admin can switch.
const { t } = useI18n()
const auth = useAuthStore()
// The admin page is admin-only already, so every viewer here can switch.
const canChange = computed(() => auth.user?.role === 'admin' || auth.user?.role === 'superadmin')

const overview = ref<ModelOverview | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const saving = ref<string | null>(null)
const error = ref('')
const flash = ref('')

// The model in use is always listed, even if it's older than 3 months.
const rows = computed(() => {
  const o = overview.value
  if (!o) return []
  const list = o.candidates.map((c) => ({ ...c, older: false }))
  if (!list.some((c) => c.id === o.current)) {
    list.push({ id: o.current, released: '', usable: true, error: null, older: true })
  }
  return list
})

async function load(refresh = false) {
  error.value = ''
  try {
    overview.value = await getModelOverview(refresh)
  } catch {
    error.value = t('model.loadFailed')
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

async function choose(id: string | null) {
  saving.value = id ?? 'default'
  error.value = ''
  try {
    overview.value = await setModel(id)
    flash.value = t('model.switched', { model: overview.value.current })
    setTimeout(() => (flash.value = ''), 4000)
  } catch (e) {
    error.value = errorStatus(e) === 422 ? t('model.notUsable') : t('model.saveFailed')
  } finally {
    saving.value = null
  }
}

function refresh() {
  refreshing.value = true
  load(true)
}

onMounted(() => load())
</script>

<template>
  <section class="model-picker">
    <div class="head">
      <div>
        <h2>{{ t('model.title') }}</h2>
        <p class="desc">{{ t('model.desc', { days: overview?.recent_days ?? 92 }) }}</p>
      </div>
      <button type="button" class="btn-outline refresh" :disabled="refreshing || loading" @click="refresh">
        {{ refreshing ? t('model.checking') : t('model.refresh') }}
      </button>
    </div>

    <p v-if="loading" class="muted">{{ t('model.checking') }}</p>
    <template v-else-if="overview">
      <p class="current">
        {{ t('model.current') }}
        <strong>{{ overview.current }}</strong>
        <span class="muted">
          ·
          {{
            overview.chosen_here
              ? t('model.chosenBy', { who: overview.updated_by ?? '—' })
              : t('model.usingDefault')
          }}
        </span>
      </p>

      <div class="grid">
        <div
          v-for="m in rows"
          :key="m.id"
          class="model"
          :class="{ current: m.id === overview.current, unusable: !m.usable }"
        >
          <div class="model-id">{{ m.id }}</div>
          <div class="model-meta">
            <span v-if="m.released">{{ t('model.released', { date: m.released }) }}</span>
            <span v-else>{{ t('model.olderModel') }}</span>
            <span v-if="m.usable" class="ok">✓ {{ t('model.usable') }}</span>
            <span v-else class="bad">✕ {{ t('model.unusable') }}{{ m.error ? `（${m.error}）` : '' }}</span>
          </div>
          <span v-if="m.id === overview.current" class="badge">{{ t('model.inUse') }}</span>
          <button
            v-else-if="canChange && m.usable"
            type="button"
            class="btn-outline use"
            :disabled="saving !== null"
            @click="choose(m.id)"
          >
            {{ saving === m.id ? t('model.switching') : t('model.use') }}
          </button>
        </div>
      </div>

      <div class="foot">
        <button
          v-if="canChange && overview.chosen_here"
          type="button"
          class="btn-text"
          :disabled="saving !== null"
          @click="choose(null)"
        >
          {{ t('model.resetDefault', { model: overview.default }) }}
        </button>
        <span class="muted">{{ t('model.checkedAt', { time: new Date(overview.checked_at).toLocaleString() }) }}</span>
        <span v-if="flash" class="flash">{{ flash }}</span>
      </div>
    </template>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<style scoped>
.model-picker {
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
.desc {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}
.refresh {
  padding: 7px 14px;
  font-size: 13px;
}
.current {
  margin: 14px 0 12px;
  font-size: 14px;
}
.current strong {
  font-family: ui-monospace, monospace;
  color: var(--accent);
}
.muted {
  font-size: 12.5px;
  color: var(--text-muted);
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
}
.model {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}
.model.current {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.model.unusable {
  opacity: 0.6;
}
.model-id {
  font-family: ui-monospace, monospace;
  font-size: 14px;
  font-weight: 700;
}
.model-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 12px;
  color: var(--text-muted);
}
.ok {
  color: #1c8a4a;
}
.bad {
  color: var(--danger);
}
.badge {
  align-self: flex-start;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--accent);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.use {
  align-self: flex-start;
  padding: 5px 14px;
  font-size: 12.5px;
}
.foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 16px;
  margin-top: 12px;
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
