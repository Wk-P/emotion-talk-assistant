import './assets/main.css'

import { createApp, watch } from 'vue'
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
// ConsentDialog happens to mount and fix it — which never happens for a
// visitor landing straight on /history, /help, etc. via a saved link.
i18n.global.locale.value = detectLang()

// Tab title, <html lang> and the description follow the UI language, so the
// browser, screen readers and search previews all see the right one.
watch(
  i18n.global.locale,
  (lang) => {
    document.documentElement.lang = lang === 'ko' ? 'ko' : lang === 'en' ? 'en' : 'zh-CN'
    document.title = i18n.global.t('app.title')
    document.querySelector('meta[name="description"]')?.setAttribute('content', i18n.global.t('site.description'))
  },
  { immediate: true },
)

useAuthStore().init()

app.mount('#app')
