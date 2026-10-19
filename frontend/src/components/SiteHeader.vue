<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import LanguageSwitch from '@/components/LanguageSwitch.vue'

// Top bar of the login / register pages only — every other page is inside
// AppLayout, whose sidebar has the navigation.
const { t } = useI18n()
</script>

<template>
  <header class="site-header">
    <RouterLink to="/" class="site-brand">
      <img src="/emotion-talk.png" alt="" />
      <span>{{ t('app.title') }}</span>
    </RouterLink>
    <LanguageSwitch class="site-lang" />
  </header>
</template>

<style scoped>
.site-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 24px;
  height: var(--site-header-h);
  padding: 0 16px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: saturate(1.4) blur(10px);
  border-bottom: 1px solid var(--border);
}
@media (min-width: 640px) {
  .site-header {
    padding: 0 32px;
  }
}
.site-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  color: var(--text);
  font-size: 15px;
  font-weight: 700;
  text-decoration: none;
}
.site-brand img {
  width: 30px;
  height: 30px;
  border-radius: 8px;
}
.site-lang {
  margin-left: auto;
}
</style>
