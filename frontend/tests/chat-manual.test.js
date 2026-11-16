import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setSession, mockApi } from './helpers'
import { manualIntent, historyPayload, hullCard, drawingCard, progressText, sizeText } from '../src/utils/chat'
import { MANUAL_STEPS, visibleSteps, startStep } from '../src/utils/manual'
import ShipChat from '../src/components/ShipChat.vue'
import ChatReport from '../src/components/ChatReport.vue'
import WorkflowManual from '../src/components/WorkflowManual.vue'

beforeEach(() => setSession())

describe('chat utils', () => {
  it('매뉴얼 의도와 주제', () => {
    expect(manualIntent('도면 결재 매뉴얼')).toBe('dwg-approval')
    expect(manualIntent('도면 어떻게 사용해?')).toBe('dwg-list')
    expect(manualIntent('실적 사용법')).toBe('progress')
    expect(manualIntent('공정 업무 흐름')).toBe('plan-gantt')
    expect(manualIntent('3D 야드 메뉴얼')).toBe('hull-list')
    expect(manualIntent('문의 사용 방법')).toBe('inquiry')
    expect(manualIntent('매뉴얼')).toBe('dashboard')
    expect(manualIntent('호선 정보 알려줘')).toBeNull()
  })
  it('대화는 최근 10개·2000자, 오류·보고서 제외', () => {
    const msgs = Array.from({ length: 14 }, (_, i) => ({ role: i % 2 ? 'assistant' : 'user', text: 'x'.repeat(2500) + i }))
    msgs.push({ role: 'error', text: 'e' }, { role: 'user', text: '보고서 작성하기', local: true })
    const p = historyPayload(msgs)
    expect(p).toHaveLength(10)
    expect(p[0].content).toHaveLength(2000)
    expect(p.every((m) => m.role !== 'error')).toBe(true)
  })
  it('카드·실적 문구', () => {
    expect(hullCard({ hull_no: '8004', hull_nm: 'Star Chemi', hull_status: 'PLAN', progress: null })).toEqual({ title: '8004 · Star Chemi', sub: '계획 · 계획 없음' })
    expect(hullCard({ hull_no: '8001', hull_nm: 'A', hull_status: 'BUILD', progress: 65 }).sub).toBe('건조 · 65%')
    expect(drawingCard({ drawing_no: 'D1', drawing_nm: '구조도', hull_no: '8001', dwg_status: 'ISSUED' }).sub).toBe('8001 · 배포')
    const plan = { label: '[101] 절단', plan_status: 'WORK', progress_rate: 40 }
    expect(progressText(plan, [])).toBe('[101] 절단\n상태 진행 · 진척률 40%\n등록된 실적 이력이 없습니다.')
    expect(progressText(plan, [{ work_dt: '2026-10-18', progress_rate: 40, man_hour: 12, worker_cnt: null }]))
      .toBe('[101] 절단\n상태 진행 · 진척률 40%\n최근 작업일 2026-10-18 · 누적 40% · 공수 12 · 인원 미입력')
    expect(sizeText(27800)).toBe('27KB')
  })
})

const provideAll = (extra = {}) => ({
  openManual: (s) => { extra.manual = s }, openHull: (n) => { extra.hull = n },
  openDrawing: (id, o) => { extra.drawing = [id, o] }, refreshInquiry: () => { extra.refreshed = true },
})

describe('ShipChat', () => {
  it('매뉴얼 의도는 서버 호출 없이 매뉴얼을 연다', async () => {
    const calls = mockApi([])
    const got = {}
    const w = mount(ShipChat, { global: { provide: provideAll(got) }, attachTo: document.body })
    await w.find('.launcher').trigger('click')
    expect(w.text()).toContain('조선소 챗봇')
    await w.find('.cin').setValue('도면 결재 사용법 알려줘')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(calls).toHaveLength(0)
    expect(got.manual).toBe('dwg-approval')
    expect(w.find('.cpanel').exists()).toBe(false)
    w.unmount()
  })

  it('호선 카드 클릭 → 호선 상세, 도면 카드 → 읽기 전용 도면', async () => {
    const calls = mockApi([
      ['POST', /\/api\/chat$/, (u, b) => (b.messages.at(-1).content.includes('호선')
        ? [200, { answer: '상세 정보를 볼 호선을 선택해 주세요.', hulls: [{ hull_no: '8001', hull_nm: 'SWP LNG 174K 1호', hull_status: 'BUILD', progress: 65 }] }]
        : [200, { answer: '상세 정보를 볼 도면을 선택해 주세요.', choice_type: 'drawing', choices: [{ drawing_id: 3, drawing_no: 'D-3', drawing_nm: '도', hull_no: '8001', dwg_status: 'DRAFT' }] }])],
    ])
    const got = {}
    const w = mount(ShipChat, { global: { provide: provideAll(got) } })
    await w.find('.launcher').trigger('click')
    await w.findAll('.qb')[0].trigger('click')
    await flushPromises()
    expect(calls[0].body.messages).toEqual([{ role: 'user', content: '호선 정보 알려줘' }])
    expect(w.find('.ccard').text()).toContain('8001 · SWP LNG 174K 1호')
    expect(w.find('.ccard').text()).toContain('건조 · 65%')
    await w.find('.ccard').trigger('click')
    expect(got.hull).toBe('8001')
    await w.find('.launcher').trigger('click')
    await w.findAll('.qb')[1].trigger('click')
    await flushPromises()
    await w.findAll('.ccard').at(-1).trigger('click')
    expect(got.drawing).toEqual([3, { readonly: true }])
  })

  it('공정 실적: 호선 → 공정 → 요약', async () => {
    mockApi([
      ['POST', /\/api\/chat$/, () => [200, { answer: '어떤 공정의 실적을 볼까요? 먼저 호선을 선택해 주세요.', choice_type: 'progress-hull', choices: [{ hull_no: '8001', hull_nm: 'A' }] }]],
      ['GET', /progress-targets\?include_done=true/, () => [200, { plans: [{ plan_id: 7, label: '[101] 절단', plan_status: 'DONE', progress_rate: 100 }] }]],
      ['GET', /\/api\/plans\/7\/progress/, () => [200, { plan: { label: '[101] 절단', plan_status: 'DONE', progress_rate: 100 }, history: [] }]],
    ])
    const w = mount(ShipChat, { global: { provide: provideAll() } })
    await w.find('.launcher').trigger('click')
    await w.findAll('.qb')[2].trigger('click'); await flushPromises()
    await w.find('.ccard').trigger('click'); await flushPromises()
    expect(w.text()).toContain('8001호선의 공정을 선택해 주세요.')
    await w.findAll('.ccard').at(-1).trigger('click'); await flushPromises()
    expect(w.text()).toContain('등록된 실적 이력이 없습니다.')
  })

  it('건의 접수: 같은 내용 재전송은 같은 request_id, 성공 시 탭 새로고침', async () => {
    let fail = true
    const calls = mockApi([
      ['POST', /\/api\/chat$/, () => [200, { answer: '접수할 내용을 입력하고 접수 버튼을 눌러 주세요.', feedback_kind: 'suggestion' }]],
      ['POST', /\/api\/chat\/feedback/, () => (fail ? (fail = false, [502, { message: '호선 조회 서버에 연결하지 못했습니다.' }]) : [200, { receipt: 'FB-000012', inquiry_id: 12 }])],
    ])
    const got = {}
    const w = mount(ShipChat, { global: { provide: provideAll(got) } })
    await w.find('.launcher').trigger('click')
    await w.findAll('.qb')[4].trigger('click'); await flushPromises()
    expect(w.find('.fbar').text()).toContain('건의 접수')
    expect(w.find('.csend').text()).toBe('접수')
    await w.find('.cin').setValue('엑셀 내보내기')
    await w.find('form').trigger('submit'); await flushPromises()
    expect(w.find('.msg.err').text()).toContain('연결하지 못했습니다')
    expect(w.find('.cin').element.value).toBe('엑셀 내보내기')
    await w.find('form').trigger('submit'); await flushPromises()
    const fb = calls.filter((c) => c.url.includes('/feedback'))
    expect(fb[0].body.request_id).toBe(fb[1].body.request_id)
    expect(w.text()).toContain('접수했습니다. 접수번호 FB-000012')
    expect(got.refreshed).toBe(true)
    expect(w.find('.fbar').exists()).toBe(false)
  })

  it('오류는 빨간 말풍선, 입력 복원; Esc로 닫힘', async () => {
    mockApi([['POST', /\/api\/chat$/, () => [503, { code: 'CHAT_OFFLINE', message: '로컬 모델에 연결할 수 없습니다. Ollama 실행 상태를 확인해 주세요.' }]]])
    const w = mount(ShipChat, { global: { provide: provideAll() } })
    await w.find('.launcher').trigger('click')
    await w.find('.cin').setValue('블록이 뭐야?')
    await w.find('form').trigger('submit'); await flushPromises()
    expect(w.find('.msg.err').text()).toContain('Ollama 실행 상태')
    expect(w.find('.cin').element.value).toBe('블록이 뭐야?')
    await w.find('.cpanel').trigger('keydown', { key: 'Escape' })
    expect(w.find('.cpanel').exists()).toBe(false)
  })
})

describe('ChatReport', () => {
  it('범위·형식 선택 후 생성, 결과 표시, 오류 박스', async () => {
    const calls = mockApi([
      ['GET', /report\/options/, () => [200, { hulls: [{ hull_no: '8001', hull_nm: 'A' }], formats: [] }]],
      ['POST', /\/api\/chat\/report$/, (u, b) => (b.format === 'xlsx' ? [400, { message: '보고서에 넣을 수 있는 메뉴 권한(호선·공정·도면 조회)이 없습니다.' }]
        : [201, { report_id: 'a'.repeat(24), format: 'pdf', filename: '8001_호선_현황_보고서_20261113_2043.pdf', title: '8001 호선 현황 보고서', size: 27800, summary: { hulls: 1, plans: 27, delay: 0, drawings: 15 }, download_url: '/api/chat/reports/x?format=pdf' }])],
    ])
    const w = mount(ChatReport)
    await flushPromises()
    expect(w.findAll('.pill').map((b) => b.text())).toEqual(['전체 호선', '8001'])
    expect(w.findAll('.pill')[1].attributes('title')).toBe('A')
    await w.findAll('.fmt')[1].trigger('click')
    await w.find('.go').trigger('click'); await flushPromises()
    expect(w.find('.rerr').text()).toContain('메뉴 권한')
    await w.findAll('.pill')[1].trigger('click')
    await w.findAll('.fmt')[0].trigger('click')
    await w.find('.go').trigger('click'); await flushPromises()
    expect(calls.at(-1).body).toEqual({ format: 'pdf', hull_no: '8001' })
    expect(w.text()).toContain('8001_호선_현황_보고서_20261113_2043.pdf · 27KB')
    expect(w.text()).toContain('호선 1 · 공정 27 · 지연 0 · 도면 15')
    await w.find('.again').trigger('click')
    expect(w.find('.go').exists()).toBe(true)
  })
})

describe('WorkflowManual', () => {
  const menu = ['dashboard', 'hull-list', 'plan-gantt', 'inquiry'].map((t, i) => ({ menu_id: 'M' + i, token: t }))
  it('권한 없는 단계 숨김, 요청 섹션 숨김이면 첫 단계', () => {
    const vis = visibleSteps(MANUAL_STEPS, (t) => menu.some((m) => m.token === t))
    expect(vis.map((s) => s.id)).toEqual(['dashboard', 'hull-list', 'plan-gantt', 'inquiry', 'chat'])
    expect(startStep(vis, 'dwg-list')).toBe('dashboard')
    expect(startStep(vis, 'plan-gantt')).toBe('plan-gantt')
  })
  it('현재 단계로 시작, 업무 화면 열기 성공 시 닫힘', async () => {
    setSession({ menu })
    const opened = []
    const w = mount(WorkflowManual, { props: { section: 'plan-gantt' }, global: { provide: { navigate: async (t) => { opened.push(t); return true } } }, attachTo: document.body })
    const body = document.body
    expect(body.querySelector('.mt').textContent).toBe('공정계획')
    expect(body.querySelector('[aria-pressed="true"]').textContent).toBe('공정계획')
    expect([...body.querySelectorAll('.steps .btn')].map((b) => b.textContent)).not.toContain('도면 관리')
    expect(body.querySelector('figcaption').textContent).toContain('화면 예시')
    ;[...body.querySelectorAll('.mhd .btn')][0].click(); await flushPromises()
    expect(opened).toEqual(['plan-gantt'])
    expect(w.emitted('close')).toBeTruthy()
    const chat = [...body.querySelectorAll('.steps .btn')].find((b) => b.textContent === '챗봇')
    chat.click(); await flushPromises()
    expect(body.querySelector('.mhd .btn')).toBeNull()
    w.unmount()
  })
})
