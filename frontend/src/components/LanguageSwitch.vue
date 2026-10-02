<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { Language } from '@/api/client'
import { saveLang } from '@/i18n/langPreference'
import { useSessionStore } from '@/stores/session'

// The one language control used everywhere (chat sidebar, site header,
// mobile menu): switches the interface at once, remembers the choice, and
// moves an ongoing conversation over to the new language too.
withDefaults(defineProps<{ showLabel?: boolean }>(), { showLabel: false })

const { t, locale } = useI18n()
const session = useSessionStore()

const LANGS: { id: Language; label: string }[] = [
  { id: 'zh', label: '中文' },
  { id: 'ko', label: '한국어' },
]

function choose(lang: Language) {
  if (locale.value === lang) return
  locale.value = lang
  saveLang(lang)
  // Best effort: the interface has already switched even if this fails.
  session.setLanguage(lang).catch(() => {})
}
</script>

<template>
  <div class="lang-switch">
    <span v-if="showLabel" class="lang-label">{{ t('toolbar.language') }}</span>
    <div class="lang-options" role="radiogroup" :aria-label="t('toolbar.language')">
      <button
        v-for="l in LANGS"
        :key="l.id"
        type="button"
        role="radio"
        :aria-checked="locale === l.id"
        :class="{ on: locale === l.id }"
        @click="choose(l.id)"
      >
        {{ l.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.lang-switch {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.lang-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}
.lang-options {
  display: flex;
  padding: 3px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--bg);
}
.lang-options button {
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
.lang-options button.on {
  background: var(--surface);
  color: var(--accent);
  box-shadow: var(--shadow-sm);
}
.lang-options button:not(.on):hover {
  color: var(--text);
}
</style>
