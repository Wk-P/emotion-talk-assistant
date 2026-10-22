<script setup lang="ts" generic="T extends string | number">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

// The one drop-down used everywhere, instead of the browser's own <select>
// (which can't be styled to the theme). Follows the WAI-ARIA "select-only
// combobox" pattern: a button that opens a listbox; keyboard: ↑ ↓ Home End
// to move, Enter / Space to pick, Esc / Tab to close, typing a letter jumps.
export interface SelectOption<V> {
  value: V
  label: string
  /** A second, muted line under the label (e.g. a persona's intro). */
  hint?: string
}

const props = withDefaults(
  defineProps<{
    options: SelectOption<T>[]
    ariaLabel?: string
    /** 'field' for forms and filters; 'pill' for the small round one in the chat header. */
    variant?: 'field' | 'pill'
    disabled?: boolean
  }>(),
  { ariaLabel: undefined, variant: 'field', disabled: false },
)
const model = defineModel<T>({ required: true })

const open = ref(false)
const active = ref(0)
// Opens upward when there isn't room below (e.g. near the bottom of the page).
const upward = ref(false)
const root = ref<HTMLElement | null>(null)
const list = ref<HTMLElement | null>(null)
const uid = `sel-${Math.random().toString(36).slice(2, 9)}`

const selectedIndex = computed(() => props.options.findIndex((o) => o.value === model.value))
const selectedLabel = computed(() => props.options[selectedIndex.value]?.label ?? '')

function show() {
  if (props.disabled || open.value) return
  active.value = Math.max(0, selectedIndex.value)
  const rect = root.value?.getBoundingClientRect()
  upward.value = !!rect && window.innerHeight - rect.bottom < 260 && rect.top > window.innerHeight - rect.bottom
  open.value = true
  nextTick(scrollActiveIntoView)
}
function hide() {
  open.value = false
}
function pick(i: number) {
  const o = props.options[i]
  if (o) model.value = o.value
  hide()
}
function scrollActiveIntoView() {
  list.value?.querySelector<HTMLElement>(`#${uid}-${active.value}`)?.scrollIntoView({ block: 'nearest' })
}
function move(to: number) {
  const n = props.options.length
  if (!n) return
  active.value = (to + n) % n
  nextTick(scrollActiveIntoView)
}

let typed = ''
let typedAt = 0
function typeAhead(ch: string) {
  const now = Date.now()
  typed = now - typedAt > 700 ? ch : typed + ch
  typedAt = now
  const start = open.value ? active.value + (typed.length === 1 ? 1 : 0) : selectedIndex.value + 1
  const n = props.options.length
  for (let k = 0; k < n; k++) {
    const i = (start + k) % n
    if (props.options[i]!.label.toLowerCase().startsWith(typed.toLowerCase())) {
      if (open.value) move(i)
      else model.value = props.options[i]!.value
      return
    }
  }
}

function onKeydown(e: KeyboardEvent) {
  if (props.disabled) return
  const k = e.key
  if (!open.value) {
    if (k === 'ArrowDown' || k === 'ArrowUp' || k === 'Enter' || k === ' ') {
      e.preventDefault()
      show()
    } else if (k.length === 1) typeAhead(k)
    return
  }
  if (k === 'ArrowDown') move(active.value + 1)
  else if (k === 'ArrowUp') move(active.value - 1)
  else if (k === 'Home') move(0)
  else if (k === 'End') move(props.options.length - 1)
  else if (k === 'Enter' || k === ' ') pick(active.value)
  else if (k === 'Escape') hide()
  else if (k === 'Tab') return hide()
  else if (k.length === 1) return typeAhead(k)
  else return
  e.preventDefault()
}

function onDocPointer(e: PointerEvent) {
  if (root.value && !root.value.contains(e.target as Node)) hide()
}
watch(open, (on) => {
  if (on) document.addEventListener('pointerdown', onDocPointer)
  else document.removeEventListener('pointerdown', onDocPointer)
})
onBeforeUnmount(() => document.removeEventListener('pointerdown', onDocPointer))
</script>

<template>
  <div ref="root" class="app-select" :class="[variant, { open, disabled }]">
    <button
      type="button"
      class="trigger"
      role="combobox"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-controls="`${uid}-list`"
      :aria-activedescendant="open ? `${uid}-${active}` : undefined"
      :aria-label="ariaLabel"
      :disabled="disabled"
      @click="open ? hide() : show()"
      @keydown="onKeydown"
    >
      <span class="value">{{ selectedLabel }}</span>
      <svg class="chevron" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
        <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </button>
    <Transition name="pop">
      <ul v-if="open" :id="`${uid}-list`" ref="list" class="menu" :class="{ upward }" role="listbox" :aria-label="ariaLabel">
        <li
          v-for="(o, i) in options"
          :id="`${uid}-${i}`"
          :key="String(o.value)"
          role="option"
          :aria-selected="o.value === model"
          :class="{ active: i === active, selected: o.value === model }"
          @pointerenter="active = i"
          @pointerdown.prevent
          @click.stop="pick(i)"
        >
          <span class="text">
            <span class="label">{{ o.label }}</span>
            <span v-if="o.hint" class="hint">{{ o.hint }}</span>
          </span>
          <svg v-if="o.value === model" class="check" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
            <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </li>
      </ul>
    </Transition>
  </div>
</template>

<style scoped>
.app-select {
  position: relative;
  display: inline-flex;
  min-width: 0;
}
.trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  min-width: 0;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-size: 13px;
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}
.trigger:hover:not(:disabled) {
  border-color: var(--accent);
}
.open .trigger {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}
.trigger:disabled {
  opacity: 0.55;
  cursor: default;
}
.value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chevron {
  flex-shrink: 0;
  color: var(--text-muted);
  transition: transform 0.15s ease;
}
.open .chevron {
  transform: rotate(180deg);
}

/* Small round one in the chat header. */
.pill .trigger {
  padding: 5px 10px 5px 12px;
  border-radius: 999px;
  font-size: 12.5px;
}

.menu {
  position: absolute;
  z-index: 60;
  top: calc(100% + 6px);
  left: 0;
  min-width: 100%;
  max-width: min(320px, 90vw);
  max-height: 280px;
  overflow-y: auto;
  margin: 0;
  padding: 4px;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  box-shadow: var(--shadow-md);
}
.menu.upward {
  top: auto;
  bottom: calc(100% + 6px);
}
/* The chat header's picker sits at the right edge: open toward the left. */
.pill .menu {
  left: auto;
  right: 0;
  min-width: 220px;
}
.menu li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text);
  cursor: pointer;
}
.menu li.active {
  background: var(--bg);
}
.menu li.selected {
  color: var(--accent);
  font-weight: 600;
}
.text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.label {
  white-space: nowrap;
}
.hint {
  font-size: 11.5px;
  font-weight: 400;
  color: var(--text-muted);
}
.check {
  flex-shrink: 0;
}

.pop-enter-active,
.pop-leave-active {
  transition:
    opacity 0.12s ease,
    transform 0.12s ease;
}
.pop-enter-from,
.pop-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
.upward.pop-enter-from,
.upward.pop-leave-to {
  transform: translateY(4px);
}
</style>
