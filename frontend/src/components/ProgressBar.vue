<template>
  <div class="pbar" role="progressbar" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100">
    <div class="pfill" :style="{ width: pct + '%' }"></div>
    <span class="plabel">{{ pct }}%</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ value: { type: Number, default: 0 } })
const pct = computed(() => Math.max(0, Math.min(100, Math.round(Number(props.value) || 0))))
</script>

<style>
.pbar { position: relative; height: 16px; border-radius: 8px; background: #e8ecf2; box-shadow: inset 0 1px 2px rgba(15,23,42,.08); min-width: 90px; overflow: hidden; }
.pfill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 8px; background: linear-gradient(90deg, #60a5fa, var(--pri)); transform-origin: left; animation: grow-x var(--t-slow) var(--ease); }
.plabel { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: 10.5px; font-weight: 700; color: #fff; text-shadow: 0 0 2px rgba(15,23,42,.7), 0 0 1px rgba(15,23,42,.9); }
</style>
