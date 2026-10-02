import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // No separate landing page: '/' is the chat itself, with an informed-
    // notice dialog before every new conversation (components/ConsentDialog.vue).
    // Login is required for everything a participant does (no anonymous
    // use); help, privacy, contact and the auth pages stay public.
    { path: '/', name: 'chat', component: () => import('@/views/ChatView.vue'), meta: { requiresAuth: true } },
    { path: '/chat', redirect: '/' },
    { path: '/records', name: 'records', component: () => import('@/views/RecordsView.vue'), meta: { requiresAuth: true } },
    {
      path: '/reflection',
      name: 'reflection',
      component: () => import('@/views/ReflectionView.vue'),
      meta: { requiresAuth: true },
    },
    { path: '/history', name: 'history', component: () => import('@/views/HistoryView.vue'), meta: { requiresAuth: true } },
    { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') },
    { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue') },
    { path: '/help', name: 'help', component: () => import('@/views/HelpView.vue') },
    { path: '/privacy', name: 'privacy', component: () => import('@/views/PrivacyView.vue') },
    { path: '/contact', name: 'contact', component: () => import('@/views/ContactView.vue') },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
  ],
})

// `ready` guards against a race on hard refresh, where the store hasn't
// finished checking the stored token yet. After signing in, the login page
// sends the user back to `redirect`.
router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if ((to.name === 'login' || to.name === 'register') && auth.ready && auth.user) return { path: '/' }
  if (!to.meta.requiresAuth) return true
  if (!auth.ready) await auth.init()
  if (!auth.user) return { path: '/login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
  if (to.meta.requiresAdmin && auth.user.role === 'user') return { path: '/' }
  return true
})

export default router
