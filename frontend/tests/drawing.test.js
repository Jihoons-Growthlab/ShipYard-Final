import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DrawingList from '../src/screens/DrawingList.vue'
import DrawingModal from '../src/screens/DrawingModal.vue'
import { checkPdf, previewRev } from '../src/utils/pdf'
import { setSession, mockApi, CODES } from './helpers'

const CODES2 = { ...CODES, DWGDISC: [{ code: 'HULL', name: '선체' }, { code: 'PIPE', name: '배관' }], DWGSTAT: [...CODES.DWGSTAT, { code: 'OBSOLETE', name: '폐기' }] }
const ITEM = (id, extra = {}) => ({ drawing_id: id, drawing_no: 'D-' + id, drawing_nm: 'N' + id, hull_no: '8001', block_id: 1, block_cd: '101', discipline: 'HULL', dwg_status: 'ISSUED', current_rev_no: 0, latest_rev_no: 0, designer_emp_no: 'lee.dwg', designer_nm: '이도면', link_count: 0, ...extra })
const REV = (n, st, extra = {}) => ({ rev_no: n, rev_status: st, change_desc: 'c' + n, has_file: false, file_nm: null, author_emp_no: 'lee.dwg', author_nm: '이도면', issue_dt: null, create_dt: '2026-01-01', ...extra })
const DETAIL = (revs, extra = {}) => ({ ...ITEM(1), block_nm: '선수부', revisions: revs, approvals: [], plans: [], available_plans: [{ plan_id: 5, label: '[101] 탑재' }], impacts: [], today: '2026-10-19', ...extra })
const BASE = [
  ['GET', /\/api\/hulls$/, () => [200, [{ hull_no: '8001', hull_nm: 'SWP' }]]],
  ['GET', /\/api\/hulls\/8001\/blocks/, () => [200, [{ block_id: 1, block_cd: '101', block_nm: '선수부' }]]],
  ['GET', /\/api\/users\/options/, () => [200, [{ emp_no: 'lee.dwg', display_name: '이도면' }, { emp_no: 'admin', display_name: '김관리' }]]],
]
const file = (name, text, type = '') => new File([text], name, { type })

describe('pdf utils', () => {
  it('PDF 검사: 확장자·서명·크기', async () => {
    expect(await checkPdf(file('a.pdf', '%PDF-1.4'))).toBeNull()
    expect(await checkPdf(file('a.txt', '%PDF-1.4', 'text/plain'))).toBe('PDF 파일만 업로드할 수 있습니다.')
    expect(await checkPdf(file('a.pdf', 'hello'))).toBe('PDF 파일만 업로드할 수 있습니다.')
    const big = { name: 'b.pdf', type: 'application/pdf', size: 31 * 1024 * 1024 }
    expect(await checkPdf(big)).toBe('파일 크기는 30MB 이하여야 합니다.')
  })
  it('미리볼 리비전: 현재 우선, 없으면 파일 있는 최신', () => {
    expect(previewRev({ current_rev_no: 1, revisions: [REV(2, 'DRAFT', { has_file: true }), REV(1, 'ISSUED', { has_file: true })] }).rev_no).toBe(1)
    expect(previewRev({ current_rev_no: 1, revisions: [REV(2, 'DRAFT', { has_file: true }), REV(1, 'ISSUED')] }).rev_no).toBe(2)
    expect(previewRev({ current_rev_no: 0, revisions: [REV(0, 'ISSUED')] })).toBeNull()
  })
})

describe('DrawingList', () => {
  beforeEach(() => { setSession({ codes: CODES2 }); document.body.innerHTML = '' })

  it('Rev 표기·연계 0은 -, 필터 쿼리, param 호선 적용', async () => {
    const calls = mockApi([...BASE, ['GET', /\/api\/drawings/, () => [200, [ITEM(1), ITEM(2, { current_rev_no: 0, latest_rev_no: 1, link_count: 3 })]]]])
    const w = mount(DrawingList, { props: { title: '도면 목록', canWrite: true, param: '8001', ctx: 0 } })
    await flushPromises()
    expect(calls.find((c) => c.url.startsWith('/api/drawings')).url).toContain('hull_no=8001')
    const rows = w.findAll('tbody tr')
    expect(rows[1].text()).toContain('Rev0 (최신 Rev1)')
    expect(rows[0].findAll('td')[8].text()).toBe('-')
    expect(w.text()).toContain('총 2건')
    expect(w.text()).not.toContain('폐기')
    expect(w.text()).toContain('+ 도면 등록')
  })

  it('조회 전용: 등록 버튼 없음', async () => {
    mockApi([...BASE, ['GET', /\/api\/drawings/, () => [200, []]]])
    const w = mount(DrawingList, { props: { title: '도면 목록', canWrite: false } })
    await flushPromises()
    expect(w.text()).toContain('조회 전용')
    expect(w.text()).not.toContain('+ 도면 등록')
  })
})

describe('DrawingModal', () => {
  beforeEach(() => { setSession({ codes: CODES2, me: { emp_no: 'admin', display_name: '김관리', groups: [], today: '2026-10-19' } }); document.body.innerHTML = '' })

  it('DRAFT: 결재 요청 기본 검토자·승인자, 샘플 표시, 업로드 활성', async () => {
    const calls = mockApi([...BASE,
      ['GET', /\/api\/drawings\/1$/, () => [200, DETAIL([REV(0, 'DRAFT', { file_nm: 'a.dwg' })], { dwg_status: 'DRAFT' })]],
      ['POST', /request-approval/, () => [200, {}]]])
    const w = mount(DrawingModal, { props: { drawingId: 1, canWrite: true }, attachTo: document.body })
    await flushPromises()
    const t = document.body.textContent
    expect(t).toContain('샘플 PDF (미업로드)')
    expect(t).toContain('이 리비전에는 업로드된 도면 파일이 없습니다.')
    expect(t).toContain('a.dwg (미업로드)')
    expect(t).toContain('Rev0 작성중입니다.')
    expect(document.querySelector('input[aria-label="PDF 업로드"]').disabled).toBe(false)
    expect(document.querySelector('select[aria-label="1단계 검토자"]').value).toBe('lee.dwg')
    expect(document.querySelector('select[aria-label="2단계 승인자"]').value).toBe('admin')
    ;[...document.querySelectorAll('button')].find((b) => b.textContent === '결재 요청').click()
    await flushPromises()
    expect(calls.find((c) => c.method === 'POST').body).toEqual({ reviewer_emp_no: 'lee.dwg', approver_emp_no: 'admin' })
    w.unmount()
  })

  it('ISSUED: 업로드 비활성·신규 Rev, 영향 경고, 조회 전용은 쓰기 요소 없음', async () => {
    const det = DETAIL([REV(1, 'ISSUED', { issue_dt: '2026-10-01' }), REV(0, 'OBSOLETE')], { current_rev_no: 1, latest_rev_no: 1, plans: [{ plan_id: 3, label: '[101] 대조립', plan_status: 'WORK', required: true, need_dt: null }], impacts: [{ rev_no: 1, issue_dt: '2026-10-01', plan_label: '[101] 대조립' }] })
    mockApi([...BASE, ['GET', /\/api\/drawings\/1$/, () => [200, det]]])
    let w = mount(DrawingModal, { props: { drawingId: 1, canWrite: true }, attachTo: document.body })
    await flushPromises()
    expect(document.querySelector('input[aria-label="PDF 업로드"]').disabled).toBe(true)
    expect(document.body.textContent).toContain('신규 Rev2 개정 사유')
    expect(document.body.textContent).toContain('⚠ 최근 개정(Rev1, 2026-10-01)으로 이미 착수·완료된 공정 1건이 영향을 받습니다: [101] 대조립')
    w.unmount(); document.body.innerHTML = ''
    w = mount(DrawingModal, { props: { drawingId: 1, canWrite: false }, attachTo: document.body })
    await flushPromises()
    expect(document.querySelector('input[aria-label="PDF 업로드"]')).toBeNull()
    expect(document.body.textContent).not.toContain('신규 Rev 작성')
    expect(document.body.textContent).not.toContain('+ 공정 연계')
    expect(document.body.textContent).not.toContain('해제')
    w.unmount()
  })

  it('신규 등록: 기본값(첫 호선·로그인 설계자) 후 상세 전환', async () => {
    const calls = mockApi([...BASE,
      ['POST', /\/api\/drawings$/, (u, b) => [201, { ...DETAIL([REV(0, 'DRAFT')]), drawing_no: b.drawing_no }]],
      ['GET', /\/api\/drawings\/1$/, () => [200, DETAIL([REV(0, 'DRAFT')], { drawing_no: 'X-1' })]]])
    const w = mount(DrawingModal, { props: { drawingId: null, canWrite: true }, attachTo: document.body })
    await flushPromises()
    expect(document.querySelector('.mtitle').textContent).toBe('도면 등록')
    const no = document.querySelector('input[aria-label="도면번호"]')
    no.value = 'X-1'; no.dispatchEvent(new Event('input'))
    document.querySelector('form.dwg-info').dispatchEvent(new Event('submit'))
    await flushPromises()
    const post = calls.find((c) => c.method === 'POST')
    expect(post.body).toMatchObject({ drawing_no: 'X-1', hull_no: '8001', discipline: 'HULL', designer_emp_no: 'admin', block_id: null })
    expect(document.querySelector('.mtitle').textContent).toBe('도면 X-1')
    expect(w.emitted('changed')[0]).toEqual([1])
    w.unmount()
  })
})
