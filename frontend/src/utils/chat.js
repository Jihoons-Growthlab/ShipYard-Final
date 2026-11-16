// 챗봇(F13) 순수 함수: 매뉴얼 의도, 대화 전송 범위, 결과 카드 문구.
import { codeName } from '../stores/session'

export const GREETING = '안녕하세요! 아래 버튼을 누르고 보고 싶은 항목을 선택해 주세요. 질문을 직접 입력해도 돼요.'
export const REPORT_GUIDE = '보고서 범위와 형식을 골라 주세요. 권한이 있는 호선·공정·도면 현황을 담아 만들어 드릴게요.'
export const WAITING = '답변을 작성 중입니다…'
export const QUICK = [
  { label: '호선 정보', text: '호선 정보 알려줘' },
  { label: '도면 정보', text: '도면 정보 알려줘' },
  { label: '공정 실적', text: '공정 실적 알려줘' },
  { label: '매뉴얼', text: '매뉴얼' },
  { label: '건의하기', text: '건의하기' },
  { label: '문의하기', text: '문의하기' },
]
export const FEEDBACK_LABEL = { suggestion: '건의', inquiry: '문의' }
export const MAX_HISTORY = 10
export const MAX_LEN = 2000

const MANUAL_RE = /매뉴얼|메뉴얼|사용법|사용 방법|업무 흐름|어떻게 (사용|쓰|보)/
const TOPICS = [
  [/결재/, 'dwg-approval'], [/도면/, 'dwg-list'], [/실적/, 'progress'], [/공정/, 'plan-gantt'],
  [/호선|3d|야드/i, 'hull-list'], [/건의|문의/, 'inquiry'],
]

/** 매뉴얼 의도면 섹션 토큰, 아니면 null(서버로 보낸다). */
export function manualIntent(text) {
  if (!MANUAL_RE.test(text)) return null
  return TOPICS.find(([re]) => re.test(text))?.[1] || 'dashboard'
}

/** 서버로 보낼 대화: 사용자·챗봇 텍스트 말풍선 중 최근 10개, 각 2000자. */
export function historyPayload(messages) {
  return messages
    .filter((m) => (m.role === 'user' || m.role === 'assistant') && m.text && !m.local && !m.report)
    .slice(-MAX_HISTORY)
    .map((m) => ({ role: m.role, content: m.text.slice(0, MAX_LEN) }))
}

const pct = (v) => (v === null || v === undefined ? null : `${Number(v)}%`)

export function hullCard(h) {
  return { title: `${h.hull_no} · ${h.hull_nm}`, sub: `${codeName('HULLSTAT', h.hull_status)} · ${pct(h.progress) ?? '계획 없음'}` }
}
export function drawingCard(d) {
  return { title: `${d.drawing_no} · ${d.drawing_nm}`, sub: `${d.hull_no ?? '-'} · ${codeName('DWGSTAT', d.dwg_status)}` }
}
export function progressHullCard(h) { return { title: `${h.hull_no} · ${h.hull_nm}`, sub: '' } }
export function planCard(p) {
  return { title: p.label, sub: `${codeName('PLANSTAT', p.plan_status)} · ${pct(p.progress_rate) ?? '0%'}` }
}

/** 공정 실적 요약 문구(F13). */
export function progressText(plan, history) {
  const head = `${plan.label}\n상태 ${codeName('PLANSTAT', plan.plan_status)} · 진척률 ${Number(plan.progress_rate ?? 0)}%`
  const last = history?.[0]
  if (!last) return `${head}\n등록된 실적 이력이 없습니다.`
  const n = (v) => (v === null || v === undefined || v === '' ? '미입력' : String(v))
  return `${head}\n최근 작업일 ${last.work_dt} · 누적 ${Number(last.progress_rate)}% · 공수 ${n(last.man_hour)} · 인원 ${n(last.worker_cnt)}`
}

export function sizeText(bytes) { return `${Math.max(1, Math.round((bytes || 0) / 1024))}KB` }
