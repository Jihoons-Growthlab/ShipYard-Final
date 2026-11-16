import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import HullList from '../src/screens/HullList.vue'
import HullDetailModal from '../src/screens/HullDetailModal.vue'
import { setSession, mockApi } from './helpers'

const H = (no, extra = {}) => ({ hull_no: no, hull_nm: 'N' + no, ship_type: 'LNG', hull_status: 'BUILD', owner_nm: 'O', class_society: 'DNV', dock_no: null, contract_dt: '2025-01-01', delivery_dt: '2027-01-01', progress: 65, delay_count: 0, use_yn: true, ...extra })

describe('HullList', () => {
  beforeEach(() => { setSession(); document.body.innerHTML = '' })

  it('목록·필터 쿼리·초기화·총 N척·계획 없음', async () => {
    const calls = mockApi([['GET', /\/api\/hulls/, () => [200, [H('8001'), H('8004', { progress: null, delay_count: 2 })]]]])
    const w = mount(HullList, { props: { title: '호선 목록', canWrite: true } })
    await flushPromises()
    expect(w.findAll('tbody tr')).toHaveLength(2)
    expect(w.text()).toContain('총 2척')
    expect(w.text()).toContain('계획 없음')
    expect(w.text()).toContain('건조')
    await w.findAll('select')[0].setValue('BUILD')
    await w.find('input').setValue('lng')
    await w.find('form').trigger('submit'); await flushPromises()
    expect(calls.at(-1).url).toContain('status=BUILD')
    expect(calls.at(-1).url).toContain('q=lng')
    await w.findAll('button').find((b) => b.text() === '초기화').trigger('click'); await flushPromises()
    expect(calls.at(-1).url).toBe('/api/hulls')
    expect(w.text()).toContain('+ 호선 등록')
  })

  it('조회 전용: 배지 표시·등록 버튼 숨김, 더블클릭 상세', async () => {
    mockApi([['GET', /\/api\/hulls$/, () => [200, [H('8001')]]], ['GET', /\/api\/hulls\/8001$/, () => [200, H('8001')]]])
    const w = mount(HullList, { props: { title: '호선 목록', canWrite: false }, attachTo: document.body })
    await flushPromises()
    expect(w.text()).toContain('조회 전용')
    expect(w.text()).not.toContain('+ 호선 등록')
    await w.find('tbody tr').trigger('dblclick'); await flushPromises()
    expect(document.querySelector('.mtitle').textContent).toBe('호선 8001')
    expect([...document.querySelectorAll('.hull-info button')].every((b) => b.disabled)).toBe(true)
    w.unmount()
  })
})

describe('HullDetailModal', () => {
  beforeEach(() => { setSession(); document.body.innerHTML = '' })

  it('신규 등록 후 해당 호선 상세로 전환, 서브탭 표시', async () => {
    const calls = mockApi([
      ['POST', /\/api\/hulls$/, (u, b) => [201, H(b.hull_no)]],
      ['GET', /\/api\/hulls\/9001$/, () => [200, H('9001')]],
      ['GET', /\/api\/hulls\/9001\/milestones/, () => [200, [{ milestone_cd: 'DELIVER', name: '인도', plan_dt: '2027-01-01', actual_dt: null, diff_days: null }]]],
    ])
    const w = mount(HullDetailModal, { props: { hullNo: null, canWrite: true }, attachTo: document.body })
    expect(document.querySelector('.subtabs')).toBeNull()
    expect(document.body.textContent).toContain('신규 호선을 등록합니다.')
    const inp = document.querySelector('.hull-info input')
    inp.value = '9001'; inp.dispatchEvent(new Event('input'))
    document.querySelector('.hull-info').dispatchEvent(new Event('submit'))
    await flushPromises()
    const post = calls.find((c) => c.method === 'POST')
    expect(post.body.hull_no).toBe('9001')
    expect(post.body.length_m).toBeNull()
    expect(document.querySelector('.mtitle').textContent).toBe('호선 9001')
    expect(document.querySelectorAll('.subtabs button')).toHaveLength(5)
    expect(w.emitted('changed')[0]).toEqual(['9001'])
    document.querySelectorAll('.subtabs button')[1].click(); await flushPromises()
    expect(document.body.textContent).toContain('일정 저장')
    w.unmount()
  })
})
