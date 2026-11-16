// 단일 API 클라이언트. 토큰은 sessionStorage `swp_token`.
export const TOKEN_KEY = 'swp_token'

let unauthorizedHandler = null

export function getToken() {
  try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
}

export function setToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token)
    else sessionStorage.removeItem(TOKEN_KEY)
  } catch { /* storage 사용 불가 */ }
}

export function clearToken() { setToken(null) }

/** 토큰을 쓴 요청이 401이면 호출된다(세션 정리 후 /login 이동). */
export function onUnauthorized(fn) { unauthorizedHandler = fn }

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.message || `요청에 실패했습니다. (${status})`)
    this.status = status
    this.code = body?.code
    this.details = body?.details || {}
  }
}

export async function request(method, path, { body, query, token, raw } = {}) {
  let url = path.startsWith('/api') ? path : `/api${path}`
  if (query) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(query)) if (v !== undefined && v !== null && v !== '') qs.set(k, v)
    const s = qs.toString()
    if (s) url += `?${s}`
  }
  const headers = {}
  const auth = token ?? getToken()
  if (auth) headers.Authorization = `Bearer ${auth}`
  let payload
  if (body instanceof FormData) payload = body
  else if (typeof Blob !== 'undefined' && body instanceof Blob) { headers['Content-Type'] = body.type || 'application/pdf'; payload = body }
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  const res = await fetch(url, { method, headers, body: payload })
  if (raw && res.ok) return res
  if (res.status === 204) return null
  const text = await res.text()
  const data = text ? (() => { try { return JSON.parse(text) } catch { return text } })() : null
  if (!res.ok) {
    if (res.status === 401 && auth && !token && unauthorizedHandler) unauthorizedHandler()
    throw new ApiError(res.status, typeof data === 'object' ? data : null)
  }
  return data
}

export const api = {
  get: (p, query) => request('GET', p, { query }),
  post: (p, body) => request('POST', p, { body }),
  put: (p, body) => request('PUT', p, { body }),
  patch: (p, body) => request('PATCH', p, { body }),
  del: (p) => request('DELETE', p),
}
