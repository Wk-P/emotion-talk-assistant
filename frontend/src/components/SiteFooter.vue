<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const year = new Date().getFullYear()
</script>

<template>
  <footer class="site-footer">
    <div class="footer-main">
      <span class="footer-name">{{ t('app.title') }}</span>
      <span>{{ t('site.footer.project') }}</span>
    </div>
    <div class="footer-links">
      <RouterLink to="/privacy">{{ t('privacy.title') }}</RouterLink>
      <RouterLink to="/help">{{ t('toolbar.help') }}</RouterLink>
      <RouterLink to="/contact">{{ t('site.footer.contact') }}</RouterLink>
    </div>
    <div class="footer-copy">© {{ year }} {{ t('site.footer.org') }} · {{ t('site.footer.disclaimer') }}</div>
  </footer>
</template>

<style scoped>
.site-footer {
  margin-top: auto;
  padding: 24px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg);
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--text-muted);
  display: grid;
  gap: 6px;
}
@media (min-width: 640px) {
  .site-footer {
    padding: 28px 32px;
  }
}
@media (min-width: 960px) {
  .site-footer {
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
  }
  .footer-copy {
    grid-column: 1 / -1;
  }
}
.footer-main {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
}
.footer-name {
  font-weight: 700;
  color: var(--text);
}
.footer-links {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 18px;
}
.footer-links a {
  color: var(--text-muted);
  text-decoration: none;
}
.footer-links a:hover {
  color: var(--accent);
  text-decoration: underline;
}
</style>
