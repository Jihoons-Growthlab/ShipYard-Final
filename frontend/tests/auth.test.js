import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

const push = vi.fn()
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))

import LoginView from '../src/views/LoginView.vue'
import { getToken, TOKEN_KEY } from '../src/api/client'
import { toasts } from '../src/utils/toast'

function mockFetch(handler) {
  globalThis.fetch = vi.fn(async (url, opts) => {
    const [status, body] = handler(url, opts)
    return { ok: status < 400, status, text: async () => (body == null ? '' : JSON.stringify(body)) }
  })
}

describe('LoginView', () => {
  beforeEach(() => { sessionStorage.clear(); push.mockReset(); toasts.splice(0) })

  it('로그인 실패 메시지를 카드 안에 표시', async () => {
    mockFetch(() => [401, { code: 'INVALID_CREDENTIALS', message: '아이디 또는 비밀번호가 올바르지 않습니다.' }])
    const w = mount(LoginView)
    await w.find('#lg-id').setValue('x'); await w.find('#lg-pw').setValue('y')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('.auth-err').text()).toBe('아이디 또는 비밀번호가 올바르지 않습니다.')
    expect(getToken()).toBeNull()
  })

  it('일반 계정은 토큰 저장 후 / 이동', async () => {
    mockFetch(() => [200, { otp_required: false, access_token: 'T1', user: {} }])
    const w = mount(LoginView)
    await w.find('form').trigger('submit'); await flushPromises()
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('T1')
    expect(push).toHaveBeenCalledWith('/')
  })

  it('OTP 계정은 2단계에서 otp_token으로 인증', async () => {
    const calls = []
    mockFetch((url, opts) => {
      calls.push([url, opts.headers.Authorization])
      return url.includes('/otp/verify') ? [200, { access_token: 'FULL' }] : [200, { otp_required: true, otp_token: 'OTP' }]
    })
    const w = mount(LoginView)
    await w.find('form').trigger('submit'); await flushPromises()
    expect(w.text()).toContain('구글 2차 인증')
    expect(getToken()).toBeNull()
    await w.find('input.otp').setValue('123456')
    await w.find('form').trigger('submit'); await flushPromises()
    expect(calls[1]).toEqual(['/api/auth/otp/verify', 'Bearer OTP'])
    expect(getToken()).toBe('FULL')
  })

  it('가입 성공 시 로그인으로 돌아가 토스트', async () => {
    mockFetch(() => [201, { emp_no: 'abcd', status: 'pending' }])
    const w = mount(LoginView)
    await w.find('.ac-foot a').trigger('click')
    expect(w.findAll('.signup input')).toHaveLength(8)
    await w.find('form').trigger('submit'); await flushPromises()
    expect(w.text()).toContain('조선소 통합관리')
    expect(toasts[0].message).toBe('가입 신청 완료. 관리자 승인 후 로그인할 수 있습니다.')
  })

  it('가입 검증 오류 표시', async () => {
    mockFetch(() => [400, { code: 'VALIDATION_ERROR', message: '성과 이름을 입력하세요.', details: { field: 'name' } }])
    const w = mount(LoginView)
    await w.find('.ac-foot a').trigger('click')
    await w.find('form').trigger('submit'); await flushPromises()
    expect(w.find('.auth-err').text()).toBe('성과 이름을 입력하세요.')
  })
})
