<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { PRIVACY } from '@/content/privacy'

const { t } = useI18n()

const doc = PRIVACY
</script>

<template>
  <div class="privacy-view">
    <main class="page-body">

    <h1 class="page-title">{{ t('privacy.title') }}</h1>
    <p class="doc-title">{{ doc.title }}</p>

    <div class="sections">
      <section v-for="section in doc.sections" :key="section.title" class="section">
        <h2>{{ section.title }}</h2>
        <p v-for="(line, i) in section.body" :key="i">{{ line }}</p>
      </section>
    </div>
  </main>
  </div>
</template>

<style scoped>
.page-title {
  margin-bottom: 6px;
}
.doc-title {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0 0 20px;
}
/* One section after another, top to bottom, each spanning the full page
   width — read in order like the document it is. */
.sections {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section {
  padding: 16px 18px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}
.section {
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}
.section:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: var(--shadow-hover);
}
@media (prefers-reduced-motion: reduce) {
  .section:hover {
    transform: none;
  }
}
h2 {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--accent);
  margin: 0 0 8px;
}
p {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text);
}
p + p {
  margin-top: 2px;
}
</style>
