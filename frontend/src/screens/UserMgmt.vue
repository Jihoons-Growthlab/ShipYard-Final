<template>
  <div class="users">
    <section class="top">
      <PageHead :title="title" desc="상단 목록 / 하단 입력·수정 (CRUD)" />
      <form class="toolbar" @submit.prevent="load()">
        <select v-model="f.status" class="inp w110" aria-label="상태">
          <option value="">상태 전체</option>
          <option v-for="(v, k) in USER_STATUS" :key="k" :value="k">{{ v.name }}</option>
        </select>
        <input v-model.trim="f.q" class="inp w148" placeholder="아이디/이름/이메일/전화" aria-label="검색어" />
        <button class="btn pri" type="submit">조회</button>
        <button class="btn" type="button" @click="reset">초기화</button>
        <div class="grow"></div>
        <span class="muted cnt">{{ total }}명 · 승인대기 {{ pending }}명</span>
      </form>
      <div class="tw list">
        <table class="t clk user-table">
          <thead><tr><th>아이디</th><th>이름</th><th>이메일</th><th>전화번호</th><th>생년월일</th><th>상태</th><th>2차인증</th><th>권한그룹</th><th>가입일</th></tr></thead>
          <tbody>
            <tr v-for="u in users" :key="u.emp_no" :class="{ sel: sel?.emp_no === u.emp_no }" @click="select(u)">
              <td><b>{{ u.emp_no }}</b></td><td>{{ u.display_name }}</td><td>{{ u.email }}</td><td>{{ u.phone }}</td><td>{{ dash(u.birth_date) }}</td>
              <td><span class="b" :class="USER_STATUS[u.status]?.cls">{{ USER_STATUS[u.status]?.name || u.status }}</span></td>
              <td>{{ u.totp_enabled ? '사용' : '-' }}</td>
              <td>{{ u.groups?.length ? u.groups.map((g) => g.name).join(', ') : '-' }}</td>
              <td>{{ dash(u.created_at?.slice(0, 10)) }}</td>
            </tr>
            <tr v-if="loaded && !users.length"><td colspan="9" class="empty">조회된 회원이 없습니다.</td></tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card bottom">
      <h3>{{ mode === 'edit' ? `회원 수정 — ${sel.display_name}` : mode === 'new' ? '회원 등록' : '입력 / 수정' }}</h3>
      <div v-if="!mode" class="muted pick">목록에서 회원을 선택하거나 [신규]를 누르세요.</div>
      <div class="bwrap" :class="{ withperm: mode === 'edit' || mode === 'new' }">
        <form v-if="mode" class="user-form" @submit.prevent="save">
          <div class="fg c4">
            <div class="fld"><label>성 *</label><input v-model.trim="form.last_name" class="inp" aria-label="성" /></div>
            <div class="fld"><label>이름 *</label><input v-model.trim="form.first_name" class="inp" aria-label="이름" /></div>
            <div class="fld"><label>생년월일 *</label><input v-model="form.birth_date" type="date" class="inp" aria-label="생년월일" /></div>
            <div class="fld"><label>전화번호 *</label><input v-model.trim="form.phone" class="inp" placeholder="010-0000-0000" aria-label="전화번호" /></div>
            <div class="fld s2"><label>이메일 *</label><input v-model.trim="form.email" class="inp" aria-label="이메일" /></div>
            <div class="fld"><label>아이디 *</label><input v-model.trim="form.emp_no" class="inp" :readonly="mode === 'edit'" aria-label="아이디" /></div>
            <div class="fld"><label>{{ mode === 'edit' ? '비밀번호 (변경 시만 입력)' : '비밀번호 *' }}</label><input v-model="form.password" type="password" class="inp" placeholder="8자 이상" autocomplete="new-password" aria-label="비밀번호" /></div>
            <div class="fld"><label>상태</label><select v-model="form.status" class="inp" aria-label="회원 상태"><option v-for="(v, k) in USER_STATUS" :key="k" :value="k">{{ v.name }}</option></select></div>
            <div class="fld"><label>권한 그룹</label><select v-model="form.group" class="inp" aria-label="권한 그룹"><option value="">없음</option><option v-for="g in groups" :key="g.code" :value="g.code">{{ g.name }}</option></select></div>
            <div class="fld"><label>구글 2차인증</label><label class="row chk"><input v-model="form.totp_enabled" type="checkbox" />사용 (등록된 사용자만)</label></div>
            <div class="fld"><label>가입일</label><input :value="mode === 'edit' ? dash(sel.created_at?.slice(0, 10)) : '-'" class="inp" readonly aria-label="가입일" /></div>
          </div>
        </form>

        <div v-if="mode" class="perm">
          <div class="perm-h"><b>메뉴 권한</b><span class="muted">회원별 지정이 그룹 권한보다 우선합니다.</span><div class="grow"></div>
            <button v-if="mode === 'edit'" class="btn sm" type="button" @click="resetToGroup(perm)">그룹 기본값</button></div>
          <div v-if="mode === 'new'" class="muted pick">저장한 뒤 메뉴 권한을 지정할 수 있습니다.</div>
          <div v-else class="tw ptable">
            <table class="t perm-table">
              <thead><tr><th>메뉴</th><th v-for="l in LEVELS" :key="l.v" class="c">{{ l.name }}</th><th>그룹</th></tr></thead>
              <tbody>
                <tr v-for="r in perm" :key="r.menu_id">
                  <td :class="{ sub: r.depth }"><b v-if="isCustom(r)">{{ r.title }}</b><template v-else>{{ r.title }}</template> <span v-if="isCustom(r)" class="b b-info">개별</span></td>
                  <td v-for="l in LEVELS" :key="l.v" class="c">
                    <input type="radio" :name="`perm-${r.menu_id}`" :checked="effective(r) === l.v" :aria-label="`${r.title} ${l.name}`" @change="setLevel(perm, r.menu_id, l.v)" />
                  </td>
                  <td class="muted">{{ levelName(r.group_level) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div class="btns">
        <button class="btn" type="button" @click="startNew">신규</button>
        <button class="btn pri" type="button" :disabled="!mode || busy" @click="save">저장</button>
        <button class="btn danger" type="button" :disabled="mode !== 'edit' || busy" @click="remove">삭제</button>
        <button v-if="mode === 'edit' && sel.status === 'pending'" class="btn ok" type="button" :disabled="busy" @click="approve">가입 승인</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { api } from '../api/client'
import { session, loadSession } from '../stores/session'
import { dash } from '../utils/status'
import { LEVELS, levelName, permRows, effective, isCustom, setLevel, resetToGroup, menusPayload, permChanged } from '../utils/menuPerm'
import { toast, toastError, toastOk } from '../utils/toast'
import PageHead from '../components/PageHead.vue'

defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })

const USER_STATUS = { pending: { name: '승인대기', cls: 'b-warn' }, approved: { name: '승인', cls: 'b-ok' }, rejected: { name: '반려', cls: 'b-bad' }, disabled: { name: '중지', cls: '' } }
const BLANK = { emp_no: '', last_name: '', first_name: '', birth_date: '', phone: '', email: '', password: '', status: 'approved', group: '', totp_enabled: false }

const f = reactive({ status: '', q: '' })
const users = ref([])
const total = ref(0)
const pending = ref(0)
const groups = ref([])
const loaded = ref(false)
const sel = ref(null)
const mode = ref(null) // null | 'new' | 'edit'
const form = reactive({ ...BLANK })
const perm = ref([])
const busy = ref(false)

async function load(keep = sel.value?.emp_no) {
  try {
    const r = await api.get('/users', { ...f })
    users.value = r.users; total.value = r.total; pending.value = r.pending; loaded.value = true
    const again = keep && r.users.find((u) => u.emp_no === keep)
    if (again) await select(again)
  } catch (e) { toastError(e) }
}
function reset() { Object.assign(f, { status: '', q: '' }); load() }

async function select(u) {
  sel.value = u; mode.value = 'edit'
  Object.assign(form, BLANK, {
    emp_no: u.emp_no, last_name: u.last_name, first_name: u.first_name, birth_date: u.birth_date || '', phone: u.phone, email: u.email,
    status: u.status, group: u.groups?.[0]?.code || '', totp_enabled: !!u.totp_enabled,
  })
  try { perm.value = permRows((await api.get(`/users/${u.emp_no}/menus`)).menus) } catch (e) { perm.value = []; toastError(e) }
}
function startNew() { sel.value = null; mode.value = 'new'; perm.value = []; Object.assign(form, BLANK) }

function body() {
  const b = { last_name: form.last_name, first_name: form.first_name, birth_date: form.birth_date || null, phone: form.phone, email: form.email,
    status: form.status, groups: form.group ? [form.group] : [], totp_enabled: form.totp_enabled }
  if (form.password) b.password = form.password
  return b
}

async function save() {
  busy.value = true
  try {
    const self = mode.value === 'edit' && sel.value.emp_no === session.me?.emp_no
    if (mode.value === 'new') {
      const u = await api.post('/users', { ...body(), emp_no: form.emp_no, password: form.password })
      toastOk('저장되었습니다.')
      await load(u.emp_no)
      return
    }
    await api.patch(`/users/${sel.value.emp_no}`, body())
    if (permChanged(perm.value)) await api.put(`/users/${sel.value.emp_no}/menus`, menusPayload(perm.value))
    toastOk('저장되었습니다.')
    if (self) await loadSession()
    await load(sel.value.emp_no)
  } catch (e) { toastError(e) } finally { busy.value = false }
}

async function remove() {
  if (sel.value.emp_no === session.me?.emp_no) { toast('로그인 중인 본인 계정은 삭제할 수 없습니다.', 'error'); return }
  if (!confirm(`회원 ${sel.value.emp_no} 을(를) 삭제합니다.`)) return
  busy.value = true
  try {
    await api.del(`/users/${sel.value.emp_no}`)
    toastOk('삭제되었습니다.')
    sel.value = null; mode.value = null
    await load(null)
  } catch (e) { toastError(e) } finally { busy.value = false }
}

async function approve() {
  busy.value = true
  try {
    await api.post(`/users/${sel.value.emp_no}/approve`, { groups: form.group ? [form.group] : [] })
    toastOk(`${sel.value.display_name} 님의 가입을 승인했습니다.`)
    await load(sel.value.emp_no)
  } catch (e) { toastError(e) } finally { busy.value = false }
}

onMounted(async () => {
  try { groups.value = await api.get('/auth-groups') } catch (e) { toastError(e) }
  load()
})
</script>

<style scoped>
.users { height: 100%; display: grid; grid-template-rows: 1fr 1fr; gap: 12px; min-height: 0; }
.top { display: flex; flex-direction: column; min-height: 0; }
.list { flex: 1; min-height: 0; }
.w110 { width: 110px; } .w148 { width: 148px; }
.cnt { font-size: 12px; }
.bottom { margin: 0; display: flex; flex-direction: column; min-height: 0; }
.bwrap { flex: 1; min-height: 0; display: grid; grid-template-columns: 1fr; gap: 16px; }
.bwrap.withperm { grid-template-columns: 1fr 400px; }
.user-form { min-width: 0; }
.chk { height: 30px; gap: 6px; }
.pick { padding: 6px 0; font-size: 12.5px; }
.perm { display: flex; flex-direction: column; min-height: 0; }
.perm-h { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 12px; }
.perm-h b { font-size: 12.5px; }
.ptable { flex: 1; min-height: 0; border-radius: 8px; }
.perm-table td, .perm-table th { padding: 4px 8px; }
.perm-table .c { text-align: center; width: 44px; }
.perm-table td.sub { padding-left: 22px; }
.btns { display: flex; gap: 8px; margin-top: 10px; flex: none; }
@media (max-width: 1200px) {
  .bwrap.withperm { grid-template-columns: 1fr; }
  .ptable { max-height: 240px; }
  .bottom { overflow: auto; }
}
</style>
