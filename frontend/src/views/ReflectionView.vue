<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  deleteReflection,
  listMyReflections,
  saveReflection,
  type Language,
  type Reflection,
  type ReflectionAnswers,
} from '@/api/client'
import SiteFooter from '@/components/SiteFooter.vue'
import { chatLangFor } from '@/i18n/langPreference'
import SiteHeader from '@/components/SiteHeader.vue'
import { displayDay } from '@/utils/time'

// 每日省察 — the daily usage reflection questionnaire
// (documents/02_内容与需求/每日省察功能.md). One per day; today's can be edited.
const { t, te, locale } = useI18n()

const QUESTIONS = ['helpful', 'changed', 'improve'] as const

const today = displayDay()

const entries = ref<Reflection[]>([])
const loaded = ref(false)
const form = reactive<ReflectionAnswers>({ helpful: '', changed: '', improve: '' })
const saving = ref(false)
const saved = ref(false)
const error = ref('')
const confirmingDelete = ref<string | null>(null)

const todayEntry = computed(() => entries.value.find((e) => e.day === today) ?? null)
const pastEntries = computed(() => entries.value.filter((e) => e.day !== today))
const canSave = computed(() => QUESTIONS.some((q) => form[q].trim()))

async function load() {
  try {
    entries.value = await listMyReflections()
  } finally {
    loaded.value = true
  }
  if (todayEntry.value) Object.assign(form, todayEntry.value.answers)
}

async function submit() {
  if (!canSave.value || saving.value) return
  saving.value = true
  error.value = ''
  try {
    const lang: Language = chatLangFor(locale.value)
    const entry = await saveReflection(today, lang, { ...form })
    entries.value = [entry, ...entries.value.filter((e) => e.day !== today)]
    saved.value = true
    setTimeout(() => (saved.value = false), 3000)
  } catch {
    error.value = t('reflection.saveFailed')
  } finally {
    saving.value = false
  }
}

async function remove(id: string) {
  confirmingDelete.value = null
  await deleteReflection(id)
  entries.value = entries.value.filter((e) => e.id !== id)
  if (!todayEntry.value) Object.assign(form, { helpful: '', changed: '', improve: '' })
}

onMounted(load)
</script>

<template>
  <div class="reflection-view">
    <SiteHeader />
    <main class="page-body">
      <h1 class="page-title">{{ t('reflection.title') }}</h1>
      <p class="lead">{{ t('reflection.lead') }}</p>

      <div class="reflection-layout">
        <form class="today" @submit.prevent="submit">
          <div class="today-head">
            <h2>{{ t('reflection.today', { date: today }) }}</h2>
            <span v-if="todayEntry" class="badge">{{ t('reflection.alreadySaved') }}</span>
          </div>

          <div v-for="(q, i) in QUESTIONS" :key="q" class="question">
            <label :for="`q-${q}`">
              <span class="q-no">{{ i + 1 }}</span>
              <span class="q-title">{{ t(`reflection.q.${q}.title`) }}</span>
            </label>
            <p class="q-desc">{{ t(`reflection.q.${q}.desc`) }}</p>
            <p v-if="te(`reflection.q.${q}.example`)" class="q-example">{{ t(`reflection.q.${q}.example`) }}</p>
            <textarea :id="`q-${q}`" v-model="form[q]" rows="4" maxlength="4000" :placeholder="t('reflection.placeholder')" />
          </div>

          <p class="privacy-note">{{ t('reflection.privacyNote') }}</p>
          <div class="actions">
            <button type="submit" class="btn-primary" :disabled="!canSave || saving">
              {{ saving ? t('reflection.saving') : todayEntry ? t('reflection.update') : t('reflection.submit') }}
            </button>
            <span v-if="saved" class="saved" role="status">✓ {{ t('reflection.saved') }}</span>
            <span v-if="error" class="error">{{ error }}</span>
          </div>
        </form>

        <section class="history">
          <h2>{{ t('reflection.history') }}</h2>
          <p v-if="loaded && pastEntries.length === 0" class="empty">{{ t('reflection.historyEmpty') }}</p>
          <article v-for="e in pastEntries" :key="e.id" class="entry">
            <div class="entry-head">
              <span class="entry-day">{{ e.day }}</span>
              <template v-if="confirmingDelete === e.id">
                <span class="confirm-text">{{ t('records.deleteConfirm') }}</span>
                <button type="button" class="btn-danger small" @click="remove(e.id)">{{ t('records.deleteYes') }}</button>
                <button type="button" class="btn-outline small" @click="confirmingDelete = null">
                  {{ t('records.deleteNo') }}
                </button>
              </template>
              <button v-else type="button" class="btn-text delete" @click="confirmingDelete = e.id">
                {{ t('records.delete') }}
              </button>
            </div>
            <dl>
              <template v-for="q in QUESTIONS" :key="q">
                <div v-if="e.answers[q]" class="answer">
                  <dt>{{ t(`reflection.q.${q}.title`) }}</dt>
                  <dd>{{ e.answers[q] }}</dd>
                </div>
              </template>
            </dl>
          </article>
        </section>
      </div>
    </main>
    <SiteFooter />
  </div>
</template>

<style scoped>
.lead {
  margin: 8px 0 24px;
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--text-muted);
}
h2 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
}
/* Wide: today's questionnaire on the left, past entries on the right. */
.reflection-layout {
  display: grid;
  gap: 28px;
}
@media (min-width: 1024px) {
  .reflection-layout {
    grid-template-columns: minmax(0, 1.6fr) minmax(320px, 1fr);
    align-items: start;
  }
  .history {
    position: sticky;
    top: calc(var(--site-header-h) + 24px);
    max-height: calc(100dvh - var(--site-header-h) - 48px);
    overflow-y: auto;
  }
}
.today {
  padding: 20px 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}
.today-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.badge {
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12px;
  font-weight: 600;
}
.question {
  padding: 16px 0;
  border-bottom: 1px solid var(--border);
}
.question label {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
}
.q-no {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-size: 13px;
  line-height: 24px;
  text-align: center;
}
.q-desc {
  margin: 6px 0 4px 34px;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--text);
}
.q-example {
  margin: 0 0 10px 34px;
  padding: 8px 12px;
  border-left: 3px solid var(--border);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--text-muted);
  white-space: pre-line;
}
.question textarea {
  display: block;
  width: calc(100% - 34px);
  margin-left: 34px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 14px;
  line-height: 1.6;
  resize: vertical;
}
.privacy-note {
  margin: 14px 0 12px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-muted);
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.actions .btn-primary {
  padding: 11px 22px;
}
.saved {
  font-size: 13px;
  font-weight: 600;
  color: #1c8a4a;
}
.error {
  font-size: 13px;
  color: var(--danger);
}
.history h2 {
  margin-bottom: 12px;
}
.empty {
  font-size: 13.5px;
  color: var(--text-muted);
}
.entry {
  padding: 14px 16px;
  margin-bottom: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}
.entry-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.entry-day {
  flex: 1;
  font-weight: 700;
  font-size: 14px;
}
.confirm-text {
  font-size: 12px;
  color: var(--text-muted);
}
.small {
  padding: 4px 10px;
  font-size: 12px;
}
.delete {
  color: var(--danger);
  font-size: 12.5px;
}
dl {
  margin: 0;
}
.answer + .answer {
  margin-top: 8px;
}
.answer dt {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}
.answer dd {
  margin: 2px 0 0;
  font-size: 13.5px;
  line-height: 1.65;
  white-space: pre-wrap;
}
</style>
