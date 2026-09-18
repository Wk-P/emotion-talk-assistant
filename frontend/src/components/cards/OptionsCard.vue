<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CandidateCard } from '@/api/client'

const props = defineProps<{ card: CandidateCard; multiSelect?: boolean; disabled?: boolean }>()
const emit = defineEmits<{ confirm: [selectedLabels: string[], customText?: string] }>()

const { t } = useI18n()
const selected = ref<Set<string>>(new Set())
const customText = ref('')
const showCustom = ref(false)

function toggle(id: string) {
  if (props.disabled) return
  if (props.multiSelect) {
    selected.value.has(id) ? selected.value.delete(id) : selected.value.add(id)
    // reassign so Vue's reactivity picks up the mutation on the Set
    selected.value = new Set(selected.value)
  } else {
    selected.value = new Set([id])
    emit('confirm', [id])
  }
}

function submit() {
  if (props.disabled) return
  const labels = props.card.items.filter((i) => selected.value.has(i.id)).map((i) => i.label)
  emit('confirm', labels, customText.value || undefined)
}
</script>

<template>
  <div class="options-card" :class="{ disabled }">
    <button
      v-for="item in card.items"
      :key="item.id"
      class="option"
      :class="{ selected: selected.has(item.id) }"
      type="button"
      :disabled="disabled"
      @click="toggle(item.id)"
    >
      {{ item.label }}
    </button>

    <button v-if="!showCustom" class="option ghost" type="button" :disabled="disabled" @click="showCustom = true">
      {{ t('chat.customOption') }}
    </button>
    <input
      v-else
      v-model="customText"
      class="custom-input"
      :disabled="disabled"
      :placeholder="t('chat.customOption')"
    />

    <button v-if="multiSelect || customText" class="submit" type="button" :disabled="disabled" @click="submit">
      {{ t('chat.submit') }}
    </button>
  </div>
</template>

<style scoped>
.options-card {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
  transition: opacity 0.15s ease;
}
.options-card.disabled {
  opacity: 0.55;
}
.option {
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--card-border, #d8d3ea);
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  transition:
    background 0.15s ease,
    transform 0.1s ease,
    border-color 0.15s ease;
}
.option:active:not(:disabled) {
  transform: scale(0.96);
}
.option:disabled {
  cursor: not-allowed;
}
.option.selected {
  background: #6c5ce7;
  color: #fff;
  border-color: #6c5ce7;
}
.option.ghost {
  border-style: dashed;
  color: #666;
}
.custom-input {
  flex: 1 1 100%;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #d8d3ea;
}
.submit {
  flex-basis: 100%;
  margin-top: 4px;
  padding: 8px;
  border-radius: 8px;
  border: none;
  background: #6c5ce7;
  color: #fff;
  cursor: pointer;
  transition: opacity 0.15s ease;
}
.submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
