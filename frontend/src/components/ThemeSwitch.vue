<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

// Dark / light, chosen by hand (dark by default, not the device setting).
// index.html applies the saved choice before the page renders; this keeps
// it in localStorage ("theme") and switches <html data-theme> at once.
type Theme = 'dark' | 'light'
const THEME_COLOR: Record<Theme, string> = { dark: '#2e3440', light: '#5e81ac' }

const { t } = useI18n()
const theme = ref<Theme>(document.documentElement.dataset.theme === 'light' ? 'light' : 'dark')

function choose(next: Theme) {
  if (theme.value === next) return
  theme.value = next
  document.documentElement.dataset.theme = next
  document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[next])
  try {
    localStorage.setItem('theme', next)
  } catch {
    // Private mode / storage blocked: the switch still works for this visit.
  }
}
</script>

<template>
  <div class="theme-switch">
    <span class="theme-label">{{ t('toolbar.theme') }}</span>
    <div class="theme-options" role="radiogroup" :aria-label="t('toolbar.theme')">
      <button
        v-for="id in ['dark', 'light'] as const"
        :key="id"
        type="button"
        role="radio"
        :aria-checked="theme === id"
        :class="{ on: theme === id }"
        @click="choose(id)"
      >
        {{ id === 'dark' ? t('toolbar.themeDark') : t('toolbar.themeLight') }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.theme-switch {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.theme-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}
.theme-options {
  display: flex;
  padding: 3px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg);
}
.theme-options button {
  flex: 1;
  border: none;
  background: transparent;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-muted);
  white-space: nowrap;
}
.theme-options button.on {
  background: var(--surface);
  color: var(--accent);
  box-shadow: var(--shadow-sm);
}
.theme-options button:not(.on):hover {
  color: var(--text);
}
</style>
