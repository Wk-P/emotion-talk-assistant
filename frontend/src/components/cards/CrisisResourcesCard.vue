<script setup lang="ts">
import type { CandidateCard } from '@/api/client'
import { useI18n } from 'vue-i18n'

defineProps<{ card: CandidateCard }>()
const { t } = useI18n()
</script>

<template>
  <div class="crisis-card">
    <div class="crisis-title">{{ t('crisis.title') }}</div>
    <div v-for="item in card.items" :key="item.id" class="resource">
      <div class="name">{{ item.label }}</div>
      <div class="desc">{{ item.description }}</div>
      <div class="contact">
        <a :href="`tel:${item.contact}`">{{ item.contact }}</a>
        <a v-if="item.url" :href="item.url" target="_blank" rel="noopener">{{ item.url }}</a>
      </div>
      <div class="verified">{{ item.verified_at }}</div>
    </div>
  </div>
</template>

<style scoped>
.crisis-card {
  margin-top: 8px;
  border: 2px solid #e74c3c;
  border-radius: 10px;
  padding: 12px;
  background: #fff5f5;
}
.crisis-title {
  font-weight: 700;
  color: #c0392b;
  margin-bottom: 8px;
}
.resource {
  padding: 8px 0;
  border-top: 1px solid #f3d3d3;
}
.resource:first-of-type {
  border-top: none;
}
.name {
  font-weight: 600;
}
.desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 2px 0;
}
.contact {
  display: flex;
  gap: 12px;
  font-size: 14px;
}
.verified {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}
</style>
