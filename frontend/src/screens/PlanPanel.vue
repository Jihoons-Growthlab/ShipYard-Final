<template>
  <div class="card plan-panel">
    <div class="pp-head">
      <b>{{ plan ? plan.label : '공정 추가' }}</b>
      <StatusBadge v-if="plan" :value="plan.plan_status" />
      <span v-if="plan" class="muted">진척 {{ Math.round(plan.progress_rate) }}% · 실제 {{ plan.actual_start_dt || '-' }} ~ {{ plan.actual_end_dt || '-' }}</span>
    </div>
    <div class="pp-body">
      <form class="pf" @submit.prevent="save">
        <div class="fld f-block"><label>블록</label>
          <select v-model="form.block_id" class="inp"><option value="">호선 전체(블록 없음)</option><option v-for="b in blocks" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm }}</option></select></div>
        <div class="fld f-proc"><label>공정</label>
          <select v-model="form.proc_cd" class="inp"><option v-for="p in procs" :key="p.proc_cd" :value="p.proc_cd">{{ p.proc_nm }}</option></select></div>
        <div class="fld f-s"><label>계획 시작</label><input v-model="form.plan_start_dt" class="inp" type="date" /></div>
        <div class="fld f-e"><label>계획 종료</label><input v-model="form.plan_end_dt" class="inp" type="date" /></div>
        <div class="fld f-m"><label>담당자</label>
          <select v-model="form.manager_emp_no" class="inp"><option value="">미지정</option><option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option></select></div>
        <div class="fld f-pred"><label>선행 공정 (Ctrl 다중선택)</label>
          <select v-model="form.pred_plan_ids" class="inp h66" multiple><option v-for="p in predOptions" :key="p.plan_id" :value="p.plan_id">{{ p.label }}</option></select></div>
        <div class="fld f-rm"><label>비고</label><textarea v-model="form.remark" class="inp h66"></textarea></div>
        <div class="f-acts">
          <button class="btn pri" type="submit" :disabled="!canWrite">저장</button>
          <button v-if="plan" class="btn danger" type="button" :disabled="!canWrite" @click="remove">삭제</button>
          <button class="btn" type="button" @click="emit('close')">닫기</button>
        </div>
      </form>

      <div class="pp-right">
        <template v-if="plan">
          <div v-if="links.blockers.length" class="note warn">📐 도면 대기: 필수 도면 {{ links.blockers.map((b) => `${b.drawing_no}(${dwgStatusName(b.dwg_status)})`).join(', ') }} 미배포 → 착수 불가</div>
          <div class="pp-title"><b>연계 도면</b> (필수 도면은 배포 전 착수 불가)</div>
          <div class="tw r3">
            <table class="t">
              <thead><tr><th>도면번호</th><th>상태</th><th>필수</th><th></th></tr></thead>
              <tbody>
                <tr v-for="l in links.links" :key="l.drawing_id">
                  <td><a @click="openDrawing(l.drawing_id)">{{ l.drawing_no }}</a></td>
                  <td><StatusBadge :value="l.dwg_status" kind="dwg" /> <span v-if="!l.has_issued" class="b b-warn">미배포</span></td>
                  <td>{{ l.required ? '필수' : '참고' }}</td>
                  <td><button class="btn sm danger" type="button" :disabled="!canWrite" @click="unlink(l)">해제</button></td>
                </tr>
                <tr v-if="!links.links.length"><td colspan="4" class="empty">연계된 도면이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
          <div class="linkrow">
            <select v-model="newLink.drawing_id" class="inp grow" aria-label="도면 선택" :disabled="!canWrite">
              <option value="">도면 선택</option>
              <option v-for="d in links.available" :key="d.drawing_id" :value="d.drawing_id">{{ d.drawing_no }} {{ d.drawing_nm }}</option>
            </select>
            <label class="row"><input v-model="newLink.required" type="checkbox" :disabled="!canWrite" /> 필수</label>
            <button class="btn" type="button" :disabled="!canWrite" @click="link">+ 연계</button>
          </div>
        </template>
        <div v-else class="muted pp-new">저장한 뒤 이 공정에 도면을 연계할 수 있습니다.</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, computed, watch, inject } from 'vue'
import { api } from '../api/client'
import { toast, toastError } from '../utils/toast'
import { dwgStatusName } from '../utils/status'
import { addDays } from '../utils/date'
import StatusBadge from '../components/StatusBadge.vue'

const props = defineProps({
  hullNo: String, plan: { type: Object, default: null }, plans: { type: Array, default: () => [] },
  blocks: Array, procs: Array, users: Array, canWrite: Boolean, defaultBlockId: { default: '' }, today: String,
})
const emit = defineEmits(['close', 'saved', 'deleted'])
const openDrawingFn = inject('openDrawing', null)

const form = reactive({})
const links = reactive({ links: [], blockers: [], available: [] })
const newLink = reactive({ drawing_id: '', required: true })
const predOptions = computed(() => props.plans.filter((p) => p.plan_id !== props.plan?.plan_id))

function fill() {
  const p = props.plan
  Object.assign(form, p ? {
    block_id: p.block_id ?? '', proc_cd: p.proc_cd, plan_start_dt: p.plan_start_dt, plan_end_dt: p.plan_end_dt,
    manager_emp_no: p.manager_emp_no ?? '', pred_plan_ids: [...(p.pred_plan_ids || [])], remark: p.remark ?? '',
  } : {
    block_id: props.defaultBlockId ?? '', proc_cd: 'CUT', plan_start_dt: props.today, plan_end_dt: addDays(props.today, 13),
    manager_emp_no: '', pred_plan_ids: [], remark: '',
  })
  Object.assign(newLink, { drawing_id: '', required: true })
  if (p) loadLinks(); else Object.assign(links, { links: [], blockers: [], available: [] })
}

async function loadLinks() {
  try { Object.assign(links, await api.get(`/plans/${props.plan.plan_id}/drawings`)) } catch (e) { toastError(e) }
}

function body(confirmLate) {
  return {
    block_id: form.block_id === '' ? null : form.block_id, proc_cd: form.proc_cd,
    plan_start_dt: form.plan_start_dt || null, plan_end_dt: form.plan_end_dt || null,
    manager_emp_no: form.manager_emp_no || null, remark: form.remark || null,
    pred_plan_ids: form.pred_plan_ids, confirm_late_preds: confirmLate,
  }
}

async function save() {
  const send = (c) => (props.plan ? api.patch(`/plans/${props.plan.plan_id}`, body(c)) : api.post(`/hulls/${props.hullNo}/plans`, body(c)))
  try {
    let res
    try { res = await send(false) } catch (e) {
      if (e.status !== 409 || !confirm(e.message)) { if (e.status !== 409) throw e; return }
      res = await send(true)
    }
    toast('저장되었습니다.', 'success')
    emit('saved', res.plan_id)
  } catch (e) { toastError(e) }
}

async function remove() {
  if (!confirm('공정을 삭제합니다. (실적·선후행·도면 연계 함께 삭제)')) return
  try { await api.del(`/plans/${props.plan.plan_id}`); toast('삭제되었습니다.', 'success'); emit('deleted') } catch (e) { toastError(e) }
}

async function link() {
  if (!newLink.drawing_id) { toast('도면을 선택하세요.', 'error'); return }
  try {
    await api.post(`/plans/${props.plan.plan_id}/drawings`, { drawing_id: newLink.drawing_id, required: newLink.required })
    toast('도면이 연계되었습니다.', 'success')
    emit('saved', props.plan.plan_id)
  } catch (e) { toastError(e) }
}

async function unlink(l) {
  try {
    await api.del(`/plans/${props.plan.plan_id}/drawings/${l.drawing_id}`)
    toast('연계가 해제되었습니다.', 'success')
    emit('saved', props.plan.plan_id)
  } catch (e) { toastError(e) }
}

function openDrawing(id) { if (openDrawingFn) openDrawingFn(id) }

watch(() => props.plan, fill, { immediate: true })
defineExpose({ form, loadLinks })
</script>

<style scoped>
.plan-panel { flex: none; margin: 10px 0 0; }
.pp-head { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.pp-head b { font-size: 13.5px; }
.pp-body { display: grid; grid-template-columns: 1fr 430px; gap: 16px; }
.pf { display: grid; grid-template-columns: repeat(6, minmax(0,1fr)); gap: 10px 12px; align-items: end; }
.f-block { grid-column: span 2; } .f-pred, .f-rm { grid-column: span 3; }
.f-acts { grid-column: 1 / -1; display: flex; gap: 8px; }
.h66 { height: 66px !important; }
.pp-title { margin-bottom: 6px; }
.pp-right .note { margin-bottom: 8px; }
.linkrow { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.pp-new { padding-top: 20px; }
@media (max-width: 1560px) {
  .pf { grid-template-columns: repeat(4, minmax(0,1fr)); }
  .f-block, .f-proc, .f-m, .f-pred, .f-rm { grid-column: span 2; }
}
@media (max-width: 1000px) { .pp-body { grid-template-columns: 1fr; } }
</style>
