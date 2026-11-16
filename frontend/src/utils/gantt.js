// 간트 좌표 계산(F05). x는 타임라인(왼쪽 열 제외) 기준 px.
import { addDays, diffDays, monthStart, addMonths, minDate, maxDate } from './date'

export const LEFT = 230
export const ROW_H = 28
export const HEAD_H = 34
export const SCALES = [{ label: '축소', value: 2.5 }, { label: '보통', value: 4 }, { label: '확대', value: 6 }]

export function ganttLayout(plans, today, scale) {
  let lo = addDays(today, -5)
  let hi = addDays(today, 5)
  for (const p of plans) {
    if (p.plan_start_dt) lo = minDate(lo, p.plan_start_dt)
    if (p.plan_end_dt) hi = maxDate(hi, p.plan_end_dt)
  }
  const start = monthStart(lo)
  const days = diffDays(hi, start) + 8
  const timelineWidth = Math.ceil(days * scale)
  return { start, end: hi, days, scale, timelineWidth, width: LEFT + timelineWidth, x: (d) => diffDays(d, start) * scale }
}

export function months(layout) {
  const out = []
  const last = addDays(layout.start, layout.days)
  for (let m = layout.start; m < last; m = addMonths(m, 1)) {
    const x = layout.x(m)
    const w = Math.min(layout.x(addMonths(m, 1)), layout.timelineWidth) - x
    out.push({ key: m, label: m.slice(0, 7).replace('-', '.'), x, w })
  }
  return out
}

export function barGeom(startDt, endDt, layout) {
  return { left: layout.x(startDt), width: (diffDays(endDt, startDt) + 1) * layout.scale }
}

/** 드래그 결과 날짜. mode: move | start | end. 기간은 최소 1일. */
export function dragDates(startDt, endDt, mode, dx, scale) {
  const n = Math.round(dx / scale)
  if (mode === 'move') return { start: addDays(startDt, n), end: addDays(endDt, n) }
  if (mode === 'start') { const s = addDays(startDt, n); return { start: s > endDt ? endDt : s, end: endDt } }
  const e = addDays(endDt, n)
  return { start: startDt, end: e < startDt ? startDt : e }
}

/** 선후행선: 선행 종료+1일 지점의 행 중앙 → 4px 오른쪽 → 수직 → 후행 시작. [{d, from, to}] */
export function depPaths(plans, deps, layout) {
  const idx = new Map(plans.map((p, i) => [p.plan_id, i]))
  const out = []
  for (const { plan_id: to, pred_plan_id: from } of deps) {
    if (!idx.has(from) || !idx.has(to)) continue
    const a = plans[idx.get(from)], b = plans[idx.get(to)]
    const y1 = idx.get(from) * ROW_H + ROW_H / 2
    const y2 = idx.get(to) * ROW_H + ROW_H / 2
    const x1 = layout.x(addDays(a.plan_end_dt, 1))
    const x2 = layout.x(b.plan_start_dt)
    out.push({ d: `M${x1} ${y1} H${x1 + 4} V${y2} H${x2}`, from, to })
  }
  return out
}
