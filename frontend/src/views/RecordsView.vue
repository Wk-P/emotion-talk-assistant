<script setup lang="ts">
import SiteFooter from '@/components/SiteFooter.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { deleteRecord, listMyRecords, type OwnRecord } from '@/api/client'
import { fieldLabel, fieldText, recordTypeLabel } from '@/utils/fieldLabels'
import { formatDate, formatDateTime } from '@/utils/time'

const { t, te } = useI18n()
const records = ref<OwnRecord[]>([])
const loaded = ref(false)
// '' = all types
const typeFilter = ref('')

const typesPresent = computed(() => [...new Set(records.value.map((r) => r.record_type))])
const shown = computed(() =>
  typeFilter.value ? records.value.filter((r) => r.record_type === typeFilter.value) : records.value,
)
const confirmingDelete = ref<string | null>(null)

// Each payload field as a labelled line; a lone `text` field (a saved
// sentence) is shown as the sentence itself, without a label.
function recordLines(record: OwnRecord) {
  return Object.entries(record.payload)
    .map(([key, value]) => ({ key, label: fieldLabel(t, te, key), text: fieldText(value) }))
    .filter((line) => line.text)
}

async function load() {
  try {
    records.value = await listMyRecords()
  } finally {
    loaded.value = true
  }
  if (typeFilter.value && !typesPresent.value.includes(typeFilter.value)) typeFilter.value = ''
}

async function remove(id: string) {
  confirmingDelete.value = null
  await deleteRecord(id)
  await load()
}

onMounted(load)
</script>

<template>
  <div class="records-view">
    <SiteHeader />
    <main class="page-body">
    <div class="page-full">

      <h1 class="page-title">{{ t('records.title') }}</h1>

      <p v-if="loaded && records.length === 0" class="empty">{{ t('records.emptyHint') }}</p>

      <div v-if="typesPresent.length > 1" class="type-chips" role="radiogroup">
        <button
          type="button"
          role="radio"
          class="chip"
          :class="{ on: typeFilter === '' }"
          :aria-checked="typeFilter === ''"
          @click="typeFilter = ''"
        >
          {{ t('records.all') }} · {{ records.length }}
        </button>
        <button
          v-for="type in typesPresent"
          :key="type"
          type="button"
          role="radio"
          class="chip"
          :class="{ on: typeFilter === type }"
          :aria-checked="typeFilter === type"
          @click="typeFilter = type"
        >
          {{ recordTypeLabel(t, te, type) }} · {{ records.filter((r) => r.record_type === type).length }}
        </button>
      </div>

      <div class="record-grid">
      <div v-for="record in shown" :key="record.id" class="record">
        <div class="type">{{ recordTypeLabel(t, te, record.record_type) }}</div>
        <dl class="lines">
          <template v-for="line in recordLines(record)" :key="line.key">
            <p v-if="line.key === 'text' && recordLines(record).length === 1" class="quote">{{ line.text }}</p>
            <div v-else class="line">
              <dt>{{ line.label }}</dt>
              <dd>{{ line.text }}</dd>
            </div>
          </template>
        </dl>
        <div class="meta">
          <span :title="formatDateTime(record.created_at)">
            {{ t('records.fromConversation', { date: formatDate(record.session_created_at) }) }}
          </span>
          <div v-if="confirmingDelete === record.id" class="confirm">
            <span>{{ t('records.deleteConfirm') }}</span>
            <button type="button" class="btn-danger" @click="remove(record.id)">{{ t('records.deleteYes') }}</button>
            <button type="button" class="btn-outline" @click="confirmingDelete = null">{{ t('records.deleteNo') }}</button>
          </div>
          <button v-else type="button" class="btn-text delete" @click="confirmingDelete = record.id">
            {{ t('records.delete') }}
          </button>
        </div>
      </div>
      </div>
    </div>
  </main>
    <SiteFooter />
  </div>
</template>

<style scoped>
.page-title {
  margin-bottom: 20px;
}
.empty {
  color: var(--text-muted);
  font-size: 14px;
}
.page-full {
  width: 100%;
}
/* Cards flow into as many columns as the screen fits. */
.type-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}
.chip {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 12.5px;
}
.chip.on {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
.record-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
  align-items: start;
}
.record {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
  background: var(--surface);
}
.type {
  font-weight: 600;
  font-size: 13px;
  color: var(--accent);
}
.lines {
  flex: 1;
  margin: 10px 0 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.line dt {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 2px;
}
.line dd {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
}
.quote {
  margin: 0;
  padding: 10px 14px;
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-size: 15px;
  line-height: 1.6;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
  font-size: 12px;
  color: var(--text-muted);
}
.meta .delete {
  color: var(--danger);
  font-size: 12.5px;
}
.confirm {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}
.confirm button {
  padding: 4px 10px;
  font-size: 12px;
}
</style>
