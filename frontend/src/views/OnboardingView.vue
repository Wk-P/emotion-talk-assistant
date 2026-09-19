<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { Language } from '@/api/client'
import AppMenu from '@/components/AppMenu.vue'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'

const { t, locale } = useI18n()
const router = useRouter()
const session = useSessionStore()
const auth = useAuthStore()
// Default to the visitor's own browser language instead of always
// highlighting 中文 — this app serves both Chinese and Korean speakers.
const browserLang: Language = navigator.language.toLowerCase().startsWith('ko') ? 'ko' : 'zh'
const selected = ref<Language>(browserLang)
locale.value = browserLang
const starting = ref(false)

function choose(lang: Language) {
  selected.value = lang
  locale.value = lang
}

async function start() {
  starting.value = true
  try {
    await session.begin(selected.value)
    router.push('/chat')
  } finally {
    starting.value = false
  }
}
</script>

<template>
  <div class="onboarding">
    <div class="account-bar">
      <AppMenu v-if="auth.user" />
    </div>

    <div class="page-inner onboarding-inner">
    <img class="logo reveal" style="animation-delay: 0.02s" src="/emotion-talk.png" :alt="t('app.title')" />

    <h1 class="reveal" style="animation-delay: 0.06s">{{ t('app.title') }}</h1>

    <p v-if="auth.user" class="welcome reveal" style="animation-delay: 0.08s" :title="auth.user.email">
      {{ t('onboarding.welcomeBack', { email: auth.user.email }) }}
    </p>

    <div class="lang-picker reveal" style="animation-delay: 0.1s">
      <button
        class="btn-outline"
        :class="{ active: selected === 'zh' }"
        type="button"
        @click="choose('zh')"
      >
        中文
      </button>
      <button
        class="btn-outline"
        :class="{ active: selected === 'ko' }"
        type="button"
        @click="choose('ko')"
      >
        한국어
      </button>
    </div>

    <!-- Returning user: they've already read the full disclaimer once, so
         skip straight to the actions instead of re-showing both long
         paragraphs above the fold every time. Full text stays one tap away
         via 帮助. -->
    <template v-if="auth.user">
      <div class="cta reveal" style="animation-delay: 0.14s">
        <button class="btn-primary start" type="button" :disabled="starting" @click="start">
          {{ t('onboarding.start') }}
        </button>
        <button class="btn-outline" type="button" @click="router.push('/history')">
          {{ t('toolbar.history') }}
        </button>
      </div>
      <button
        type="button"
        class="btn-text about-link reveal"
        style="animation-delay: 0.18s"
        @click="router.push('/help')"
      >
        {{ t('onboarding.aboutLink') }}
      </button>
    </template>
    <template v-else>
      <p class="intro reveal" style="animation-delay: 0.14s">{{ t('onboarding.intro') }}</p>
      <p class="note reveal" style="animation-delay: 0.18s">{{ t('onboarding.consentNote') }}</p>

      <div class="cta reveal" style="animation-delay: 0.22s">
        <p class="login-hint">{{ t('onboarding.loginHint') }}</p>
        <button class="btn-primary start" type="button" @click="router.push('/login')">
          {{ t('toolbar.login') }}
        </button>
        <button class="btn-text register-link" type="button" @click="router.push('/register')">
          {{ t('auth.needAccount') }}
        </button>
      </div>
    </template>
    </div>
  </div>
</template>

<style scoped>
.onboarding {
  padding: 20px 20px 28px;
}
@media (min-width: 640px) {
  .onboarding {
    padding: 32px;
  }
}
.onboarding-inner {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.account-bar {
  display: flex;
  justify-content: flex-end;
  min-height: 20px;
  margin-bottom: 8px;
}
.logo {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  align-self: center;
  box-shadow: var(--shadow-md);
}
h1 {
  text-align: center;
  font-size: 20px;
}
.welcome {
  align-self: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: center;
  font-size: 13px;
  color: var(--accent);
  font-weight: 500;
  margin: -6px 0 0;
}
.about-link {
  align-self: center;
}
.lang-picker {
  display: flex;
  gap: 8px;
  align-self: center;
}
.lang-picker button {
  min-width: 100px;
}
.intro,
.note {
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-muted);
  text-align: center;
}
.cta {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 6px;
}
.login-hint {
  text-align: center;
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
}
.register-link {
  align-self: center;
}
.start {
  font-size: 16px;
}
.reveal {
  opacity: 0;
  animation: fade-up 0.5s ease forwards;
}
</style>
