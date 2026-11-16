import { describe, it, expect, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import UserMgmt from '../src/screens/UserMgmt.vue'
import { permRows, setLevel, effective, isCustom, resetToGroup, menusPayload, permChanged } from '../src/utils/menuPerm'
import { setSession, mockApi } from './helpers'
import { toasts } from '../src/utils/toast'

const MENUS = [
  { menu_id: 'M10', parent_id: null, title: '호선관리', seq: 10, group_level: 1, user_level: null, level: 1 },
  { menu_id: 'M11', parent_id: 'M10', title: '호선 목록', seq: 11, group_level: 1, user_level: null, level: 1 },
  { menu_id: 'M00', parent_id: null, title: '대시보드', seq: 0, group_level: 1, user_level: 2, level: 2 },
]

describe('menuPerm', () => {
  it('정렬·개별 표시·부모 올림·자식 내림·그룹 기본값', () => {
    const rows = permRows(MENUS)
    expect(rows.map((r) => r.menu_id)).toEqual(['M00', 'M10', 'M11'])
    expect(isCustom(rows[0])).toBe(true)
    expect(permChanged(rows)).toBe(false)
    setLevel(rows, 'M10', 0)
    expect(effective(rows[2])).toBe(0)
    setLevel(rows, 'M11', 2)
    expect(effective(rows[1])).toBe(1)
    expect(permChanged(rows)).toBe(true)
    resetToGroup(rows)
    expect(menusPayload(rows).menus.every((m) => m.level === null)).toBe(true)
  })
})

const U = (emp, extra = {}) => ({ emp_no: emp, last_name: '최', first_name: '품질', display_name: '최품질', email: emp + '@x.kr', phone: '010-5555-0005', birth_date: '1983-09-09', status: 'approved', totp_enabled: false, groups: [{ code: 'VIEW', name: '조회전용' }], created_at: '2026-01-05 00:00:00', ...extra })

describe('UserMgmt', () => {
  beforeEach(() => { setSession({ me: { emp_no: 'admin', display_name: '김관리', groups: [], today: '2026-10-19' } }); toasts.splice(0) })

  it('선택·수정 저장 시 바뀐 메뉴 권한만 PUT, 승인 버튼, 본인 삭제 차단', async () => {
    const calls = mockApi([
      ['GET', /\/api\/users\?|\/api\/users$/, () => [200, { users: [U('choi.qa'), U('jung.new', { status: 'pending', groups: [], display_name: '정신입' }), U('admin', { display_name: '김관리' })], total: 3, pending: 1 }]],
      ['GET', /auth-groups/, () => [200, [{ code: 'VIEW', name: '조회전용' }, { code: 'ADMIN', name: '시스템관리자' }]]],
      ['GET', /\/menus$/, () => [200, { emp_no: 'x', menus: MENUS }]],
      ['PATCH', /\/api\/users\//, () => [200, {}]], ['PUT', /\/menus$/, () => [200, {}]],
    ])
    const w = mount(UserMgmt, { props: { title: '회원관리', canWrite: true } })
    await flushPromises()
    expect(w.text()).toContain('3명 · 승인대기 1명')
    expect(w.text()).toContain('목록에서 회원을 선택하거나 [신규]를 누르세요.')
    await w.findAll('tbody tr')[0].trigger('click'); await flushPromises()
    expect(w.text()).toContain('회원 수정 — 최품질')
    expect(w.find('input[aria-label="아이디"]').attributes('readonly')).toBeDefined()
    expect(w.text()).not.toContain('가입 승인')
    await w.find('input[aria-label="호선 목록 쓰기"]').setValue(true)
    await w.findAll('button').find((b) => b.text() === '저장').trigger('click'); await flushPromises()
    const patch = calls.find((c) => c.method === 'PATCH')
    expect(patch.body.password).toBeUndefined()
    expect(patch.body.groups).toEqual(['VIEW'])
    const put = calls.find((c) => c.method === 'PUT')
    expect(put.body.menus.find((m) => m.menu_id === 'M11').level).toBe(2)
    expect(put.body.menus.find((m) => m.menu_id === 'M10').level).toBe(null)
    await w.findAll('tbody tr')[1].trigger('click'); await flushPromises()
    expect(w.text()).toContain('가입 승인')
    await w.findAll('.user-table tbody tr')[2].trigger('click'); await flushPromises()
    await w.findAll('button').find((b) => b.text() === '삭제').trigger('click')
    expect(toasts.at(-1).message).toBe('로그인 중인 본인 계정은 삭제할 수 없습니다.')
    await w.findAll('button').find((b) => b.text() === '신규').trigger('click')
    expect(w.text()).toContain('회원 등록')
    expect(w.text()).toContain('저장한 뒤 메뉴 권한을 지정할 수 있습니다.')
    expect(w.text()).toContain('비밀번호 *')
  })
})
