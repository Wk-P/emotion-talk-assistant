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
    <header class="header">
      <button type="button" @click="router.push('/chat')">← {{ t('records.back') }}</button>
      <h1>{{ t('records.title') }}</h1>
    </header>

    <p v-if="records.length === 0" class="empty">{{ t('records.empty') }}</p>

    <div v-for="record in records" :key="record.id" class="record">
      <div class="type">{{ record.record_type }}</div>
      <pre class="payload">{{ JSON.stringify(record.payload, null, 2) }}</pre>
      <div class="meta">
        <span>{{ new Date(record.created_at).toLocaleString() }}</span>
        <button type="button" @click="remove(record.id)">{{ t('records.delete') }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.records-view {
  max-width: 480px;
  margin: 0 auto;
  padding: 16px;
}
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.header button {
  border: none;
  background: none;
  color: #6c5ce7;
}
.empty {
  color: #888;
}
.record {
  border: 1px solid #eee;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 10px;
}
.type {
  font-weight: 600;
  font-size: 13px;
  color: #6c5ce7;
}
.payload {
  font-size: 12px;
  background: #f7f6fb;
  padding: 8px;
  border-radius: 6px;
  overflow-x: auto;
}
.meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: #888;
}
.meta button {
  border: 1px solid #e0a0a0;
  color: #c0392b;
  background: #fff;
  border-radius: 6px;
  padding: 4px 8px;
}
</style>
