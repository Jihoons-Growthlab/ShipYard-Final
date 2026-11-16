// 로그인 사용자·메뉴·코드(셸 진입 시 1회 로드).
import { reactive } from 'vue'
import { api, clearToken } from '../api/client'

export const TABS_KEY = 'swp_tabs'
export const FORBIDDEN_MSG = '해당 화면에 대한 권한이 없습니다.'

export const session = reactive({ me: null, menu: [], codes: {}, loaded: false })

export async function loadSession() {
  const [me, menu, codes] = await Promise.all([api.get('/auth/me'), api.get('/me/menu'), api.get('/codes')])
  Object.assign(session, { me, menu, codes, loaded: true })
}

export function endSession() {
  clearToken()
  try { sessionStorage.removeItem(TABS_KEY) } catch { /* 무시 */ }
  Object.assign(session, { me: null, menu: [], codes: {}, loaded: false })
}

export async function logout() {
  try { await api.post('/auth/logout') } catch { /* 실패와 무관하게 정리 */ }
  endSession()
}

export function menuByToken(token) { return session.menu.find((m) => m.token === token) || null }
export function canWrite(token) { return !!menuByToken(token)?.can_write }

export function codeOptions(group) { return session.codes[group] || [] }
export function codeName(group, code) {
  if (code == null || code === '') return ''
  return codeOptions(group).find((c) => c.code === code)?.name ?? code
}
