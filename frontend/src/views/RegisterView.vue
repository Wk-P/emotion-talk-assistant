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
const done = ref(false)

async function submit() {
  submitting.value = true
  error.value = null
  try {
    await auth.register(email.value, password.value)
    done.value = true
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    error.value = detail ?? t('auth.registerFailed')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-view">
    <header class="header">
      <button type="button" @click="router.push('/chat')">← {{ t('auth.back') }}</button>
      <h1>{{ t('auth.registerTitle') }}</h1>
    </header>

    <div v-if="done" class="done">
      <p>{{ t('auth.registerDone') }}</p>
      <button class="primary" type="button" @click="router.push('/login')">{{ t('auth.goLogin') }}</button>
    </div>

    <form v-else class="form" @submit.prevent="submit">
      <label>
        {{ t('auth.email') }}
        <input v-model="email" type="email" required autocomplete="email" />
      </label>
      <label>
        {{ t('auth.password') }}
        <input v-model="password" type="password" required minlength="8" autocomplete="new-password" />
      </label>
      <p class="hint">{{ t('auth.passwordHint') }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="primary" type="submit" :disabled="submitting">{{ t('auth.register') }}</button>
    </form>

    <div v-if="!done" class="links">
      <button type="button" @click="router.push('/login')">{{ t('auth.haveAccount') }}</button>
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
.hint {
  font-size: 12px;
  color: #888;
  margin-top: -8px;
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
  justify-content: center;
  margin-top: 16px;
}
.links button {
  border: none;
  background: none;
  color: #6c5ce7;
  font-size: 13px;
}
.done {
  text-align: center;
  padding: 24px 0;
}
.done p {
  margin-bottom: 16px;
  color: #444;
  font-size: 14px;
}
</style>
