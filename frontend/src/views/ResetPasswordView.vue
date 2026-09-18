<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const token = String(route.query.token ?? '')
const password = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)
const done = ref(false)

async function submit() {
  submitting.value = true
  error.value = null
  try {
    await auth.resetPassword(token, password.value)
    done.value = true
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    error.value = detail ?? t('auth.resetFailed')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-view">
    <header class="header">
      <h1>{{ t('auth.resetTitle') }}</h1>
    </header>

    <p v-if="!token" class="error">{{ t('auth.resetNoToken') }}</p>

    <div v-else-if="done" class="done">
      <p>{{ t('auth.resetDone') }}</p>
      <button class="primary" type="button" @click="router.push('/login')">{{ t('auth.goLogin') }}</button>
    </div>

    <form v-else class="form" @submit.prevent="submit">
      <label>
        {{ t('auth.newPassword') }}
        <input v-model="password" type="password" required minlength="8" autocomplete="new-password" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="primary" type="submit" :disabled="submitting">{{ t('auth.resetSubmit') }}</button>
    </form>
  </div>
</template>

<style scoped>
.auth-view {
  max-width: 420px;
  margin: 0 auto;
  padding: 16px;
}
.header {
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
