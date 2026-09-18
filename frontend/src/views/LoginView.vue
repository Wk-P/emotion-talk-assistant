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
    router.push('/chat')
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
      <button type="button" @click="router.push('/chat')">← {{ t('auth.back') }}</button>
      <h1>{{ t('auth.loginTitle') }}</h1>
    </header>

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
      <button class="primary" type="submit" :disabled="submitting">{{ t('auth.login') }}</button>
    </form>

    <div class="links">
      <button type="button" @click="router.push('/forgot-password')">{{ t('auth.forgotPassword') }}</button>
      <button type="button" @click="router.push('/register')">{{ t('auth.needAccount') }}</button>
    </div>
  </div>
</template>

<style scoped>
.auth-view {
  max-width: 420px;
  margin: 0 auto;
  padding: 16px;
}
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.header button {
  border: none;
  background: none;
  color: #6c5ce7;
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
  color: #555;
}
input {
  padding: 10px;
  border-radius: 8px;
  border: 1px solid #d8d3ea;
  font-size: 14px;
}
.primary {
  padding: 12px;
  border-radius: 10px;
  border: none;
  background: #6c5ce7;
  color: #fff;
  font-size: 15px;
}
.primary:disabled {
  opacity: 0.6;
}
.error {
  color: #c0392b;
  font-size: 13px;
}
.links {
  display: flex;
  justify-content: space-between;
  margin-top: 16px;
}
.links button {
  border: none;
  background: none;
  color: #6c5ce7;
  font-size: 13px;
}
</style>
