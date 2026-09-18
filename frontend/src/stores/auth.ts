import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { AuthUser } from '@/api/client'
import {
  fetchMe,
  forgotPassword as apiForgotPassword,
  getAuthToken,
  login as apiLogin,
  register as apiRegister,
  resetPassword as apiResetPassword,
  setAuthToken,
  verifyEmail as apiVerifyEmail,
} from '@/api/client'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const ready = ref(false)

  async function init() {
    if (getAuthToken()) {
      try {
        user.value = await fetchMe()
      } catch {
        setAuthToken(null)
        user.value = null
      }
    }
    ready.value = true
  }

  async function login(email: string, password: string) {
    const res = await apiLogin(email, password)
    setAuthToken(res.access_token)
    user.value = res.user
  }

  async function register(email: string, password: string) {
    return apiRegister(email, password)
  }

  async function verifyEmail(token: string) {
    return apiVerifyEmail(token)
  }

  async function forgotPassword(email: string) {
    return apiForgotPassword(email)
  }

  async function resetPassword(token: string, newPassword: string) {
    return apiResetPassword(token, newPassword)
  }

  function logout() {
    setAuthToken(null)
    user.value = null
  }

  return { user, ready, init, login, register, verifyEmail, forgotPassword, resetPassword, logout }
})
