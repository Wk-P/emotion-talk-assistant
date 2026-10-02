<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { listResources, type Resource } from '@/api/client'
import SiteFooter from '@/components/SiteFooter.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import { CONTACT } from '@/content/contact'

// Help & contact in one page: about the tool, emergency resources (first, so
// they're never buried), FAQ, and how to reach the research team. The old
// /contact address redirects to the #contact section here.
const { t, locale } = useI18n()
const lang = computed(() => (locale.value === 'ko' || locale.value === 'en' ? locale.value : 'zh'))

const SECTIONS = ['about', 'resources', 'faq', 'contact'] as const
const FAQ = ['password', 'data', 'language', 'research', 'ai'] as const
const TOPICS = ['research', 'account', 'privacy'] as const

const resources = ref<Resource[]>([])
const resourcesLoaded = ref(false)

// Only channels that are actually filled in (src/content/contact.ts).
const channels = computed(() =>
  [
    { key: 'email', value: CONTACT.email, href: `mailto:${CONTACT.email}` },
    { key: 'wechat', value: CONTACT.wechat },
    { key: 'kakao', value: CONTACT.kakao },
    { key: 'phone', value: CONTACT.phone, href: `tel:${CONTACT.phone}` },
  ].filter((c) => c.value),
)

const copied = ref<string | null>(null)
async function copy(key: string, value: string) {
  try {
    await navigator.clipboard.writeText(value)
    copied.value = key
    setTimeout(() => {
      if (copied.value === key) copied.value = null
    }, 2000)
  } catch {
    // clipboard unavailable — the value is still visible to select by hand
  }
}

onMounted(async () => {
  try {
    resources.value = await listResources()
  } finally {
    resourcesLoaded.value = true
  }
})
</script>

<template>
  <div class="help-view">
    <SiteHeader />
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
            <p>{{ t('help.roleText') }}</p>
            <p class="muted">{{ t('help.aboutPrivacy') }} <RouterLink to="/privacy">{{ t('privacy.title') }}</RouterLink></p>
          </section>

          <section id="resources" class="section">
            <h2><span class="sec-no">2</span>{{ t('help.sections.resources') }}</h2>
            <div class="urgent" role="note">
              <strong>{{ t('contact.topics.urgent.title') }}</strong>
              {{ t('contact.topics.urgent.body') }}
            </div>
            <p v-if="resourcesLoaded && resources.length === 0" class="muted">{{ t('help.resourcesEmpty') }}</p>
            <div class="resource-list">
              <div v-for="r in resources" :key="r.id" class="resource">
                <div class="resource-main">
                  <div class="name">{{ r.name[locale] ?? r.name.ko ?? r.name.zh }}</div>
                  <div class="desc">{{ r.description[locale] ?? r.description.ko ?? r.description.zh }}</div>
                </div>
                <div class="resource-links">
                  <a class="phone" :href="`tel:${r.contact}`">{{ r.contact }}</a>
                  <a v-if="r.url" :href="r.url" target="_blank" rel="noopener">{{ t('help.website') }}</a>
                </div>
              </div>
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

          <section id="contact" class="section">
            <h2><span class="sec-no">4</span>{{ t('help.sections.contact') }}</h2>
            <p>{{ t('contact.lead') }}</p>
            <div class="contact-layout">
              <table class="topics">
                <thead>
                  <tr>
                    <th>{{ t('help.topicCol') }}</th>
                    <th>{{ t('help.howCol') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="topic in TOPICS" :key="topic">
                    <th scope="row">{{ t(`contact.topics.${topic}.title`) }}</th>
                    <td>{{ t(`contact.topics.${topic}.body`) }}</td>
                  </tr>
                </tbody>
              </table>

              <aside class="card">
                <h3>{{ t('contact.channelsTitle') }}</h3>
                <dl class="channels">
                  <div v-for="c in channels" :key="c.key" class="channel">
                    <dt>{{ t(`contact.channels.${c.key}`) }}</dt>
                    <dd>
                      <a v-if="c.href" :href="c.href">{{ c.value }}</a>
                      <span v-else>{{ c.value }}</span>
                      <button type="button" class="btn-text copy" @click="copy(c.key, c.value)">
                        {{ copied === c.key ? t('contact.copied') : t('contact.copy') }}
                      </button>
                    </dd>
                  </div>
                  <div class="channel">
                    <dt>{{ t('contact.person') }}</dt>
                    <dd>{{ CONTACT.person[lang] }}</dd>
                  </div>
                  <div class="channel">
                    <dt>{{ t('contact.org') }}</dt>
                    <dd>{{ CONTACT.org[lang] }}</dd>
                  </div>
                </dl>
                <p class="muted">{{ t('contact.replyNote') }}</p>
              </aside>
            </div>
          </section>
        </div>
      </div>
    </main>
    <SiteFooter />
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
  margin-bottom: 2px;
  color: var(--danger);
}
.resource-list {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.resource {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 24px;
  padding: 14px 18px;
}
.resource + .resource {
  border-top: 1px solid var(--border);
}
.resource-main {
  flex: 1 1 320px;
}
.name {
  font-weight: 700;
  font-size: 14.5px;
}
.desc {
  margin-top: 3px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-muted);
}
.resource-links {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 13.5px;
}
.phone {
  font-weight: 700;
  font-size: 15px;
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
.contact-layout {
  display: grid;
  gap: 20px;
  margin-top: 6px;
}
@media (min-width: 1024px) {
  .contact-layout {
    grid-template-columns: minmax(0, 1.6fr) minmax(280px, 1fr);
    align-items: start;
  }
}
.topics {
  width: 100%;
  border-collapse: collapse;
  font-size: 13.5px;
}
.topics th,
.topics td {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
  line-height: 1.65;
}
.topics thead th {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
  background: var(--bg);
}
.topics tbody th {
  width: 30%;
  font-weight: 700;
  white-space: nowrap;
}
.card {
  padding: 18px 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}
.channels {
  margin: 0 0 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.channel dt {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 2px;
}
.channel dd {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 10px;
  font-size: 14px;
  word-break: break-all;
}
.copy {
  font-size: 12.5px;
}
@media (max-width: 639px) {
  .topics tbody th {
    white-space: normal;
  }
}
</style>
