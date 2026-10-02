import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // No separate landing page: '/' is the chat itself, with an informed-
    // notice dialog before every new conversation (components/ConsentDialog.vue).
    // Anonymous (device_id-scoped) use is allowed here — see app/api/session.py.
    { path: '/', name: 'chat', component: () => import('@/views/ChatView.vue') },
    { path: '/chat', redirect: '/' },
    { path: '/records', name: 'records', component: () => import('@/views/RecordsView.vue') },
    { path: '/history', name: 'history', component: () => import('@/views/HistoryView.vue') },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue') },
    { path: '/help', name: 'help', component: () => import('@/views/HelpView.vue') },
    { path: '/privacy', name: 'privacy', component: () => import('@/views/PrivacyView.vue') },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
  ],
})

// Only /admin still requires a login. `ready` guards against a race on hard
// refresh, where the store hasn't finished checking the stored token yet.
router.beforeEach(async (to) => {
  if (!to.meta.requiresAuth) return true
  const auth = useAuthStore()
  if (!auth.ready) await auth.init()
  if (!auth.user) return { path: '/login' }
  if (to.meta.requiresAdmin && auth.user.role === 'user') return { path: '/' }
  return true
})

export default router
