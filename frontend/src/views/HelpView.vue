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
    <div class="page-inner">
      <header class="header">
        <button type="button" class="btn-back" @click="router.push('/chat')"><span class="arrow">&lt;</span> {{ t('help.back') }}</button>
      </header>

      <h1 class="page-title">{{ t('help.title') }}</h1>

      <section>
        <h2>{{ t('help.roleTitle') }}</h2>
        <p>{{ t('help.roleText') }}</p>
      </section>

      <section>
        <h2>{{ t('help.resourcesTitle') }}</h2>
        <p v-if="resources.length === 0" class="empty">{{ t('help.resourcesEmpty') }}</p>
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
  </div>
</template>

<style scoped>
.help-view {
  padding: 16px;
}
@media (min-width: 640px) {
  .help-view {
    padding: 32px;
  }
}
.header {
  margin-bottom: 14px;
}
.page-title {
  font-size: 17px;
  font-weight: 700;
  margin-bottom: 20px;
}
section {
  margin-bottom: 22px;
}
h2 {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 8px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
p {
  font-size: 14px;
  color: var(--text);
  line-height: 1.65;
}
.resource {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  margin-bottom: 8px;
}
.name {
  font-weight: 600;
}
.desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 4px 0;
}
.contact {
  display: flex;
  gap: 12px;
  font-size: 13px;
}
.contact a {
  color: var(--accent);
}
.empty {
  color: var(--text-muted);
  font-size: 13px;
}
</style>
