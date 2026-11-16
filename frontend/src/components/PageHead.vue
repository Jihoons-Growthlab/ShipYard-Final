<template>
  <div class="ph">
    <h2>{{ title }}</h2>
    <span v-if="readonly" class="ro-badge">조회 전용</span>
    <span v-if="desc" class="desc">{{ desc }}</span>
    <slot />
  </div>
</template>

<script setup>
defineProps({ title: String, desc: String, readonly: Boolean })
</script>
