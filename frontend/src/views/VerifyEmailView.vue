<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const status = ref<'pending' | 'ok' | 'error'>('pending')

onMounted(async () => {
  const token = String(route.query.token ?? '')
  if (!token) {
    status.value = 'error'
    return
  }
  try {
    await auth.verifyEmail(token)
    status.value = 'ok'
  } catch {
    status.value = 'error'
  }
})
</script>

<template>
  <div class="auth-view">
    <h1>{{ t('auth.verifyTitle') }}</h1>
    <p v-if="status === 'pending'">{{ t('auth.verifying') }}</p>
    <div v-else-if="status === 'ok'" class="done">
      <p>{{ t('auth.verifyOk') }}</p>
      <button class="btn-primary" type="button" @click="router.push('/login')">{{ t('auth.goLogin') }}</button>
    </div>
    <p v-else class="error">{{ t('auth.verifyError') }}</p>
  </div>
</template>

<style scoped>
.auth-view {
  padding: 24px 16px;
  text-align: center;
}
.done p {
  margin-bottom: 16px;
  color: var(--text);
  font-size: 14px;
}
.error {
  color: var(--danger);
  font-size: 14px;
}
</style>
