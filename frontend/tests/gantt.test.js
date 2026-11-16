import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { offDays, dayKind } from '../src/utils/holidays'
import { ganttLayout, months, barGeom, dragDates, depPaths, ROW_H } from '../src/utils/gantt'
import PlanGantt from '../src/screens/PlanGantt.vue'
import PlanPanel from '../src/screens/PlanPanel.vue'
import { setSession, mockApi } from './helpers'

const P = (id, s, e, extra = {}) => ({ plan_id: id, label: `[1] P${id}`, block_id: 1, block_cd: '101', proc_cd: 'CUT', proc_nm: '강재절단', plan_start_dt: s, plan_end_dt: e, actual_start_dt: null, actual_end_dt: null, progress_rate: 0, plan_status: 'PLAN', pred_plan_ids: [], blockers: [], drawing_wait: false, ...extra })

describe('휴일', () => {
  it('PLAN-T12: 개천절(토)·대체공휴일·일·토', () => {
    const lay = ganttLayout([], '2026-10-19', 4)
    const m = Object.fromEntries(offDays(lay).map((o) => [o.date, o]))
    expect(m['2026-10-03'].kind).toBe('hol')
    expect(m['2026-10-03'].name).toBe('개천절')
    expect(m['2026-10-05'].kind).toBe('hol')
    expect(m['2026-10-05'].name).toBe('대체공휴일(개천절)')
    expect(m['2026-10-04'].kind).toBe('sun')
    expect(m['2026-10-10'].kind).toBe('sat')
    expect(m['2026-10-06']).toBeUndefined()
    expect(m['2026-10-10'].x).toBe(9 * 4)
    expect(dayKind('2028-10-03')).toBe(null) // 표에 없는 해는 주말만(화요일)
  })
})

describe('간트 계산', () => {
  it('범위·폭·월·막대', () => {
    const plans = [P(1, '2026-09-15', '2026-09-20'), P(2, '2026-11-01', '2026-11-14')]
    const lay = ganttLayout(plans, '2026-10-19', 4)
    expect(lay.start).toBe('2026-09-01')
    expect(lay.days).toBe(74 + 8)
    expect(lay.width).toBe(230 + Math.ceil(82 * 4))
    expect(months(lay).map((m) => m.label)).toEqual(['2026.09', '2026.10', '2026.11'])
    expect(barGeom('2026-09-15', '2026-09-20', lay)).toEqual({ left: 56, width: 24 })
    expect(ganttLayout([], '2026-10-03', 2.5).start).toBe('2026-09-01')
  })
  it('드래그 날짜: 이동·양끝·최소 1일', () => {
    expect(dragDates('2026-11-01', '2026-11-14', 'move', 24, 4)).toEqual({ start: '2026-11-07', end: '2026-11-20' })
    expect(dragDates('2026-11-01', '2026-11-14', 'start', 100, 4)).toEqual({ start: '2026-11-14', end: '2026-11-14' })
    expect(dragDates('2026-11-01', '2026-11-14', 'end', -9, 4)).toEqual({ start: '2026-11-01', end: '2026-11-12' })
  })
  it('선후행 경로', () => {
    const plans = [P(1, '2026-09-01', '2026-09-10'), P(2, '2026-09-11', '2026-09-20')]
    const lay = ganttLayout(plans, '2026-09-10', 4)
    const [p] = depPaths(plans, [{ plan_id: 2, pred_plan_id: 1 }, { plan_id: 2, pred_plan_id: 99 }], lay)
    expect(p).toEqual({ d: `M40 ${ROW_H / 2} H44 V${ROW_H * 1.5} H40`, from: 1, to: 2 })
  })
})

describe('PlanGantt 화면', () => {
  beforeEach(() => { setSession(); document.body.innerHTML = '' })
  const routes = (plans, deps = []) => [
    ['GET', /plan-hulls/, () => [200, [{ hull_no: '8004', plan_count: 0 }, { hull_no: '8001', hull_nm: 'A', plan_count: 2 }]]],
    ['GET', /\/procs/, () => [200, [{ proc_cd: 'CUT', proc_nm: '강재절단' }]]],
    ['GET', /users\/options/, () => [200, []]],
    ['GET', /blocks/, () => [200, [{ block_id: 1, block_cd: '101', block_nm: 'B' }]]],
    ['GET', /\/hulls\/\w+\/plans/, () => [200, { hull_no: '8001', hull_progress: 40, today: '2026-10-19', plans, deps }]],
  ]

  it('공정 있는 첫 호선, 행·오늘·휴일 표시, 클릭 시 패널', async () => {
    mockApi(routes([P(1, '2026-10-01', '2026-10-10', { drawing_wait: true, blockers: [{ drawing_no: 'D1', dwg_status: 'APPROVED' }] }), P(2, '2026-10-11', '2026-10-30')], [{ plan_id: 2, pred_plan_id: 1 }]))
    const w = mount(PlanGantt, { props: { title: '공정 계획', canWrite: true } })
    await flushPromises()
    expect(w.vm.hullNo).toBe('8001')
    expect(w.findAll('.g-row')).toHaveLength(2)
    expect(w.text()).toContain('📐')
    expect(w.text()).toContain('빨간선 = 오늘(2026-10-19)')
    expect(w.findAll('.g-hmark').length).toBeGreaterThan(0)
    expect(w.findAll('path.dep')).toHaveLength(1)
    await w.find('.g-label').trigger('click')
    expect(w.findComponent(PlanPanel).exists()).toBe(true)
    expect(w.findAll('path.dep.hl')).toHaveLength(1)
  })

  it('공정이 없으면 안내, 조회 전용이면 추가 버튼 없음', async () => {
    mockApi(routes([]))
    const w = mount(PlanGantt, { props: { title: '공정 계획', canWrite: false, param: '8004' } })
    await flushPromises()
    expect(w.vm.hullNo).toBe('8004')
    expect(w.text()).toContain('표시할 공정이 없습니다.')
    expect(w.text()).not.toContain('+ 공정 추가')
  })

  it('드래그 저장: 409 확인 후 재전송, 연쇄 건수 토스트', async () => {
    const calls = mockApi([...routes([P(1, '2026-11-01', '2026-11-14')]),
      ['PATCH', /schedule/, (u, b) => (b.confirm_late_preds ? [200, { plan: {}, shifted_plan_ids: [2, 3] }] : [409, { message: '선행 공정 종료일이 이 공정의 시작일보다 늦습니다. 그대로 저장할까요?' }])]])
    vi.stubGlobal('confirm', vi.fn(() => true))
    const { toasts } = await import('../src/utils/toast')
    toasts.splice(0)
    const w = mount(PlanGantt, { props: { title: '공정 계획', canWrite: true } })
    await flushPromises()
    await w.vm.saveSchedule(w.vm.rows[0], '2026-11-07', '2026-11-20')
    await flushPromises()
    const sends = calls.filter((c) => c.method === 'PATCH')
    expect(sends.map((c) => c.body.confirm_late_preds)).toEqual([false, true])
    expect(sends[0].body.plan_start_dt).toBe('2026-11-07')
    expect(toasts.at(-1).message).toBe('저장되었습니다. 후행 공정 2건의 일정이 함께 조정되었습니다.')
    vi.unstubAllGlobals()
  })
})

describe('PlanPanel', () => {
  beforeEach(() => setSession())
  it('신규 기본값과 늦은 선행 취소 시 미저장', async () => {
    const calls = mockApi([['POST', /plans/, () => [409, { message: 'late' }]]])
    vi.stubGlobal('confirm', vi.fn(() => false))
    const w = mount(PlanPanel, { props: { hullNo: '8001', plan: null, plans: [], blocks: [], procs: [{ proc_cd: 'CUT', proc_nm: '강재절단' }], users: [], canWrite: true, defaultBlockId: '', today: '2026-10-19' } })
    expect(w.vm.form.plan_end_dt).toBe('2026-11-01')
    expect(w.vm.form.proc_cd).toBe('CUT')
    expect(w.text()).toContain('저장한 뒤 이 공정에 도면을 연계할 수 있습니다.')
    await w.find('form').trigger('submit'); await flushPromises()
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1)
    expect(w.emitted('saved')).toBeUndefined()
    vi.unstubAllGlobals()
  })
})
