<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { listResources, type Resource } from '@/api/client'

const { t, locale } = useI18n()
const router = useRouter()
const resources = ref<Resource[]>([])

onMounted(async () => {
  resources.value = await listResources()
})
</script>

<template>
  <div class="help-view">
    <header class="header">
      <button type="button" @click="router.push('/chat')">← {{ t('help.back') }}</button>
      <h1>{{ t('help.title') }}</h1>
    </header>

    <section>
      <h2>{{ t('help.roleTitle') }}</h2>
      <p>{{ t('help.roleText') }}</p>
    </section>

    <section>
      <h2>{{ t('help.resourcesTitle') }}</h2>
      <div v-for="r in resources" :key="r.id" class="resource">
        <div class="name">{{ r.name[locale] ?? r.name.ko }}</div>
        <div class="desc">{{ r.description[locale] ?? r.description.ko }}</div>
        <div class="contact">
          <a :href="`tel:${r.contact}`">{{ r.contact }}</a>
          <a v-if="r.url" :href="r.url" target="_blank" rel="noopener">{{ r.url }}</a>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.help-view {
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
section {
  margin-bottom: 20px;
}
h2 {
  font-size: 15px;
  margin-bottom: 6px;
}
p {
  font-size: 14px;
  color: #444;
  line-height: 1.6;
}
.resource {
  border: 1px solid #eee;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 8px;
}
.name {
  font-weight: 600;
}
.desc {
  font-size: 13px;
  color: #555;
  margin: 4px 0;
}
.contact {
  display: flex;
  gap: 12px;
  font-size: 13px;
}
</style>
