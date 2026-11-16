<template>
  <div class="plan-screen">
    <PageHead :title="title" :readonly="!canWrite" desc="막대 또는 좌측 공정명을 클릭하면 아래에 상세·수정 패널이 열립니다." />
    <div class="toolbar">
      <select v-model="hullNo" class="inp w165" aria-label="호선" @change="onHullChange">
        <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
      </select>
      <select v-model="blockId" class="inp w128" aria-label="블록">
        <option value="">블록 전체</option>
        <option v-for="b in blocks" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm }}</option>
      </select>
      <select v-model.number="scale" class="inp w110" aria-label="배율">
        <option v-for="s in SCALES" :key="s.value" :value="s.value">{{ s.label }}</option>
      </select>
      <span>호선 진척</span>
      <div class="w170"><ProgressBar :value="hullProgress ?? 0" /></div>
      <div class="grow"></div>
      <button v-if="canWrite" class="btn pri" type="button" @click="openNew">+ 공정 추가</button>
    </div>
    <div class="legend">
      <span v-for="s in PLAN_STATUSES" :key="s" class="lg"><i class="sw" :style="{ background: STATUS_COLORS[s] }"></i>{{ planStatusName(s) }}</span>
      <span class="lg">📐 도면 대기</span>
      <span class="lg"><i class="sw sat"></i>토요일</span>
      <span class="lg"><i class="sw sun"></i>일요일·공휴일</span>
      <span class="muted">— 선후행 연결선 / 빨간선 = 오늘({{ today }})</span>
    </div>

    <div ref="scroller" class="g-scroll">
      <div v-if="!rows.length && loaded" class="g-empty muted">표시할 공정이 없습니다.</div>
      <div v-else-if="layout" class="g-inner" :style="{ width: layout.width + 'px' }">
        <div class="g-head">
          <div class="g-corner">블록 / 공정</div>
          <div class="g-months" :style="{ width: layout.timelineWidth + 'px' }">
            <div v-for="m in monthList" :key="m.key" class="g-month" :style="{ left: m.x + 'px', width: m.w + 'px' }">{{ m.label }}</div>
            <div v-for="o in holidayMarks" :key="'h' + o.date" class="g-hmark" :style="{ left: o.x + 'px', width: Math.max(scale, 3) + 'px' }" :title="`${o.date} ${o.name}`"></div>
          </div>
        </div>
        <div class="g-body" :style="{ height: rows.length * ROW_H + 'px' }">
          <div class="g-bg" :style="{ left: LEFT + 'px', width: layout.timelineWidth + 'px' }">
            <div v-for="o in offList" :key="o.date" class="g-off" :class="o.kind" :style="{ left: o.x + 'px', width: scale + 'px' }"></div>
            <div v-for="m in monthList" :key="'b' + m.key" class="g-mline" :style="{ left: m.x + 'px' }"></div>
          </div>
          <div class="g-today" :style="{ left: LEFT + todayX + 'px' }"><span class="g-today-lbl">오늘</span></div>
          <svg class="g-deps" :width="layout.timelineWidth" :height="rows.length * ROW_H" :style="{ left: LEFT + 'px' }" aria-hidden="true">
            <defs>
              <marker id="g-arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#64748b" /></marker>
              <marker id="g-arr-hl" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#2563eb" /></marker>
            </defs>
            <path v-for="p in pathsNormal" :key="p.from + '-' + p.to" :d="p.d" class="dep" marker-end="url(#g-arr)" />
            <path v-for="p in pathsHl" :key="'hl' + p.from + '-' + p.to" :d="p.d" class="dep hl" marker-end="url(#g-arr-hl)" />
          </svg>
          <div v-for="p in rows" :key="p.plan_id" class="g-row" :class="{ hov: hoverId === p.plan_id, sel: selectedId === p.plan_id, rel: related.has(p.plan_id) }"
               @mouseenter="hoverId = p.plan_id" @mouseleave="hoverId = null">
            <div class="g-label" @click="select(p)"><span class="muted bc">{{ p.block_cd || '호선' }}</span>{{ p.proc_nm }}<span v-if="p.drawing_wait"> 📐</span></div>
            <div class="g-track">
              <div class="bar" :class="{ sel: selectedId === p.plan_id, dragging: drag.id === p.plan_id && drag.moved, rw: canWrite }"
                   :style="barStyle(p)" role="button" :aria-label="ariaOf(p)"
                   @pointerdown="startDrag($event, p)" @click="onBarClick(p)"
                   @mouseenter="preview.enter(p.plan_id, $event, p)" @mouseleave="preview.leave()">
                <div class="fill" :style="{ width: Math.min(100, p.progress_rate) + '%' }"></div>
                <template v-if="canWrite"><span class="hd l"></span><span class="hd r"></span></template>
                <span v-if="drag.id === p.plan_id && drag.moved" class="drag-lbl">{{ drag.start }} ~ {{ drag.end }}</span>
              </div>
              <span class="plbl" :style="{ left: geomOf(p).left + geomOf(p).width + 6 + 'px' }">{{ Math.round(p.progress_rate) }}%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <PlanPanel v-if="panel" :hull-no="hullNo" :plan="panel === 'new' ? null : selectedPlan" :plans="plans" :blocks="blocks" :procs="procs" :users="users"
               :can-write="canWrite" :default-block-id="blockId" :today="today" @close="closePanel" @saved="onSaved" @deleted="onDeleted" />

    <HoverCard :preview="preview" :width="400" :height="380">
      <template #default="{ data, ctx: p, loading }">
        <div v-if="p" class="pv">
          <div class="pvh">{{ p.label }} <StatusBadge :value="p.plan_status" /><span v-if="p.drawing_wait">📐</span></div>
          <div class="pvr">
            <span class="k">계획</span><span>{{ p.plan_start_dt }} ~ {{ p.plan_end_dt }} ({{ diffDays(p.plan_end_dt, p.plan_start_dt) + 1 }}일)</span>
            <span class="k">실제</span><span>{{ p.actual_start_dt || '-' }} ~ {{ p.actual_end_dt || '-' }}</span>
            <span class="k">진척</span><ProgressBar :value="p.progress_rate" />
            <template v-if="overdue(p) > 0"><span></span><span class="od">종료 예정일 {{ overdue(p) }}일 경과</span></template>
            <span class="k">담당자</span><span>{{ p.manager_nm || '미지정' }}</span>
            <span class="k">선행</span><span>{{ labelsOf(p.pred_plan_ids) || '-' }}</span>
            <span class="k">후행</span><span>{{ labelsOf(succOf(p.plan_id)) || '-' }}</span>
            <template v-if="p.remark"><span class="k">비고</span><span class="pre">{{ p.remark }}</span></template>
          </div>
          <div v-if="p.blockers?.length" class="note warn">📐 도면 대기: 필수 도면 {{ p.blockers.map((b) => `${b.drawing_no}(${dwgStatusName(b.dwg_status)})`).join(', ') }} 미배포 → 착수 불가</div>
          <div v-if="loading" class="pvm">불러오는 중…</div>
          <table v-else-if="data && data.links.length" class="pvt">
            <thead><tr><th>연계 도면</th><th>상태</th><th>필수</th></tr></thead>
            <tbody><tr v-for="l in data.links" :key="l.drawing_id"><td>{{ l.drawing_no }}</td>
              <td><StatusBadge :value="l.dwg_status" kind="dwg" /> <span v-if="!l.has_issued" class="b b-warn">미배포</span></td>
              <td>{{ l.required ? '필수' : '참고' }}</td></tr></tbody>
          </table>
          <div class="pvf">{{ canWrite ? '클릭하면 수정 패널이 열리고, 끌면 일정을 옮깁니다.' : '클릭하면 상세 패널이 열립니다.' }}</div>
        </div>
      </template>
    </HoverCard>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api/client'
import { toast, toastError } from '../utils/toast'
import { useHoverPreview } from '../utils/hoverPreview'
import { PLAN_STATUSES, STATUS_COLORS, planStatusName, dwgStatusName } from '../utils/status'
import { diffDays } from '../utils/date'
import { LEFT, ROW_H, SCALES, ganttLayout, months, barGeom, dragDates, depPaths } from '../utils/gantt'
import { offDays } from '../utils/holidays'
import PageHead from '../components/PageHead.vue'
import ProgressBar from '../components/ProgressBar.vue'
import HoverCard from '../components/HoverCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import PlanPanel from './PlanPanel.vue'

const props = defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })

const hulls = ref([])
const hullNo = ref('')
const blockId = ref('')
const scale = ref(4)
const blocks = ref([])
const procs = ref([])
const users = ref([])
const plans = ref([])
const deps = ref([])
const today = ref('')
const hullProgress = ref(null)
const loaded = ref(false)
const selectedId = ref(null)
const hoverId = ref(null)
const panel = ref(null) // null | 'edit' | 'new'
const scroller = ref(null)
const drag = reactive({ id: null, mode: null, x0: 0, moved: false, start: null, end: null, plan: null })
let suppressClick = false

const preview = useHoverPreview((id) => api.get(`/plans/${id}/drawings`))

const rows = computed(() => (blockId.value === '' ? plans.value : plans.value.filter((p) => p.block_id === blockId.value)))
const byId = computed(() => new Map(plans.value.map((p) => [p.plan_id, p])))
const layout = computed(() => (today.value ? ganttLayout(rows.value, today.value, scale.value) : null))
const monthList = computed(() => (layout.value ? months(layout.value) : []))
const offList = computed(() => (layout.value ? offDays(layout.value, scale.value) : []))
const holidayMarks = computed(() => offList.value.filter((o) => o.kind === 'hol'))
const todayX = computed(() => (layout.value ? layout.value.x(today.value) : 0))
const paths = computed(() => (layout.value ? depPaths(rows.value, deps.value, layout.value) : []))
const focusId = computed(() => hoverId.value ?? selectedId.value)
const pathsHl = computed(() => paths.value.filter((p) => p.from === focusId.value || p.to === focusId.value))
const pathsNormal = computed(() => paths.value.filter((p) => !(p.from === focusId.value || p.to === focusId.value)))
const related = computed(() => new Set(pathsHl.value.flatMap((p) => [p.from, p.to]).filter((id) => id !== focusId.value)))
const selectedPlan = computed(() => byId.value.get(selectedId.value) || null)

const succOf = (id) => deps.value.filter((d) => d.pred_plan_id === id).map((d) => d.plan_id)
const labelsOf = (ids) => (ids || []).map((id) => byId.value.get(id)?.label).filter(Boolean).join(', ')
const overdue = (p) => (p.plan_status !== 'DONE' && today.value > p.plan_end_dt ? diffDays(today.value, p.plan_end_dt) : 0)
const ariaOf = (p) => `${p.label} ${p.plan_start_dt} ~ ${p.plan_end_dt} 진척 ${Math.round(p.progress_rate)}% ${planStatusName(p.plan_status)}${p.drawing_wait ? ' 도면 대기' : ''}`

function geomOf(p) {
  const d = drag.id === p.plan_id && drag.moved ? drag : null
  return barGeom(d ? d.start : p.plan_start_dt, d ? d.end : p.plan_end_dt, layout.value)
}
function barStyle(p) {
  const g = geomOf(p)
  return { left: g.left + 'px', width: g.width + 'px', '--c': STATUS_COLORS[p.plan_status] }
}

async function loadPlans({ keepScroll = true } = {}) {
  if (!hullNo.value) { loaded.value = true; return }
  const sl = scroller.value?.scrollLeft ?? 0
  try {
    const res = await api.get(`/hulls/${hullNo.value}/plans`)
    plans.value = res.plans; deps.value = res.deps; today.value = res.today; hullProgress.value = res.hull_progress
    loaded.value = true
    preview.clear()
    await nextTick()
    if (!scroller.value) return
    if (keepScroll) scroller.value.scrollLeft = sl
    else scroller.value.scrollLeft = Math.max(0, todayX.value - 0.4 * (scroller.value.clientWidth - LEFT))
  } catch (e) { toastError(e) }
}

async function loadHullData() {
  try { blocks.value = hullNo.value ? await api.get(`/hulls/${hullNo.value}/blocks`) : [] } catch (e) { toastError(e) }
  await loadPlans({ keepScroll: false })
}

function onHullChange() {
  blockId.value = ''; selectedId.value = null; panel.value = null
  loadHullData()
}

function applyParam() {
  if (props.param && hulls.value.some((h) => h.hull_no === String(props.param))) {
    hullNo.value = String(props.param)
    onHullChange()
  }
}

function select(p) { selectedId.value = p.plan_id; panel.value = 'edit' }
function onBarClick(p) { if (suppressClick) return; select(p) }
function openNew() { selectedId.value = null; panel.value = 'new' }
function closePanel() { panel.value = null; selectedId.value = null }
async function onSaved(id) { await loadPlans(); if (id) { selectedId.value = id; panel.value = 'edit' } }
async function onDeleted() { closePanel(); await loadPlans() }

function startDrag(e, p) {
  if (!props.canWrite || e.button !== 0) return
  const r = e.currentTarget.getBoundingClientRect()
  const off = e.clientX - r.left
  Object.assign(drag, { id: p.plan_id, plan: p, mode: off <= 6 ? 'start' : off >= r.width - 6 ? 'end' : 'move', x0: e.clientX, moved: false, start: p.plan_start_dt, end: p.plan_end_dt })
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', onUp)
  e.preventDefault()
}
function onMove(e) {
  const dx = e.clientX - drag.x0
  if (!drag.moved && Math.abs(dx) > 3) { drag.moved = true; preview.setDisabled(true) }
  if (drag.moved) Object.assign(drag, dragDates(drag.plan.plan_start_dt, drag.plan.plan_end_dt, drag.mode, dx, scale.value))
}
function endListeners() { window.removeEventListener('pointermove', onMove); window.removeEventListener('pointerup', onUp) }
function resetDrag() { Object.assign(drag, { id: null, plan: null, moved: false }); preview.setDisabled(false) }
async function onUp() {
  endListeners()
  if (!drag.moved) { resetDrag(); return }
  suppressClick = true
  setTimeout(() => { suppressClick = false }, 0)
  const p = drag.plan
  if (drag.start === p.plan_start_dt && drag.end === p.plan_end_dt) { resetDrag(); return }
  await saveSchedule(p, drag.start, drag.end)
}

async function saveSchedule(p, start, end) {
  const send = (c) => api.patch(`/plans/${p.plan_id}/schedule`, { plan_start_dt: start, plan_end_dt: end, confirm_late_preds: c })
  try {
    let res
    try { res = await send(false) } catch (e) {
      if (e.status !== 409) throw e
      if (!confirm(e.message)) { resetDrag(); return }
      res = await send(true)
    }
    const n = res.shifted_plan_ids?.length || 0
    toast(n ? `저장되었습니다. 후행 공정 ${n}건의 일정이 함께 조정되었습니다.` : '저장되었습니다.', 'success')
    await loadPlans()
  } catch (e) { toastError(e) }
  resetDrag()
}

watch(() => props.ctx, applyParam)

onMounted(async () => {
  try {
    const [h, pr, us] = await Promise.all([api.get('/plan-hulls'), api.get('/procs'), api.get('/users/options')])
    hulls.value = h; procs.value = pr; users.value = us
    const fromParam = props.param && h.find((x) => x.hull_no === String(props.param))
    hullNo.value = fromParam ? fromParam.hull_no : (h.find((x) => x.plan_count > 0) || h[0])?.hull_no || ''
    await loadHullData()
  } catch (e) { toastError(e) }
})
onBeforeUnmount(endListeners)

defineExpose({ hullNo, blockId, scale, rows, select, saveSchedule })
</script>

<style scoped>
.plan-screen { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.w165 { width: 165px; } .w128 { width: 128px; } .w110 { width: 110px; } .w170 { width: 170px; }
.legend { display: flex; align-items: center; gap: 12px; font-size: 12px; margin: -2px 0 10px; flex-wrap: wrap; }
.lg { display: inline-flex; align-items: center; gap: 4px; }
.sw { width: 12px; height: 10px; border-radius: 2px; display: inline-block; }
.sw.sat { background: rgba(100,116,139,.13); border: 1px solid rgba(100,116,139,.25); }
.sw.sun { background: rgba(220,38,38,.12); border: 1px solid rgba(220,38,38,.2); }
.g-scroll { flex: 1; min-height: 140px; overflow: auto; background: #fff; border: 1px solid var(--card-line); border-radius: 8px; box-shadow: var(--shadow-sm); position: relative; }
.g-empty { padding: 30px; text-align: center; }
.g-inner { position: relative; }
.g-head { position: sticky; top: 0; z-index: 8; display: flex; height: 34px; background: var(--head); border-bottom: 1px solid var(--line); }
.g-corner { position: sticky; left: 0; z-index: 9; width: 230px; flex: none; background: var(--head); padding: 0 10px; display: flex; align-items: center; font-weight: 600; color: #374151; border-right: 1px solid var(--line); }
.g-months { position: relative; flex: none; height: 100%; }
.g-month { position: absolute; top: 0; height: 100%; padding: 6px 6px 0; font-size: 11px; font-weight: 600; color: #475569; border-left: 1px solid var(--line); white-space: nowrap; overflow: hidden; }
.g-hmark { position: absolute; bottom: 0; height: 6px; background: #ef4444; border-radius: 1px; }
.g-body { position: relative; }
.g-bg { position: absolute; top: 0; bottom: 0; z-index: 0; pointer-events: none; }
.g-off { position: absolute; top: 0; bottom: 0; }
.g-off.sat { background: rgba(100,116,139,.13); }
.g-off.sun, .g-off.hol { background: rgba(220,38,38,.07); }
.g-mline { position: absolute; top: 0; bottom: 0; border-left: 1px dashed var(--line); }
.g-today { position: absolute; top: 0; bottom: 0; width: 2px; margin-left: -1px; background: #dc2626; box-shadow: 0 0 4px rgba(220,38,38,.6); z-index: 5; pointer-events: none; }
.g-today-lbl { position: absolute; top: 2px; left: 50%; transform: translateX(-50%); background: #dc2626; color: #fff; font-size: 10px; font-weight: 700; border-radius: 8px; padding: 0 5px; white-space: nowrap; }
.g-deps { position: absolute; top: 0; z-index: 2; pointer-events: none; overflow: visible; }
.dep { fill: none; stroke: #64748b; stroke-width: 1; opacity: .5; stroke-linejoin: round; }
.dep.hl { stroke: var(--pri); stroke-width: 1.6; opacity: 1; }
.g-row { display: flex; height: 28px; border-bottom: 1px solid var(--line2); transition: background var(--t-fast) var(--ease); }
.g-row.hov, .g-row.rel { background: rgba(219,234,254,.45); }
.g-row.sel { background: rgba(219,234,254,.85); }
.g-label { position: sticky; left: 0; z-index: 6; width: 230px; flex: none; background: #fff; padding: 0 10px; display: flex; align-items: center; gap: 12px; cursor: pointer; border-right: 1px solid var(--line); white-space: nowrap; overflow: hidden; }
.g-row.hov .g-label, .g-row.rel .g-label { background: #f1f6ff; }
.g-row.sel .g-label { background: var(--sel); }
.bc { width: 28px; }
.g-track { position: relative; flex: 1; }
.bar { position: absolute; top: 6px; height: 16px; border-radius: 5px; z-index: 3; overflow: hidden; cursor: pointer;
  background: color-mix(in srgb, var(--c) 28%, white); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--c) 45%, transparent), var(--shadow-sm);
  transition: left var(--t-med) var(--ease), width var(--t-med) var(--ease), transform var(--t-fast) var(--ease), box-shadow var(--t-fast) var(--ease); touch-action: none; user-select: none; }
.bar.rw { cursor: grab; }
.bar:hover { transform: translateY(-1px); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--c) 45%, transparent), 0 3px 8px color-mix(in srgb, var(--c) 40%, transparent); }
.bar.sel { box-shadow: 0 0 0 2px #fff, 0 0 0 4px var(--c); overflow: visible; }
.bar.dragging { transition: none; cursor: grabbing; overflow: visible; box-shadow: 0 6px 16px color-mix(in srgb, var(--c) 45%, transparent); }
.fill { position: absolute; left: 0; top: 0; bottom: 0; border-radius: 5px; background: linear-gradient(color-mix(in srgb, var(--c) 75%, white), var(--c)); transform-origin: left; animation: grow-x var(--t-slow) var(--ease); }
.hd { position: absolute; top: 0; bottom: 0; width: 6px; cursor: ew-resize; z-index: 1; }
.hd.l { left: 0; } .hd.r { right: 0; }
.hd:hover { background: var(--c); box-shadow: inset 2px 0 0 transparent; }
.hd:hover::after { content: ''; position: absolute; left: 2.5px; top: 4px; bottom: 4px; width: 1px; background: #fff; }
.drag-lbl { position: absolute; bottom: 20px; left: 0; background: #1f2937; color: #fff; font-size: 11px; padding: 1px 6px; border-radius: 4px; white-space: nowrap; z-index: 7; }
.plbl { position: absolute; top: 7px; font-size: 10px; color: var(--muted); z-index: 3; pointer-events: none; opacity: 0; transition: opacity var(--t-fast) var(--ease); }
.g-row.hov .plbl, .g-row.sel .plbl, .g-row.rel .plbl { opacity: 1; }
.od { color: var(--err); font-weight: 600; }
.pre { white-space: pre-wrap; }
</style>
