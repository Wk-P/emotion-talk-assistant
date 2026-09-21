import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { i18n } from './i18n'
import { detectLang } from './i18n/langPreference'
import router from './router'
import { useAuthStore } from './stores/auth'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)

// Otherwise every page renders in i18n's hardcoded 'zh' default until
// OnboardingView happens to mount and fix it — which never happens for a
// logged-in user landing straight on /chat, /history, etc. via a saved link.
i18n.global.locale.value = detectLang()

useAuthStore().init()

app.mount('#app')
