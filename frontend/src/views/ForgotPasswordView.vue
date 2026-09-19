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
      <button type="button" class="btn-back" @click="router.push('/login')"><span class="arrow">&lt;</span> {{ t('auth.back') }}</button>
    </header>

    <h1 class="page-title">{{ t('auth.forgotTitle') }}</h1>

    <div v-if="done" class="done">
      <p>{{ t('auth.forgotDone') }}</p>
    </div>

    <form v-else class="form" @submit.prevent="submit">
      <label>
        {{ t('auth.email') }}
        <input v-model="email" type="email" required autocomplete="email" />
      </label>
      <button class="btn-primary" type="submit" :disabled="submitting">{{ t('auth.sendResetLink') }}</button>
    </form>
  </div>
</template>

<style scoped>
.auth-view {
  padding: 16px;
}
.header {
  margin-bottom: 14px;
}
.page-title {
  font-size: 19px;
  text-align: center;
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
.done {
  text-align: center;
  padding: 24px 0;
  color: var(--text);
  font-size: 14px;
}
</style>
