<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Language } from '@/api/client'
import { detectChatLang, detectLang, saveChatLang, saveLang, type UiLang } from '@/i18n/langPreference'

// Informed-notice gate shown before every new conversation (replaces the
// old landing page). A card in the middle of the chat, not a pop-up: the
// sidebar stays usable, and the chat's input appears once it's accepted. Nothing is stored until the user then sends their
// first message — see stores/session.ts.
const emit = defineEmits<{ start: [lang: Language] }>()

const { t, locale } = useI18n()

const UI_LANGS: { id: UiLang; label: string }[] = [
  { id: 'zh', label: '中文' },
  { id: 'ko', label: '한국어' },
  { id: 'en', label: 'English' },
]

const selected = ref<UiLang>(detectLang())
// Conversations are in Chinese or Korean; with the English interface the
// user picks which one separately.
const chatLang = ref<Language>(detectChatLang())
locale.value = selected.value

function choose(lang: UiLang) {
  selected.value = lang
  locale.value = lang
  saveLang(lang)
  if (lang !== 'en') chatLang.value = lang
}

function chooseChat(lang: Language) {
  chatLang.value = lang
  saveChatLang(lang)
}
</script>

<template>
  <section class="welcome" aria-labelledby="consent-title">
    <div class="head">
      <img class="logo" src="/emotion-talk.png" alt="" />
      <h2 id="consent-title">{{ t('app.title') }}</h2>
    </div>

    <!-- documents/02_内容与需求/首页提示词.md — shown here, before the chat starts, and
         not repeated inside the conversation. -->
    <p class="tagline">{{ t('welcome.title') }}</p>
    <p class="intro">{{ t('welcome.body') }}</p>
    <div class="tip">
      <span class="tip-title">{{ t('welcome.noteTitle') }}</span>
      {{ t('welcome.note') }}
    </div>
    <p class="note">{{ t('onboarding.consentNote') }}</p>

    <div class="lang-row">
      <span class="lang-label">{{ t('onboarding.chooseLanguage') }}</span>
      <div class="segmented" role="radiogroup" :aria-label="t('onboarding.chooseLanguage')">
        <button
          v-for="l in UI_LANGS"
          :key="l.id"
          type="button"
          role="radio"
          :aria-checked="selected === l.id"
          :class="{ on: selected === l.id }"
          @click="choose(l.id)"
        >
          {{ l.label }}
        </button>
      </div>
    </div>
    <div v-if="selected === 'en'" class="lang-row">
      <span class="lang-label">{{ t('onboarding.chatLanguage') }}</span>
      <div class="segmented" role="radiogroup" :aria-label="t('onboarding.chatLanguage')">
        <button type="button" role="radio" :aria-checked="chatLang === 'zh'" :class="{ on: chatLang === 'zh' }" @click="chooseChat('zh')">
          中文
        </button>
        <button type="button" role="radio" :aria-checked="chatLang === 'ko'" :class="{ on: chatLang === 'ko' }" @click="chooseChat('ko')">
          한국어
        </button>
      </div>
      <p class="lang-hint">{{ t('onboarding.chatLanguageHint') }}</p>
    </div>

    <button type="button" class="btn-primary start" @click="emit('start', chatLang)">
      {{ t('onboarding.acknowledge') }}
    </button>
  </section>
</template>

<style scoped>
.welcome {
  max-width: 560px;
  margin: clamp(16px, 6vh, 64px) auto 24px;
  padding: 28px 24px 24px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-md);
  animation: fade-up 0.25s ease;
}
.head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.logo {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  box-shadow: var(--shadow-sm);
}
h2 {
  font-size: 18px;
  font-weight: 700;
}
.tagline {
  margin: 0 0 8px;
  font-size: 15.5px;
  font-weight: 700;
  line-height: 1.6;
  color: var(--accent);
}
.intro {
  margin: 0 0 12px;
  font-size: 14.5px;
  line-height: 1.75;
}
.tip {
  margin: 0 0 12px;
  padding: 10px 12px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-muted);
}
.tip-title {
  display: block;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 2px;
}
.note {
  margin: 0 0 18px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-size: 13px;
  line-height: 1.6;
  color: var(--accent);
}
.lang-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px 12px;
  margin-bottom: 14px;
}
.lang-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}
.lang-hint {
  flex-basis: 100%;
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
.segmented {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--bg);
  border: 1px solid var(--border);
}
.segmented button {
  border: none;
  background: transparent;
  padding: 5px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}
.segmented button.on {
  background: var(--surface);
  color: var(--accent);
  box-shadow: var(--shadow-sm);
}
.segmented button:not(:disabled):hover {
  color: var(--accent);
}
.start {
  width: 100%;
  margin-top: 6px;
}
@media (max-width: 480px) {
  .welcome {
    padding: 22px 18px 18px;
    box-shadow: none;
  }
}
</style>
