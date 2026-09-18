<script setup lang="ts">
import type { CandidateCard, ConfirmationPayload } from '@/api/client'
import CrisisResourcesCard from './CrisisResourcesCard.vue'
import FieldsCard from './FieldsCard.vue'
import OptionsCard from './OptionsCard.vue'

const props = defineProps<{ card: CandidateCard; disabled?: boolean }>()
const emit = defineEmits<{ confirm: [payload: ConfirmationPayload] }>()

const MULTI_SELECT_TYPES = new Set(['emotion_options', 'recovery_action_options'])

function onOptionsConfirm(selectedLabels: string[], customText?: string) {
  emit('confirm', { card_type: props.card.type, selected_labels: selectedLabels, custom_text: customText })
}

function onFieldsConfirm(fields: Record<string, unknown>) {
  emit('confirm', { card_type: props.card.type, fields })
}
</script>

<template>
  <CrisisResourcesCard v-if="card.type === 'crisis_resources'" :card="card" />
  <FieldsCard
    v-else-if="card.fields"
    :card="card"
    :disabled="disabled"
    @confirm="onFieldsConfirm"
    @skip="emit('confirm', { card_type: card.type })"
  />
  <OptionsCard
    v-else-if="card.items?.length"
    :card="card"
    :multi-select="MULTI_SELECT_TYPES.has(card.type)"
    :disabled="disabled"
    @confirm="onOptionsConfirm"
  />
</template>
