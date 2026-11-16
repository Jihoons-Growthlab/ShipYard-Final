<template>
  <div class="progress-screen">
    <PageHead title="공정 실적 입력" :readonly="!canWrite" desc="착수 가능/진행/지연 공정의 일별 진척률·공수를 입력하면 공정 진척과 상태가 갱신됩니다." />
    <div class="toolbar">
      <select v-model="hullNo" class="inp w165" aria-label="호선" @change="onHullChange">
        <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
      </select>
      <label class="row"><input v-model="includeDone" type="checkbox" @change="loadTargets" /> 완료 공정 포함</label>
    </div>

    <div class="tw">
      <table class="t clk progress-table">
        <thead><tr><th>공정</th><th>계획기간</th><th>실제착수</th><th class="wbar">진척</th><th>상태</th><th>담당</th></tr></thead>
        <tbody>
          <tr v-for="p in targets" :key="p.plan_id" :class="{ sel: selectedId === p.plan_id }" @click="select(p.plan_id)"
              @mouseenter="preview.enter(p.plan_id, $event, p)" @mouseleave="preview.leave()">
            <td>{{ p.label }}<span v-if="p.drawing_wait"> 📐</span></td>
            <td>{{ p.plan_start_dt }} ~ {{ p.plan_end_dt }}</td>
            <td>{{ p.actual_start_dt || '-' }}</td>
            <td><ProgressBar :value="p.progress_rate" /></td>
            <td><StatusBadge :value="p.plan_status" /></td>
            <td>{{ p.manager_nm || '-' }}</td>
          </tr>
          <tr v-if="loaded && !targets.length"><td colspan="6" class="empty">대상 공정이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="!detail" class="card muted pick">위 목록에서 공정을 선택하세요.</div>
    <div v-else class="card prog-detail">
      <h3>{{ detail.plan.label }} <StatusBadge :value="detail.plan.plan_status" /></h3>
      <form v-if="canWrite" class="fg c6" @submit.prevent="save">
        <div class="fld"><label>작업일</label><input v-model="form.work_dt" class="inp" type="date" :max="today" /></div>
        <div class="fld"><label>누적 진척률(%)</label><input v-model="form.progress_rate" class="inp" type="number" min="0" max="100" step="1" /></div>
        <div class="fld"><label>투입 공수(MH)</label><input v-model="form.man_hour" class="inp" type="number" min="0" step=".5" /></div>
        <div class="fld"><label>투입 인원</label><input v-model="form.worker_cnt" class="inp" type="number" min="0" step="1" /></div>
        <div class="fld"><label>작업자</label>
          <select v-model="form.worker_emp_no" class="inp"><option value="">-</option><option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option></select></div>
        <div class="fld"><button class="btn pri" type="submit">실적 저장</button></div>
        <div class="fld"><label>비고</label><input v-model="form.remark" class="inp" /></div>
      </form>
      <h3 class="hist-h">실적 이력</h3>
      <div class="tw">
        <table class="t">
          <thead><tr><th>작업일</th><th>누적 진척률</th><th class="num">공수</th><th class="num">인원</th><th>작업자</th><th>비고</th><th v-if="canWrite"></th></tr></thead>
          <tbody>
            <tr v-for="h in detail.history" :key="h.progress_id">
              <td>{{ h.work_dt }}</td><td>{{ fmtNum(h.progress_rate) }}%</td><td class="num">{{ fmtNum(h.man_hour) }}</td><td class="num">{{ dash(h.worker_cnt) }}</td>
              <td>{{ h.worker_nm || '-' }}</td><td class="wrap">{{ h.remark || '' }}</td>
              <td v-if="canWrite" class="right"><button class="btn sm danger" type="button" @click="remove(h)">삭제</button></td>
            </tr>
            <tr v-if="!detail.history.length"><td :colspan="canWrite ? 7 : 6" class="empty">실적 이력이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <HoverCard :preview="preview" :width="360" :height="270">
      <template #default="{ data, ctx: p, loading }">
        <div v-if="p" class="pv">
          <div class="pvh">{{ p.label }}<span class="sp"></span><StatusBadge :value="p.plan_status" /></div>
          <div>누적 진척률 {{ fmtNum(p.progress_rate) }}%</div>
          <div v-if="loading" class="pvm">불러오는 중…</div>
          <template v-else-if="data">
            <div v-if="!data.history.length" class="pvm">등록된 실적 이력이 없습니다.</div>
            <template v-else>
              <b>최근 실적</b>
              <table class="pvt">
                <thead><tr><th>작업일</th><th>진척률</th><th>공수</th><th>인원</th></tr></thead>
                <tbody><tr v-for="h in data.history.slice(0, 3)" :key="h.progress_id">
                  <td>{{ h.work_dt }}</td><td>{{ fmtNum(h.progress_rate) }}%</td><td>{{ fmtNum(h.man_hour) }}</td><td>{{ dash(h.worker_cnt) }}</td>
                </tr></tbody>
              </table>
            </template>
          </template>
          <div class="pvf">클릭하면 전체 실적 이력을 볼 수 있습니다.</div>
        </div>
      </template>
    </HoverCard>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api } from '../api/client'
import { session } from '../stores/session'
import { toast, toastError } from '../utils/toast'
import { useHoverPreview } from '../utils/hoverPreview'
import { dash, fmtNum } from '../utils/status'
import PageHead from '../components/PageHead.vue'
import ProgressBar from '../components/ProgressBar.vue'
import StatusBadge from '../components/StatusBadge.vue'
import HoverCard from '../components/HoverCard.vue'

defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })

const hulls = ref([])
const hullNo = ref('')
const includeDone = ref(false)
const targets = ref([])
const loaded = ref(false)
const today = ref(session.me?.today || '')
const users = ref([])
const selectedId = ref(null)
const detail = ref(null)
const form = reactive({})

const preview = useHoverPreview((id) => api.get(`/plans/${id}/progress`))

function resetForm() {
  Object.assign(form, {
    work_dt: today.value, progress_rate: detail.value ? Math.round(detail.value.plan.progress_rate) : 0,
    man_hour: '', worker_cnt: '', worker_emp_no: session.me?.emp_no || '', remark: '',
  })
}

async function loadTargets() {
  if (!hullNo.value) { loaded.value = true; return }
  try {
    const res = await api.get(`/hulls/${hullNo.value}/progress-targets`, { include_done: includeDone.value })
    targets.value = res.plans; today.value = res.today; loaded.value = true
    preview.clear()
  } catch (e) { toastError(e) }
}

function onHullChange() { selectedId.value = null; detail.value = null; loadTargets() }

async function select(id) {
  selectedId.value = id
  try { detail.value = await api.get(`/plans/${id}/progress`); resetForm() } catch (e) { toastError(e) }
}

const num = (v) => (v === '' || v === null || v === undefined ? null : Number(v))

async function save() {
  const id = selectedId.value
  try {
    const res = await api.put(`/plans/${id}/progress/${form.work_dt || '-'}`, {
      progress_rate: num(form.progress_rate), man_hour: num(form.man_hour), worker_cnt: num(form.worker_cnt),
      worker_emp_no: form.worker_emp_no || null, remark: form.remark || null,
    })
    detail.value = res
    toast(res.plan.progress_rate >= 100 ? '실적 저장 — 공정이 완료 처리되었습니다.' : '실적이 저장되었습니다.', 'success')
    resetForm()
    await loadTargets()
  } catch (e) { toastError(e) }
}

async function remove(h) {
  if (!confirm('실적을 삭제합니다.')) return
  try {
    detail.value = await api.del(`/progress/${h.progress_id}`)
    toast('실적이 삭제되었습니다.', 'success')
    resetForm()
    await loadTargets()
  } catch (e) { toastError(e) }
}

onMounted(async () => {
  try {
    const [ph, us] = await Promise.all([api.get('/progress-hulls'), api.get('/users/options')])
    hulls.value = ph.hulls; users.value = us
    hullNo.value = ph.default_hull_no || ph.hulls[0]?.hull_no || ''
    await loadTargets()
  } catch (e) { toastError(e) }
})

defineExpose({ select, form, hullNo })
</script>

<style scoped>
.w165 { width: 165px; }
.wbar { width: 240px; }
.tw { margin-bottom: 12px; }
.pick { padding: 16px 14px; }
.prog-detail h3 { display: flex; justify-content: space-between; margin-bottom: 8px; }
.prog-detail .fg { margin-bottom: 14px; }
.hist-h { margin: 6px 0 8px !important; }
</style>
