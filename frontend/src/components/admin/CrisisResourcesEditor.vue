<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  deleteCrisisResource,
  listCrisisResources,
  saveCrisisResource,
  type CrisisResourceInput,
  type CrisisResourceItem,
} from '@/api/client'

// The verified contacts shown with a crisis reply and on the help screen
// (backend app/api/resources.py). Admins add, edit and remove them here; the
// AI never writes contact details itself.
const { t } = useI18n()

const items = ref<CrisisResourceItem[]>([])
const error = ref('')
const busy = ref(false)
// id of the row being edited, 'new' for a new one, null for none.
const editing = ref<string | null>(null)
const form = ref<CrisisResourceInput>(blank())

function blank(): CrisisResourceInput {
  return {
    country: 'KR',
    category: 'other',
    name: { zh: '', ko: '' },
    description: { zh: '', ko: '' },
    contact: '',
    url: '',
    verified_at: new Date().toISOString().slice(0, 10),
  }
}

async function load() {
  try {
    items.value = await listCrisisResources()
  } catch {
    error.value = t('crisisResources.failed')
  }
}
onMounted(load)

function edit(item?: CrisisResourceItem) {
  error.value = ''
  editing.value = item?.id ?? 'new'
  form.value = item
    ? {
        country: item.country,
        category: item.category,
        name: { zh: '', ko: '', ...item.name },
        description: { zh: '', ko: '', ...item.description },
        contact: item.contact,
        url: item.url ?? '',
        verified_at: item.verified_at.slice(0, 10),
      }
    : blank()
}

async function save() {
  const f = form.value
  if (!f.contact.trim() || !Object.values(f.name).some((v) => v?.trim())) {
    error.value = t('crisisResources.needNameContact')
    return
  }
  busy.value = true
  error.value = ''
  try {
    await saveCrisisResource(f, editing.value === 'new' ? undefined : editing.value!)
    editing.value = null
    await load()
  } catch {
    error.value = t('crisisResources.failed')
  } finally {
    busy.value = false
  }
}

// Two-step delete instead of a browser confirm dialog.
const confirmingDelete = ref<string | null>(null)
async function remove(id: string) {
  if (confirmingDelete.value !== id) {
    confirmingDelete.value = id
    return
  }
  busy.value = true
  try {
    await deleteCrisisResource(id)
    confirmingDelete.value = null
    await load()
  } catch {
    error.value = t('crisisResources.failed')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="resources">
    <h2>{{ t('crisisResources.title') }}</h2>
    <p class="desc">{{ t('crisisResources.desc') }}</p>

    <ul class="list">
      <li v-for="r in items" :key="r.id" class="row">
        <div class="body">
          <div class="name">
            {{ r.name.zh || r.name.ko }}<span v-if="r.name.zh && r.name.ko"> / {{ r.name.ko }}</span>
            <span class="badge">{{ r.country }}</span>
          </div>
          <div class="meta">{{ r.contact }}<span v-if="r.url"> · {{ r.url }}</span></div>
          <div class="meta">{{ t('crisisResources.verifiedAt', { date: r.verified_at.slice(0, 10) }) }}</div>
        </div>
        <div class="actions">
          <button type="button" class="btn-text small" @click="edit(r)">{{ t('crisisResources.edit') }}</button>
          <button type="button" class="btn-text small danger" :disabled="busy" @click="remove(r.id)">
            {{ confirmingDelete === r.id ? t('crisisResources.confirmDelete') : t('crisisResources.delete') }}
          </button>
        </div>
      </li>
      <li v-if="!items.length" class="meta">{{ t('crisisResources.empty') }}</li>
    </ul>

    <form v-if="editing" class="form" @submit.prevent="save">
      <label>{{ t('crisisResources.nameZh') }}<input v-model="form.name.zh" maxlength="100" /></label>
      <label>{{ t('crisisResources.nameKo') }}<input v-model="form.name.ko" maxlength="100" /></label>
      <label>{{ t('crisisResources.descZh') }}<textarea v-model="form.description.zh" rows="2" maxlength="500" /></label>
      <label>{{ t('crisisResources.descKo') }}<textarea v-model="form.description.ko" rows="2" maxlength="500" /></label>
      <label>{{ t('crisisResources.contact') }}<input v-model="form.contact" maxlength="200" /></label>
      <label>{{ t('crisisResources.url') }}<input v-model="form.url" maxlength="500" placeholder="https://" /></label>
      <div class="two">
        <label>{{ t('crisisResources.country') }}<input v-model="form.country" maxlength="8" /></label>
        <label>{{ t('crisisResources.verified') }}<input v-model="form.verified_at" type="date" /></label>
      </div>
      <p class="meta">{{ t('crisisResources.verifyNote') }}</p>
      <div class="foot">
        <button type="button" class="btn-text" @click="editing = null">{{ t('prompts.cancel') }}</button>
        <button type="submit" class="btn-primary" :disabled="busy">{{ t('crisisResources.save') }}</button>
      </div>
    </form>
    <button v-else type="button" class="btn-outline" @click="edit()">{{ t('crisisResources.add') }}</button>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<style scoped>
.resources {
  margin-bottom: 20px;
  padding: 20px 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
}
h2 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
}
.desc,
.meta {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-muted);
}
.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 12px 0;
  padding: 0;
  list-style: none;
}
.row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}
.body {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.name {
  font-size: 13.5px;
  font-weight: 600;
}
.badge {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--accent-soft);
  font-size: 11px;
  font-weight: 500;
}
.actions {
  display: flex;
  gap: 4px;
}
.danger {
  color: var(--danger, #c0392b);
}
.form {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}
.form label {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.form input,
.form textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font: inherit;
}
.two {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.two label {
  flex: 1;
  min-width: 140px;
}
.foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.error {
  color: var(--danger, #c0392b);
  font-size: 13px;
}
</style>
