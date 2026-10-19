<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { listAdminRecords, type AdminUserRecord } from '@/api/client'
import { fieldLabel, fieldText, recordTypeLabel } from '@/utils/fieldLabels'
import { displayDay, formatDateTime } from '@/utils/time'

// Everything participants saved to "我的记录" (backend GET /api/admin/records),
// shown by account ID, as the reflections page.
const { t, te } = useI18n()

const items = ref<AdminUserRecord[]>([])
const loading = ref(true)
const filter = reactive({ participant: '', type: '', dayFrom: '', dayTo: '' })
const filtered = computed(() => Boolean(filter.participant.trim() || filter.type || filter.dayFrom || filter.dayTo))
// Types offered in the filter: what exists, plus the one picked.
const types = ref<string[]>([])

async function load() {
  loading.value = true
  try {
    items.value = await listAdminRecords({
      participant: filter.participant.trim() || undefined,
      record_type: filter.type || undefined,
      day_from: filter.dayFrom || undefined,
      day_to: filter.dayTo || undefined,
    })
    if (!filtered.value) types.value = [...new Set(items.value.map((r) => r.record_type))]
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
  Object.assign(filter, { participant: '', type: '', dayFrom: '', dayTo: '' })
}

// Same lines as the participant's own "我的记录" page: a conversation card
// always shows its three parts, an empty one as "空".
const CARD_FIELDS = ['summary', 'plan', 'kindness']
function lines(r: AdminUserRecord) {
  if (r.record_type === 'conversation_summary')
    return CARD_FIELDS.map((key) => ({ key, label: fieldLabel(t, te, key), text: fieldText(r.payload[key]) || t('chat.card.empty') }))
  return Object.entries(r.payload)
    .map(([key, value]) => ({ key, label: fieldLabel(t, te, key), text: fieldText(value) }))
    .filter((l) => l.text)
}

function download(content: string, type: string, ext: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const a = document.createElement('a')
  a.href = url
  a.download = `emotion-ai-records-${displayDay()}.${ext}`
  a.click()
  URL.revokeObjectURL(url)
}

// CSV opens straight in Excel: BOM so Chinese/Korean aren't garbled.
function exportCsv() {
  const cell = (v: string) => `"${v.replace(/"/g, '""')}"`
  const header = ['colParticipant', 'colTime', 'colType', 'colContent'].map((k) => cell(t(`admin.records.${k}`))).join(',')
  const rows = items.value.map((r) =>
    [
      r.participant_label || t('admin.records.noParticipant'),
      formatDateTime(r.created_at),
      recordTypeLabel(t, te, r.record_type),
      lines(r).map((l) => `${l.label}：${l.text}`).join('\n'),
    ]
      .map(cell)
      .join(','),
  )
  download('﻿' + [header, ...rows].join('\r\n'), 'text/csv;charset=utf-8', 'csv')
}

function exportJson() {
  download(JSON.stringify(items.value, null, 2), 'application/json', 'json')
}

onMounted(load)
</script>

<template>
  <div class="admin-records">
    <p class="intro">{{ t('admin.records.intro') }}</p>

    <div class="filters">
      <label class="filter-field grow">
        <span>{{ t('admin.filter.participant') }}</span>
        <input v-model="filter.participant" type="search" :placeholder="t('admin.filter.participantPlaceholder')" />
      </label>
      <label class="filter-field">
        <span>{{ t('admin.records.type') }}</span>
        <select v-model="filter.type">
          <option value="">{{ t('admin.records.allTypes') }}</option>
          <option v-for="ty in types" :key="ty" :value="ty">{{ recordTypeLabel(t, te, ty) }}</option>
        </select>
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
        <span class="count">{{ t('admin.records.count', { n: items.length }) }}</span>
        <button type="button" class="btn-outline" :disabled="items.length === 0" @click="exportCsv">
          {{ t('admin.records.exportCsv') }}
        </button>
        <button type="button" class="btn-outline" :disabled="items.length === 0" @click="exportJson">JSON</button>
      </div>
    </div>

    <p v-if="!loading && items.length === 0" class="empty">
      {{ filtered ? t('admin.filter.noMatch') : t('admin.records.empty') }}
    </p>

    <div class="grid">
      <article v-for="r in items" :key="r.id" class="card">
        <header class="card-head">
          <span class="participant">{{ r.participant_label || t('admin.records.noParticipant') }}</span>
          <span class="type">{{ recordTypeLabel(t, te, r.record_type) }}</span>
          <span class="time">{{ formatDateTime(r.created_at) }}</span>
        </header>
        <dl>
          <div v-for="l in lines(r)" :key="l.key" class="line">
            <dt>{{ l.label }}</dt>
            <dd>{{ l.text }}</dd>
          </div>
        </dl>
        <p v-if="r.session_deleted" class="deleted">{{ t('admin.records.sessionDeleted') }}</p>
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
.filter-field input,
.filter-field select {
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
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}
.card-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 10px;
  margin-bottom: 10px;
  font-size: 13px;
}
.participant {
  font-family: ui-monospace, monospace;
  font-weight: 700;
  color: var(--accent);
  overflow-wrap: anywhere;
}
.type {
  font-weight: 600;
}
.time {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-muted);
}
dl {
  margin: 0;
}
.line + .line {
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
  overflow-wrap: anywhere;
}
.deleted {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--text-muted);
}
@media (max-width: 480px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
