<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// What 心语 is and how to use it, what to do in an emergency, and FAQ.
const { t } = useI18n()

const SECTIONS = ['about', 'resources', 'faq'] as const
const HOW = ['start', 'style', 'end', 'history'] as const
const FAQ = ['ai', 'data', 'research', 'style', 'password'] as const

</script>

<template>
  <div class="help-view">
    <main class="page-body">
      <h1 class="page-title">{{ t('help.title') }}</h1>
      <p class="lead">{{ t('help.lead') }}</p>

      <div class="help-layout">
        <nav class="toc" :aria-label="t('help.tocLabel')">
          <a v-for="(s, i) in SECTIONS" :key="s" :href="`#${s}`">
            <span class="toc-no">{{ i + 1 }}</span>{{ t(`help.sections.${s}`) }}
          </a>
        </nav>

        <div class="sections">
          <section id="about" class="section">
            <h2><span class="sec-no">1</span>{{ t('help.sections.about') }}</h2>
            <p>{{ t('help.aboutIntro') }}</p>
            <h3>{{ t('help.howTitle') }}</h3>
            <ol class="how">
              <li v-for="h in HOW" :key="h">
                <strong>{{ t(`help.how.${h}.title`) }}</strong>
                <span>{{ t(`help.how.${h}.body`) }}</span>
              </li>
            </ol>
            <p class="role">{{ t('help.roleText') }}</p>
            <p class="muted">{{ t('help.aboutPrivacy') }} <RouterLink to="/privacy">{{ t('privacy.title') }}</RouterLink></p>
          </section>

          <section id="resources" class="section">
            <h2><span class="sec-no">2</span>{{ t('help.sections.resources') }}</h2>
            <div class="urgent" role="note">
              <strong>{{ t('help.urgentTitle') }}</strong>
              <p>{{ t('help.urgentBody') }}</p>
              <p class="numbers">{{ t('help.urgentNumbers') }}</p>
            </div>
          </section>

          <section id="faq" class="section">
            <h2><span class="sec-no">3</span>{{ t('help.sections.faq') }}</h2>
            <dl class="faq">
              <div v-for="q in FAQ" :key="q" class="faq-item">
                <dt>{{ t(`help.faq.${q}.q`) }}</dt>
                <dd>{{ t(`help.faq.${q}.a`) }}</dd>
              </div>
            </dl>
          </section>

        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.lead {
  margin: 8px 0 28px;
  font-size: 14.5px;
  line-height: 1.7;
  color: var(--text-muted);
}
/* Wide: a sticky contents list on the left, the sections on the right. */
.help-layout {
  display: grid;
  gap: 28px;
}
.toc {
  display: none;
}
@media (min-width: 1024px) {
  .help-layout {
    grid-template-columns: 220px minmax(0, 1fr);
    gap: 40px;
    align-items: start;
  }
  .toc {
    display: flex;
    flex-direction: column;
    gap: 2px;
    position: sticky;
    top: calc(var(--site-header-h) + 24px);
    padding-left: 12px;
    border-left: 2px solid var(--border);
  }
}
.toc a {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 0;
  font-size: 13.5px;
  color: var(--text-muted);
  text-decoration: none;
}
.toc a:hover {
  color: var(--accent);
}
.toc-no {
  font-size: 12px;
  font-weight: 700;
}
.sections {
  display: flex;
  flex-direction: column;
  gap: 36px;
}
.section {
  /* keep headings clear of the sticky site header when jumped to */
  scroll-margin-top: calc(var(--site-header-h) + 16px);
}
h2 {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
  font-size: 18px;
  font-weight: 700;
}
.sec-no {
  color: var(--accent);
}
h3 {
  margin: 0 0 12px;
  font-size: 14.5px;
  font-weight: 700;
}
p {
  margin: 0 0 10px;
  font-size: 14.5px;
  line-height: 1.75;
  color: var(--text);
}
.muted {
  font-size: 13px;
  color: var(--text-muted);
}
.urgent {
  margin-bottom: 14px;
  padding: 14px 16px;
  border-left: 4px solid var(--danger);
  border-radius: var(--radius-sm);
  background: var(--danger-soft);
  font-size: 14px;
  line-height: 1.7;
}
.urgent strong {
  display: block;
  margin-bottom: 4px;
  color: var(--danger);
}
.urgent p {
  margin: 0 0 8px;
  font-size: 14px;
}
.urgent .numbers {
  margin: 0;
  white-space: pre-line;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.how {
  margin: 0 0 16px;
  padding: 0;
  list-style: none;
  counter-reset: how;
  display: grid;
  gap: 10px;
}
@media (min-width: 720px) {
  .how {
    grid-template-columns: 1fr 1fr;
  }
}
.how li {
  counter-increment: how;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
  font-size: 13.5px;
  line-height: 1.7;
}
.how li {
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}
.how li:hover {
  transform: translateY(-2px);
  border-color: var(--accent);
  box-shadow: var(--shadow-hover);
}
@media (prefers-reduced-motion: reduce) {
  .how li:hover {
    transform: none;
  }
}
.how strong {
  font-size: 14px;
}
.how strong::before {
  content: counter(how) '. ';
  color: var(--accent);
}
.role {
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-size: 13.5px;
}
.faq {
  margin: 0;
}
.faq-item {
  padding: 14px 0;
}
.faq-item + .faq-item {
  border-top: 1px solid var(--border);
}
.faq dt {
  font-size: 14.5px;
  font-weight: 700;
  margin-bottom: 4px;
}
.faq dd {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text);
}
</style>
