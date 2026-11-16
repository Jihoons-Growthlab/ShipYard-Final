<template>
  <Teleport to="body">
    <div v-if="preview.state.open && preview.state.anchor" class="hcard" :style="style"
         @mouseenter="preview.cardEnter" @mouseleave="preview.cardLeave">
      <slot :data="preview.state.data" :ctx="preview.state.ctx" :loading="preview.state.loading" :error="preview.state.error" :hkey="preview.state.key" />
    </div>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
// preview: useHoverPreview() 결과. width·height는 배치 기준 크기.
const props = defineProps({ preview: { type: Object, required: true }, width: { type: Number, default: 360 }, height: { type: Number, default: 300 } })

const style = computed(() => {
  const a = props.preview.state.anchor
  const vw = window.innerWidth, vh = window.innerHeight
  const left = Math.max(8, Math.min(a.x - 40, vw - props.width - 8))
  const s = { left: left + 'px', width: props.width + 'px' }
  if (vh - (a.bottom + 4) < props.height && a.top - 4 > vh - a.bottom) s.bottom = (vh - a.top + 4) + 'px'
  else s.top = (a.bottom + 4) + 'px'
  return s
})
</script>

<style>
.hcard { position: fixed; z-index: 900; background: #fff; border-radius: 10px; box-shadow: var(--shadow-lg); border: 1px solid var(--card-line);
  padding: 12px 14px; font-size: 12.5px; max-height: 70vh; overflow: auto; animation: rise-in var(--t-fast) var(--ease); }
</style>
