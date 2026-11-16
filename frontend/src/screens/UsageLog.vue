<template>
  <div class="usage">
    <PageHead :title="title" desc="누가 어떤 기능을 얼마나 썼는지 API 호출·메뉴 진입 기록으로 봅니다. (관리자 전용)" />
    <div class="toolbar">
      <select v-model.number="f.days" class="inp w120" aria-label="기간" @change="load">
        <option :value="7">최근 7일</option><option :value="30">최근 30일</option><option :value="90">최근 90일</option>
      </select>
      <select v-model="f.emp_no" class="inp w180" aria-label="사용자" @change="load">
        <option value="">사용자 전체</option>
        <option v-for="u in s?.user_options || []" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option>
      </select>
      <button class="btn" type="button" @click="load">새로고침</button>
      <button v-if="f.emp_no" class="btn" type="button" @click="pickUser('')">필터 해제</button>
      <div class="grow"></div>
      <span v-if="s?.demo_calls > 0" class="b b-warn">예시 데이터 {{ fmtNum(s.demo_calls) }}건 포함</span>
    </div>

    <template v-if="s">
      <div class="kpis">
        <div class="kpi"><div class="kl">API 호출</div><div class="kv">{{ fmtNum(s.kpi.calls) }}</div><div class="ks">최근 {{ s.days }}일</div></div>
        <div class="kpi"><div class="kl">사용자</div><div class="kv">{{ fmtNum(s.kpi.users) }}</div><div class="ks">호출한 회원 수</div></div>
        <div class="kpi"><div class="kl">로그인</div><div class="kv">{{ fmtNum(s.kpi.logins) }}</div><div class="ks">로그인 횟수</div></div>
        <div class="kpi" :class="{ err: s.kpi.error_rate >= 5 }"><div class="kl">오류율</div><div class="kv">{{ s.kpi.error_rate }}%</div><div class="ks">오류 {{ fmtNum(s.kpi.errors) }}건 (4xx·5xx)</div></div>
        <div class="kpi" :class="{ err: s.kpi.avg_ms >= 500 }"><div class="kl">평균 응답</div><div class="kv">{{ fmtNum(s.kpi.avg_ms) }}ms</div><div class="ks">서버 처리 시간</div></div>
      </div>

      <div class="r21">
        <section class="card">
          <h3>일별 호출 추이 <span class="lg"><i class="dot pri"></i>호출 <i class="dot er"></i>오류</span></h3>
          <div class="chart" @mouseleave="hover = null">
            <svg :viewBox="`0 0 ${CH.w} ${CH.h}`" class="line" preserveAspectRatio="none" @mousemove="onMove">
              <defs><linearGradient id="ugrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2563eb" stop-opacity=".22" /><stop offset="1" stop-color="#2563eb" stop-opacity="0" /></linearGradient></defs>
              <g v-for="t in geom.ticks" :key="t">
                <line :x1="CH.l" :x2="CH.w - CH.r" :y1="geom.y(t)" :y2="geom.y(t)" class="grid" />
                <text :x="CH.l - 6" :y="geom.y(t) + 3" text-anchor="end" class="ax">{{ fmtNum(t) }}</text>
              </g>
              <rect v-for="(b, i) in geom.bars" :key="'e' + i" :x="b.x" :y="b.y" :width="b.w" :height="b.h" fill="#fca5a5" />
              <path :d="geom.area" fill="url(#ugrad)" />
              <path :d="geom.line" fill="none" stroke="#2563eb" stroke-width="2" />
              <template v-for="(d, i) in s.daily" :key="d.date">
                <text v-if="i % step === 0" :x="geom.x(i)" :y="CH.h - 8" text-anchor="middle" class="ax">{{ d.date.slice(5) }}</text>
              </template>
              <template v-if="hover !== null">
                <line :x1="geom.x(hover)" :x2="geom.x(hover)" :y1="CH.t" :y2="geom.base" class="guide" />
                <circle :cx="geom.x(hover)" :cy="geom.y(s.daily[hover].calls)" r="4" fill="#2563eb" stroke="#fff" stroke-width="2" />
              </template>
            </svg>
            <div v-if="hover !== null" class="tip" :style="{ left: (geom.x(hover) / CH.w) * 100 + '%' }">
              <b>{{ s.daily[hover].date }}</b><br />호출 {{ s.daily[hover].calls }} · 오류 {{ s.daily[hover].errors }} · 사용자 {{ s.daily[hover].users }}
            </div>
          </div>
        </section>
        <section class="card">
          <h3>시간대별 호출 <span class="muted sm">(한국 시간)</span></h3>
          <div class="hours">
            <div v-for="(v, h) in s.hours" :key="h" class="hcol">
              <i :class="{ top: v && v === hourMax }" :style="{ height: Math.max(1, (v / hourMax) * 100) + '%', animationDelay: h * 15 + 'ms' }" :title="`${h}시 ${v}`"></i>
              <span>{{ h % 3 === 0 ? h : '' }}</span>
            </div>
          </div>
        </section>
      </div>

      <div class="r3">
        <section class="card">
          <h3>기능별 사용</h3>
          <div v-for="(x, i) in s.features.slice(0, 10)" :key="x.feature" class="hb">
            <span class="ell">{{ x.feature }}</span><span class="bar"><i :style="{ width: pct(x.calls, featMax), background: PALETTE[i % 10] }"></i></span><b>{{ fmtNum(x.calls) }}</b>
          </div>
          <div v-if="!s.features.length" class="none">기록이 없습니다.</div>
        </section>
        <section class="card">
          <h3>사용자별 호출 TOP 10 <span class="muted sm">클릭하면 그 사용자만 봅니다</span></h3>
          <div v-for="u in s.top_users" :key="u.emp_no" class="hb clk" :class="{ on: f.emp_no === u.emp_no }" role="button" @click="pickUser(f.emp_no === u.emp_no ? '' : u.emp_no)">
            <span class="ell">{{ u.display_name || u.emp_no }} <small class="muted">{{ u.top_feature }}</small></span>
            <span class="bar"><i class="ub" :style="{ width: pct(u.calls, userMax) }"></i></span><b>{{ fmtNum(u.calls) }}</b>
          </div>
          <div v-if="!s.top_users.length" class="none">기록이 없습니다.</div>
        </section>
        <section class="card">
          <h3>메뉴 진입 <span class="muted sm">화면을 연 횟수</span></h3>
          <div v-for="m in s.menus" :key="m.menu_id" class="hb">
            <span class="ell">{{ m.title }}</span><span class="bar"><i class="mb" :style="{ width: pct(m.opens, menuMax) }"></i></span><span class="mv"><b>{{ m.opens }}</b> / {{ m.users }}명</span>
          </div>
          <div v-if="!s.menus.length" class="none">기록이 없습니다.</div>
        </section>
      </div>

      <div class="r21">
        <section class="card">
          <h3>많이 호출된 API TOP 15</h3>
          <div class="tw">
            <table class="t">
              <thead><tr><th>기능</th><th>요청</th><th class="num">호출</th><th class="num">오류</th><th class="num">평균 ms</th><th class="num">최대 ms</th></tr></thead>
              <tbody>
                <tr v-for="e in s.endpoints" :key="e.method + e.path">
                  <td>{{ e.feature }}</td><td><span class="mt" :class="methodClass(e.method)">{{ e.method }}</span> <code>{{ e.path }}</code></td>
                  <td class="num">{{ fmtNum(e.calls) }}</td><td class="num" :class="{ errt: e.errors }">{{ fmtNum(e.errors) }}</td>
                  <td class="num">{{ fmtNum(e.avg_ms) }}</td><td class="num">{{ fmtNum(e.max_ms) }}</td>
                </tr>
                <tr v-if="!s.endpoints.length"><td colspan="6" class="empty">기록이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
        </section>
        <section class="card">
          <h3>최근 오류</h3>
          <div v-for="(e, i) in s.recent_errors" :key="i" class="err-row">
            <span class="b" :class="e.status >= 500 ? 'b-bad' : 'b-warn'">{{ e.status }}</span>
            <div><code>{{ e.method }} {{ e.path }}</code><div class="muted sm">{{ e.display_name || e.emp_no || '-' }} · {{ localDateTime(e.call_dt) }}</div></div>
          </div>
          <div v-if="!s.recent_errors.length" class="none">오류가 없습니다.</div>
        </section>
      </div>
    </template>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { api } from '../api/client'
import { fmtNum } from '../utils/status'
import { localDateTime } from '../utils/date'
import { PALETTE, CH, lineGeom, labelStep, methodClass } from '../utils/chart'
import { toastError } from '../utils/toast'
import PageHead from '../components/PageHead.vue'

defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })

const f = reactive({ days: 7, emp_no: '' })
const s = ref(null)
const hover = ref(null)
const geom = computed(() => lineGeom(s.value?.daily || []))
const step = computed(() => labelStep(s.value?.days || 7))
const hourMax = computed(() => Math.max(1, ...(s.value?.hours || [])))
const featMax = computed(() => Math.max(1, ...(s.value?.features || []).map((x) => x.calls)))
const userMax = computed(() => Math.max(1, ...(s.value?.top_users || []).map((x) => x.calls)))
const menuMax = computed(() => Math.max(1, ...(s.value?.menus || []).map((x) => x.opens)))
const pct = (v, max) => Math.max(1, (v / max) * 100) + '%'

async function load() {
  try { s.value = await api.get('/usage/summary', { ...f }) } catch (e) { toastError(e) }
}
function pickUser(emp) { f.emp_no = emp; load() }
function onMove(ev) {
  const n = s.value?.daily.length || 0
  if (!n) return
  const r = ev.currentTarget.getBoundingClientRect()
  const vx = ((ev.clientX - r.left) / r.width) * CH.w
  const iw = CH.w - CH.l - CH.r
  hover.value = Math.min(n - 1, Math.max(0, Math.round(((vx - CH.l) / iw) * (n - 1))))
}

onMounted(load)
</script>

<style scoped>
.w120 { width: 120px; } .w180 { width: 180px; }
.sm { font-size: 11.5px; font-weight: 400; }
.kpis { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
.kpi { background: #fff; border: 1px solid var(--card-line); border-radius: 10px; padding: 12px 14px; position: relative; overflow: hidden; box-shadow: var(--shadow-sm); animation: rise-in var(--t-med) var(--ease) both; }
.kpi::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--pri); }
.kpi.err::before { background: var(--err); }
.kpi.err .kv { color: var(--err); }
.kl { font-size: 12px; color: var(--muted); }
.kv { font-size: 22px; font-weight: 700; margin: 2px 0; }
.ks { font-size: 11.5px; color: var(--muted); }
.r21 { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; }
.r3 { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.lg { font-size: 11.5px; font-weight: 400; display: flex; align-items: center; gap: 4px; }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-left: 6px; }
.dot.pri { background: var(--pri); } .dot.er { background: #f87171; }
.chart { position: relative; }
.line { width: 100%; height: 210px; display: block; }
.grid { stroke: var(--line2); }
.guide { stroke: #94a3b8; stroke-dasharray: 3 3; }
.ax { font-size: 9px; fill: var(--muted); }
.tip { position: absolute; top: 4px; transform: translateX(-50%); background: rgba(15,23,42,.88); color: #fff; font-size: 11.5px; padding: 5px 8px; border-radius: 6px; pointer-events: none; white-space: nowrap; }
.hours { height: 210px; display: flex; align-items: stretch; gap: 3px; }
.hcol { flex: 1; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; font-size: 9.5px; color: var(--muted); }
.hcol i { width: 100%; background: linear-gradient(#60a5fa, #3b82f6); border-radius: 2px 2px 0 0; transform-origin: bottom; animation: grow-y var(--t-slow) var(--ease) both; }
.hcol i.top { background: linear-gradient(#2563eb, var(--navy2)); }
.hcol span { height: 14px; line-height: 14px; }
.hb { display: grid; grid-template-columns: 120px 1fr 64px; gap: 10px; align-items: center; padding: 3px 4px; font-size: 12.5px; border-radius: 5px; }
.hb b, .hb .mv { text-align: right; font-size: 12px; }
.hb.clk { cursor: pointer; }
.hb.clk:hover { background: var(--hover); }
.hb.on { background: var(--sel); }
.ell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar { height: 8px; background: #eef1f6; border-radius: 4px; overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: 4px; transform-origin: left; animation: grow-x var(--t-slow) var(--ease) both; }
.bar i.ub { background: linear-gradient(90deg, #60a5fa, var(--pri)); }
.bar i.mb { background: linear-gradient(90deg, #5eead4, #0d9488); }
.none { text-align: center; color: var(--muted); padding: 12px; }
code { font-family: ui-monospace, Menlo, monospace; font-size: 11.5px; }
.mt { font-size: 10.5px; font-weight: 700; padding: 1px 5px; border-radius: 4px; background: #f3f4f6; }
.m-get { background: #e0f2fe; color: #0369a1; } .m-post { background: #dcfce7; color: #15803d; }
.m-put { background: #fef3c7; color: #92400e; } .m-del { background: #fee2e2; color: #b91c1c; }
.errt { color: var(--err); font-weight: 600; }
.err-row { display: flex; gap: 8px; align-items: flex-start; padding: 6px 0; border-bottom: 1px solid var(--line2); }
.err-row:last-child { border-bottom: 0; }
@media (max-width: 1200px) {
  .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .r21, .r3 { grid-template-columns: 1fr; }
}
</style>
