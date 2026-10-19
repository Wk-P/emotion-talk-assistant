<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { SummaryCard } from '@/api/client'

// The conversation card (backend app/services/summary_card.py).
// review (or `plain`): shown as is. final: front (查看详情 / 下一步) → flips to "save this
// card?" → the result with 下一步, which emits `done`.
const props = defineProps<{
  card: SummaryCard
  decide?: (save: boolean) => Promise<void>
  // Just the content (a review card, or a final card already answered).
  plain?: boolean
}>()
const emit = defineEmits<{ done: [] }>()

const { t } = useI18n()
const showDetails = ref(false)
// A final card that was already answered opens on its result.
const side = ref<'front' | 'ask' | 'result'>(props.card.kind === 'final' && props.card.decision ? 'result' : 'front')
const saved = ref(props.card.decision === 'saved')
const busy = ref(false)
const failed = ref(false)

const sections = [
  { key: 'summary', label: 'chat.card.summary' },
  { key: 'plan', label: 'chat.card.plan' },
  { key: 'kindness', label: 'chat.card.kindness' },
] as const

function text(key: (typeof sections)[number]['key']): string {
  return props.card.content[key]?.trim() || t('chat.card.empty')
}

async function choose(save: boolean) {
  if (busy.value || !props.decide) return
  busy.value = true
  failed.value = false
  try {
    await props.decide(save)
    saved.value = save
    side.value = 'result'
  } catch {
    failed.value = true
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="plain || card.kind === 'review'" class="conv-card plain">
    <div class="face">
      <p class="card-title">{{ t(card.kind === 'review' ? 'chat.card.reviewTitle' : 'chat.card.finalTitle') }}</p>
      <div v-for="s in sections" :key="s.key" class="section">
        <p class="label">{{ t(s.label) }}</p>
        <p class="body" :class="{ empty: !card.content[s.key]?.trim() }">{{ text(s.key) }}</p>
      </div>
    </div>
  </div>

  <div v-else class="conv-card final" :class="{ flipped: side !== 'front' }">
    <div class="flipper">
      <div class="face front" :aria-hidden="side !== 'front'">
        <p class="card-title">{{ t('chat.card.finalTitle') }}</p>
        <p class="body preview">{{ text('summary') }}</p>
        <div class="actions">
          <button type="button" class="btn-outline" :disabled="side !== 'front'" @click="showDetails = true">
            {{ t('chat.card.details') }}
          </button>
          <button type="button" class="btn-primary" :disabled="side !== 'front'" @click="side = 'ask'">
            {{ t('chat.card.next') }}
          </button>
        </div>
      </div>

      <div class="face back" :aria-hidden="side === 'front'">
        <template v-if="side === 'result'">
          <p class="result" :class="{ ok: saved }">{{ saved ? `✓ ${t('chat.card.saved')}` : t('chat.card.notSaved') }}</p>
          <div class="actions">
            <RouterLink v-if="saved" to="/records" class="btn-text">{{ t('chat.viewRecords') }}</RouterLink>
            <button type="button" class="btn-primary" @click="emit('done')">{{ t('chat.card.next') }}</button>
          </div>
        </template>
        <template v-else>
          <p class="question">{{ t('chat.card.saveAsk') }}</p>
          <p class="note">{{ t('chat.card.saveNote') }}</p>
          <p v-if="failed" class="note error">{{ t('chat.card.failed') }}</p>
          <div class="actions">
            <button type="button" class="btn-primary" :disabled="busy || side !== 'ask'" @click="choose(true)">
              {{ t('chat.card.save') }}
            </button>
            <button type="button" class="btn-outline" :disabled="busy || side !== 'ask'" @click="choose(false)">
              {{ t('chat.card.noSave') }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>

  <Teleport to="body">
    <div v-if="showDetails" class="details-backdrop" @click.self="showDetails = false">
      <div class="details" role="dialog" aria-modal="true" :aria-label="t('chat.card.finalTitle')">
        <p class="card-title">{{ t('chat.card.finalTitle') }}</p>
        <div v-for="s in sections" :key="s.key" class="section">
          <p class="label">{{ t(s.label) }}</p>
          <p class="body" :class="{ empty: !card.content[s.key]?.trim() }">{{ text(s.key) }}</p>
        </div>
        <div class="actions">
          <button type="button" class="btn-primary" @click="showDetails = false">{{ t('chat.card.back') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.conv-card {
  width: 100%;
  max-width: 520px;
}
.face,
.details {
  box-sizing: border-box;
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm, 12px);
  background: var(--surface);
  box-shadow: var(--shadow-md);
}
.card-title {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
}
.section + .section {
  margin-top: 10px;
}
.label {
  margin: 0 0 2px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}
.body {
  margin: 0;
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--text);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.body.empty {
  color: var(--text-muted);
}
.preview {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
}
.actions button {
  flex: 1 1 0;
  min-width: 96px;
  padding: 8px 14px;
  font-size: 14px;
  border: 1px solid transparent;
  border-radius: 999px;
}
.actions .btn-outline {
  border-color: var(--border);
}
.question {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.note {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
.note.error {
  margin-top: 4px;
  color: var(--danger);
}
.result {
  margin: 0;
  font-size: 14.5px;
  font-weight: 600;
  color: var(--text);
}
.result.ok {
  color: #1c8a4a;
}

/* The flip: both faces share one grid cell, so the card is as tall as the
   taller face and nothing needs a fixed height. */
.flipper {
  display: grid;
  transition: transform 0.5s ease;
  transform-style: preserve-3d;
}
.flipped .flipper {
  transform: rotateY(180deg);
}
.flipper > .face {
  grid-area: 1 / 1;
  backface-visibility: hidden;
  -webkit-backface-visibility: hidden;
}
.flipper > .back {
  transform: rotateY(180deg);
  display: flex;
  flex-direction: column;
  justify-content: center;
}
@media (prefers-reduced-motion: reduce) {
  .flipper {
    transition: none;
  }
}

.details-backdrop {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: rgba(0, 0, 0, 0.35);
}
.details {
  width: 100%;
  max-width: 520px;
  max-height: 85dvh;
  overflow-y: auto;
}
</style>
