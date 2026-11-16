<template>
  <span class="chips">
    <span v-for="s in shown" :key="s" class="chip"><i v-if="dots" :style="{ background: STATUS_COLORS[s] }"></i>{{ name(s) }} {{ counts[s] }}</span>
  </span>
</template>

<script setup>
// 상태별 건수 칩(0 제외).
import { computed } from 'vue'
import { PLAN_STATUSES, DWG_STATUSES, STATUS_COLORS, planStatusName, dwgStatusName } from '../utils/status'
const props = defineProps({ counts: { type: Object, default: () => ({}) }, kind: { type: String, default: 'plan' }, dots: { type: Boolean, default: true } })
const order = computed(() => (props.kind === 'dwg' ? DWG_STATUSES : PLAN_STATUSES))
const shown = computed(() => order.value.filter((s) => props.counts?.[s]))
const name = (s) => (props.kind === 'dwg' ? dwgStatusName(s) : planStatusName(s))
</script>
