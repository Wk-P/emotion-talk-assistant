<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import type { Language } from '@/api/client'
import { useSessionStore } from '@/stores/session'

const { t, locale } = useI18n()
const router = useRouter()
const session = useSessionStore()
const selected = ref<Language>('zh')
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
    <h1>{{ t('app.title') }}</h1>

    <div class="lang-picker">
      <button :class="{ active: selected === 'zh' }" type="button" @click="choose('zh')">中文</button>
      <button :class="{ active: selected === 'ko' }" type="button" @click="choose('ko')">한국어</button>
    </div>

    <p class="intro">{{ t('onboarding.intro') }}</p>
    <p class="note">{{ t('onboarding.consentNote') }}</p>

    <button class="start" type="button" :disabled="starting" @click="start">
      {{ t('onboarding.start') }}
    </button>
  </div>
</template>

<style scoped>
.onboarding {
  max-width: 480px;
  margin: 0 auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.lang-picker {
  display: flex;
  gap: 8px;
}
.lang-picker button {
  flex: 1;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid #d8d3ea;
  background: #fff;
}
.lang-picker button.active {
  background: #6c5ce7;
  color: #fff;
  border-color: #6c5ce7;
}
.intro,
.note {
  font-size: 14px;
  line-height: 1.6;
  color: #444;
}
.start {
  padding: 12px;
  border-radius: 10px;
  border: none;
  background: #6c5ce7;
  color: #fff;
  font-size: 16px;
}
.start:disabled {
  opacity: 0.6;
}
</style>
