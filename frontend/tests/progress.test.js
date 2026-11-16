import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ProgressInput from '../src/screens/ProgressInput.vue'
import { toasts } from '../src/utils/toast'
import { setSession, mockApi } from './helpers'

const plan = (rate = 70, status = 'WORK') => ({ plan_id: 10, label: '[201] 탑재', plan_start_dt: '2026-09-21', plan_end_dt: '2026-11-01', actual_start_dt: '2026-09-21', progress_rate: rate, plan_status: status, manager_nm: '한현장' })
const hist = [{ progress_id: 1, work_dt: '2026-10-19', progress_rate: 70, man_hour: 80, worker_cnt: 8, worker_nm: '한현장' }]

describe('ProgressInput', () => {
  beforeEach(() => { setSession(); toasts.splice(0) })
  const base = (extra = []) => [
    ['GET', /progress-hulls/, () => [200, { hulls: [{ hull_no: '8001', hull_nm: 'A' }, { hull_no: '8002', hull_nm: 'B' }], default_hull_no: '8001' }]],
    ['GET', /users\/options/, () => [200, [{ emp_no: 'park.pm', display_name: '박공정' }]]],
    ['GET', /progress-targets/, () => [200, { hull_no: '8001', today: '2026-10-19', plans: [plan()] }]],
    ['GET', /\/plans\/10\/progress/, () => [200, { plan: plan(), history: hist }]],
    ...extra,
  ]

  it('기본 목록·완료 포함 쿼리·선택 상세·기본값', async () => {
    const calls = mockApi(base())
    const w = mount(ProgressInput, { props: { canWrite: true } })
    await flushPromises()
    expect(calls.find((c) => c.url.includes('progress-targets')).url).toContain('include_done=false')
    expect(w.text()).toContain('위 목록에서 공정을 선택하세요.')
    await w.find('input[type=checkbox]').setValue(true); await flushPromises()
    expect(calls.at(-1).url).toContain('include_done=true')
    await w.find('tbody tr').trigger('click'); await flushPromises()
    expect(w.vm.form).toMatchObject({ work_dt: '2026-10-19', progress_rate: 70, worker_emp_no: 'park.pm' })
    expect(w.find('.prog-detail').text()).toContain('80')
  })

  it('100% 저장 토스트와 목록 재조회, 호선 변경 시 선택 해제', async () => {
    const calls = mockApi(base([['PUT', /progress\/2026-10-19/, () => [200, { plan: plan(100, 'DONE'), history: hist }]]]))
    const w = mount(ProgressInput, { props: { canWrite: true } })
    await flushPromises()
    await w.vm.select(10); await flushPromises()
    w.vm.form.progress_rate = 100
    await w.find('.prog-detail form').trigger('submit'); await flushPromises()
    const put = calls.find((c) => c.method === 'PUT')
    expect(put.body).toEqual({ progress_rate: 100, man_hour: null, worker_cnt: null, worker_emp_no: 'park.pm', remark: null })
    expect(toasts.at(-1).message).toBe('실적 저장 — 공정이 완료 처리되었습니다.')
    await w.find('select').setValue('8002'); await flushPromises()
    expect(w.text()).toContain('위 목록에서 공정을 선택하세요.')
  })

  it('조회 전용: 폼·삭제 없음', async () => {
    mockApi(base())
    const w = mount(ProgressInput, { props: { canWrite: false } })
    await flushPromises()
    await w.vm.select(10); await flushPromises()
    expect(w.find('.prog-detail form').exists()).toBe(false)
    expect(w.text()).not.toContain('삭제')
    expect(w.text()).toContain('조회 전용')
  })
})
