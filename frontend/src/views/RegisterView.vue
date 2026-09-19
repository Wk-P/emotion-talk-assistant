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
const confirmPassword = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)
const done = ref(false)

async function submit() {
  error.value = null
  if (password.value !== confirmPassword.value) {
    error.value = t('auth.passwordMismatch')
    return
  }
  submitting.value = true
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
      <button type="button" class="btn-back" @click="router.push('/')"><span class="arrow">&lt;</span> {{ t('auth.back') }}</button>
    </header>

    <div class="page-inner">
      <img v-if="!done" class="logo" src="/emotion-talk.png" :alt="t('app.title')" />
      <h1 v-if="!done">{{ t('auth.registerTitle') }}</h1>

      <div v-if="done" class="done">
        <p>{{ t('auth.registerDone') }}</p>
        <button class="btn-primary" type="button" @click="router.push('/login')">{{ t('auth.goLogin') }}</button>
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
        <label>
          {{ t('auth.confirmPassword') }}
          <input v-model="confirmPassword" type="password" required minlength="8" autocomplete="new-password" />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn-primary" type="submit" :disabled="submitting">{{ t('auth.register') }}</button>
      </form>

      <div v-if="!done" class="links">
        <button type="button" class="btn-text" @click="router.push('/login')">{{ t('auth.haveAccount') }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-view {
  padding: 16px;
}
@media (min-width: 640px) {
  .auth-view {
    padding: 32px;
  }
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
.hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: -8px;
}
.error {
  color: var(--danger);
  font-size: 13px;
}
.links {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
.done {
  text-align: center;
  padding: 24px 0;
}
.done p {
  margin-bottom: 16px;
  color: var(--text);
  font-size: 14px;
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
