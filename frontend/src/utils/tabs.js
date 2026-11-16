// 셸 탭 상태(F02). 순수 함수 — 상태 객체 { tabs:[{key,token,param,ctx}], active }를 직접 바꾼다.
export const MAX_TABS = 12
export const TAB_LIMIT_MSG = '탭은 최대 12개까지 열 수 있습니다. 사용하지 않는 탭을 닫아주세요.'

export const tabKey = (token, param) => `${token}:${param ?? ''}`

/** 반환: { tab, created, error } */
export function openTab(state, token, param = null) {
  const key = tabKey(token, param)
  const found = state.tabs.find((t) => t.key === key)
  if (found) { state.active = key; return { tab: found, created: false } }
  if (state.tabs.length >= MAX_TABS) return { tab: null, created: false, error: TAB_LIMIT_MSG }
  const tab = { key, token, param: param ?? null, ctx: 0 }
  state.tabs.push(tab)
  state.active = key
  return { tab, created: true }
}

/** 닫으면 같은 위치의 다음 탭(없으면 이전 탭)을 활성으로 */
export function closeTab(state, key) {
  const i = state.tabs.findIndex((t) => t.key === key)
  if (i < 0) return
  state.tabs.splice(i, 1)
  if (state.active === key) state.active = (state.tabs[i] || state.tabs[i - 1] || {}).key ?? null
}

export function closeOthers(state) {
  state.tabs = state.tabs.filter((t) => t.key === state.active)
}

export function serialize(state) {
  return JSON.stringify({ tabs: state.tabs.map(({ token, param }) => ({ token, param })), active: state.active })
}

/** 저장본에서 권한 있는 화면만 복구. 없으면 fallback 토큰(대시보드, 없으면 첫 화면)을 연다. */
export function restore(raw, allowedTokens) {
  const state = { tabs: [], active: null }
  let saved = null
  try { saved = raw ? JSON.parse(raw) : null } catch { saved = null }
  for (const t of saved?.tabs || []) {
    if (allowedTokens.includes(t.token) && state.tabs.length < MAX_TABS) openTab(state, t.token, t.param)
  }
  if (state.tabs.length) {
    state.active = state.tabs.some((t) => t.key === saved.active) ? saved.active : state.tabs[0].key
  } else {
    const fb = allowedTokens.includes('dashboard') ? 'dashboard' : allowedTokens[0]
    if (fb) openTab(state, fb)
  }
  return state
}
