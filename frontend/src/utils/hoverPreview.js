// 목록 마우스오버 미리보기 공통 로직(ui.md). HoverCard.vue와 함께 쓴다.
import { reactive, onBeforeUnmount, getCurrentInstance } from 'vue'

export const OPEN_DELAY = 280
export const CLOSE_DELAY = 160
export const DEFAULT_TTL = 30000

export function useHoverPreview(loader, { onDispose, ttl = DEFAULT_TTL } = {}) {
  const state = reactive({ open: false, key: null, data: null, loading: false, error: null, anchor: null, ctx: null })
  const cache = new Map() // key -> { data, at }
  let openTimer = null
  let closeTimer = null
  let pendingKey = null
  let disabled = false

  const clearOpen = () => { clearTimeout(openTimer); openTimer = null; pendingKey = null }
  const clearClose = () => { clearTimeout(closeTimer); closeTimer = null }

  function load(key) {
    const hit = cache.get(key)
    if (hit && Date.now() - hit.at < ttl) { state.data = hit.data; state.loading = false; return }
    if (hit) { onDispose?.(hit.data); cache.delete(key) }
    state.data = null; state.loading = true; state.error = null
    Promise.resolve().then(() => loader(key)).then((data) => {
      if (state.key !== key) { onDispose?.(data); return }
      cache.set(key, { data, at: Date.now() })
      state.data = data; state.loading = false
    }, (e) => {
      if (state.key !== key) return
      state.loading = false; state.error = e?.message || '불러오지 못했습니다.'
    })
  }

  /** 행 mouseenter. ev는 이벤트(현재 대상의 위치와 마우스 x를 즉시 읽는다). ctx는 화면 데이터. */
  function enter(key, ev, ctx = null) {
    clearClose()
    if (disabled) return
    if ((state.open && state.key === key) || pendingKey === key) return
    clearOpen()
    const el = ev?.currentTarget
    const r = el?.getBoundingClientRect ? el.getBoundingClientRect() : { top: 0, bottom: 0, left: 0, right: 0 }
    const anchor = { top: r.top, bottom: r.bottom, left: r.left, right: r.right, x: ev?.clientX ?? r.left }
    pendingKey = key
    openTimer = setTimeout(() => {
      pendingKey = null; openTimer = null
      state.key = key; state.anchor = anchor; state.ctx = ctx; state.open = true
      load(key)
    }, OPEN_DELAY)
  }
  function scheduleClose() {
    clearOpen(); clearClose()
    closeTimer = setTimeout(hide, CLOSE_DELAY)
  }
  function hide() {
    clearOpen(); clearClose()
    state.open = false; state.key = null; state.ctx = null; state.data = null; state.loading = false
  }
  /** 목록 재조회·저장 후 캐시 비움 */
  function clear() {
    for (const v of cache.values()) onDispose?.(v.data)
    cache.clear()
  }
  function setDisabled(v) { disabled = !!v; if (disabled) hide() }

  if (getCurrentInstance()) onBeforeUnmount(() => { hide(); clear() })

  return { state, enter, leave: scheduleClose, cardEnter: clearClose, cardLeave: scheduleClose, hide, clear, setDisabled }
}
