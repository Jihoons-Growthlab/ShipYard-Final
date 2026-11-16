// 사용 로그 차트 계산(F11).
export const PALETTE = ['#2563eb', '#0ea5e9', '#16a34a', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#64748b', '#ef4444', '#84cc16']

/** y축 최대: 10^n 단위 올림(743 → 800, 0 → 1) */
export function niceMax(v) {
  if (!v || v <= 0) return 1
  const p = 10 ** Math.floor(Math.log10(v))
  return Math.ceil(v / p) * p
}
/** x 라벨 간격: 7일 이하 매일, 30일 5일, 90일 15일 */
export const labelStep = (days) => (days <= 7 ? 1 : days <= 30 ? 5 : 15)

export const CH = { w: 640, h: 200, l: 34, r: 10, t: 12, b: 26 }

/** 일별 추이 좌표 */
export function lineGeom(daily) {
  const max = niceMax(Math.max(0, ...daily.map((d) => d.calls)))
  const iw = CH.w - CH.l - CH.r, ih = CH.h - CH.t - CH.b
  const n = daily.length
  const x = (i) => CH.l + (n <= 1 ? iw / 2 : (i * iw) / (n - 1))
  const y = (v) => CH.t + ih - (v / max) * ih
  const pts = daily.map((d, i) => [x(i), y(d.calls)])
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
  const base = CH.t + ih
  const area = pts.length ? `${line} L${pts.at(-1)[0].toFixed(1)},${base} L${pts[0][0].toFixed(1)},${base} Z` : ''
  const bw = Math.max(2, Math.min(14, (iw / Math.max(1, n)) * 0.5))
  const bars = daily.map((d, i) => ({ x: x(i) - bw / 2, y: y(d.errors), w: bw, h: base - y(d.errors) }))
  return { max, ticks: [0, max / 2, max], x, y, line, area, bars, base }
}
export const methodClass = (m) => ({ GET: 'm-get', POST: 'm-post', PATCH: 'm-put', PUT: 'm-put', DELETE: 'm-del' }[m] || '')
