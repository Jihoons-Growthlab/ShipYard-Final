import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { openTab, closeTab, closeOthers, serialize, restore, tabKey, TAB_LIMIT_MSG } from '../src/utils/tabs'
import { useHoverPreview } from '../src/utils/hoverPreview'
import AppModal from '../src/components/AppModal.vue'
import ProgressBar from '../src/components/ProgressBar.vue'
import WeatherWidget from '../src/components/WeatherWidget.vue'
import { weatherIcon } from '../src/utils/weather'

describe('tabs', () => {
  it('같은 키 재사용, 12개 제한, 닫으면 다음 탭', () => {
    const s = { tabs: [], active: null }
    expect(openTab(s, 'hull-list').created).toBe(true)
    expect(openTab(s, 'hull-list').created).toBe(false)
    expect(s.tabs).toHaveLength(1)
    openTab(s, 'plan-gantt', '8001')
    expect(s.active).toBe(tabKey('plan-gantt', '8001'))
    for (let i = 0; i < 10; i++) openTab(s, 't' + i)
    expect(s.tabs).toHaveLength(12)
    const r = openTab(s, 'more')
    expect(r.error).toBe(TAB_LIMIT_MSG)
    expect(s.tabs).toHaveLength(12)
    s.active = s.tabs[1].key
    closeTab(s, s.tabs[1].key)
    expect(s.active).toBe('t0:')
    closeOthers(s)
    expect(s.tabs.map((t) => t.key)).toEqual(['t0:'])
  })

  it('복구 시 권한 없는 탭 제외, 없으면 대시보드', () => {
    const s = { tabs: [], active: null }
    openTab(s, 'hull-list'); openTab(s, 'user-mgmt'); openTab(s, 'progress')
    const raw = serialize(s)
    const r = restore(raw, ['dashboard', 'hull-list', 'progress'])
    expect(r.tabs.map((t) => t.token)).toEqual(['hull-list', 'progress'])
    expect(r.active).toBe('progress:')
    const r2 = restore(JSON.stringify({ tabs: [{ token: 'user-mgmt' }] }), ['dashboard', 'hull-list'])
    expect(r2.tabs.map((t) => t.token)).toEqual(['dashboard'])
    expect(restore('broken', ['hull-list']).tabs[0].token).toBe('hull-list')
  })
})

const ticks = async () => { for (let i = 0; i < 10; i++) await Promise.resolve() }

describe('useHoverPreview', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())
  const ev = { currentTarget: { getBoundingClientRect: () => ({ top: 10, bottom: 30, left: 0, right: 100 }) }, clientX: 50 }

  it('280ms 후 열림, 160ms 후 닫힘, 카드 진입 시 유지, 캐시', async () => {
    const loader = vi.fn(async (k) => ({ k }))
    const p = useHoverPreview(loader)
    p.enter('a', ev)
    vi.advanceTimersByTime(279); expect(p.state.open).toBe(false)
    vi.advanceTimersByTime(1); expect(p.state.open).toBe(true)
    await ticks()
    expect(p.state.data).toEqual({ k: 'a' })
    p.enter('a', ev) // 같은 키 재진입 무시
    p.leave(); p.cardEnter(); vi.advanceTimersByTime(500)
    expect(p.state.open).toBe(true)
    p.cardLeave(); vi.advanceTimersByTime(160)
    expect(p.state.open).toBe(false)
    p.enter('a', ev); vi.advanceTimersByTime(280)
    expect(loader).toHaveBeenCalledTimes(1)
    const disposed = []
    const q = useHoverPreview(loader, { onDispose: (d) => disposed.push(d) })
    q.enter('b', ev); vi.advanceTimersByTime(280); await ticks()
    q.clear()
    expect(disposed).toEqual([{ k: 'b' }])
  })

  it('늦은 응답은 현재 키가 아니면 버림', async () => {
    let resolveA
    const loader = vi.fn((k) => (k === 'a' ? new Promise((r) => { resolveA = r }) : Promise.resolve({ k })))
    const p = useHoverPreview(loader)
    p.enter('a', ev); vi.advanceTimersByTime(280); await ticks()
    p.enter('b', ev); vi.advanceTimersByTime(280); await ticks()
    resolveA({ k: 'a' }); await ticks()
    expect(p.state.key).toBe('b')
    expect(p.state.data).toEqual({ k: 'b' })
  })
})

describe('공통 컴포넌트', () => {
  it('AppModal Esc·닫기 버튼·배경 클릭', async () => {
    const w = mount(AppModal, { props: { title: 'T' }, attachTo: document.body })
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    document.querySelector('.mclose').click()
    document.querySelector('.mbg').dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    expect(w.emitted('close')).toHaveLength(3)
    w.unmount()
  })
  it('ProgressBar 범위 제한', () => {
    expect(mount(ProgressBar, { props: { value: 64.6 } }).text()).toBe('65%')
    expect(mount(ProgressBar, { props: { value: 140 } }).find('.pfill').attributes('style')).toContain('100%')
  })
})

describe('날씨', () => {
  it('아이콘 매핑', () => {
    expect(weatherIcon('맑음')).toBe('☀️'); expect(weatherIcon('구름조금')).toBe('⛅'); expect(weatherIcon('흐림')).toBe('☁️')
    expect(weatherIcon('눈')).toBe('❄️'); expect(weatherIcon('비')).toBe('🌧️'); expect(weatherIcon('?')).toBe('🌤️')
  })
  it('지역별 요청·늦은 응답 무시·샘플 배지', async () => {
    localStorage.clear()
    const pending = []
    globalThis.fetch = vi.fn((url) => new Promise((res) => pending.push([url, res])))
    const w = mount(WeatherWidget)
    await w.vm.$nextTick()
    expect(w.text()).toContain('날씨 조회 중…')
    await w.find('select').setValue('거제')
    expect(localStorage.getItem('swp_region')).toBe('거제')
    expect(decodeURIComponent(pending[1][0])).toContain('region=거제')
    const body = (r, t) => ({ ok: true, status: 200, text: async () => JSON.stringify({ region: r, source: 'SAMPLE', tempC: t, condition: '맑음', humidity: 1, windMs: 1 }) })
    pending[1][1](body('거제', 18.9)); await flushPromises()
    pending[0][1](body('울산', 17.6)); await flushPromises()
    expect(w.text()).toContain('18.9℃')
    expect(w.text()).toContain('샘플')
    expect(w.text()).not.toContain('LIVE')
    w.unmount()
  })
})
