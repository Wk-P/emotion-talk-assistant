<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const submitting = ref(false)
const done = ref(false)

async function submit() {
  submitting.value = true
  try {
    await auth.forgotPassword(email.value)
    done.value = true
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-view">
    <header class="header">
      <button type="button" @click="router.push('/login')">← {{ t('auth.back') }}</button>
      <h1>{{ t('auth.forgotTitle') }}</h1>
    </header>

    <div v-if="done" class="done">
      <p>{{ t('auth.forgotDone') }}</p>
    </div>

    <form v-else class="form" @submit.prevent="submit">
      <label>
        {{ t('auth.email') }}
        <input v-model="email" type="email" required autocomplete="email" />
      </label>
      <button class="primary" type="submit" :disabled="submitting">{{ t('auth.sendResetLink') }}</button>
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
.done {
  text-align: center;
  padding: 24px 0;
  color: #444;
  font-size: 14px;
}
</style>
