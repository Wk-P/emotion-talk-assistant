<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const auth = useAuthStore()
</script>

<template>
  <Transition name="overlay">
    <div v-if="auth.signOutPhase !== 'idle'" class="overlay" role="status" aria-live="polite">
      <div class="badge" :class="auth.signOutPhase">
        <span v-if="auth.signOutPhase === 'leaving'" class="ring" aria-hidden="true" />
        <svg v-else class="check" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      </div>
      <Transition name="swap" mode="out-in">
        <p :key="auth.signOutPhase" class="label">
          {{ auth.signOutPhase === 'leaving' ? t('auth.signingOut') : t('auth.signedOut') }}
        </p>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 18px;
  background: rgba(246, 246, 251, 0.82);
  backdrop-filter: blur(10px);
}
.badge {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  box-shadow: var(--shadow-lg);
  transition: background 0.3s ease;
}
.badge.done {
  background: var(--accent);
  animation: pop 0.35s ease;
}
.ring {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 3px solid var(--accent-soft);
  border-top-color: var(--accent);
  animation: spin 0.8s linear infinite;
}
.check {
  width: 30px;
  height: 30px;
  fill: none;
  stroke: #fff;
  stroke-width: 2.6;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 24;
  stroke-dashoffset: 24;
  animation: draw 0.4s 0.08s ease forwards;
}
.label {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  letter-spacing: 0.01em;
}

.overlay-enter-active,
.overlay-leave-active {
  transition: opacity 0.3s ease;
}
.overlay-enter-active .badge,
.overlay-leave-active .badge {
  transition: transform 0.3s ease;
}
.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}
.overlay-enter-from .badge {
  transform: scale(0.8);
}
.overlay-leave-to .badge {
  transform: scale(1.08);
}
.swap-enter-active,
.swap-leave-active {
  transition:
    opacity 0.18s ease,
    transform 0.18s ease;
}
.swap-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.swap-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes draw {
  to {
    stroke-dashoffset: 0;
  }
}
@keyframes pop {
  0% {
    transform: scale(0.85);
  }
  60% {
    transform: scale(1.08);
  }
  100% {
    transform: scale(1);
  }
}
@media (prefers-reduced-motion: reduce) {
  .ring,
  .check,
  .badge.done {
    animation: none;
  }
  .check {
    stroke-dashoffset: 0;
  }
}
</style>
