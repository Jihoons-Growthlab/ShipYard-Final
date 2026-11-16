<template>
  <div class="dash">
    <PageHead :title="title" :desc="s ? `기준일 ${s.today} · 호선/공정/도면 현황` : ''" />
    <section v-if="flows.length" class="card flow">
      <h3>업무 흐름</h3>
      <div class="row"><button v-for="f in flows" :key="f.token" class="btn" type="button" @click="openManual?.(f.token)">{{ f.label }}</button></div>
    </section>

    <template v-if="s">
      <div class="kpis">
        <div v-for="(k, i) in KPIS" :key="k.key" class="kpi" :style="{ animationDelay: i * 60 + 'ms' }" role="button" tabindex="0"
             @click="go(s.kpi[k.key].link)" @keydown.enter="go(s.kpi[k.key].link)">
          <div class="kl">{{ k.label }}</div>
          <div class="kv" :class="s.kpi[k.key].value ? k.tone : ''">{{ s.kpi[k.key].value }}</div>
        </div>
      </div>

      <div class="g3">
        <section class="card">
          <h3>호선별 진척률</h3>
          <div v-for="(h, i) in s.hull_progress" :key="h.hull_no" class="hp" :class="{ on: tip?.key === 'h:' + h.hull_no }" role="button" @click="go(h.link)"
               @mousemove="hover($event, 'h:' + h.hull_no, `${h.hull_no} ${h.hull_nm}`, `진척률 ${Math.round(h.progress || 0)}%`)" @mouseleave="leave">
            <span class="ell">{{ h.hull_no }} {{ h.hull_nm }}</span>
            <span class="hbar"><i :style="{ width: (h.progress || 0) + '%', animationDelay: i * 80 + 'ms' }"></i></span>
            <b>{{ Math.round(h.progress || 0) }}%</b>
          </div>
        </section>

        <section class="card">
          <h3>공정 상태 분포</h3>
          <div class="donut-wrap">
            <svg viewBox="0 0 120 120" width="120" height="120" class="donut" :class="{ hov: tip?.key?.startsWith('p:') }">
              <circle cx="60" cy="60" r="40" fill="none" stroke="#eef1f6" stroke-width="22" />
              <circle v-for="seg in donut" :key="seg.status" cx="60" cy="60" r="40" fill="none" :stroke="STATUS_COLORS[seg.status]" stroke-width="22"
                      :stroke-dasharray="`${seg.len} ${C - seg.len}`" :stroke-dashoffset="-seg.off" transform="rotate(-90 60 60)"
                      class="seg" :class="{ on: tip?.key === 'p:' + seg.status }" @mousemove="hover($event, 'p:' + seg.status, planStatusName(seg.status), segText(seg))" @mouseleave="leave" />
              <text x="60" y="60" text-anchor="middle" class="dt">{{ planTotal }}</text>
              <text x="60" y="75" text-anchor="middle" class="ds">전체</text>
            </svg>
            <div class="legend">
              <div v-for="p in s.plan_status" :key="p.status" :class="{ on: tip?.key === 'p:' + p.status }"><i :style="{ background: STATUS_COLORS[p.status] }"></i>{{ planStatusName(p.status) }} <b>{{ p.count }}</b></div>
            </div>
          </div>
        </section>

        <section class="card">
          <h3>분야별 도면 상태</h3>
          <div v-for="dd in s.drawing_disciplines" :key="dd.discipline" class="disc">
            <div>{{ dd.name }} <span class="muted">({{ dd.total }})</span></div>
            <div class="stack" :class="{ hov: tip?.key?.startsWith('d:' + dd.discipline + ':') }">
              <i v-for="st in DWG_STATUSES.filter((x) => dd.counts[x])" :key="st" :class="{ on: tip?.key === `d:${dd.discipline}:${st}` }"
                 :style="{ flex: dd.counts[st], background: STATUS_COLORS[st] }"
                 @mousemove="hover($event, `d:${dd.discipline}:${st}`, `${dd.name} · ${dwgStatusName(st)}`, `${dd.counts[st]}건 / 전체 ${dd.total}건`)" @mouseleave="leave"></i>
            </div>
          </div>
          <div class="legend row">
            <span v-for="st in DWG_STATUSES" :key="st"><i :style="{ background: STATUS_COLORS[st] }"></i>{{ dwgStatusName(st) }}</span>
          </div>
        </section>

        <section class="card">
          <h3>월별 인도 예정</h3>
          <div class="deliv" :class="{ hov: tip?.key?.startsWith('m:') }">
            <div v-for="m in s.deliveries" :key="m.month" class="dcol" :class="{ on: tip?.key === 'm:' + m.month }"
                 @mousemove="hover($event, 'm:' + m.month, `${m.month} 인도 예정`, `${m.count}건${m.hull_nos.length ? ' · ' + m.hull_nos.join(', ') : ''}`)" @mouseleave="leave">
              <span class="dv">{{ m.count }}</span>
              <i :style="{ height: Math.max(4, (m.count / deliveryMax) * 80) + 'px' }"></i>
              <span class="dm">{{ m.month.slice(2) }}</span>
              <span class="dm">{{ m.hull_nos.join(', ') }}</span>
            </div>
          </div>
        </section>

        <section class="card">
          <h3>지연 공정 <span class="b b-bad">{{ s.delay_list.count }}</span></h3>
          <div v-for="p in s.delay_list.items" :key="p.plan_id" class="li" role="button" @click="go(p.link)">
            <span>{{ p.hull_no }} {{ p.label }}</span><span class="muted">{{ Math.round(p.progress_rate || 0) }}% · 계획종료 {{ p.plan_end_dt }}</span>
          </div>
          <div v-if="!s.delay_list.items.length" class="none">지연 공정이 없습니다.</div>
        </section>

        <section class="card">
          <h3>도면 대기 공정 <span class="b b-warn">{{ s.waiting_list.count }}</span></h3>
          <div v-for="p in s.waiting_list.items" :key="p.plan_id" class="li" role="button" @click="go(p.link)">
            <span>{{ p.hull_no }} {{ p.label }}</span><span class="muted">착수 {{ p.plan_start_dt }} · {{ (p.blockers || []).join(', ') }}</span>
          </div>
          <div v-if="!s.waiting_list.items.length" class="none">대기 중인 공정이 없습니다.</div>
        </section>
      </div>

      <section class="card">
        <h3>도면 개정 영향 공정 <span class="b b-info">{{ s.impact_list.count }}</span></h3>
        <div v-for="p in s.impact_list.items" :key="`${p.drawing_id}-${p.plan_id}`" class="li" role="button" @click="openDrawing?.(p.drawing_id)">
          <span>{{ p.drawing_no }} Rev{{ p.rev_no }} → {{ p.plan_label }} <StatusBadge :value="p.plan_status" /></span>
          <span class="muted">{{ p.change_desc }} · 배포 {{ p.issue_dt }}</span>
        </div>
        <div v-if="!s.impact_list.items.length" class="none">최근 개정된 도면의 영향 공정이 없습니다.</div>
      </section>
    </template>
    <Teleport to="body">
      <div v-if="tip" class="ctip" role="tooltip" :style="{ left: tip.x + 'px', top: tip.y + 'px' }"><b>{{ tip.label }}</b><span>{{ tip.value }}</span></div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, inject, onMounted } from 'vue'
import { api } from '../api/client'
import { menuByToken } from '../stores/session'
import { STATUS_COLORS, DWG_STATUSES, planStatusName, dwgStatusName } from '../utils/status'
import { toastError } from '../utils/toast'
import PageHead from '../components/PageHead.vue'
import StatusBadge from '../components/StatusBadge.vue'

const props = defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })
const navigate = inject('navigate', null)
const openManual = inject('openManual', null)
const openDrawing = inject('openDrawing', null)

const FLOW = [
  { token: 'hull-list', label: '호선 확인' }, { token: 'plan-gantt', label: '공정계획' }, { token: 'progress', label: '실적 입력' },
  { token: 'dwg-list', label: '도면 관리' }, { token: 'dwg-approval', label: '도면 결재' },
]
const KPIS = [
  { key: 'active_hulls', label: '진행 호선', tone: '' }, { key: 'delay_plans', label: '지연 공정', tone: 'err' },
  { key: 'waiting_plans', label: '도면 대기 공정', tone: 'warn' }, { key: 'pending_drawings', label: '결재·배포 대기 도면', tone: 'warn' },
]
const C = 2 * Math.PI * 40

const s = ref(null)
const flows = computed(() => FLOW.filter((f) => menuByToken(f.token)))
const planTotal = computed(() => (s.value?.plan_status || []).reduce((a, p) => a + p.count, 0))
const donut = computed(() => {
  let off = 0
  return (s.value?.plan_status || []).filter((p) => p.count).map((p) => {
    const len = (p.count / planTotal.value) * C
    const seg = { status: p.status, count: p.count, len, off }
    off += len
    return seg
  })
})
const tip = ref(null)
const segText = (seg) => `${seg.count}건 (${Math.round((seg.count / planTotal.value) * 100)}%)`
const deliveryMax = computed(() => Math.max(1, ...(s.value?.deliveries || []).map((m) => m.count)))

// 차트 항목 호버: 키로 강조, 커서 옆 툴팁(화면 밖으로 나가지 않게)
function hover(e, key, label, value) {
  const x = Math.min(e.clientX + 14, window.innerWidth - 230), y = Math.min(e.clientY + 16, window.innerHeight - 60)
  tip.value = { key, label, value, x: Math.max(8, x), y }
}
function leave() { tip.value = null }
function go(link) { if (link) navigate?.(link.screen, link.param ?? null) }
async function load() { try { s.value = await api.get('/dashboard/summary') } catch (e) { toastError(e) } }

watch(() => props.active, (v, old) => { if (v && old === false) load() })
onMounted(load)
</script>

<style scoped>
.flow .row { flex-wrap: wrap; }
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
.kpi { background: #fff; border: 1px solid var(--card-line); border-radius: 10px; padding: 12px 14px; cursor: pointer; position: relative; overflow: hidden;
  box-shadow: var(--shadow-sm); animation: rise-in var(--t-med) var(--ease) both;
  transition: border-color var(--t-fast) var(--ease), box-shadow var(--t-fast) var(--ease), transform var(--t-fast) var(--ease); }
.kpi::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--pri); opacity: .7; }
.kpi:hover { border-color: var(--pri); box-shadow: var(--shadow-md); transform: translateY(-2px); }
.kl { font-size: 12px; color: var(--muted); }
.kv { font-size: 26px; font-weight: 700; }
.kv.err { color: var(--err); } .kv.warn { color: var(--warn); }
.g3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0 12px; }
.hp { display: grid; grid-template-columns: 130px 1fr 44px; gap: 10px; align-items: center; padding: 3px 4px; border-radius: 5px; cursor: pointer; }
.hp:hover { background: var(--hover); }
.hp b { text-align: right; }
.ell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hbar { height: 12px; background: #e8ecf2; border-radius: 6px; overflow: hidden; }
.hbar i { display: block; height: 100%; border-radius: 6px; background: linear-gradient(90deg, #60a5fa, var(--pri)); transform-origin: left; animation: grow-x var(--t-slow) var(--ease) both; }
.donut-wrap { display: flex; align-items: center; gap: 24px; }
.dt { font-size: 18px; font-weight: 700; fill: var(--ink); }
.ds { font-size: 9px; fill: var(--muted); }
.legend { display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
.legend.row { flex-direction: row; flex-wrap: wrap; gap: 12px; margin-top: 8px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
.disc { margin-bottom: 6px; font-size: 12.5px; }
.stack { display: flex; height: 16px; border-radius: 4px; overflow: hidden; gap: 2px; margin-top: 3px; }
.stack i { display: block; transform-origin: left; animation: grow-x var(--t-slow) var(--ease) both; }
.deliv { height: 130px; display: flex; align-items: flex-end; justify-content: space-around; gap: 8px; }
.dcol { display: flex; flex-direction: column; align-items: center; gap: 3px; font-size: 11px; }
.dcol i { width: 36px; border-radius: 4px 4px 0 0; background: linear-gradient(#3b82f6, var(--navy2)); transform-origin: bottom; animation: grow-y var(--t-slow) var(--ease) both; }
.dm { color: var(--muted); }
.li { display: flex; justify-content: space-between; gap: 10px; padding: 7px 4px; border-bottom: 1px solid var(--line2); cursor: pointer; font-size: 12.5px; }
.li:hover { background: var(--hover); }
.li:last-child { border-bottom: 0; }
.none { text-align: center; color: var(--muted); padding: 12px; }
.hp.on .hbar i { filter: brightness(1.12) saturate(1.2); box-shadow: 0 0 0 2px rgba(59,130,246,.25); }
.hp.on b { color: var(--pri); }
.seg { cursor: pointer; transition: stroke-width var(--t-fast) var(--ease), opacity var(--t-fast) var(--ease); }
.donut.hov .seg { opacity: .4; }
.donut.hov .seg.on { opacity: 1; stroke-width: 27; }
.legend > div { padding: 1px 4px; border-radius: 4px; transition: background var(--t-fast) var(--ease); }
.legend > div.on { background: var(--hover); font-weight: 600; }
.stack i { cursor: pointer; transition: opacity var(--t-fast) var(--ease), filter var(--t-fast) var(--ease); }
.stack.hov i { opacity: .4; }
.stack.hov i.on { opacity: 1; filter: brightness(1.08); }
.dcol { cursor: pointer; }
.dcol i { transition: opacity var(--t-fast) var(--ease), filter var(--t-fast) var(--ease); }
.deliv.hov .dcol i { opacity: .4; }
.deliv.hov .dcol.on i { opacity: 1; filter: brightness(1.15); }
.deliv.hov .dcol.on .dv { color: var(--pri); font-weight: 700; }
.ctip { position: fixed; z-index: 950; pointer-events: none; background: #fff; border: 1px solid var(--card-line); border-radius: 8px; box-shadow: var(--shadow-md);
  padding: 6px 10px; font-size: 12px; display: flex; flex-direction: column; gap: 2px; max-width: 220px; }
.ctip span { color: var(--muted); }
@media (max-width: 1200px) { .g3 { grid-template-columns: 1fr; } .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
