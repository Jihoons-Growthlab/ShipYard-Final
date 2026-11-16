<template>
  <div class="inq">
    <PageHead :title="title" :desc="isAdmin ? '회원의 건의·문의를 확인하고 상태와 답변을 처리합니다.' : '시스템 개선 건의나 사용 문의를 남겨 주세요. 관리자가 확인 후 답변합니다.'" />
    <form class="toolbar" @submit.prevent="load()">
      <div class="seg" role="group" aria-label="상태">
        <button type="button" :class="{ on: !f.status }" @click="setStatus('')">전체 <b>{{ allCount }}</b></button>
        <button v-for="(name, k) in statuses" :key="k" type="button" :class="{ on: f.status === k }" @click="setStatus(k)">{{ name }} <b>{{ counts[k] || 0 }}</b></button>
      </div>
      <input v-model.trim="f.q" class="inp w180" placeholder="제목/내용/작성자" aria-label="검색어" />
      <button class="btn pri" type="submit">조회</button>
      <label v-if="isAdmin" class="row chk"><input v-model="f.mine" type="checkbox" @change="load()" />내 글만</label>
      <div class="grow"></div>
      <button class="btn pri" type="button" @click="startNew">+ 새 글 작성</button>
    </form>

    <div class="body">
      <div class="tw list">
        <table class="t clk inq-table">
          <thead><tr><th class="num">No</th><th>상태</th><th>분류</th><th>제목</th><th v-if="isAdmin">작성자</th><th>작성일</th><th>답변일</th></tr></thead>
          <tbody>
            <tr v-for="x in items" :key="x.inquiry_id" :class="{ sel: cur?.inquiry_id === x.inquiry_id }" @click="view(x)">
              <td class="num">{{ x.inquiry_id }}</td>
              <td><span class="b" :class="ST_CLS[x.status]">{{ statuses[x.status] || x.status }}</span></td>
              <td><span class="cat" :class="'c-' + x.category">{{ categories[x.category] || x.category }}</span></td>
              <td class="ttl"><b>{{ x.title }}</b></td>
              <td v-if="isAdmin">{{ dash(x.create_user_nm) }}</td>
              <td>{{ localDateTime(x.create_dt).slice(0, 10) }}</td>
              <td>{{ x.answer_dt ? localDateTime(x.answer_dt).slice(0, 10) : '-' }}</td>
            </tr>
            <tr v-if="loaded && !items.length"><td :colspan="isAdmin ? 7 : 6" class="empty">{{ filtered ? '조건에 맞는 글이 없습니다.' : '아직 작성한 글이 없습니다.' }}</td></tr>
          </tbody>
        </table>
      </div>

      <section class="card panel">
        <!-- 작성·수정 -->
        <form v-if="mode === 'new' || mode === 'edit'" class="ed" @submit.prevent="submit">
          <h3>{{ mode === 'new' ? '새 글 작성' : '글 수정' }}</h3>
          <div class="fld"><label>분류 *</label><select v-model="form.category" class="inp" aria-label="분류"><option v-for="(name, k) in categories" :key="k" :value="k">{{ name }}</option></select></div>
          <div class="fld"><label>제목 *</label><input v-model="form.title" class="inp" placeholder="한 줄로 요약해 주세요" aria-label="제목" /></div>
          <div class="fld"><label>내용 *</label><textarea v-model="form.content" class="inp" rows="10" placeholder="어떤 화면에서 무엇을 했을 때 어떤 일이 있었는지, 또는 원하는 기능을 적어 주세요." aria-label="내용"></textarea></div>
          <div class="row"><button class="btn pri" type="submit" :disabled="busy">{{ mode === 'new' ? '등록' : '저장' }}</button><button class="btn" type="button" @click="cancel">취소</button></div>
        </form>

        <!-- 보기 -->
        <div v-else-if="mode === 'view' && cur" class="vw">
          <div class="row"><span class="b" :class="ST_CLS[cur.status]">{{ statuses[cur.status] }}</span><span class="cat" :class="'c-' + cur.category">{{ categories[cur.category] }}</span><div class="grow"></div><span class="muted sm">No.{{ cur.inquiry_id }}</span></div>
          <h4>{{ cur.title }}</h4>
          <div class="muted sm">{{ dash(cur.create_user_nm) }} · {{ localDateTime(cur.create_dt) }}<template v-if="cur.modify_dt"> · 수정 {{ localDateTime(cur.modify_dt) }}</template></div>
          <div class="content">{{ cur.content }}</div>
          <div v-if="cur.answer" class="answer">
            <div class="row"><b>관리자 답변</b><div class="grow"></div><span class="muted sm">{{ dash(cur.answer_user_nm) }} · {{ localDateTime(cur.answer_dt) }}</span></div>
            <div class="abody">{{ cur.answer }}</div>
          </div>
          <div v-else-if="!isAdmin" class="muted pending">관리자가 확인 중입니다. 답변이 등록되면 여기에 표시됩니다.</div>
          <div v-if="cur.mine && cur.status === 'OPEN' && !isAdmin" class="row">
            <button class="btn" type="button" @click="startEdit">수정</button><button class="btn danger" type="button" :disabled="busy" @click="remove">삭제</button>
          </div>
          <div v-if="isAdmin" class="proc">
            <b>처리</b>
            <div class="stbtns">
              <button v-for="(name, k) in statuses" :key="k" type="button" :class="['st', proc.status === k ? 'on-' + k : '']" @click="proc.status = k">{{ name }}</button>
            </div>
            <div class="fld"><label>답변 {{ needAnswer ? '*' : '(선택)' }}</label><textarea v-model="proc.answer" class="inp" rows="5" aria-label="답변"></textarea></div>
            <div class="row">
              <button class="btn pri" type="button" :disabled="busy" @click="process">처리 저장</button>
              <button v-if="cur.mine && cur.status === 'OPEN'" class="btn" type="button" @click="startEdit">수정</button>
              <button class="btn danger" type="button" :disabled="busy" @click="remove">삭제</button>
            </div>
          </div>
        </div>

        <!-- 빈 상태 -->
        <div v-else class="emp">
          <div>{{ isAdmin ? '목록에서 글을 선택해 처리하세요.' : '목록에서 글을 선택하거나 새 글을 작성하세요.' }}</div>
          <div class="muted sm">{{ Object.values(categories).join(' · ') || '오류 신고 · 기능 건의 · 사용 문의 · 기타' }}</div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted, watch } from 'vue'
import { api } from '../api/client'
import { dash } from '../utils/status'
import { localDateTime } from '../utils/date'
import { toastError, toastOk } from '../utils/toast'
import PageHead from '../components/PageHead.vue'

const props = defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })

const ST_CLS = { OPEN: 'b-info', IN_PROGRESS: 'b-warn', DONE: 'b-ok', REJECTED: 'b-bad' }
const f = reactive({ status: '', q: '', mine: false })
const items = ref([])
const counts = ref({})
const categories = ref({ BUG: '오류 신고', FEATURE: '기능 건의', QUESTION: '사용 문의', ETC: '기타' })
const statuses = ref({ OPEN: '접수', IN_PROGRESS: '처리중', DONE: '완료', REJECTED: '반려' })
const isAdmin = ref(false)
const loaded = ref(false)
const filtered = ref(false)
const mode = ref(null) // null | new | edit | view
const cur = ref(null)
const busy = ref(false)
const form = reactive({ category: 'FEATURE', title: '', content: '' })
const proc = reactive({ status: 'OPEN', answer: '' })

const allCount = computed(() => Object.values(counts.value).reduce((a, b) => a + b, 0))
const needAnswer = computed(() => ['DONE', 'REJECTED'].includes(proc.status))

async function load(keepId = cur.value?.inquiry_id) {
  try {
    const r = await api.get('/inquiries', { status: f.status, q: f.q, mine: f.mine ? 'true' : '' })
    items.value = r.items; counts.value = r.counts; isAdmin.value = !!r.is_admin
    if (r.categories) categories.value = r.categories
    if (r.statuses) statuses.value = r.statuses
    filtered.value = !!(f.status || f.q || f.mine) || (isAdmin.value && allCount.value > 0)
    loaded.value = true
    if (mode.value === 'view' && keepId) {
      const x = r.items.find((i) => i.inquiry_id === keepId)
      if (x) view(x)
    }
  } catch (e) { toastError(e) }
}
function setStatus(s) { f.status = s; load() }
function view(x) { cur.value = x; mode.value = 'view'; Object.assign(proc, { status: x.status, answer: x.answer || '' }) }
function startNew() { cur.value = null; mode.value = 'new'; Object.assign(form, { category: 'FEATURE', title: '', content: '' }) }
function startEdit() { mode.value = 'edit'; Object.assign(form, { category: cur.value.category, title: cur.value.title, content: cur.value.content }) }
function cancel() { mode.value = cur.value ? 'view' : null }

async function run(fn) { busy.value = true; try { await fn() } catch (e) { toastError(e) } finally { busy.value = false } }

function submit() {
  return run(async () => {
    if (mode.value === 'new') {
      const x = await api.post('/inquiries', { ...form })
      toastOk('등록되었습니다. 관리자가 확인 후 답변합니다.')
      cur.value = x; mode.value = 'view'
      await load(x.inquiry_id)
    } else {
      await api.patch(`/inquiries/${cur.value.inquiry_id}`, { ...form })
      toastOk('저장되었습니다.')
      mode.value = 'view'
      await load(cur.value.inquiry_id)
    }
  })
}
function process() {
  return run(async () => {
    await api.patch(`/inquiries/${cur.value.inquiry_id}`, { status: proc.status, answer: proc.answer })
    toastOk('처리 내용을 저장했습니다.')
    await load(cur.value.inquiry_id)
  })
}
function remove() {
  if (!confirm(`"${cur.value.title}" 글을 삭제합니다.`)) return
  return run(async () => {
    await api.del(`/inquiries/${cur.value.inquiry_id}`)
    toastOk('삭제되었습니다.')
    cur.value = null; mode.value = null
    await load(null)
  })
}

onMounted(() => load())
// 챗봇 접수(F13) 뒤 셸이 ctx를 올리면 다시 조회한다.
watch(() => props.ctx, () => load())
</script>

<style scoped>
.inq { height: 100%; display: flex; flex-direction: column; min-height: 0; }
.w180 { width: 180px; }
.sm { font-size: 11.5px; }
.chk { gap: 4px; }
.seg { display: flex; gap: 2px; background: #e8ecf2; border-radius: 8px; padding: 3px; }
.seg button { border: 0; background: transparent; font: inherit; font-size: 12.5px; padding: 4px 10px; border-radius: 6px; cursor: pointer; color: var(--muted); }
.seg button b { font-weight: 600; margin-left: 4px; }
.seg button.on { background: #fff; color: var(--pri-d); font-weight: 700; box-shadow: var(--shadow-sm); }
.body { flex: 1; min-height: 0; display: grid; grid-template-columns: 1fr 460px; gap: 12px; }
.list { min-height: 0; }
.ttl { max-width: 340px; overflow: hidden; text-overflow: ellipsis; }
.cat { font-size: 11.5px; padding: 1px 7px; border-radius: 4px; background: #f3f4f6; color: #4b5563; }
.c-BUG { background: #fee2e2; color: #b91c1c; } .c-FEATURE { background: #ede9fe; color: #7c3aed; }
.c-QUESTION { background: #e0f2fe; color: #0369a1; } .c-ETC { background: #f3f4f6; color: #6b7280; }
.panel { margin: 0; overflow: auto; min-height: 0; }
.ed, .vw { display: flex; flex-direction: column; gap: 10px; }
.ed h3 { margin: 0; }
.vw h4 { font-size: 15px; margin: 2px 0 0; }
.content { background: #f8fafc; border: 1px solid var(--line2); border-radius: 8px; padding: 10px 12px; white-space: pre-wrap; line-height: 1.6; }
.answer { border-left: 3px solid var(--ok); padding: 4px 0 4px 10px; display: flex; flex-direction: column; gap: 6px; }
.abody { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 10px 12px; white-space: pre-wrap; }
.pending { font-size: 12.5px; }
.proc { border-top: 1px dashed var(--line); padding-top: 12px; display: flex; flex-direction: column; gap: 10px; }
.stbtns { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.st { height: 30px; border: 1px solid var(--line); background: #fff; border-radius: 6px; font: inherit; cursor: pointer; color: var(--muted); }
.st.on-OPEN { background: var(--pri); border-color: var(--pri); color: #fff; font-weight: 700; }
.st.on-IN_PROGRESS { background: var(--warn); border-color: var(--warn); color: #fff; font-weight: 700; }
.st.on-DONE { background: var(--ok); border-color: var(--ok); color: #fff; font-weight: 700; }
.st.on-REJECTED { background: var(--err); border-color: var(--err); color: #fff; font-weight: 700; }
.emp { text-align: center; padding: 60px 10px; display: flex; flex-direction: column; gap: 8px; }
@media (max-width: 1200px) { .body { grid-template-columns: 1fr; } .inq { height: auto; } }
</style>
