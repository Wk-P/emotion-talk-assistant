<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { listAdminReflections, type AdminReflection } from '@/api/client'

// 每日省察 answers for research review (backend GET /api/admin/reflections).
// Participants are shown by account ID.
const { t } = useI18n()
const QUESTIONS = ['helpful', 'changed', 'improve'] as const

const items = ref<AdminReflection[]>([])
const loading = ref(true)
const filter = reactive({ participant: '', dayFrom: '', dayTo: '' })
const filtered = computed(() => Boolean(filter.participant.trim() || filter.dayFrom || filter.dayTo))

async function load() {
  loading.value = true
  try {
    items.value = await listAdminReflections({
      participant: filter.participant.trim() || undefined,
      day_from: filter.dayFrom || undefined,
      day_to: filter.dayTo || undefined,
    })
  } finally {
    loading.value = false
  }
}

let timer: ReturnType<typeof setTimeout> | undefined
watch(filter, () => {
  clearTimeout(timer)
  timer = setTimeout(load, 300)
})

function reset() {
  Object.assign(filter, { participant: '', dayFrom: '', dayTo: '' })
}

function download(content: string, type: string, ext: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = `emotion-ai-reflections-${new Date().toISOString().slice(0, 10)}.${ext}`
  a.click()
  URL.revokeObjectURL(url)
}

// CSV opens straight in Excel: BOM so Chinese/Korean aren't garbled.
function exportCsv() {
  const cell = (v: string) => `"${v.replace(/"/g, '""')}"`
  const header = [t('admin.reflections.colParticipant'), t('admin.reflections.colDay'), t('admin.reflections.colLang')]
    .concat(QUESTIONS.map((q) => t(`reflection.q.${q}.title`)))
    .map(cell)
    .join(',')
  const rows = items.value.map((r) =>
    [r.participant_label, r.day, r.language, ...QUESTIONS.map((q) => r.answers[q])].map(cell).join(','),
  )
  download('﻿' + [header, ...rows].join('\r\n'), 'text/csv;charset=utf-8', 'csv')
}

function exportJson() {
  download(JSON.stringify(items.value, null, 2), 'application/json', 'json')
}

onMounted(load)
</script>

<template>
  <div class="admin-reflections">
    <p class="intro">{{ t('admin.reflections.intro') }}</p>

    <div class="filters">
      <label class="filter-field grow">
        <span>{{ t('admin.filter.participant') }}</span>
        <input v-model="filter.participant" type="search" :placeholder="t('admin.filter.participantPlaceholder')" />
      </label>
      <label class="filter-field">
        <span>{{ t('admin.filter.dateFrom') }}</span>
        <input v-model="filter.dayFrom" type="date" :max="filter.dayTo || undefined" />
      </label>
      <label class="filter-field">
        <span>{{ t('admin.filter.dateTo') }}</span>
        <input v-model="filter.dayTo" type="date" :min="filter.dayFrom || undefined" />
      </label>
      <button v-if="filtered" type="button" class="btn-text" @click="reset">{{ t('admin.filter.reset') }}</button>
      <div class="exports">
        <span class="count">{{ t('admin.reflections.count', { n: items.length }) }}</span>
        <button type="button" class="btn-outline" :disabled="items.length === 0" @click="exportCsv">
          {{ t('admin.reflections.exportCsv') }}
        </button>
        <button type="button" class="btn-outline" :disabled="items.length === 0" @click="exportJson">JSON</button>
      </div>
    </div>

    <p v-if="!loading && items.length === 0" class="empty">
      {{ filtered ? t('admin.filter.noMatch') : t('admin.reflections.empty') }}
    </p>

    <div class="grid">
      <article v-for="r in items" :key="r.id" class="card">
        <header class="card-head">
          <span class="participant">{{ r.participant_label }}</span>
          <span class="day">{{ r.day }}</span>
          <span class="lang">{{ r.language === 'ko' ? '한국어' : '中文' }}</span>
        </header>
        <dl>
          <div v-for="q in QUESTIONS" :key="q" class="answer">
            <dt>{{ t(`reflection.q.${q}.title`) }}</dt>
            <dd :class="{ blank: !r.answers[q] }">{{ r.answers[q] || t('admin.reflections.blank') }}</dd>
          </div>
        </dl>
      </article>
    </div>
  </div>
</template>

<style scoped>
.intro {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}
.filters {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px 12px;
  padding: 12px 14px;
  margin-bottom: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}
.filter-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 140px;
  font-size: 12px;
  color: var(--text-muted);
}
.filter-field.grow {
  flex: 1 1 200px;
}
.filter-field input {
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  font-size: 13px;
}
.exports {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}
.exports .btn-outline {
  padding: 7px 14px;
  font-size: 13px;
}
.count {
  font-size: 12.5px;
  color: var(--text-muted);
}
.empty {
  color: var(--text-muted);
  font-size: 14px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px;
  align-items: start;
}
.card {
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}
.card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 13px;
}
.participant {
  font-family: ui-monospace, monospace;
  font-weight: 700;
  color: var(--accent);
}
.day {
  font-weight: 600;
}
.lang {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-muted);
}
dl {
  margin: 0;
}
.answer + .answer {
  margin-top: 10px;
}
dt {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}
dd {
  margin: 2px 0 0;
  font-size: 13.5px;
  line-height: 1.65;
  white-space: pre-wrap;
}
dd.blank {
  color: var(--text-muted);
}
</style>
