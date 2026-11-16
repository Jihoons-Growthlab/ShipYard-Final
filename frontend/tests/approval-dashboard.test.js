import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ApprovalInbox from '../src/screens/ApprovalInbox.vue'
import Dashboard from '../src/screens/Dashboard.vue'
import { setSession, mockApi } from './helpers'
import { toasts } from '../src/utils/toast'

const INBOX = { waiting: [{ approval_id: 7, drawing_id: 1, drawing_no: 'D-1', drawing_nm: 'N', rev_no: 0, step_no: 2, change_desc: '최초 작성' }],
  ready: [{ drawing_id: 2, drawing_no: 'D-2', drawing_nm: 'M', rev_no: 1, effect_plans: ['[401] 탑재'] }], can_issue: true }

describe('ApprovalInbox', () => {
  beforeEach(() => { setSession(); toasts.splice(0) })

  it('반려는 의견 필수(클라이언트), 승인 호출 후 재조회', async () => {
    const calls = mockApi([
      ['GET', /inbox/, () => [200, INBOX]], ['GET', /history/, () => [200, []]],
      ['POST', /decision/, () => [200, {}]]])
    const w = mount(ApprovalInbox, { props: { title: '결재함', canWrite: true } })
    await flushPromises()
    expect(w.text()).toContain('박공정 님의 결재 대기와 배포 대기 도면입니다.')
    expect(w.text()).toContain('[401] 탑재')
    expect(w.text()).toContain('결재 이력이 없습니다.')
    await w.findAll('button').find((b) => b.text() === '반려').trigger('click')
    expect(toasts.at(-1).message).toBe('반려 시 의견을 입력하세요.')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
    await w.findAll('button').find((b) => b.text() === '승인').trigger('click'); await flushPromises()
    expect(calls.find((c) => c.method === 'POST').body).toEqual({ result: 'APPROVE', comment: '' })
    expect(calls.filter((c) => c.url.includes('inbox'))).toHaveLength(2)
  })

  it('조회 전용·배포 권한 없음: 버튼 없음, 빈 메시지', async () => {
    mockApi([['GET', /inbox/, () => [200, { waiting: [], ready: [], can_issue: false }]], ['GET', /history/, () => [200, []]]])
    const w = mount(ApprovalInbox, { props: { title: '결재함', canWrite: false } })
    await flushPromises()
    expect(w.text()).toContain('결재 대기 건이 없습니다.')
    expect(w.text()).toContain('배포 대기 도면이 없습니다.')
    expect(w.findAll('button')).toHaveLength(0)
  })
})

const SUM = {
  today: '2026-10-19',
  kpi: { active_hulls: { value: 4, link: { screen: 'hull-list' } }, delay_plans: { value: 0, link: { screen: 'plan-gantt' } }, waiting_plans: { value: 8, link: { screen: 'plan-gantt' } }, pending_drawings: { value: 6, link: { screen: 'dwg-approval' } } },
  hull_progress: [{ hull_no: '8001', hull_nm: 'SWP', progress: 65, link: { screen: 'plan-gantt', param: '8001' } }],
  plan_status: [{ status: 'PLAN', count: 3 }, { status: 'READY', count: 0 }, { status: 'WORK', count: 1 }, { status: 'DONE', count: 0 }, { status: 'DELAY', count: 0 }],
  drawing_disciplines: [{ discipline: 'HULL', name: '선체', total: 2, counts: { ISSUED: 1, APPROVED: 0, REVIEW: 1, DRAFT: 0 } }],
  deliveries: [{ month: '2026-12', count: 1, hull_nos: ['8005'] }],
  delay_list: { count: 0, items: [] },
  waiting_list: { count: 8, items: [{ plan_id: 1, hull_no: '8002', label: '[401] 강재절단', plan_start_dt: '2026-10-31', blockers: ['8002-HULL-401'], link: { screen: 'plan-gantt', param: '8002' } }] },
  impact_list: { count: 1, items: [{ drawing_id: 9, drawing_no: 'D-9', rev_no: 2, issue_dt: '2026-10-12', plan_id: 3, plan_label: '[201] 강재절단', plan_status: 'DONE', hull_no: '8001', change_desc: '보강', link: { screen: 'drawing', param: 9 } }] },
}

describe('Dashboard', () => {
  beforeEach(() => setSession({ menu: [{ token: 'hull-list', menu_id: 'M11' }, { token: 'dwg-approval', menu_id: 'M33' }] }))

  it('흐름 버튼은 권한 메뉴만, KPI·행·영향 클릭 이동', async () => {
    mockApi([['GET', /dashboard/, () => [200, SUM]]])
    const navigate = vi.fn(); const openManual = vi.fn(); const openDrawing = vi.fn()
    const w = mount(Dashboard, { props: { title: '대시보드' }, global: { provide: { navigate, openManual, openDrawing } } })
    await flushPromises()
    expect(w.text()).toContain('기준일 2026-10-19 · 호선/공정/도면 현황')
    expect(w.findAll('.flow button').map((b) => b.text())).toEqual(['호선 확인', '도면 결재'])
    await w.findAll('.flow button')[1].trigger('click')
    expect(openManual).toHaveBeenCalledWith('dwg-approval')
    await w.findAll('.kpi')[3].trigger('click')
    expect(navigate).toHaveBeenLastCalledWith('dwg-approval', null)
    await w.find('.hp').trigger('click')
    expect(navigate).toHaveBeenLastCalledWith('plan-gantt', '8001')
    expect(w.text()).toContain('지연 공정이 없습니다.')
    expect(w.text()).toContain('착수 2026-10-31 · 8002-HULL-401')
    expect(w.findAll('.kv')[1].classes()).not.toContain('err')
    const imp = w.findAll('.li').at(-1)
    expect(imp.text()).toContain('D-9 Rev2 → [201] 강재절단')
    await imp.trigger('click')
    expect(openDrawing).toHaveBeenCalledWith(9)
    expect(w.findAll('.donut circle')).toHaveLength(3)
  })
})
