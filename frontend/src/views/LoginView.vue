<script setup lang="ts">
import SiteFooter from '@/components/SiteFooter.vue'
import SiteHeader from '@/components/SiteHeader.vue'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { errorStatus } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { redirectTarget } from '@/utils/authRedirect'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const submitting = ref(false)
const error = ref<string | null>(null)

async function submit() {
  submitting.value = true
  error.value = null
  try {
    await auth.login(username.value, password.value)
    router.push(redirectTarget(route))
  } catch (e: unknown) {
    // Only a 401 means a wrong ID or password. Anything else (no response at
    // all, CORS refusal, server error) must not be reported as one.
    const status = errorStatus(e)
    error.value =
      status === 401 ? t('auth.loginFailed') : status === 403 ? t('auth.accountDisabled') : t('auth.loginUnavailable')
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
      <h1>{{ t('auth.loginTitle') }}</h1>
      <p class="login-required">{{ t('auth.loginRequired') }}</p>

      <form class="form" @submit.prevent="submit">
        <label>
          {{ t('auth.username') }}
          <input v-model="username" type="text" required autocomplete="username" autocapitalize="off" spellcheck="false" />
        </label>
        <label>
          {{ t('auth.password') }}
          <input v-model="password" type="password" required autocomplete="current-password" />
        </label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn-primary" type="submit" :disabled="submitting">{{ t('auth.login') }}</button>
      </form>

      <p class="forgot-hint">{{ t('auth.forgotHint') }}</p>
      <div class="links">
        <button type="button" class="btn-text" @click="router.push({ path: '/register', query: route.query })">{{ t('auth.needAccount') }}</button>
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
.error {
  color: var(--danger);
  font-size: 13px;
}
.login-required {
  margin: -8px 0 18px;
  font-size: 13.5px;
  line-height: 1.6;
  color: var(--text-muted);
}
.forgot-hint {
  margin-top: 14px;
  font-size: 12.5px;
  color: var(--text-muted);
  text-align: center;
}
.links {
  display: flex;
  justify-content: center;
  margin-top: 8px;
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
