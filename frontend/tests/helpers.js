import { vi } from 'vitest'
import { session } from '../src/stores/session'

export const CODES = {
  SHIPTYPE: [{ code: 'LNG', name: 'LNG운반선' }, { code: 'PC', name: 'PC선' }],
  HULLSTAT: [{ code: 'PLAN', name: '계획' }, { code: 'BUILD', name: '건조' }],
  BLOCKTYPE: [{ code: 'FLAT', name: '평블록' }],
  PLANSTAT: [{ code: 'PLAN', name: '계획' }, { code: 'READY', name: '착수가능' }, { code: 'WORK', name: '진행' }, { code: 'DONE', name: '완료' }, { code: 'DELAY', name: '지연' }],
  DWGSTAT: [{ code: 'DRAFT', name: '작성중' }, { code: 'REVIEW', name: '검토중' }, { code: 'APPROVED', name: '승인' }, { code: 'ISSUED', name: '배포' }],
}

export function setSession(extra = {}) {
  Object.assign(session, { me: { emp_no: 'park.pm', display_name: '박공정', groups: [], today: '2026-10-19' }, menu: [], codes: CODES, loaded: true, ...extra })
}

/** routes: [[method, regex, (url, body) => [status, body]]]. 호출 기록은 반환 배열에. */
export function mockApi(routes) {
  const calls = []
  globalThis.fetch = vi.fn(async (url, opts = {}) => {
    const method = opts.method || 'GET'
    const body = opts.body ? JSON.parse(opts.body) : undefined
    calls.push({ method, url: decodeURIComponent(url), body })
    for (const [m, re, fn] of routes) {
      if (m === method && re.test(url)) {
        const [status, data] = fn(url, body)
        return { ok: status < 400, status, text: async () => (data == null ? '' : JSON.stringify(data)) }
      }
    }
    return { ok: false, status: 404, text: async () => JSON.stringify({ message: 'nf ' + url }) }
  })
  return calls
}
