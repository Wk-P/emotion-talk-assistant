<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useSessionStore } from '@/stores/session'

const { t, locale } = useI18n()
const router = useRouter()
const session = useSessionStore()
const auth = useAuthStore()

async function toggleLanguage() {
  if (session.sending) return
  const next = session.language === 'zh' ? 'ko' : 'zh'
  await session.switchLanguage(next)
  locale.value = next
}

function skipQuestion() {
  if (session.sending) return
  session.send(undefined, { card_type: 'skip' })
}

function anotherQuestion() {
  if (session.sending) return
  session.send(locale.value === 'zh' ? '换一个问题' : '다른 질문으로 해주세요')
}
</script>

<template>
  <nav class="toolbar">
    <button type="button" :disabled="session.sending" @click="anotherQuestion">
      {{ t('toolbar.another') }}
    </button>
    <button type="button" :disabled="session.sending" @click="skipQuestion">
      {{ t('toolbar.skip') }}
    </button>
    <button type="button" :disabled="session.sending" @click="toggleLanguage">
      {{ t('toolbar.language') }}: {{ session.language === 'zh' ? '中文' : '한국어' }}
    </button>
    <button type="button" @click="router.push('/records')">{{ t('toolbar.records') }}</button>
    <button type="button" @click="router.push('/history')">{{ t('toolbar.history') }}</button>
    <button type="button" @click="router.push('/help')">{{ t('toolbar.help') }}</button>
    <button v-if="!auth.user" type="button" @click="router.push('/login')">{{ t('toolbar.login') }}</button>
    <button v-else type="button" @click="auth.logout()">{{ auth.user.email }} · {{ t('toolbar.logout') }}</button>
  </nav>
</template>

<style scoped>
.toolbar {
  position: sticky;
  bottom: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px;
  background: #faf9fd;
  border-top: 1px solid #e6e2f2;
}
.toolbar button {
  flex: 1 1 auto;
  padding: 8px 6px;
  font-size: 12px;
  border-radius: 8px;
  border: 1px solid #d8d3ea;
  background: #fff;
  color: #444;
  transition:
    opacity 0.15s ease,
    background 0.15s ease;
}
.toolbar button:active:not(:disabled) {
  background: #f1eefa;
}
.toolbar button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
