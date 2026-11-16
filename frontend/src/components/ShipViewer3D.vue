<template>
  <div class="v3d" :class="{ fleet: isFleet }">
    <div class="vwrap" :data-state="state" @contextmenu.prevent @pointerenter="inside = true" @pointerleave="inside = false">
      <canvas :id="canvasId" :key="attempt" ref="canvasEl" class="vcanvas" tabindex="-1"></canvas>
      <div v-if="state === 'loading'" class="vover">
        <div>3D 뷰어 불러오는 중…</div>
        <div class="vbar"><i :style="{ width: Math.round(progress * 100) + '%' }"></i></div>
      </div>
      <div v-else-if="state === 'error'" class="vover verr">
        <b>3D 뷰어를 불러오지 못했습니다.</b>
        <span class="vreason">{{ error }}</span>
        <button class="btn" type="button" @click="retry">재시도</button>
      </div>
      <div v-if="hoverInfo" class="vhover">
        <div class="vh-t">{{ hoverInfo.hull_no }} · {{ hoverInfo.hull_nm }}</div>
        <template v-if="isFleet">
          <div>{{ hoverSlot < 3 ? '드라이도크' : '안벽' }} · {{ codeName('HULLSTAT', hoverInfo.hull_status) }}</div>
          <div class="vh-kv">
            <span>진척률</span><span>{{ pctText(hoverInfo.progress) }}</span>
            <span>지연 공정</span><span>{{ hoverInfo.delay_count || 0 }}건</span>
            <span>인도 예정</span><span>{{ hoverInfo.delivery_dt || '미정' }}</span>
          </div>
          <div class="vh-f">클릭하여 상세 보기</div>
        </template>
        <div v-else>{{ codeName('HULLSTAT', hoverInfo.hull_status) }} · 진척률 {{ pctText(hoverInfo.progress) }}</div>
      </div>
    </div>

    <aside v-if="!isFleet" class="vside">
      <div class="card">
        <h3>호선 디지털 트윈</h3>
        <template v-if="hull">
          <div class="vname">{{ hull.hull_no }} · {{ hull.hull_nm }}</div>
          <div class="vkv">
            <span>상태</span><span>{{ codeName('HULLSTAT', hull.hull_status) }}</span>
            <span>도크</span><span>{{ hull.dock_no || '미지정' }}</span>
            <span>진척률</span><span>{{ pctText(hull.progress) }}</span>
            <span>지연 공정</span><span>{{ hull.delay_count || 0 }}건</span>
            <span>인도 예정</span><span>{{ hull.delivery_dt || '미정' }}</span>
          </div>
        </template>
        <div v-if="hullError" class="verr-t">호선 정보를 불러오지 못했습니다.</div>
        <button class="btn" type="button" :disabled="hullLoading" @click="loadHull">{{ hullLoading ? '조회 중…' : '호선 정보 새로고침' }}</button>
        <div class="muted vnote">가상 조선소 · 예시 선체 형상</div>
      </div>
      <div class="card">
        <h3>시점</h3>
        <div class="vviews">
          <button v-for="v in VIEW_BUTTONS" :key="v.k" class="btn" type="button" :disabled="state !== 'ready'" @click="setView(v.k)">{{ v.label }}</button>
        </div>
      </div>
      <div class="card">
        <h3>조작 안내</h3>
        <div class="vkv">
          <span>선체에 마우스</span><span>호선 정보</span>
          <span>왼쪽 드래그</span><span>회전</span>
          <span>휠</span><span>확대·축소</span>
          <span>오른쪽 드래그</span><span>화면 이동</span>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api/client'
import { codeName } from '../stores/session'
import { startViewer } from '../utils/unityViewer'

// 단일: hullNo. fleet: fleet(최대 6개 호선 배열), 슬롯 클릭 시 select(hull_no).
const props = defineProps({ hullNo: { type: String, default: null }, fleet: { type: Array, default: null } })
const emit = defineEmits(['select'])

const VIEW_BUTTONS = [{ k: 'front', label: '정면' }, { k: 'side', label: '측면' }, { k: 'top', label: '상단' }, { k: 'reset', label: '초기화' }]
let uid = (globalThis.__swpViewerUid = (globalThis.__swpViewerUid || 0) + 1)

const isFleet = computed(() => Array.isArray(props.fleet))
const attempt = ref(0)
const canvasId = computed(() => `shipviewer-${uid}-${attempt.value}`)
const canvasEl = ref(null)
const state = ref('loading')
const progress = ref(0)
const error = ref('')
const inside = ref(false)
const hullHover = ref(false)
const hoverSlot = ref(-1)
const hull = ref(null)
const hullLoading = ref(false)
const hullError = ref(false)
let handle = null
let unmounted = false

const pctText = (p) => (p === null || p === undefined ? '계획 없음' : `${p}%`)

const hoverInfo = computed(() => {
  if (state.value !== 'ready' || !inside.value) return null
  if (isFleet.value) return hoverSlot.value >= 0 ? props.fleet[hoverSlot.value] || null : null
  return hullHover.value ? hull.value : null
})

function onHover(e) { hullHover.value = !!e.detail }
function onFleetHover(e) { hoverSlot.value = Number(e.detail) }
function onSelect(e) {
  const h = props.fleet?.[Number(e.detail)]
  if (h) emit('select', h.hull_no)
}

function bind(c, on) {
  const f = on ? 'addEventListener' : 'removeEventListener'
  c[f]('shipviewer-hover', onHover)
  c[f]('shipyard-hover', onFleetHover)
  c[f]('shipyard-select', onSelect)
}

function sendFleet() { if (isFleet.value && handle) handle.send('SetFleet', props.fleet.length) }

async function start() {
  await nextTick()
  const c = canvasEl.value
  if (unmounted || !c) return
  state.value = 'loading'; progress.value = 0; error.value = ''
  hullHover.value = false; hoverSlot.value = -1
  bind(c, true)
  const h = startViewer(c, { onProgress: (p) => { if (handle === h) progress.value = p } })
  handle = h
  try {
    await h.ready
    if (handle !== h) return
    state.value = 'ready'
    sendFleet()
  } catch (e) {
    if (handle !== h || h.closed) return
    state.value = 'error'
    error.value = e.message
    h.stop()
  }
}

function stop() {
  const h = handle
  handle = null
  if (canvasEl.value) bind(canvasEl.value, false)
  return h ? h.stop() : Promise.resolve()
}

function retry() { stop(); attempt.value++; start() }
function setView(v) { if (state.value === 'ready') handle?.send('SetView', v) }

async function loadHull() {
  if (!props.hullNo) return
  hullLoading.value = true; hullError.value = false
  try { hull.value = await api.get(`/hulls/${props.hullNo}`) } catch { hullError.value = true } finally { hullLoading.value = false }
}

watch(() => (isFleet.value ? props.fleet.map((h) => h.hull_no).join(',') : null), () => { hoverSlot.value = -1; if (state.value === 'ready') sendFleet() })

onMounted(() => { if (!isFleet.value) loadHull(); start() })
onBeforeUnmount(() => { unmounted = true; stop() })
defineExpose({ state, setView, retry })
</script>

<style scoped>
.v3d { display: grid; grid-template-columns: 1fr 260px; gap: 12px; height: 100%; min-height: 0; }
.v3d.fleet { display: block; height: clamp(260px, 32vw, 410px); }
.vwrap { position: relative; border: 1px solid var(--card-line); border-radius: 8px; background: #dde4ee; overflow: hidden; min-height: 260px; height: 100%; }
.vcanvas { display: block; width: 100%; height: 100%; outline: none; }
.vover { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; background: rgba(221,228,238,.92); font-size: 13px; color: var(--ink); }
.vbar { width: 220px; height: 6px; border-radius: 3px; background: #c4cfdd; overflow: hidden; }
.vbar i { display: block; height: 100%; background: var(--pri, #2563eb); transition: width .2s; }
.verr b { font-size: 14px; }
.vreason { color: var(--muted); max-width: 80%; text-align: center; }
.vhover { position: absolute; left: 14px; top: 14px; background: #172a40; color: #fff; border-radius: 8px; padding: 10px 14px; font-size: 12.5px; line-height: 1.6; pointer-events: none; min-width: 170px; box-shadow: 0 6px 18px rgba(0,0,0,.25); }
.vh-t { font-weight: 700; font-size: 13.5px; }
.vh-kv { display: grid; grid-template-columns: auto 1fr; column-gap: 12px; margin-top: 4px; }
.vh-f { margin-top: 4px; }
.vside { display: flex; flex-direction: column; gap: 12px; min-height: 0; overflow: auto; }
.vside .card { margin: 0; }
.vside h3 { margin: 0 0 10px; font-size: 13px; }
.vname { font-size: 15px; font-weight: 700; margin-bottom: 10px; }
.vkv { display: grid; grid-template-columns: 1fr 1fr; row-gap: 6px; font-size: 12.5px; margin-bottom: 12px; }
.vkv:last-child { margin-bottom: 0; }
.vnote { font-size: 12.5px; margin-top: 12px; }
.verr-t { color: var(--danger, #dc2626); font-size: 12px; margin-bottom: 8px; }
.vviews { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 760px) {
  .v3d { grid-template-columns: 1fr; height: auto; }
  .v3d:not(.fleet) .vwrap { min-height: 260px; height: 60vh; }
  .vside { max-height: 40vh; }
  .v3d.fleet { height: clamp(210px, 50vw, 320px); }
}
</style>
