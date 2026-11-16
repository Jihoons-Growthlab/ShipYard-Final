<template>
  <span class="b" :class="'b-' + value">{{ kind === 'dwg' ? dwgStatusName(value) : planStatusName(value) }}</span>
</template>

<script setup>
import { planStatusName, dwgStatusName } from '../utils/status'
defineProps({ value: String, kind: { type: String, default: 'plan' } })
</script>
