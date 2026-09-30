<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { Language } from '@/api/client'
import { detectLang, saveLang } from '@/i18n/langPreference'
import { useAuthStore } from '@/stores/auth'

// Informed-notice gate shown before every new conversation (replaces the
// old landing page). Nothing is stored until the user then sends their
// first message — see stores/session.ts.
const emit = defineEmits<{ start: [lang: Language] }>()

const { t, locale } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const selected = ref<Language>(detectLang())
locale.value = selected.value

function choose(lang: Language) {
  selected.value = lang
  locale.value = lang
  saveLang(lang)
}
</script>

<template>
  <div class="backdrop">
    <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="consent-title">
      <img class="logo" src="/emotion-talk.png" alt="" />
      <h2 id="consent-title">{{ t('app.title') }}</h2>

      <div class="segmented" role="radiogroup" :aria-label="t('onboarding.chooseLanguage')">
        <button type="button" role="radio" :aria-checked="selected === 'zh'" :class="{ on: selected === 'zh' }" @click="choose('zh')">
          中文
        </button>
        <button type="button" role="radio" :aria-checked="selected === 'ko'" :class="{ on: selected === 'ko' }" @click="choose('ko')">
          한국어
        </button>
      </div>

      <p class="intro">{{ t('onboarding.intro') }}</p>
      <p class="note">{{ t('onboarding.consentNote') }}</p>

      <button type="button" class="btn-primary start" @click="emit('start', selected)">
        {{ t('onboarding.acknowledge') }}
      </button>

      <div v-if="!auth.user" class="account">
        <div class="divider"><span>{{ t('onboarding.haveAccount') }}</span></div>
        <div class="account-actions">
          <button type="button" class="btn-outline" @click="router.push('/login')">{{ t('toolbar.login') }}</button>
          <button type="button" class="btn-outline" @click="router.push('/register')">{{ t('auth.register') }}</button>
        </div>
        <p class="login-hint">{{ t('onboarding.loginHint') }}</p>
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
.account {
  width: 100%;
  margin-top: 20px;
}
.divider {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
}
.divider::before,
.divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}
.account-actions {
  display: flex;
  gap: 10px;
}
.account-actions .btn-outline {
  flex: 1;
  padding: 10px 14px;
  font-size: 14px;
}
.login-hint {
  margin: 12px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-muted);
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
