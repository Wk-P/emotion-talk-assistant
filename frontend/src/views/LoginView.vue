<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)

async function submit() {
  submitting.value = true
  error.value = null
  try {
    await auth.login(email.value, password.value)
    // Not '/chat' — there's no active session yet right after login, so
    // ChatView's own guard would immediately bounce back to '/' anyway,
    // flashing an empty chat shell in between. Go straight there instead.
    router.push('/')
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    error.value = detail ?? t('auth.loginFailed')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-view">
    <header class="header">
      <button type="button" class="btn-back" @click="router.push('/')"><span class="arrow">&lt;</span> {{ t('auth.back') }}</button>
    </header>

    <img class="logo" src="/emotion-talk.png" :alt="t('app.title')" />
    <h1>{{ t('auth.loginTitle') }}</h1>

    <form class="form" @submit.prevent="submit">
      <label>
        {{ t('auth.email') }}
        <input v-model="email" type="email" required autocomplete="email" />
      </label>
      <label>
        {{ t('auth.password') }}
        <input v-model="password" type="password" required autocomplete="current-password" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn-primary" type="submit" :disabled="submitting">{{ t('auth.login') }}</button>
    </form>

    <div class="links">
      <button type="button" class="btn-text" @click="router.push('/forgot-password')">
        {{ t('auth.forgotPassword') }}
      </button>
      <button type="button" class="btn-text" @click="router.push('/register')">{{ t('auth.needAccount') }}</button>
    </div>
  </div>
</template>

<style scoped>
.auth-view {
  padding: 16px;
}
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
}
input {
  padding: 11px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  font-size: 14px;
}
.error {
  color: var(--danger);
  font-size: 13px;
}
.links {
  display: flex;
  justify-content: space-between;
  margin-top: 16px;
}
.logo {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: block;
  margin: 0 auto 4px;
  box-shadow: var(--shadow-sm);
}
h1 {
  text-align: center;
  font-size: 19px;
  margin-bottom: 20px;
}
</style>
