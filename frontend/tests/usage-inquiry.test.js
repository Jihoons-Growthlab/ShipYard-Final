import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import UsageLog from '../src/screens/UsageLog.vue'
import Inquiry from '../src/screens/Inquiry.vue'
import { niceMax, labelStep, lineGeom, methodClass } from '../src/utils/chart'
import { setSession, mockApi } from './helpers'

describe('chart utils', () => {
  it('y 최대·라벨 간격·좌표', () => {
    expect(niceMax(743)).toBe(800)
    expect(niceMax(0)).toBe(1)
    expect(niceMax(12)).toBe(20)
    expect([7, 30, 90].map(labelStep)).toEqual([1, 5, 15])
    const g = lineGeom([{ calls: 0, errors: 0 }, { calls: 10, errors: 1 }])
    expect(g.ticks).toEqual([0, 5, 10])
    expect(g.line.startsWith('M')).toBe(true)
    expect(methodClass('DELETE')).toBe('m-del')
  })
})

const SUM = (extra = {}) => ({
  days: 7, emp_no: null, since: '2026-11-08', kpi: { calls: 4928, users: 5, logins: 51, errors: 143, error_rate: 2.9, avg_ms: 29 },
  daily: Array.from({ length: 7 }, (_, i) => ({ date: `2026-11-0${i + 1}`, calls: i * 10, errors: 1, users: 2 })), hours: Array(24).fill(0).map((_, i) => i),
  features: [{ feature: '공정 계획', calls: 10, paths: 2 }], top_users: [{ emp_no: 'park.pm', display_name: '박공정', calls: 9, last_dt: '', top_feature: '공정 계획' }],
  endpoints: [{ method: 'GET', path: '/api/plans/{plan_id}', calls: 5, errors: 1, avg_ms: 3, max_ms: 9, feature: '공정 계획' }],
  menus: [], recent_errors: [{ call_dt: '2026-11-13 01:00:00', method: 'POST', path: '/api/x', status: 503, emp_no: 'admin', display_name: '김관리' }],
  demo_calls: 4151, user_options: [{ emp_no: 'park.pm', display_name: '박공정' }], ...extra,
})

describe('UsageLog', () => {
  beforeEach(() => setSession())
  it('KPI·예시 배지·사용자 클릭 필터와 해제·빈 메시지', async () => {
    const calls = mockApi([['GET', /usage\/summary/, () => [200, SUM()]]])
    const w = mount(UsageLog, { props: { title: '사용 로그' } })
    await flushPromises()
    expect(w.text()).toContain('4,928')
    expect(w.text()).toContain('예시 데이터 4,151건 포함')
    expect(w.text()).toContain('오류 143건 (4xx·5xx)')
    expect(w.text()).toContain('기록이 없습니다.')
    expect(w.findAll('.hcol')).toHaveLength(24)
    expect(w.find('.b-bad').text()).toBe('503')
    await w.find('.hb.clk').trigger('click'); await flushPromises()
    expect(calls.at(-1).url).toContain('emp_no=park.pm')
    expect(w.text()).toContain('필터 해제')
    await w.find('.hb.clk').trigger('click'); await flushPromises()
    expect(calls.at(-1).url).not.toContain('emp_no')
  })
})

const ITEM = (id, extra = {}) => ({ inquiry_id: id, category: 'FEATURE', title: 'T' + id, content: 'line1\nline2', status: 'OPEN', create_user_id: 'park.pm', create_user_nm: '박공정', create_dt: '2026-11-07 10:19:00', modify_dt: null, answer: null, answer_user_nm: null, answer_dt: null, mine: true, ...extra })
const LIST = (items, isAdmin) => ({ items, total: items.length, counts: { OPEN: 1, IN_PROGRESS: 1, DONE: 0, REJECTED: 0 }, is_admin: isAdmin,
  categories: { BUG: '오류 신고', FEATURE: '기능 건의', QUESTION: '사용 문의', ETC: '기타' }, statuses: { OPEN: '접수', IN_PROGRESS: '처리중', DONE: '완료', REJECTED: '반려' } })

describe('Inquiry', () => {
  beforeEach(() => setSession())

  it('회원: 칩 건수, 작성 등록, 본인 OPEN 글 수정·삭제 버튼, 작성자 열 없음', async () => {
    const calls = mockApi([
      ['GET', /\/api\/inquiries/, () => [200, LIST([ITEM(2), ITEM(1, { status: 'IN_PROGRESS', answer: '검토 중', answer_user_nm: '김관리', answer_dt: '2026-11-08 00:19:00' })], false)]],
      ['POST', /\/api\/inquiries$/, (u, b) => [201, ITEM(3, b)]],
    ])
    const w = mount(Inquiry, { props: { title: '건의·문의' } })
    await flushPromises()
    expect(w.find('.seg').text()).toContain('전체 2')
    expect(w.findAll('thead th').map((t) => t.text())).not.toContain('작성자')
    expect(w.text()).toContain('목록에서 글을 선택하거나 새 글을 작성하세요.')
    await w.findAll('tbody tr')[0].trigger('click')
    expect(w.text()).toContain('관리자가 확인 중입니다.')
    expect(w.findAll('button').some((b) => b.text() === '수정')).toBe(true)
    await w.findAll('tbody tr')[1].trigger('click')
    expect(w.text()).toContain('관리자 답변')
    expect(w.findAll('button').some((b) => b.text() === '수정')).toBe(false)
    await w.findAll('button').find((b) => b.text() === '+ 새 글 작성').trigger('click')
    expect(w.find('select[aria-label="분류"]').element.value).toBe('FEATURE')
    await w.find('input[aria-label="제목"]').setValue('  제목 ')
    await w.find('textarea').setValue('내용')
    await w.find('form.ed').trigger('submit'); await flushPromises()
    expect(calls.find((c) => c.method === 'POST').body).toEqual({ category: 'FEATURE', title: '  제목 ', content: '내용' })
  })

  it('관리자: 내 글만·작성자 열·처리 저장', async () => {
    const calls = mockApi([
      ['GET', /\/api\/inquiries/, () => [200, LIST([ITEM(1, { mine: false })], true)]],
      ['PATCH', /\/api\/inquiries\/1$/, () => [200, ITEM(1)]],
    ])
    const w = mount(Inquiry, { props: { title: '건의·문의' } })
    await flushPromises()
    expect(w.text()).toContain('내 글만')
    expect(w.text()).toContain('목록에서 글을 선택해 처리하세요.')
    await w.find('tbody tr').trigger('click')
    expect(w.text()).toContain('답변 (선택)')
    await w.findAll('.st')[2].trigger('click')
    expect(w.text()).toContain('답변 *')
    await w.find('textarea[aria-label="답변"]').setValue('완료했습니다')
    await w.findAll('button').find((b) => b.text() === '처리 저장').trigger('click'); await flushPromises()
    expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ status: 'DONE', answer: '완료했습니다' })
  })
})
