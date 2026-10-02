<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CandidateCard } from '@/api/client'
import { fieldLabel } from '@/utils/fieldLabels'

const props = defineProps<{ card: CandidateCard; disabled?: boolean }>()
const emit = defineEmits<{ confirm: [fields: Record<string, unknown>]; skip: [] }>()

const { t, te } = useI18n()
const local = reactive<Record<string, string>>(
  Object.fromEntries(Object.entries(props.card.fields ?? {}).map(([k, v]) => [k, String(v ?? '')])),
)

// The AI's reply_text is asked to explain what a card is for, but that's a
// prompt-level request, not a guarantee (BUG 反馈, documents/02_内容与需求/Modified_Log.md:
// users had no idea what a fields card was for). Every known card type gets
// a fixed, code-owned caption instead of relying on the model to say so.
const captionKey = computed(() => `fieldsCard.${props.card.type}`)
const caption = computed(() => (te(captionKey.value) ? t(captionKey.value) : t('fieldsCard.generic')))

function submit() {
  if (props.disabled) return
  emit('confirm', { ...local })
}
</script>

<template>
  <div class="fields-card" :class="{ disabled }">
    <p class="caption">{{ caption }}</p>
    <label v-for="(_, key) in local" :key="key" class="field">
      <span class="field-label">{{ fieldLabel(t, te, String(key)) }}</span>
      <textarea v-model="local[key]" rows="2" :disabled="disabled" />
    </label>
    <div class="actions">
      <button type="button" class="btn-primary submit" :disabled="disabled" @click="submit">
        {{ t('chat.submit') }}
      </button>
      <button type="button" class="btn-outline skip" :disabled="disabled" @click="emit('skip')">
        {{ t('chat.skip') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.fields-card {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px;
  transition: opacity 0.15s ease;
}
.fields-card.disabled {
  opacity: 0.55;
}
.caption {
  font-size: 12.5px;
  color: var(--text-muted);
  line-height: 1.5;
  margin: 0;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: capitalize;
}
textarea {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 6px 8px;
  font: inherit;
  resize: vertical;
}
.actions {
  display: flex;
  gap: 8px;
}
.submit {
  flex: 1;
}
.skip {
  padding: 8px 14px;
}
</style>
