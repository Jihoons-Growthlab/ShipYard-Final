<template>
  <div class="auth">
    <img class="auth-scene" :src="scene" alt="" aria-hidden="true" />
    <div class="auth-wrap">
      <section class="auth-intro">
        <div class="ai-logo">⚓ SWP SHIPYARD</div>
        <h2 class="ai-title">설계부터 인도까지,<br>조선소 운영을 한곳에서</h2>
        <ul class="ai-list">
          <li><b>호선</b><span>호선별 진척률과 인도 일정을 한눈에</span></li>
          <li><b>공정</b><span>간트 계획부터 일별 실적까지</span></li>
          <li><b>도면</b><span>리비전·결재·배포 이력 관리</span></li>
        </ul>
      </section>

      <form v-if="mode === 'login'" class="auth-card" @submit.prevent="doLogin">
        <div class="ac-logo">SWP SHIPYARD</div>
        <h1>조선소 통합관리</h1>
        <p class="ac-sub">호선 · 공정 · 도면 관리 시스템</p>
        <div class="fld"><label for="lg-id">아이디</label><input id="lg-id" v-model.trim="login.emp_no" class="inp" autocomplete="username" autofocus /></div>
        <div class="fld"><label for="lg-pw">비밀번호</label><input id="lg-pw" v-model="login.password" class="inp" type="password" autocomplete="current-password" /></div>
        <div class="auth-err">{{ err }}</div>
        <button class="btn pri wide" type="submit" :disabled="busy">로그인</button>
        <div class="ac-foot"><a @click="go('signup')">회원가입</a><span>구글 2차 인증 사용 계정은 다음 단계에서 OTP 입력</span></div>
      </form>

      <form v-else-if="mode === 'otp'" class="auth-card" @submit.prevent="doOtp">
        <div class="ac-logo">2-STEP VERIFICATION</div>
        <h1>구글 2차 인증</h1>
        <p class="ac-sub">Google Authenticator 앱에 표시된 6자리 코드를 입력하세요.</p>
        <input v-model.trim="otp" class="inp otp" maxlength="6" inputmode="numeric" autocomplete="one-time-code" aria-label="인증 코드" autofocus />
        <div class="auth-err">{{ err }}</div>
        <button class="btn pri wide" type="submit" :disabled="busy">인증</button>
        <div class="ac-foot"><a @click="go('login')">← 로그인으로</a></div>
      </form>

      <form v-else class="auth-card signup" @submit.prevent="doSignup">
        <div class="ac-logo">SIGN UP</div>
        <h1>회원가입</h1>
        <p class="ac-sub">가입 후 관리자 승인이 완료되면 로그인할 수 있습니다.</p>
        <div class="fg c2">
          <div v-for="f in signupFields" :key="f.k" class="fld">
            <label :for="'su-' + f.k">{{ f.label }}</label>
            <input :id="'su-' + f.k" v-model.trim="reg[f.k]" class="inp" :type="f.type || 'text'" :placeholder="f.ph || ''" />
          </div>
        </div>
        <div class="auth-err">{{ err }}</div>
        <button class="btn pri wide" type="submit" :disabled="busy">가입 신청</button>
        <div class="ac-foot"><a @click="go('login')">← 로그인으로</a></div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, request, setToken } from '../api/client'
import { toast } from '../utils/toast'
import scene from '../assets/auth-scene.svg'

const router = useRouter()
const mode = ref('login')
const err = ref('')
const busy = ref(false)
const login = reactive({ emp_no: '', password: '' })
const otp = ref('')
let otpToken = null
const emptyReg = () => ({ last_name: '', first_name: '', birth_date: '', phone: '', email: '', emp_no: '', password: '', password_confirm: '' })
const reg = reactive(emptyReg())
const signupFields = [
  { k: 'last_name', label: '성' }, { k: 'first_name', label: '이름' },
  { k: 'birth_date', label: '생년월일', type: 'date' }, { k: 'phone', label: '전화번호', ph: '010-0000-0000' },
  { k: 'email', label: '이메일', type: 'email' }, { k: 'emp_no', label: '아이디' },
  { k: 'password', label: '비밀번호', type: 'password' }, { k: 'password_confirm', label: '비밀번호 확인', type: 'password' },
]

function go(m) { mode.value = m; err.value = ''; otp.value = '' }

function startSession(res) {
  setToken(res.access_token)
  router.push('/')
}

async function run(fn) {
  busy.value = true; err.value = ''
  try { await fn() } catch (e) { err.value = e.message } finally { busy.value = false }
}

const doLogin = () => run(async () => {
  const res = await api.post('/auth/login', { emp_no: login.emp_no, password: login.password })
  if (res.otp_required) { otpToken = res.otp_token; go('otp') } else startSession(res)
})
const doOtp = () => run(async () => {
  startSession(await request('POST', '/auth/otp/verify', { body: { code: otp.value }, token: otpToken }))
})
const doSignup = () => run(async () => {
  await api.post('/auth/register', { ...reg })
  Object.assign(reg, emptyReg())
  go('login')
  toast('가입 신청 완료. 관리자 승인 후 로그인할 수 있습니다.', 'success')
})
</script>

<style scoped>
.auth { position: fixed; inset: 0; background: #060f22; overflow: auto; }
.auth-scene { position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none; }
.auth-wrap { position: relative; min-height: 100%; display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 48px; padding: 40px clamp(28px,7vw,120px); }
.auth-intro { position: relative; z-index: 1; color: #fff; margin-bottom: 22vh; max-width: 520px; }
.auth-intro::before { content: ''; position: absolute; inset: -60px -80px; z-index: -1; background: radial-gradient(ellipse at 40% 50%, rgba(6,15,34,.75), rgba(6,15,34,0) 70%); }
.ai-logo { font-size: 13px; font-weight: 700; letter-spacing: 3px; color: #8cc1f2; }
.ai-title { font-size: clamp(28px,3.1vw,42px); font-weight: 700; margin: 14px 0 34px; line-height: 1.32; }
.ai-list { list-style: none; margin: 0; padding: 0; border-top: 1px solid rgba(140,193,242,.25); }
.ai-list li { display: flex; gap: 32px; padding: 9px 0; border-bottom: 1px solid rgba(140,193,242,.25); font-size: 13.5px; }
.ai-list b { color: #8cc1f2; }
.auth-card { position: relative; z-index: 1; width: 400px; background: #fff; border-radius: 14px; padding: 32px 32px 28px; box-shadow: 0 24px 60px rgba(0,0,0,.45); display: flex; flex-direction: column; gap: 10px; animation: pop-in var(--t-med) var(--ease); }
.auth-card.signup { width: 560px; }
.ac-logo { font-size: 12px; font-weight: 700; letter-spacing: 2px; color: var(--pri); }
.auth-card h1 { font-size: 22px; color: var(--navy); margin: 0; }
.ac-sub { color: var(--muted); margin: -4px 0 6px; font-size: 12px; }
.auth-card .inp { height: 38px; }
.inp.otp { height: 46px; font-size: 22px; text-align: center; letter-spacing: 8px; }
.auth-err { min-height: 18px; color: var(--err); font-size: 12.5px; }
.btn.wide { width: 100%; height: 42px; font-weight: 700; }
.ac-foot { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: var(--muted); }
@media (max-width: 1000px) {
  .auth-wrap { grid-template-columns: 1fr; justify-items: center; background: rgba(6,15,34,.35); }
  .auth-intro { display: none; }
  .auth-card, .auth-card.signup { width: min(100%, 400px); }
  .auth-card.signup { width: min(100%, 560px); }
}
@media (max-width: 480px) {
  .auth-wrap { padding: 24px 16px; }
  .auth-card { padding: 26px 20px 22px; }
  .ac-foot { flex-direction: column; }
}
</style>
