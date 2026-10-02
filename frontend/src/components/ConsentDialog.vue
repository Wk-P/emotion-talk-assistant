<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Language } from '@/api/client'
import { detectChatLang, detectLang, saveChatLang, saveLang, type UiLang } from '@/i18n/langPreference'

// Informed-notice gate shown before every new conversation (replaces the
// old landing page). Nothing is stored until the user then sends their
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
  <div class="backdrop">
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="consent-title">
      <div class="dialog-main">
      <img class="logo" src="/emotion-talk.png" alt="" />
      <h2 id="consent-title">{{ t('app.title') }}</h2>

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

      <div v-if="selected === 'en'" class="chat-lang">
        <span class="chat-lang-label">{{ t('onboarding.chatLanguage') }}</span>
        <div class="segmented small" role="radiogroup" :aria-label="t('onboarding.chatLanguage')">
          <button type="button" role="radio" :aria-checked="chatLang === 'zh'" :class="{ on: chatLang === 'zh' }" @click="chooseChat('zh')">
            中文
          </button>
          <button type="button" role="radio" :aria-checked="chatLang === 'ko'" :class="{ on: chatLang === 'ko' }" @click="chooseChat('ko')">
            한국어
          </button>
        </div>
        <p class="chat-lang-hint">{{ t('onboarding.chatLanguageHint') }}</p>
      </div>

      <!-- documents/首页提示词.md — shown here, before the chat starts, and
           not repeated inside the conversation. -->
      <p class="tagline">{{ t('welcome.title') }}</p>
      <p class="intro">{{ t('welcome.body') }}</p>
      <div class="tip">
        <span class="tip-title">{{ t('welcome.noteTitle') }}</span>
        {{ t('welcome.note') }}
      </div>
      <p class="note">{{ t('onboarding.consentNote') }}</p>
      </div>

      <div class="dialog-side">

      <button type="button" class="btn-primary start" @click="emit('start', chatLang)">
        {{ t('onboarding.acknowledge') }}
      </button>

      </div>
    </div>
  </div>
</template>

<style scoped>
.backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  padding-top: max(16px, env(safe-area-inset-top, 0px));
  padding-bottom: max(16px, env(safe-area-inset-bottom, 0px));
  background: rgba(31, 35, 51, 0.32);
  backdrop-filter: blur(6px);
  animation: fade-in 0.2s ease;
}
.dialog {
  width: 100%;
  max-width: 440px;
  max-height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 32px 28px 24px;
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-lg);
  animation: pop-in 0.28s ease;
}
.logo {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  box-shadow: var(--shadow-md);
  margin-bottom: 14px;
}
h2 {
  font-size: 19px;
  font-weight: 700;
  margin-bottom: 16px;
}
.segmented {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--bg);
  border: 1px solid var(--border);
  margin-bottom: 20px;
}
.segmented button {
  border: none;
  background: transparent;
  padding: 7px 20px;
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
  transform: none;
  color: var(--accent);
}
.chat-lang {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  margin: -8px 0 18px;
}
.chat-lang-label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-muted);
}
.segmented.small {
  margin-bottom: 0;
}
.segmented.small button {
  padding: 5px 14px;
  font-size: 12.5px;
}
.chat-lang-hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-muted);
}
.tagline {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.6;
  color: var(--accent);
}
.tip {
  width: 100%;
  margin: 0 0 12px;
  padding: 10px 12px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  line-height: 1.65;
  color: var(--text-muted);
  text-align: left;
}
.tip-title {
  display: block;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 2px;
}
.intro {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text);
  text-align: left;
}
.note {
  margin: 0 0 22px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--accent);
  text-align: left;
}
.start {
  width: 100%;
}
.dialog-main,
.dialog-side {
  display: contents;
}

/* >=960px: not a small box in the middle of the screen — the notice takes
   the whole screen as a split: what this is on the left, the choices
   (language, start) on the right. */
@media (min-width: 960px) {
  .backdrop {
    padding: 0;
    background: var(--surface);
    backdrop-filter: none;
  }
  .dialog {
    max-width: none;
    height: 100%;
    max-height: none;
    border-radius: 0;
    box-shadow: none;
    padding: 0;
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
    align-items: stretch;
    text-align: left;
  }
  .dialog-main,
  .dialog-side {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 48px clamp(32px, 5vw, 96px);
  }
  .dialog-main {
    align-items: flex-start;
    background: var(--accent-soft);
  }
  .dialog-side {
    align-items: stretch;
  }
  .logo {
    width: 72px;
    height: 72px;
    border-radius: 20px;
  }
  h2 {
    font-size: clamp(22px, 2.2vw, 32px);
  }
  .tagline {
    font-size: clamp(18px, 1.6vw, 22px);
  }
  .intro {
    font-size: 16px;
    line-height: 1.85;
  }
  .tip {
    font-size: 14px;
    padding: 14px 16px;
    background: var(--surface);
  }
  .note {
    font-size: 14px;
    padding: 14px 16px;
  }
  .start {
    padding: 14px 20px;
    font-size: 16px;
  }
}
@keyframes fade-in {
  from {
    opacity: 0;
  }
}
@keyframes pop-in {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.97);
  }
}
</style>
