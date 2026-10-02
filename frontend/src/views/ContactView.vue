<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SiteFooter from '@/components/SiteFooter.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import { CONTACT } from '@/content/contact'

const { t, locale } = useI18n()
const lang = computed(() => (locale.value === 'ko' ? 'ko' : 'zh'))

// What people usually get in touch about — each says which channel to use.
// Emergencies deliberately point to the help page, not to an inbox.
const TOPICS = ['research', 'account', 'privacy'] as const

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
</script>

<template>
  <div class="contact-view">
    <SiteHeader />
    <main class="page-body">
      <h1 class="page-title">{{ t('contact.title') }}</h1>
      <p class="lead">{{ t('contact.lead') }}</p>

      <div class="contact-layout">
        <section class="topics">
          <h2>{{ t('contact.topicsTitle') }}</h2>
          <div class="topic-grid">
            <div v-for="topic in TOPICS" :key="topic" class="topic">
              <h3>{{ t(`contact.topics.${topic}.title`) }}</h3>
              <p>{{ t(`contact.topics.${topic}.body`) }}</p>
            </div>
            <div class="topic urgent">
              <h3>{{ t('contact.topics.urgent.title') }}</h3>
              <p>{{ t('contact.topics.urgent.body') }}</p>
              <RouterLink to="/help" class="btn-outline urgent-link">{{ t('contact.topics.urgent.link') }}</RouterLink>
            </div>
          </div>
        </section>

        <aside class="card">
          <h2>{{ t('contact.channelsTitle') }}</h2>
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
          </dl>

          <h2 class="team-title">{{ t('contact.teamTitle') }}</h2>
          <dl class="channels">
            <div class="channel">
              <dt>{{ t('contact.person') }}</dt>
              <dd>{{ CONTACT.person[lang] }}</dd>
            </div>
            <div class="channel">
              <dt>{{ t('contact.org') }}</dt>
              <dd>{{ CONTACT.org[lang] }}</dd>
            </div>
          </dl>
          <p class="reply-note">{{ t('contact.replyNote') }}</p>
        </aside>
      </div>
    </main>
    <SiteFooter />
  </div>
</template>

<style scoped>
.lead {
  margin: 8px 0 24px;
  font-size: 14.5px;
  color: var(--text-muted);
  line-height: 1.7;
}
h2 {
  font-size: 15px;
  font-weight: 700;
  margin: 0 0 12px;
}
/* Wide: what-to-ask-about on the left, the contact card on the right. */
.contact-layout {
  display: grid;
  gap: 24px;
}
@media (min-width: 1024px) {
  .contact-layout {
    grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
    align-items: start;
  }
  .card {
    position: sticky;
    top: calc(var(--site-header-h) + 24px);
  }
}
.topic-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}
.topic {
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
}
.topic h3 {
  margin: 0 0 6px;
  font-size: 14.5px;
  color: var(--accent);
}
.topic p {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--text);
}
.topic.urgent {
  border-color: var(--danger-border);
  background: var(--danger-soft);
}
.topic.urgent h3 {
  color: var(--danger);
}
.urgent-link {
  display: inline-block;
  margin-top: 10px;
  padding: 6px 14px;
  font-size: 13px;
  text-decoration: none;
}
.card {
  padding: 20px 22px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg);
}
.team-title {
  margin-top: 20px;
}
.channels {
  margin: 0;
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
  font-size: 14.5px;
  word-break: break-all;
}
.copy {
  font-size: 12.5px;
}
.reply-note {
  margin: 18px 0 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-muted);
}
</style>
