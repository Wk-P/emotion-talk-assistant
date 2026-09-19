<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { deleteRecord, listRecords, type SavedRecord } from '@/api/client'
import { useSessionStore } from '@/stores/session'

const { t } = useI18n()
const router = useRouter()
const session = useSessionStore()
const records = ref<SavedRecord[]>([])

async function load() {
  if (!session.sessionId) return
  records.value = await listRecords(session.sessionId)
}

async function remove(id: string) {
  await deleteRecord(id)
  await load()
}

onMounted(load)
</script>

<template>
  <div class="records-view">
    <div class="page-inner-wide">
      <header class="header">
        <button type="button" class="btn-back" @click="router.push('/chat')"><span class="arrow">&lt;</span> {{ t('records.back') }}</button>
      </header>

      <h1 class="page-title">{{ t('records.title') }}</h1>

      <p v-if="records.length === 0" class="empty">{{ t('records.empty') }}</p>

      <div v-for="record in records" :key="record.id" class="record">
        <div class="type">{{ record.record_type }}</div>
        <pre class="payload">{{ JSON.stringify(record.payload, null, 2) }}</pre>
        <div class="meta">
          <span>{{ new Date(record.created_at).toLocaleString() }}</span>
          <button type="button" class="btn-danger" @click="remove(record.id)">{{ t('records.delete') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.records-view {
  padding: 16px;
}
@media (min-width: 640px) {
  .records-view {
    padding: 32px;
  }
}
.header {
  margin-bottom: 14px;
}
.page-title {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 20px;
}
.empty {
  color: var(--text-muted);
  font-size: 14px;
}
.record {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  margin-bottom: 10px;
}
.type {
  font-weight: 600;
  font-size: 13px;
  color: var(--accent);
}
.payload {
  font-size: 12px;
  background: var(--bg);
  padding: 8px;
  border-radius: var(--radius-sm);
  overflow-x: auto;
  margin: 8px 0;
}
.meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--text-muted);
}
.meta .btn-danger {
  padding: 4px 8px;
  font-size: 12px;
}
</style>
