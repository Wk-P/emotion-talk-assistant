<script setup lang="ts">
import SiteFooter from '@/components/SiteFooter.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { errorStatus, MIN_PASSWORD_LENGTH, USERNAME_PATTERN } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { redirectTarget } from '@/utils/authRedirect'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)

async function submit() {
  error.value = null
  if (password.value !== confirmPassword.value) {
    error.value = t('auth.passwordMismatch')
    return
  }
  submitting.value = true
  try {
    await auth.register(username.value, password.value)
    router.push(redirectTarget(route))
  } catch (e: unknown) {
    const status = errorStatus(e)
    error.value =
      status === 409 ? t('auth.usernameTaken') : status === 422 ? t('auth.usernameRules') : t('auth.registerFailed')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-view">
    <SiteHeader />
    <main class="page-body">

    <div class="auth-split">
      <aside class="auth-intro">
        <img class="auth-intro-logo" src="/emotion-talk.png" alt="" />
        <div class="auth-intro-app">{{ t('app.title') }}</div>
        <h2>{{ t('welcome.title') }}</h2>
        <p>{{ t('welcome.body') }}</p>
      </aside>
      <div class="auth-card">
      <img class="logo" src="/emotion-talk.png" :alt="t('app.title')" />
      <h1>{{ t('auth.registerTitle') }}</h1>

      <form class="form" @submit.prevent="submit">
        <label>
          {{ t('auth.username') }}
          <input
            v-model="username"
            type="text"
            required
            :pattern="USERNAME_PATTERN"
            :title="t('auth.usernameRules')"
            autocomplete="username"
            autocapitalize="off"
            spellcheck="false"
          />
        </label>
        <p class="hint">{{ t('auth.usernameRules') }}</p>
        <label>
          {{ t('auth.password') }}
          <input v-model="password" type="password" required :minlength="MIN_PASSWORD_LENGTH" autocomplete="new-password" />
        </label>
        <p class="hint">{{ t('auth.passwordHint') }}</p>
        <label>
          {{ t('auth.confirmPassword') }}
          <input
            v-model="confirmPassword"
            type="password"
            required
            :minlength="MIN_PASSWORD_LENGTH"
            autocomplete="new-password"
          />
        </label>
        <p class="hint">{{ t('auth.noRecoveryHint') }}</p>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn-primary" type="submit" :disabled="submitting">{{ t('auth.register') }}</button>
      </form>

      <div class="links">
        <button type="button" class="btn-text" @click="router.push({ path: '/login', query: route.query })">{{ t('auth.haveAccount') }}</button>
      </div>
      </div>
    </div>
  </main>
    <SiteFooter />
  </div>
</template>

<style scoped>
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
