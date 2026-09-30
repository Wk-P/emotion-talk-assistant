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
  // Drives the full-screen sign-out transition (components/SignOutOverlay.vue):
  // 'leaving' while it fades in, 'done' once signed out (check mark), then
  // back to 'idle' as it fades away.
  const signOutPhase = ref<'idle' | 'leaving' | 'done'>('idle')

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

  // Signing out is instant; this just paces it so it reads as a deliberate
  // step instead of the page silently flipping. `afterSignOut` runs while
  // the overlay covers the screen (clear the open chat, navigate).
  async function signOut(afterSignOut: () => unknown) {
    if (signOutPhase.value !== 'idle') return
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const wait = (ms: number) => new Promise((r) => setTimeout(r, reduced ? Math.min(ms, 150) : ms))
    signOutPhase.value = 'leaving'
    await wait(450)
    logout()
    await afterSignOut()
    signOutPhase.value = 'done'
    await wait(800)
    signOutPhase.value = 'idle'
  }

  return {
    user,
    ready,
    signOutPhase,
    init,
    login,
    register,
    verifyEmail,
    forgotPassword,
    resetPassword,
    logout,
    signOut,
  }
})
