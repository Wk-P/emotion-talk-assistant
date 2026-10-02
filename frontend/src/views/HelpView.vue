<script setup lang="ts">
import SiteFooter from '@/components/SiteFooter.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { listResources, type Resource } from '@/api/client'

const { t, locale } = useI18n()
const resources = ref<Resource[]>([])

onMounted(async () => {
  resources.value = await listResources()
})
</script>

<template>
  <div class="help-view">
    <SiteHeader />
    <main class="page-body">
    <div class="page-full">

      <h1 class="page-title">{{ t('help.title') }}</h1>

      <div class="help-layout">
      <section class="about">
        <h2>{{ t('help.roleTitle') }}</h2>
        <p>{{ t('help.roleText') }}</p>
      </section>

      <section>
        <h2>{{ t('help.resourcesTitle') }}</h2>
        <p v-if="resources.length === 0" class="empty">{{ t('help.resourcesEmpty') }}</p>
        <div class="resource-grid">
        <div v-for="r in resources" :key="r.id" class="resource">
          <div class="name">{{ r.name[locale] ?? r.name.ko }}</div>
          <div class="desc">{{ r.description[locale] ?? r.description.ko }}</div>
          <div class="contact">
            <a :href="`tel:${r.contact}`">{{ r.contact }}</a>
            <a v-if="r.url" :href="r.url" target="_blank" rel="noopener">{{ r.url }}</a>
          </div>
        </div>
        </div>
      </section>
      </div>
    </div>
  </main>
    <SiteFooter />
  </div>
</template>

<style scoped>
.page-title {
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
.page-full {
  width: 100%;
}
/* Wide: "about" on the left, the support resources (the part people come
   here for) taking the rest, as a multi-column card grid. */
@media (min-width: 1024px) {
  .help-layout {
    display: grid;
    grid-template-columns: minmax(260px, 1fr) minmax(0, 2.4fr);
    gap: 32px;
    align-items: start;
  }
  .about {
    position: sticky;
    top: calc(var(--site-header-h) + 24px);
    padding: 18px 20px;
    border-radius: var(--radius-md);
    background: var(--accent-soft);
  }
}
.resource-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
}
.resource {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px;
}
.contact {
  flex-wrap: wrap;
  word-break: break-all;
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
