<script setup lang="ts">
import { reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CandidateCard } from '@/api/client'

const props = defineProps<{ card: CandidateCard; disabled?: boolean }>()
const emit = defineEmits<{ confirm: [fields: Record<string, unknown>]; skip: [] }>()

const { t } = useI18n()
const local = reactive<Record<string, string>>(
  Object.fromEntries(Object.entries(props.card.fields ?? {}).map(([k, v]) => [k, String(v ?? '')])),
)

function submit() {
  if (props.disabled) return
  emit('confirm', { ...local })
}
</script>

<template>
  <div class="fields-card" :class="{ disabled }">
    <label v-for="(_, key) in local" :key="key" class="field">
      <span class="field-label">{{ key }}</span>
      <textarea v-model="local[key]" rows="2" :disabled="disabled" />
    </label>
    <div class="actions">
      <button type="button" class="submit" :disabled="disabled" @click="submit">{{ t('chat.submit') }}</button>
      <button type="button" class="skip" :disabled="disabled" @click="emit('skip')">{{ t('chat.skip') }}</button>
    </div>
  </div>
</template>

<style scoped>
.fields-card {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #d8d3ea;
  border-radius: 10px;
  padding: 10px;
  transition: opacity 0.15s ease;
}
.fields-card.disabled {
  opacity: 0.55;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.field-label {
  font-size: 12px;
  color: #777;
  text-transform: capitalize;
}
textarea {
  border: 1px solid #d8d3ea;
  border-radius: 6px;
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
  padding: 8px;
  border: none;
  border-radius: 8px;
  background: #6c5ce7;
  color: #fff;
}
.submit:disabled,
.skip:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.skip {
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid #d8d3ea;
  background: #fff;
}
</style>
