<template>
  <AppModal :title="id ? `도면 ${d?.drawing_no || ''}` : '도면 등록'" :size="id ? 'xl' : 'large'" @close="emit('close')">
    <!-- 신규 -->
    <template v-if="!id">
      <p class="muted intro">신규 도면은 Rev0(작성중)으로 생성됩니다. PDF는 지금 첨부하거나 등록 후 뷰어에서 업로드할 수 있습니다.</p>
      <form class="card dwg-info" @submit.prevent="create">
        <div class="fg c2">
          <div class="fld"><label>도면번호 *</label><input v-model.trim="form.drawing_no" class="inp" aria-label="도면번호" /></div>
          <div class="fld"><label>분야</label><select v-model="form.discipline" class="inp" aria-label="분야"><option v-for="c in codeOptions('DWGDISC')" :key="c.code" :value="c.code">{{ c.name }}</option></select></div>
          <div class="fld s2"><label>도면명 *</label><input v-model.trim="form.drawing_nm" class="inp" aria-label="도면명" /></div>
          <div class="fld"><label>호선</label><select v-model="form.hull_no" class="inp" aria-label="호선" @change="onHull"><option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option></select></div>
          <div class="fld"><label>블록</label><select v-model="form.block_id" class="inp" aria-label="블록"><option :value="null">블록 없음</option><option v-for="b in blocks" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm }}</option></select></div>
          <div class="fld s2"><label>설계자</label><select v-model="form.designer_emp_no" class="inp" aria-label="설계자"><option :value="null">-</option><option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option></select></div>
          <div class="fld s2"><label>도면 파일 (PDF, 선택)</label><input type="file" accept=".pdf,application/pdf" class="inp file" aria-label="도면 파일" @change="newFile = $event.target.files[0] || null" /></div>
        </div>
        <div class="acts"><button class="btn pri" type="submit" :disabled="busy">저장</button></div>
      </form>
    </template>

    <!-- 상세 -->
    <div v-else-if="d" class="dgrid">
      <section class="card viewer">
        <h3>도면 뷰어 (PDF) <small class="muted">작성중(DRAFT) 리비전만 업로드·교체·삭제할 수 있습니다.</small></h3>
        <div class="vtool">
          <select v-model.number="viewRev" class="inp w110" aria-label="리비전">
            <option v-for="r in d.revisions" :key="r.rev_no" :value="r.rev_no">Rev{{ r.rev_no }} ({{ dwgStatusName(r.rev_status) }})</option>
          </select>
          <span class="fname" :title="cur?.file_nm">{{ cur?.file_nm || '파일 없음' }}</span>
          <span v-if="cur?.has_file" class="b b-ok">업로드 파일</span><span v-else class="b b-warn">샘플 PDF (미업로드)</span>
          <div class="grow"></div>
          <input v-if="canWrite" type="file" accept=".pdf,application/pdf" class="inp file w230" aria-label="PDF 업로드" :disabled="!isDraft || busy" @change="onUpload" />
          <button v-if="canWrite" class="btn" type="button" :disabled="!(isDraft && cur?.has_file) || busy" @click="delFile">파일 삭제</button>
          <button class="btn" type="button" @click="openNew">새 창으로 열기</button>
        </div>
        <div class="vbody">
          <template v-if="blobUrl">
            <iframe v-if="viewable" :src="blobUrl + '#view=FitH'" title="도면 PDF"></iframe>
            <div v-else class="vnone">이 브라우저는 PDF를 화면에 표시하지 않도록 설정되어 있습니다. <a :href="blobUrl" target="_blank" rel="noopener">PDF 열기</a></div>
          </template>
          <div v-else class="vnone">
            <b>샘플 PDF (미업로드)</b>
            <div>{{ d.drawing_no }} · Rev{{ viewRev }} · {{ dwgStatusName(cur?.rev_status) }}</div>
            <small>이 리비전에는 업로드된 도면 파일이 없습니다.</small>
          </div>
        </div>
      </section>

      <div class="side">
        <div class="meta">{{ d.hull_no }} · {{ codeName('DWGDISC', d.discipline) }} · {{ d.drawing_nm }}</div>

        <form class="card dwg-info" @submit.prevent="save">
          <h3>도면 정보</h3>
          <div class="fg c2">
            <div class="fld"><label>도면번호 *</label><input :value="d.drawing_no" class="inp" readonly aria-label="도면번호" /></div>
            <div class="fld"><label>분야</label><select v-model="form.discipline" class="inp" aria-label="분야" :disabled="!canWrite"><option v-for="c in codeOptions('DWGDISC')" :key="c.code" :value="c.code">{{ c.name }}</option></select></div>
            <div class="fld s2"><label>도면명 *</label><input v-model.trim="form.drawing_nm" class="inp" aria-label="도면명" :readonly="!canWrite" /></div>
            <div class="fld"><label>호선</label><select :value="d.hull_no" class="inp" disabled aria-label="호선"><option :value="d.hull_no">{{ d.hull_no }} {{ hullName(d.hull_no) }}</option></select></div>
            <div class="fld"><label>블록</label><select v-model="form.block_id" class="inp" aria-label="블록" :disabled="!canWrite"><option :value="null">블록 없음</option><option v-for="b in blocks" :key="b.block_id" :value="b.block_id">{{ b.block_cd }} {{ b.block_nm }}</option></select></div>
            <div class="fld s2"><label>설계자</label><select v-model="form.designer_emp_no" class="inp" aria-label="설계자" :disabled="!canWrite"><option :value="null">-</option><option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option></select></div>
          </div>
          <div v-if="canWrite" class="acts"><button class="btn pri" type="submit" :disabled="busy">저장</button><button class="btn danger" type="button" :disabled="busy" @click="remove">삭제</button></div>
        </form>

        <section class="card">
          <h3>리비전 이력 <span class="b b-DRAFT">{{ d.revisions.length }}</span></h3>
          <div class="tw rv">
            <table class="t revs">
              <colgroup><col style="width:92px" /><col style="width:62px" /><col /><col style="width:92px" /></colgroup>
              <thead><tr><th>Rev</th><th>상태</th><th>변경사유</th><th>배포일</th></tr></thead>
              <tbody><tr v-for="r in d.revisions" :key="r.rev_no" :class="{ sel: r.rev_no === viewRev }">
                <td><b>Rev{{ r.rev_no }}</b> <a @click="viewRev = r.rev_no">보기</a></td>
                <td><StatusBadge :value="r.rev_status" kind="dwg" /></td>
                <td class="cd"><div class="ell">{{ r.change_desc }}</div><div class="fn ell" :title="r.file_nm || '파일 없음'">{{ r.file_nm || '파일 없음' }}<template v-if="r.file_nm && !r.has_file"> (미업로드)</template></div></td>
                <td>{{ r.issue_dt || '미배포' }}<div class="fn">{{ dash(r.author_nm) }}</div></td>
              </tr></tbody>
            </table>
          </div>
          <template v-if="canWrite && latest">
            <form v-if="['ISSUED', 'OBSOLETE'].includes(latest.rev_status)" class="fg c2 act" @submit.prevent="newRev">
              <div class="fld s2"><label>신규 Rev{{ latest.rev_no + 1 }} 개정 사유</label><input v-model.trim="act.change_desc" class="inp" aria-label="개정 사유" /></div>
              <div class="fld"><label>도면 파일 (PDF, 선택)</label><input type="file" accept=".pdf,application/pdf" class="inp file" aria-label="신규 Rev 파일" @change="act.file = $event.target.files[0] || null" /></div>
              <div><button class="btn pri" type="submit" :disabled="busy">신규 Rev 작성</button></div>
            </form>
            <form v-else-if="latest.rev_status === 'DRAFT'" class="fg c2 act" @submit.prevent="requestApproval">
              <div class="note warn s2">Rev{{ latest.rev_no }} 작성중입니다. 검토자/승인자를 지정해 결재를 요청하세요.</div>
              <div class="fld"><label>1단계 검토자</label><select v-model="act.reviewer" class="inp" aria-label="1단계 검토자"><option value="">선택</option><option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option></select></div>
              <div class="fld"><label>2단계 승인자</label><select v-model="act.approver" class="inp" aria-label="2단계 승인자"><option value="">선택</option><option v-for="u in users" :key="u.emp_no" :value="u.emp_no">{{ u.display_name }} ({{ u.emp_no }})</option></select></div>
              <div><button class="btn pri" type="submit" :disabled="busy">결재 요청</button></div>
            </form>
            <div v-else-if="latest.rev_status === 'REVIEW'" class="note warn act">Rev{{ latest.rev_no }} 결재 진행중입니다. 결재자는 [결재함]에서 처리합니다.</div>
            <div v-else-if="latest.rev_status === 'APPROVED'" class="act">
              <div class="note ok">Rev{{ latest.rev_no }} 승인 완료 — 배포하면 연계 공정의 도면 게이트가 열립니다.</div>
              <button class="btn ok mt" type="button" :disabled="busy" @click="issue">Rev{{ latest.rev_no }} 배포</button>
            </div>
          </template>
        </section>

        <section class="card">
          <h3>결재 이력</h3>
          <div class="tw">
            <table class="t">
              <thead><tr><th>Rev</th><th>단계</th><th>결재자</th><th>결과</th></tr></thead>
              <tbody>
                <tr v-for="a in d.approvals" :key="a.approval_id" :title="[a.comment, a.act_dt].filter(Boolean).join(' · ')">
                  <td>Rev{{ a.rev_no }}</td><td>{{ stepName(a.step_no) }}</td><td>{{ dash(a.approver_nm) }}</td>
                  <td><span class="b" :class="RESULT[a.result]?.cls">{{ RESULT[a.result]?.name || a.result }}</span></td>
                </tr>
                <tr v-if="!d.approvals.length"><td colspan="4" class="empty">결재 이력이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card">
          <h3>연계 공정 <span class="b b-info">{{ d.plans.length }}</span></h3>
          <div v-if="d.impacts?.length" class="note warn imp">⚠ 최근 개정(Rev{{ d.impacts[0].rev_no }}, {{ d.impacts[0].issue_dt }})으로 이미 착수·완료된 공정 {{ d.impacts.length }}건이 영향을 받습니다: {{ d.impacts.map((i) => i.plan_label).join(', ') }}</div>
          <div class="tw">
            <table class="t">
              <thead><tr><th>공정</th><th>상태</th><th>구분</th><th>필요일</th><th v-if="canWrite"></th></tr></thead>
              <tbody>
                <tr v-for="p in d.plans" :key="p.plan_id">
                  <td><a @click="goPlan">{{ p.label }}</a></td><td><StatusBadge :value="p.plan_status" /></td>
                  <td>{{ p.required ? '필수' : '참고' }}</td><td>{{ dash(p.need_dt) }}</td>
                  <td v-if="canWrite"><button class="btn sm danger" type="button" :disabled="busy" @click="unlink(p.plan_id)">해제</button></td>
                </tr>
                <tr v-if="!d.plans.length"><td :colspan="canWrite ? 5 : 4" class="empty">연계된 공정이 없습니다.</td></tr>
              </tbody>
            </table>
          </div>
          <div v-if="canWrite" class="row act">
            <select v-model="link.plan_id" class="inp grow" aria-label="연계할 공정"><option :value="null">공정 선택</option><option v-for="p in d.available_plans" :key="p.plan_id" :value="p.plan_id">{{ p.label }}</option></select>
            <label class="row chk"><input v-model="link.required" type="checkbox" />필수</label>
            <button class="btn" type="button" :disabled="busy" @click="addLink">+ 공정 연계</button>
          </div>
        </section>
      </div>
    </div>
  </AppModal>
</template>

<script setup>
import { ref, reactive, computed, watch, inject, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api/client'
import { session, codeOptions, codeName } from '../stores/session'
import { dash, dwgStatusName } from '../utils/status'
import { RESULT, stepName } from '../utils/approval'
import { checkPdf, uploadPdf, pdfBlobUrl, revokeUrl, pdfViewable } from '../utils/pdf'
import { toast, toastError, toastOk } from '../utils/toast'
import AppModal from '../components/AppModal.vue'
import StatusBadge from '../components/StatusBadge.vue'

const props = defineProps({ drawingId: { type: Number, default: null }, canWrite: Boolean })
const emit = defineEmits(['close', 'changed'])
const navigate = inject('navigate', null)


const id = ref(props.drawingId)
const d = ref(null)
const hulls = ref([])
const blocks = ref([])
const users = ref([])
const busy = ref(false)
const newFile = ref(null)
const viewRev = ref(null)
const blobUrl = ref(null)
const viewable = pdfViewable()
const form = reactive({ drawing_no: '', drawing_nm: '', discipline: '', hull_no: '', block_id: null, designer_emp_no: null })
const act = reactive({ change_desc: '', file: null, reviewer: '', approver: '' })
const link = reactive({ plan_id: null, required: true })

const cur = computed(() => d.value?.revisions.find((r) => r.rev_no === viewRev.value) || null)
const latest = computed(() => d.value?.revisions[0] || null)
const isDraft = computed(() => cur.value?.rev_status === 'DRAFT')
const hullName = (no) => hulls.value.find((h) => h.hull_no === no)?.hull_nm || ''
const optOr = (emp) => (users.value.some((u) => u.emp_no === emp) ? emp : '')

async function loadBlocks(hullNo) {
  blocks.value = hullNo ? await api.get(`/hulls/${hullNo}/blocks`) : []
}
async function onHull() { form.block_id = null; try { await loadBlocks(form.hull_no) } catch (e) { toastError(e) } }

async function loadDetail(rev = null) {
  const x = await api.get(`/drawings/${id.value}`)
  d.value = x
  Object.assign(form, { drawing_no: x.drawing_no, drawing_nm: x.drawing_nm, discipline: x.discipline, hull_no: x.hull_no, block_id: x.block_id, designer_emp_no: x.designer_emp_no })
  if (rev !== null) viewRev.value = rev
  else if (!x.revisions.some((r) => r.rev_no === viewRev.value)) viewRev.value = x.current_rev_no
  Object.assign(act, { change_desc: '', file: null, reviewer: optOr('lee.dwg'), approver: optOr('admin') })
  link.plan_id = null
  await loadBlocks(x.hull_no)
}

// PDF blob: 표시 리비전·파일 유무가 바뀌면 다시 받는다. 이전 blob URL은 해제.
let blobSeq = 0
async function refreshBlob() {
  const seq = ++blobSeq
  revokeUrl(blobUrl.value); blobUrl.value = null
  if (!cur.value?.has_file) return
  try {
    const u = await pdfBlobUrl(id.value, cur.value.rev_no)
    if (seq !== blobSeq) { revokeUrl(u); return }
    blobUrl.value = u
  } catch (e) { toastError(e) }
}
watch(() => [id.value, viewRev.value, cur.value?.has_file, cur.value?.file_nm, d.value], refreshBlob)

async function run(fn) {
  busy.value = true
  try { await fn() } catch (e) { toastError(e) } finally { busy.value = false }
}

function create() {
  return run(async () => {
    const err = await checkPdf(newFile.value)
    if (err) { toast(err, 'error'); return }
    const x = await api.post('/drawings', { drawing_no: form.drawing_no, drawing_nm: form.drawing_nm, discipline: form.discipline || null, hull_no: form.hull_no, block_id: form.block_id, designer_emp_no: form.designer_emp_no })
    let msg = '도면이 등록되었습니다. (Rev0 작성중)'
    if (newFile.value) {
      try { await uploadPdf(x.drawing_id, 0, newFile.value); msg += ' PDF 첨부됨.' } catch (e) { msg += ` (PDF 저장 실패: ${e.message})` }
    }
    toastOk(msg)
    id.value = x.drawing_id
    emit('changed', x.drawing_id)
    await loadDetail(0)
  })
}
function save() {
  return run(async () => {
    await api.patch(`/drawings/${id.value}`, { drawing_nm: form.drawing_nm, discipline: form.discipline || null, block_id: form.block_id, designer_emp_no: form.designer_emp_no })
    toastOk('저장되었습니다.')
    emit('changed', id.value)
    await loadDetail()
  })
}
function remove() {
  if (!confirm('도면과 리비전·결재·공정 연계를 삭제합니다.')) return
  return run(async () => {
    await api.del(`/drawings/${id.value}`)
    toastOk('삭제되었습니다.')
    emit('changed', null); emit('close')
  })
}
async function onUpload(ev) {
  const file = ev.target.files[0]
  ev.target.value = ''
  if (!file) return
  const rev = viewRev.value
  await run(async () => {
    const err = await checkPdf(file)
    if (err) { toast(err, 'error'); return }
    await uploadPdf(id.value, rev, file)
    toastOk(`Rev${rev}에 PDF를 업로드했습니다.`)
    await loadDetail(rev)
  })
}
function delFile() {
  return run(async () => {
    await api.del(`/drawings/${id.value}/revisions/${viewRev.value}/pdf`)
    toastOk('파일을 삭제했습니다.')
    await loadDetail(viewRev.value)
  })
}
function openNew() {
  if (!blobUrl.value) { toast('표시 중인 PDF가 없습니다.', 'error'); return }
  window.open(blobUrl.value, '_blank')
}
function newRev() {
  return run(async () => {
    const err = await checkPdf(act.file)
    if (err) { toast(err, 'error'); return }
    const n = latest.value.rev_no + 1
    const file = act.file
    await api.post(`/drawings/${id.value}/revisions`, { change_desc: act.change_desc })
    let msg = `Rev${n} 작성중으로 생성되었습니다.`
    if (file) { try { await uploadPdf(id.value, n, file) } catch (e) { msg += ` (PDF 저장 실패: ${e.message})` } }
    toastOk(msg)
    emit('changed', id.value)
    await loadDetail(n)
  })
}
function requestApproval() {
  return run(async () => {
    await api.post(`/drawings/${id.value}/revisions/${latest.value.rev_no}/request-approval`, { reviewer_emp_no: act.reviewer || null, approver_emp_no: act.approver || null })
    toastOk('결재가 요청되었습니다.')
    emit('changed', id.value)
    await loadDetail()
  })
}
function issue() {
  return run(async () => {
    const n = latest.value.rev_no
    await api.post(`/drawings/${id.value}/revisions/${n}/issue`)
    toastOk('도면이 배포되었습니다. 연계 공정 상태가 갱신됩니다.')
    emit('changed', id.value)
    await loadDetail(n)
  })
}
function addLink() {
  if (!link.plan_id) { toast('공정을 선택하세요.', 'error'); return }
  return run(async () => {
    await api.post(`/drawings/${id.value}/plans`, { plan_id: link.plan_id, required: link.required })
    toastOk('공정이 연계되었습니다.')
    emit('changed', id.value)
    await loadDetail()
  })
}
function unlink(planId) {
  return run(async () => {
    await api.del(`/drawings/${id.value}/plans/${planId}`)
    toastOk('연계가 해제되었습니다.')
    emit('changed', id.value)
    await loadDetail()
  })
}
function goPlan() { emit('close'); navigate?.('plan-gantt', d.value.hull_no) }

onMounted(async () => {
  try {
    const [hs, us] = await Promise.all([api.get('/hulls'), api.get('/users/options')])
    hulls.value = hs; users.value = us
    if (id.value) await loadDetail()
    else {
      Object.assign(form, { discipline: codeOptions('DWGDISC')[0]?.code || '', hull_no: hs[0]?.hull_no || '', designer_emp_no: session.me?.emp_no || null })
      await loadBlocks(form.hull_no)
    }
  } catch (e) { toastError(e) }
})
onBeforeUnmount(() => { blobSeq++; revokeUrl(blobUrl.value) })
</script>

<style scoped>
.intro { margin: 2px 0 10px; font-size: 12.5px; }
.acts { display: flex; gap: 8px; margin-top: 12px; }
.file { padding: 3px 4px; }
.w110 { width: 110px; } .w230 { width: 230px; }
.dgrid { display: grid; grid-template-columns: 1fr 440px; gap: 12px; height: 100%; min-height: 0; }
.viewer { display: flex; flex-direction: column; margin: 0; min-height: 0; }
.viewer h3 small { font-size: 12px; font-weight: 400; }
.vtool { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.fname { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.vbody { flex: 1; background: #525659; border-radius: 4px; overflow: hidden; display: flex; align-items: center; justify-content: center; min-height: 300px; }
.vbody iframe { width: 100%; height: 100%; border: 0; background: #525659; }
.vnone { color: #fff; text-align: center; display: flex; flex-direction: column; gap: 8px; font-size: 12.5px; }
.vnone b { font-size: 13px; }
.vnone a { color: #bfdbfe; }
.side { overflow: auto; min-height: 0; padding-right: 2px; }
.meta { font-size: 12px; color: var(--muted); margin: 0 0 8px 2px; }
.rv { max-height: 190px; }
.revs { table-layout: fixed; }
.revs .cd { white-space: normal; }
.ell { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fn { font-size: 11.5px; color: var(--muted); }
.act { margin-top: 10px; }
.mt { margin-top: 8px; }
.imp { margin-bottom: 8px; }
.chk { gap: 4px; white-space: nowrap; }
@media (max-width: 1100px) {
  .dgrid { grid-template-columns: 1fr; height: auto; }
  .viewer { height: 60vh; }
  .side { overflow: visible; }
}
</style>
