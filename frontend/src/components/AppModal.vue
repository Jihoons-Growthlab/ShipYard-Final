<template>
  <Teleport to="body">
    <div class="mbg" @mousedown.self="emit('close')">
      <div class="mpanel" :class="size" role="dialog" aria-modal="true" :aria-label="title">
        <header class="mhead">
          <span class="mtitle">{{ title }}</span>
          <button type="button" class="mclose" @click="emit('close')">닫기 ✕</button>
        </header>
        <div class="mbody"><slot /></div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { onMounted, onBeforeUnmount } from 'vue'

defineProps({ title: { type: String, default: '' }, size: { type: String, default: '' } })
const emit = defineEmits(['close'])

const stack = (globalThis.__swpModalStack ||= [])
const me = Symbol('modal')
function onKey(e) { if (e.key === 'Escape' && stack[stack.length - 1] === me) emit('close') }
onMounted(() => { stack.push(me); window.addEventListener('keydown', onKey) })
onBeforeUnmount(() => {
  const i = stack.indexOf(me); if (i >= 0) stack.splice(i, 1)
  window.removeEventListener('keydown', onKey)
})
</script>

<style>
.mbg { position: fixed; inset: 0; background: rgba(15,23,42,.55); backdrop-filter: blur(2px); z-index: 1000; display: flex; align-items: center; justify-content: center; animation: fade-in var(--t-fast) var(--ease); }
.mpanel { background: var(--bg); border-radius: 12px; box-shadow: var(--shadow-lg); width: 760px; max-width: 96vw; max-height: 94vh; display: flex; flex-direction: column; overflow: hidden; animation: pop-in var(--t-med) var(--ease); }
.mpanel.large { width: 1100px; max-width: 96vw; }
.mpanel.xl { width: min(1640px, 97vw); max-width: 97vw; height: 94vh; }
.mhead { background: var(--navy); color: #fff; padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; flex: none; }
.mtitle { font-size: 14px; font-weight: 700; }
.mclose { height: 22px; background: transparent; color: #fff; border: 1px solid #3b5a8c; border-radius: 5px; font: inherit; font-size: 12px; cursor: pointer; padding: 0 8px; }
.mclose:hover { background: rgba(255,255,255,.1); }
.mbody { padding: 14px 18px 20px; overflow: auto; flex: 1; }
</style>
