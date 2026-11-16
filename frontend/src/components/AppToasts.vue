<template>
  <Teleport to="body">
    <TransitionGroup tag="div" name="toast" class="toasts">
      <div v-for="t in toasts" :key="t.id" class="toast" :class="t.kind" role="status">{{ t.message }}</div>
    </TransitionGroup>
  </Teleport>
</template>

<script setup>
import { toasts } from '../utils/toast'
</script>

<style>
.toasts { position: fixed; right: 20px; bottom: 20px; z-index: 2000; display: flex; flex-direction: column; gap: 8px; align-items: flex-end; pointer-events: none; }
.toast { background: #111827; color: #fff; border-radius: 8px; padding: 10px 16px 10px 14px; box-shadow: var(--shadow-lg); border-left: 4px solid rgba(255,255,255,.35); font-size: 13px; max-width: 420px; pointer-events: auto; }
.toast.error { background: #b91c1c; }
.toast.success { background: #15803d; }
.toast-enter-active, .toast-leave-active { transition: transform var(--t-med) var(--ease), opacity var(--t-med) var(--ease); }
.toast-enter-from { transform: translateX(40px); opacity: 0; }
.toast-leave-to { transform: translateY(16px); opacity: 0; }
</style>
