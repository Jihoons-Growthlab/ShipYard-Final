// 회원별 메뉴 권한 표(F09). rows: [{menu_id,parent_id,title,seq,group_level,user_level,level}] → choice(null=그룹 따름).
export const LEVELS = [{ v: 0, name: '없음' }, { v: 1, name: '읽기' }, { v: 2, name: '쓰기' }]
export const levelName = (v) => LEVELS.find((l) => l.v === v)?.name ?? '-'

/** 표 행: 부모 다음에 자식(seq순), choice 초기값은 user_level */
export function permRows(menus) {
  const sorted = [...menus].sort((a, b) => a.seq - b.seq)
  const out = []
  for (const p of sorted.filter((m) => !m.parent_id)) {
    out.push({ ...p, depth: 0, choice: p.user_level ?? null })
    for (const c of sorted.filter((m) => m.parent_id === p.menu_id)) out.push({ ...c, depth: 1, choice: c.user_level ?? null })
  }
  return out
}
export const effective = (r) => (r.choice ?? r.group_level)
export const isCustom = (r) => effective(r) !== r.group_level

/** 하위를 0보다 크게 하면 부모가 0일 때 부모를 1로, 0으로 하면 자식도 0 */
export function setLevel(rows, menuId, level) {
  const row = rows.find((r) => r.menu_id === menuId)
  if (!row) return
  row.choice = level
  if (level > 0 && row.parent_id) {
    const p = rows.find((r) => r.menu_id === row.parent_id)
    if (p && effective(p) === 0) p.choice = 1
  }
  if (level === 0) for (const c of rows.filter((r) => r.parent_id === menuId)) c.choice = 0
}
export function resetToGroup(rows) { for (const r of rows) r.choice = null }
export const menusPayload = (rows) => ({ menus: rows.map((r) => ({ menu_id: r.menu_id, level: r.choice })) })
export const permChanged = (rows) => rows.some((r) => r.choice !== (r.user_level ?? null))
