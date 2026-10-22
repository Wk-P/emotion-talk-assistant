// Chinese web font for non-Apple devices (see --font-zh in assets/main.css).
import '@fontsource-variable/noto-sans-sc'
import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import { i18n } from './i18n'
import router from './router'
import { useAuthStore } from './stores/auth'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(i18n)

document.documentElement.lang = 'zh-CN'
document.title = i18n.global.t('app.title')
document.querySelector('meta[name="description"]')?.setAttribute('content', i18n.global.t('site.description'))

useAuthStore().init()

app.mount('#app')
