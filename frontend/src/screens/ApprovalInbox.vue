<template>
  <div class="apv">
    <PageHead :title="title" :readonly="!canWrite" :desc="`${session.me?.display_name || ''} 님의 결재 대기와 배포 대기 도면입니다.`" />

    <section class="card">
      <h3>내 결재 대기 <span class="b b-warn">{{ inbox.waiting.length }}</span></h3>
      <div class="tw">
        <table class="t wait-table">
          <thead><tr><th>도면번호</th><th>도면명</th><th>Rev</th><th>단계</th><th>변경사유</th><th>의견</th><th v-if="canWrite"></th></tr></thead>
          <tbody>
            <tr v-for="a in inbox.waiting" :key="a.approval_id">
              <td><a @click="openDrawing?.(a.drawing_id)">{{ a.drawing_no }}</a></td><td>{{ a.drawing_nm }}</td>
              <td>Rev{{ a.rev_no }}</td><td>{{ stepName(a.step_no) }}</td><td>{{ dash(a.change_desc) }}</td>
              <td><input v-model.trim="comments[a.approval_id]" class="inp w150" placeholder="의견 (반려 시 필수)" aria-label="의견" :disabled="!canWrite" /></td>
              <td v-if="canWrite" class="right">
                <button class="btn sm ok" type="button" :disabled="busy" @click="decide(a, 'APPROVE')">승인</button>
                <button class="btn sm danger" type="button" :disabled="busy" @click="decide(a, 'REJECT')">반려</button>
              </td>
            </tr>
            <tr v-if="loaded && !inbox.waiting.length"><td :colspan="canWrite ? 7 : 6" class="empty">결재 대기 건이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h3>배포 대기 (승인 완료) <span class="b b-info">{{ inbox.ready.length }}</span></h3>
      <div class="tw">
        <table class="t">
          <thead><tr><th>도면번호</th><th>도면명</th><th>Rev</th><th>배포 시 착수 가능해질 수 있는 공정</th><th v-if="inbox.can_issue"></th></tr></thead>
          <tbody>
            <tr v-for="r in inbox.ready" :key="r.drawing_id">
              <td><a @click="openDrawing?.(r.drawing_id)">{{ r.drawing_no }}</a></td><td>{{ r.drawing_nm }}</td><td>Rev{{ r.rev_no }}</td>
              <td class="wrap">{{ r.effect_plans?.length ? r.effect_plans.join(', ') : '-' }}</td>
              <td v-if="inbox.can_issue" class="right"><button class="btn sm ok" type="button" :disabled="busy" @click="issue(r)">배포</button></td>
            </tr>
            <tr v-if="loaded && !inbox.ready.length"><td :colspan="inbox.can_issue ? 5 : 4" class="empty">배포 대기 도면이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card">
      <h3>최근 결재 이력</h3>
      <div class="tw">
        <table class="t">
          <thead><tr><th>일시</th><th>도면번호</th><th>Rev</th><th>단계</th><th>결재자</th><th>결과</th><th>의견</th></tr></thead>
          <tbody>
            <tr v-for="h in history" :key="h.approval_id">
              <td>{{ h.act_dt }}</td><td>{{ h.drawing_no }}</td><td>Rev{{ h.rev_no }}</td><td>{{ stepName(h.step_no) }}</td>
              <td>{{ dash(h.approver_nm) }}</td><td><span class="b" :class="RESULT[h.result]?.cls">{{ RESULT[h.result]?.name || h.result }}</span></td>
              <td class="wrap">{{ dash(h.comment) }}</td>
            </tr>
            <tr v-if="loaded && !history.length"><td colspan="7" class="empty">결재 이력이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref, watch, inject, onMounted } from 'vue'
import { api } from '../api/client'
import { session } from '../stores/session'
import { dash } from '../utils/status'
import { RESULT, stepName } from '../utils/approval'
import { toast, toastError, toastOk } from '../utils/toast'
import PageHead from '../components/PageHead.vue'

const props = defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })
const openDrawing = inject('openDrawing', null)

const inbox = reactive({ waiting: [], ready: [], can_issue: false })
const history = ref([])
const comments = reactive({})
const loaded = ref(false)
const busy = ref(false)

async function load() {
  try {
    const [ib, hs] = await Promise.all([api.get('/approvals/inbox'), api.get('/approvals/history')])
    Object.assign(inbox, ib); history.value = hs; loaded.value = true
  } catch (e) { toastError(e) }
}

async function decide(a, result) {
  const comment = comments[a.approval_id] || ''
  if (result === 'REJECT' && !comment) { toast('반려 시 의견을 입력하세요.', 'error'); return }
  busy.value = true
  try {
    await api.post(`/approvals/${a.approval_id}/decision`, { result, comment })
    delete comments[a.approval_id]
    toastOk(result === 'APPROVE' ? '승인했습니다.' : '반려했습니다. 도면은 작성중으로 되돌려집니다.')
  } catch (e) { toastError(e) } finally { busy.value = false; await load() }
}
async function issue(r) {
  busy.value = true
  try {
    await api.post(`/drawings/${r.drawing_id}/revisions/${r.rev_no}/issue`)
    toastOk('도면이 배포되었습니다. 연계 공정 상태가 갱신됩니다.')
  } catch (e) { toastError(e) } finally { busy.value = false; await load() }
}

// 탭 복귀·도면 모달 닫힘 뒤 다시 불러온다.
watch(() => props.active, (v, old) => { if (v && old === false) load() })
watch(() => props.ctx, load)
onMounted(load)
</script>

<style scoped>
.w150 { width: 148px; }
.card h3 .b { font-weight: 600; }
</style>
