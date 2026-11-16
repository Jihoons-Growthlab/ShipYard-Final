<template>
  <AppModal :title="no ? `호선 ${no}` : '호선 등록'" :size="tab === '3d' ? 'xl' : 'large'" @close="emit('close')">
    <div class="sub muted">{{ no ? codeName('HULLSTAT', hull?.hull_status) : '신규 호선을 등록합니다.' }}</div>
    <div v-if="no" class="subtabs">
      <button v-for="t in TABS" :key="t.k" type="button" :class="{ on: tab === t.k }" @click="switchTab(t.k)">{{ t.label }}</button>
    </div>

    <form v-if="tab === 'info'" class="card hull-info" @submit.prevent="saveInfo">
      <div class="fg c4">
        <div class="fld"><label>호선번호 *</label><input v-model.trim="form.hull_no" class="inp" :readonly="!!no" /></div>
        <div class="fld s2"><label>호선명</label><input v-model="form.hull_nm" class="inp" /></div>
        <div class="fld"><label>선종</label><select v-model="form.ship_type" class="inp"><option :value="null"></option><option v-for="c in codeOptions('SHIPTYPE')" :key="c.code" :value="c.code">{{ c.name }}</option></select></div>
        <div class="fld"><label>상태</label><select v-model="form.hull_status" class="inp"><option v-for="c in codeOptions('HULLSTAT')" :key="c.code" :value="c.code">{{ c.name }}</option></select></div>
        <div class="fld s2"><label>선주</label><input v-model="form.owner_nm" class="inp" /></div>
        <div class="fld"><label>선급</label><input v-model="form.class_society" class="inp" /></div>
        <div class="fld"><label>전장(m)</label><input v-model="form.length_m" class="inp" type="number" min="0" step="any" /></div>
        <div class="fld"><label>선폭(m)</label><input v-model="form.breadth_m" class="inp" type="number" min="0" step="any" /></div>
        <div class="fld"><label>선심(m)</label><input v-model="form.depth_m" class="inp" type="number" min="0" step="any" /></div>
        <div class="fld"><label>재화중량(DWT)</label><input v-model="form.dead_weight" class="inp" type="number" min="0" step="any" /></div>
        <div class="fld"><label>도크/건조장소</label><input v-model="form.dock_no" class="inp" /></div>
        <div class="fld"><label>계약일</label><input v-model="form.contract_dt" class="inp" type="date" /></div>
        <div class="fld"><label>인도 예정일</label><input v-model="form.delivery_dt" class="inp" type="date" /></div>
        <div class="fld"><span class="lb">사용여부</span><label class="chk"><input v-model="form.use_yn" type="checkbox" /> 사용</label></div>
        <div class="fld sall"><label>비고</label><input v-model="form.remark" class="inp" /></div>
      </div>
      <div class="acts">
        <button class="btn pri" type="submit" :disabled="!canWrite">저장</button>
        <template v-if="no">
          <button class="btn danger" type="button" :disabled="!canWrite" @click="removeHull">삭제</button>
          <span class="muted">삭제 시 블록·공정·도면이 함께 삭제됩니다(FK CASCADE).</span>
        </template>
      </div>
    </form>

    <div v-else-if="tab === 'ms'" class="card">
      <div class="tw">
        <table class="t">
          <thead><tr><th>일정</th><th>계획일</th><th>실적일</th><th class="num">차이(일)</th></tr></thead>
          <tbody><tr v-for="m in milestones" :key="m.milestone_cd">
            <td>{{ m.name }}</td>
            <td><input v-model="m.plan_dt" class="inp" type="date" :disabled="!canWrite" /></td>
            <td><input v-model="m.actual_dt" class="inp" type="date" :disabled="!canWrite" /></td>
            <td class="num">{{ m.diff_days ?? '-' }}</td>
          </tr></tbody>
        </table>
      </div>
      <div class="acts"><button class="btn pri" type="button" :disabled="!canWrite" @click="saveMilestones">일정 저장</button></div>
    </div>

    <div v-else-if="tab === 'blocks'" class="card">
      <div class="tw">
        <table class="t">
          <thead><tr><th>블록코드</th><th>블록명</th><th>유형</th><th class="num">중량(ton)</th><th class="wbar">진척</th><th class="num">공정</th><th class="num">도면</th><th></th></tr></thead>
          <tbody>
            <tr v-for="b in blocks" :key="b.block_id">
              <td><b>{{ b.block_cd }}</b></td><td>{{ b.block_nm }}</td><td>{{ codeName('BLOCKTYPE', b.block_type) }}</td>
              <td class="num">{{ fmtNum(b.weight_ton) }}</td>
              <td><ProgressBar v-if="b.progress !== null" :value="b.progress" /><span v-else>-</span></td>
              <td class="num">{{ b.plan_count }}</td><td class="num">{{ b.drawing_count }}</td>
              <td><button class="btn sm danger" type="button" :disabled="!canWrite" @click="removeBlock(b)">삭제</button></td>
            </tr>
            <tr v-if="!blocks.length"><td colspan="8" class="empty">블록이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
      <form class="addrow" @submit.prevent="addBlock">
        <input v-model.trim="nb.block_cd" class="inp" placeholder="블록코드 *" aria-label="블록코드" :disabled="!canWrite" />
        <input v-model="nb.block_nm" class="inp" placeholder="블록명" aria-label="블록명" :disabled="!canWrite" />
        <select v-model="nb.block_type" class="inp w110" aria-label="유형" :disabled="!canWrite"><option value="">유형 선택</option><option v-for="c in codeOptions('BLOCKTYPE')" :key="c.code" :value="c.code">{{ c.name }}</option></select>
        <input v-model="nb.weight_ton" class="inp" type="number" min="0" step="any" placeholder="중량(ton)" aria-label="중량" :disabled="!canWrite" />
        <button class="btn pri" type="submit" :disabled="!canWrite">+ 블록 추가</button>
      </form>
    </div>

    <div v-else-if="tab === '3d'" class="viewer-tab">
      <ShipViewer3D :hull-no="no" />
    </div>

    <div v-else-if="tab === 'summary' && summary" class="sum">
      <div class="card">
        <h3><span class="row">공정 <button class="btn sm" type="button" @click="go('plan-gantt')">간트 보기</button></span></h3>
        <template v-if="summary.plan_count">
          <p>전체 진척 {{ summary.progress ?? 0 }}%</p>
          <ul><li v-for="s in PLAN_STATUSES" :key="s">{{ planStatusName(s) }}: {{ summary.plan_status[s] || 0 }}</li></ul>
        </template>
        <p v-else class="muted">공정 계획이 없습니다.</p>
      </div>
      <div class="card">
        <h3><span class="row">도면 <button class="btn sm" type="button" @click="go('dwg-list')">목록 보기</button></span></h3>
        <ul v-if="summary.drawing_count"><li v-for="s in DWG_STATUSES" :key="s">{{ dwgStatusName(s) }}: {{ summary.drawing_status[s] || 0 }}</li></ul>
        <p v-else class="muted">도면이 없습니다.</p>
      </div>
    </div>
  </AppModal>
</template>

<script setup>
import { ref, reactive, inject, onMounted } from 'vue'
import { api } from '../api/client'
import { codeOptions, codeName } from '../stores/session'
import { toast, toastError } from '../utils/toast'
import { PLAN_STATUSES, DWG_STATUSES, planStatusName, dwgStatusName, fmtNum } from '../utils/status'
import AppModal from '../components/AppModal.vue'
import ProgressBar from '../components/ProgressBar.vue'
import ShipViewer3D from '../components/ShipViewer3D.vue'

const props = defineProps({ hullNo: { type: String, default: null }, canWrite: Boolean })
const emit = defineEmits(['close', 'changed'])
const navigate = inject('navigate', () => {})

const TABS = [{ k: 'info', label: '기본정보' }, { k: 'ms', label: '주요일정' }, { k: 'blocks', label: '블록 구성' }, { k: 'summary', label: '연계 현황' }, { k: '3d', label: '3D 보기' }]
const FIELDS = ['hull_no', 'hull_nm', 'ship_type', 'hull_status', 'owner_nm', 'class_society', 'length_m', 'breadth_m', 'depth_m', 'dead_weight', 'dock_no', 'contract_dt', 'delivery_dt', 'remark', 'use_yn']
const NUMS = ['length_m', 'breadth_m', 'depth_m', 'dead_weight']

const no = ref(props.hullNo)
const tab = ref('info')
const hull = ref(null)
const blankForm = () => ({ hull_no: '', hull_nm: '', ship_type: null, hull_status: 'PLAN', owner_nm: '', class_society: '', length_m: '', breadth_m: '', depth_m: '', dead_weight: '', dock_no: '', contract_dt: '', delivery_dt: '', remark: '', use_yn: true })
const form = reactive(blankForm())
const milestones = ref([])
const blocks = ref([])
const summary = ref(null)
const blankBlock = () => ({ block_cd: '', block_nm: '', block_type: '', weight_ton: '' })
const nb = reactive(blankBlock())

const nn = (v) => (v === '' || v === undefined ? null : v)

async function loadTab(k) {
  try {
    if (k === 'info') {
      hull.value = await api.get(`/hulls/${no.value}`)
      for (const key of FIELDS) form[key] = hull.value[key] ?? (NUMS.includes(key) ? '' : key === 'use_yn' ? true : '')
    } else if (k === 'ms') milestones.value = await api.get(`/hulls/${no.value}/milestones`)
    else if (k === 'blocks') blocks.value = await api.get(`/hulls/${no.value}/blocks`)
    else if (k === 'summary') summary.value = await api.get(`/hulls/${no.value}/summary`)
  } catch (e) { toastError(e) }
}
// 3D 탭에서 직전 데이터 탭으로 돌아올 때는 재조회하지 않는다(작성 내용 유지).
let lastDataTab = 'info'
function switchTab(k) {
  if (k === tab.value) return
  const back = tab.value === '3d' && k === lastDataTab
  tab.value = k
  if (k === '3d') return
  lastDataTab = k
  if (!back) loadTab(k)
}

function payload() {
  const p = {}
  for (const k of FIELDS) {
    let v = form[k]
    if (NUMS.includes(k)) v = v === '' || v === null ? null : Number(v)
    else if (k !== 'use_yn') v = nn(typeof v === 'string' ? v.trim() : v)
    p[k] = v
  }
  return p
}

async function saveInfo() {
  try {
    if (no.value) {
      const p = payload(); delete p.hull_no
      await api.patch(`/hulls/${no.value}`, p)
      toast('저장되었습니다.', 'success')
    } else {
      const res = await api.post('/hulls', payload())
      no.value = res.hull_no
      toast('호선이 등록되었습니다.', 'success')
    }
    emit('changed', no.value)
    await loadTab('info')
  } catch (e) { toastError(e) }
}

async function removeHull() {
  if (!confirm(`호선 ${no.value} 및 하위 데이터(블록·공정·도면)를 모두 삭제합니다. 계속할까요?`)) return
  try {
    await api.del(`/hulls/${no.value}`)
    toast('삭제되었습니다.', 'success')
    emit('changed', null); emit('close')
  } catch (e) { toastError(e) }
}

async function saveMilestones() {
  try {
    await api.put(`/hulls/${no.value}/milestones`, { items: milestones.value.map((m) => ({ milestone_cd: m.milestone_cd, plan_dt: nn(m.plan_dt), actual_dt: nn(m.actual_dt) })) })
    toast('주요일정이 저장되었습니다.', 'success')
    await loadTab('ms')
  } catch (e) { toastError(e) }
}

async function addBlock() {
  try {
    await api.post(`/hulls/${no.value}/blocks`, { block_cd: nb.block_cd, block_nm: nn(nb.block_nm), block_type: nn(nb.block_type), weight_ton: nb.weight_ton === '' ? null : Number(nb.weight_ton) })
    toast('블록이 추가되었습니다.', 'success')
    Object.assign(nb, blankBlock())
    emit('changed', no.value)
    await loadTab('blocks')
  } catch (e) { toastError(e) }
}

async function removeBlock(b) {
  if (!confirm('블록과 해당 블록의 공정을 삭제합니다. (도면의 블록 연결은 해제)')) return
  try {
    await api.del(`/blocks/${b.block_id}`)
    toast('삭제되었습니다.', 'success')
    emit('changed', no.value)
    await loadTab('blocks')
  } catch (e) { toastError(e) }
}

async function go(token) {
  await navigate(token, no.value)
  emit('close')
}

onMounted(() => { if (no.value) loadTab('info') })
defineExpose({ tab, no })
</script>

<style scoped>
.sub { font-size: 12px; margin: -2px 0 10px; }
.acts { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
.chk { display: flex; align-items: center; gap: 6px; height: 30px; color: var(--ink) !important; font-size: 13px !important; }
.addrow { display: flex; gap: 8px; margin-top: 12px; }
.addrow .inp { width: 148px; }
.w110 { width: 110px !important; }
.wbar { width: 200px; }
.viewer-tab { height: calc(94vh - 151px); min-height: 300px; }
@media (max-width: 760px) { .viewer-tab { height: auto; } }
.sum { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.sum .card { min-height: 200px; }
.sum ul { margin: 6px 0; padding-left: 20px; }
.sum p { margin: 12px 0 6px; }
</style>
