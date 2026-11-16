<template>
  <div class="ship-chat">
    <section v-if="open" ref="panelEl" class="cpanel" role="dialog" aria-label="조선소 챗봇" @keydown.esc.stop="close">
      <header class="chead">
        <div><b>조선소 챗봇</b><small>로컬 AI</small></div>
        <button type="button" class="cx" aria-label="챗봇 닫기" @click="close">✕</button>
      </header>
      <div ref="bodyEl" class="cbody">
        <div class="msg bot">{{ GREETING }}</div>
        <div class="quick">
          <button v-for="q in QUICK" :key="q.label" type="button" class="qb" :disabled="busy" @click="send(q.text)">{{ q.label }}</button>
          <button type="button" class="qb rep" @click="startReport"><span aria-hidden="true">📄</span> 보고서 작성하기</button>
        </div>
        <template v-for="m in messages" :key="m.id">
          <div v-if="m.text" class="msg" :class="m.role === 'user' ? 'me' : m.role === 'error' ? 'err' : 'bot'">{{ m.text }}</div>
          <div v-if="m.cards?.length" class="cards">
            <button v-for="(c, i) in m.cards" :key="i" type="button" class="ccard" @click="pick(m, c)">
              <b>{{ c.title }}</b><small v-if="c.sub">{{ c.sub }}</small>
            </button>
          </div>
          <ChatReport v-if="m.report" />
        </template>
        <div v-if="busy" class="msg bot wait">{{ WAITING }}</div>
      </div>
      <div v-if="feedback" class="fbar">
        <b>{{ FEEDBACK_LABEL[feedback] }} 접수</b>
        <button type="button" class="fcancel" @click="feedback = null">취소</button>
      </div>
      <form class="cfoot" @submit.prevent="submit">
        <input ref="inputEl" v-model="input" class="cin" :maxlength="MAX_LEN" aria-label="메시지 입력"
               :placeholder="feedback ? `${FEEDBACK_LABEL[feedback]} 내용을 입력하세요` : '메시지 입력'" />
        <button type="submit" class="csend" :disabled="busy || !input.trim()">{{ feedback ? '접수' : '보내기' }}</button>
      </form>
    </section>
    <div class="launch-wrap">
      <button ref="launcherEl" type="button" class="launcher" aria-label="조선소 챗봇 열기" :aria-expanded="open" @click="toggle">
        <span class="boat" aria-hidden="true">
          <span class="funnel"></span><span class="bridge"><i></i><i></i></span><span class="hull"><i></i><i></i><i></i></span>
        </span>
      </button>
      <div v-if="!open" class="hello">안녕하세요! 친절한 조선소 AI 에이전트입니다.<br /><small>눌러서 질문해 보세요.</small></div>
    </div>
  </div>
</template>

<script setup>
import { inject, nextTick, ref } from 'vue'
import { api } from '../api/client'
import ChatReport from './ChatReport.vue'
import {
  GREETING, REPORT_GUIDE, WAITING, QUICK, FEEDBACK_LABEL, MAX_LEN,
  manualIntent, historyPayload, hullCard, drawingCard, progressHullCard, planCard, progressText,
} from '../utils/chat'

const openManual = inject('openManual', () => {})
const openHull = inject('openHull', () => {})
const openDrawing = inject('openDrawing', () => {})
const refreshInquiry = inject('refreshInquiry', () => {})

const open = ref(false)
const busy = ref(false)
const input = ref('')
const messages = ref([])
const feedback = ref(null)
let lastFeedback = null
let seq = 0
const bodyEl = ref(null)
const inputEl = ref(null)
const launcherEl = ref(null)
const panelEl = ref(null)

function push(m) {
  messages.value.push({ id: ++seq, ...m })
  nextTick(() => { if (bodyEl.value) bodyEl.value.scrollTop = bodyEl.value.scrollHeight })
}
function toggle() { open.value ? close() : show() }
function show() { open.value = true; nextTick(() => inputEl.value?.focus()) }
function close() {
  if (!open.value) return
  open.value = false
  nextTick(() => launcherEl.value?.focus())
}

function submit() { feedback.value ? sendFeedback() : send(input.value) }

async function send(raw) {
  const text = (raw || '').trim()
  if (!text || busy.value) return
  const typed = text === input.value.trim()
  input.value = ''
  push({ role: 'user', text })
  const section = manualIntent(text)
  if (section) { close(); openManual(section); return }
  busy.value = true
  try {
    const r = await api.post('/chat', { messages: historyPayload(messages.value) })
    if (r.feedback_kind) feedback.value = r.feedback_kind
    if (r.hulls) push({ role: 'assistant', text: r.answer, type: 'hulls', cards: r.hulls.map((h) => ({ ...hullCard(h), item: h })) })
    else if (r.choice_type === 'drawing') push({ role: 'assistant', text: r.answer, type: 'drawing', cards: r.choices.map((d) => ({ ...drawingCard(d), item: d })) })
    else if (r.choice_type === 'progress-hull') push({ role: 'assistant', text: r.answer, type: 'progress-hull', cards: r.choices.map((h) => ({ ...progressHullCard(h), item: h })) })
    else push({ role: 'assistant', text: r.answer })
  } catch (e) {
    push({ role: 'error', text: e.message })
    if (typed) input.value = text
  } finally {
    busy.value = false
    nextTick(() => inputEl.value?.focus())
  }
}

async function pick(m, c) {
  if (m.type === 'hulls') { close(); openHull(c.item.hull_no); return }
  if (m.type === 'drawing') { close(); openDrawing(c.item.drawing_id, { readonly: true }); return }
  busy.value = true
  try {
    if (m.type === 'progress-hull') {
      const no = c.item.hull_no
      const r = await api.get(`/hulls/${encodeURIComponent(no)}/progress-targets`, { include_done: true })
      if (!r.plans.length) push({ role: 'assistant', text: '등록된 공정이 없습니다.' })
      else push({ role: 'assistant', text: `${no}호선의 공정을 선택해 주세요.`, type: 'progress-plan', cards: r.plans.map((p) => ({ ...planCard(p), item: p })) })
    } else if (m.type === 'progress-plan') {
      const r = await api.get(`/plans/${c.item.plan_id}/progress`)
      push({ role: 'assistant', text: progressText(r.plan, r.history) })
    }
  } catch (e) { push({ role: 'error', text: e.message }) } finally { busy.value = false }
}

async function sendFeedback() {
  const content = input.value.trim()
  if (busy.value) return
  const kind = feedback.value
  if (!lastFeedback || lastFeedback.kind !== kind || lastFeedback.content !== content) {
    lastFeedback = { kind, content, request_id: crypto.randomUUID() }
  }
  busy.value = true
  try {
    const r = await api.post('/chat/feedback', { kind, content, request_id: lastFeedback.request_id })
    input.value = ''
    push({ role: 'user', text: content })
    push({ role: 'assistant', text: `접수했습니다. 접수번호 ${r.receipt}` })
    feedback.value = null
    refreshInquiry()
  } catch (e) {
    push({ role: 'error', text: e.message })
  } finally { busy.value = false }
}

function startReport() {
  push({ role: 'user', text: '보고서 작성하기', local: true })
  push({ role: 'assistant', text: REPORT_GUIDE, report: true })
}

defineExpose({ close, show, open })
</script>

<style scoped>
.ship-chat { position: fixed; left: calc(14px + env(safe-area-inset-left)); bottom: calc(14px + env(safe-area-inset-bottom)); z-index: 900; }
.launch-wrap { display: flex; align-items: center; gap: 10px; }
.launcher { width: 64px; height: 64px; border-radius: 16px; background: #def6fa; border: 1px solid #acdbe4; box-shadow: 0 6px 18px rgba(15,23,42,.18); cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0; }
.launcher:focus-visible { outline: 3px solid #60a5fa; outline-offset: 2px; }
.hello { background: #fff; border: 1px solid #cfe5ea; border-radius: 12px; padding: 7px 11px; font-size: 12px; line-height: 1.45; box-shadow: var(--shadow-md); white-space: nowrap; position: relative; }
.hello small { color: var(--muted); }
/* 아이콘·말풍선(숨은 뒤에도 자리를 차지해 호버를 받음) 위에 있으면 숨김. opacity라 깜빡이지 않는다. */
.hello { transition: opacity var(--t-fast) var(--ease); }
.launch-wrap:hover .hello { opacity: 0; }
.boat { position: relative; width: 44px; height: 34px; animation: rock 2.6s ease-in-out infinite; transform-origin: 50% 90%; }
.funnel { position: absolute; left: 19px; top: 0; width: 7px; height: 8px; background: #e2554b; border-radius: 2px 2px 0 0; box-shadow: inset 0 2px 0 #1f3347; }
.bridge { position: absolute; left: 10px; top: 7px; width: 25px; height: 11px; background: #fff; border: 2px solid #1f3347; border-radius: 4px 4px 0 0; display: flex; justify-content: center; gap: 3px; padding-top: 2px; }
.bridge i { width: 5px; height: 4px; background: #46b3c8; border-radius: 1px; }
.hull { position: absolute; left: 0; bottom: 0; width: 44px; height: 17px; background: #1f3347; border-radius: 3px 3px 14px 14px; display: flex; justify-content: center; gap: 6px; padding-top: 5px; }
.hull i { width: 5px; height: 5px; background: #bfeaf2; border-radius: 50%; }
@keyframes rock { 0%, 100% { transform: rotate(-4deg) translateY(0); } 50% { transform: rotate(4deg) translateY(-1px); } }
@media (prefers-reduced-motion: reduce) { .boat { animation: none; } }

.cpanel { position: absolute; left: 0; bottom: 76px; width: min(360px, calc(100vw - 28px)); height: min(440px, calc(100vh - 110px)); background: #fff; border-radius: 16px; box-shadow: 0 18px 50px rgba(15,23,42,.25); display: flex; flex-direction: column; overflow: hidden; animation: pop-in var(--t-med) var(--ease); }
.chead { background: #173d58; color: #fff; display: flex; align-items: center; justify-content: space-between; padding: 9px 14px 9px 14px; flex: none; }
.chead b { display: block; font-size: 15px; }
.chead small { font-size: 10px; opacity: .9; }
.cx { width: 28px; height: 28px; border: 0; background: transparent; color: #fff; font-size: 16px; font-weight: 700; cursor: pointer; border-radius: 6px; }
.cx:hover { background: rgba(255,255,255,.12); }
.cbody { flex: 1; overflow: auto; padding: 14px 12px; display: flex; flex-direction: column; gap: 8px; }
.msg { max-width: 86%; padding: 8px 10px; border-radius: 10px; font-size: 12.5px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; align-self: flex-start; }
.msg.bot { background: #eef3f5; color: #1f2937; }
.msg.me { background: #d6eef4; align-self: flex-end; }
.msg.err { background: #fef2f2; color: #b91c1c; border: 1px solid #fca5a5; }
.msg.wait { color: var(--muted); }
.quick { display: flex; flex-wrap: wrap; gap: 6px; }
.qb { height: 32px; padding: 0 10px; border-radius: 16px; border: 1px solid #9fcfd9; background: #eef8fa; color: #1d3f55; font: inherit; font-size: 12.5px; cursor: pointer; }
.qb:hover { background: #dff1f5; }
.qb.rep { background: #1f4a66; border-color: #1f4a66; color: #fff; font-weight: 700; }
.qb.rep:hover { background: #173d58; }
.cards { display: flex; flex-direction: column; gap: 6px; }
.ccard { text-align: left; padding: 7px 9px; border: 1px solid #a8d6e0; background: #eff9fb; border-radius: 6px; cursor: pointer; font: inherit; display: flex; flex-direction: column; gap: 2px; }
.ccard:hover { background: #d9eff5; }
.ccard b { font-size: 13px; }
.ccard small { font-size: 11px; color: #475569; }
.fbar { display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; background: #fff7ed; border-top: 1px solid #fed7aa; font-size: 12px; flex: none; }
.fcancel { height: 24px; padding: 0 8px; border: 1px solid #d6dbe3; border-radius: 5px; background: #fff; font: inherit; font-size: 12px; cursor: pointer; }
.cfoot { display: flex; gap: 8px; padding: 10px 10px 10px 10px; border-top: 1px solid #e2e8f0; flex: none; }
.cin { flex: 1; min-width: 0; height: 30px; border: 1px solid #c4ccd6; border-radius: 6px; padding: 0 8px; font: inherit; font-size: 14px; }
.cin:focus { outline: none; border-color: #46b3c8; box-shadow: 0 0 0 3px rgba(70,179,200,.2); }
.csend { height: 30px; padding: 0 10px; border: 0; border-radius: 6px; background: #1f5878; color: #fff; font: inherit; cursor: pointer; }
.csend:disabled { background: #9bb4c6; cursor: default; }
</style>
