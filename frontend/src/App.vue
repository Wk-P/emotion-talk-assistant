<script setup lang="ts">
import { RouterView } from 'vue-router'
import SignOutOverlay from '@/components/SignOutOverlay.vue'
</script>

<template>
  <RouterView v-slot="{ Component }">
    <Transition name="route">
      <component :is="Component" />
    </Transition>
  </RouterView>
  <SignOutOverlay />
</template>
