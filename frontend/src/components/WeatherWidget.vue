<template>
  <div class="wx">
    <select v-model="region" class="wx-sel" aria-label="지역" @change="onRegion">
      <option v-for="r in REGIONS" :key="r" :value="r">{{ r }}</option>
    </select>
    <template v-if="loading && !data"><span>날씨 조회 중…</span></template>
    <template v-else-if="failed"><span>날씨 조회 실패</span></template>
    <template v-else-if="data">
      <span class="wx-ic">{{ icon(data.condition) }}</span>
      <b class="wx-t">{{ data.tempC }}℃</b>
      <span>{{ data.condition }}</span>
      <span class="wx-sub">습도 {{ data.humidity }}% · 바람 {{ data.windMs }}m/s</span>
      <span class="wx-badge" :class="data.source === 'LIVE' ? 'live' : 'sample'" :title="data.error || ''">{{ data.source === 'LIVE' ? 'LIVE' : '샘플' }}</span>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api/client'
import { REGIONS, REGION_KEY as KEY, weatherIcon } from '../utils/weather'

const readRegion = () => { try { const r = localStorage.getItem(KEY); return REGIONS.includes(r) ? r : '울산' } catch { return '울산' } }

const region = ref(readRegion())
const data = ref(null)
const loading = ref(false)
const failed = ref(false)
let seq = 0
let timer = null

const icon = weatherIcon

async function load() {
  const my = ++seq
  loading.value = true
  try {
    const res = await api.get('/weather', { region: region.value })
    if (my !== seq) return
    data.value = res; failed.value = false
  } catch {
    if (my !== seq) return
    failed.value = true
  } finally { if (my === seq) loading.value = false }
}
function onRegion() {
  try { localStorage.setItem(KEY, region.value) } catch { /* 무시 */ }
  data.value = null
  load()
}
onMounted(() => { load(); timer = setInterval(load, 600000) })
onBeforeUnmount(() => { seq++; clearInterval(timer) })
</script>

<style scoped>
.wx { display: flex; align-items: center; gap: 8px; background: var(--navy2); border-radius: 18px; padding: 4px 12px; font-size: 12px; white-space: nowrap; }
.wx-sel { height: 26px; background: var(--navy); color: #fff; border: 1px solid #3b5a8c; border-radius: 6px; font: inherit; padding: 0 4px; }
.wx-t { font-size: 14px; }
.wx-badge { font-size: 10.5px; font-weight: 700; border-radius: 9px; padding: 1px 7px; }
.wx-badge.sample { background: #f59e0b; color: #3b2600; }
.wx-badge.live { background: #22c55e; color: #052e16; }
@media (max-width: 1100px) { .wx-sub { display: none; } }
</style>
