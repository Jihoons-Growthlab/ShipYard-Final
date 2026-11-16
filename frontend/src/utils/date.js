// 'YYYY-MM-DD' 문자열 날짜 계산(UTC 기준으로 시간대 영향 없음).
const DAY = 86400000

export function parseDate(s) {
  const [y, m, d] = String(s).slice(0, 10).split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d))
}
export function fmtDate(dt) { return dt.toISOString().slice(0, 10) }
export function addDays(s, n) { return fmtDate(new Date(parseDate(s).getTime() + n * DAY)) }
export function diffDays(a, b) { return Math.round((parseDate(a) - parseDate(b)) / DAY) }
export function dow(s) { return parseDate(s).getUTCDay() }
export function monthStart(s) { return String(s).slice(0, 8) + '01' }
export function addMonths(s, n) {
  const d = parseDate(monthStart(s))
  return fmtDate(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + n, 1)))
}
export const minDate = (a, b) => (a < b ? a : b)
export const maxDate = (a, b) => (a > b ? a : b)

/** 서버 UTC 'YYYY-MM-DD HH:MM[:SS]' → 브라우저 현지 'YYYY-MM-DD HH:MM' */
export function localDateTime(s) {
  if (!s) return ''
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  if (!m) return String(s)
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]))
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
