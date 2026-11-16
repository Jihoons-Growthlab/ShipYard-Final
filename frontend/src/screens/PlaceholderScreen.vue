<template>
  <PageHead :title="title" :readonly="!canWrite" />
</template>

<script setup>
// 아직 구현 전 화면(P3 규약): 제목과 조회 전용 배지만.
import PageHead from '../components/PageHead.vue'
defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })
</script>
