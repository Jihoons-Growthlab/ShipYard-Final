import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { startViewer, firstLine, MSG_NO_BUILD, MSG_TIMEOUT, MSG_LOADER, _resetForTest } from '../src/utils/unityViewer'
import ShipViewer3D from '../src/components/ShipViewer3D.vue'
import HullDetailModal from '../src/screens/HullDetailModal.vue'
import HullList from '../src/screens/HullList.vue'
import { setSession, mockApi } from './helpers'

const BUILD = { loaderUrl: 'l.js', dataUrl: 'd.data', frameworkUrl: 'f.js', codeUrl: 'c.wasm', companyName: 'SWP', productName: 'ShipyardViewer', productVersion: '1.0' }
const H = (no, extra = {}) => ({ hull_no: no, hull_nm: 'N' + no, ship_type: 'LNG', hull_status: 'BUILD', dock_no: null, delivery_dt: '2027-01-01', progress: 65, delay_count: 0, use_yn: true, ...extra })

function mockFetch({ build = BUILD, text, hulls = [] } = {}) {
  globalThis.fetch = vi.fn(async (url) => {
    if (String(url).endsWith('build.json')) return { ok: true, status: 200, text: async () => text ?? JSON.stringify(build) }
    if (/\/api\/hulls$/.test(url)) return { ok: true, status: 200, text: async () => JSON.stringify(hulls) }
    const m = /\/api\/hulls\/([^/]+)$/.exec(url)
    if (m) return { ok: true, status: 200, text: async () => JSON.stringify(H(m[1])) }
    return { ok: false, status: 404, text: async () => '{}' }
  })
}

/** 가짜 Unity: 인스턴스 생성, 준비 신호, Quit 기록 */
function fakeUnity({ delay = 0, ready = true, fail } = {}) {
  const u = { created: [], quits: 0, sent: [] }
  window.createUnityInstance = vi.fn((canvas, config) => new Promise((resolve, reject) => {
    setTimeout(() => {
      if (fail) { config.showBanner(fail, 'error'); reject(new Error(fail)); return }
      const inst = { canvas, SendMessage: (o, m, a) => u.sent.push([o, m, a]), Quit: vi.fn(async () => { u.quits++ }) }
      u.created.push(inst)
      resolve(inst)
      if (ready) setTimeout(() => canvas.dispatchEvent(new CustomEvent('shipviewer-ready')), 0)
    }, delay)
  }))
  return u
}

function canvas(id = 'cv') { const c = document.createElement('canvas'); c.id = id; document.body.appendChild(c); return c }

beforeEach(() => { HTMLCanvasElement.prototype.getContext = () => null; _resetForTest(); delete window.createUnityInstance; document.head.innerHTML = ''; document.body.innerHTML = ''; setSession() })
afterEach(() => { vi.useRealTimers() })

describe('unityViewer 수명주기', () => {
  it('firstLine은 스택을 뺀다', () => {
    expect(firstLine(new Error('boom\n at x'))).toBe('boom')
  })

  it('canvas id가 없으면 시작하지 않는다', () => {
    expect(() => startViewer(document.createElement('canvas'))).toThrow()
  })

  it('build.json이 JSON이 아니면(SPA 폴백) 빌드 없음', async () => {
    mockFetch({ text: '<!doctype html><html></html>' })
    const h = startViewer(canvas())
    await expect(h.ready).rejects.toThrow(MSG_NO_BUILD)
    expect(fetch.mock.calls[0][1]).toEqual({ cache: 'no-store' })
  })

  it('준비 = 인스턴스 + 준비 신호, config와 SendMessage', async () => {
    mockFetch(); const u = fakeUnity()
    const h = startViewer(canvas())
    const inst = await h.ready
    expect(inst).toBe(u.created[0])
    const cfg = window.createUnityInstance.mock.calls[0][1]
    expect(cfg.codeUrl).toBe('/unity/ship-viewer/Build/c.wasm')
    expect(cfg.devicePixelRatio).toBeLessThanOrEqual(2)
    h.send('SetView', 'front')
    expect(u.sent).toEqual([['ShipViewer', 'SetView', 'front']])
    await h.stop()
    expect(u.quits).toBe(1)
  })

  it('로더 스크립트 실패 시 태그를 지워 재시도를 허용한다', async () => {
    mockFetch()
    const h = startViewer(canvas())
    await flushPromises()
    const s = document.head.querySelector('script[data-unity-loader]')
    expect(s.src).toContain('/unity/ship-viewer/Build/l.js')
    s.onerror()
    await expect(h.ready).rejects.toThrow(MSG_LOADER)
    expect(document.head.querySelector('script[data-unity-loader]')).toBeNull()
    await h.stop()
    const h2 = startViewer(canvas('cv2'))
    await flushPromises()
    expect(document.head.querySelectorAll('script[data-unity-loader]')).toHaveLength(1)
    h2.stop()
  })

  it('wasm 실패(showBanner error)는 첫 줄로 실패 처리', async () => {
    mockFetch(); fakeUnity({ fail: 'wasm streaming compile failed\nstack' })
    const h = startViewer(canvas())
    await expect(h.ready).rejects.toThrow('wasm streaming compile failed')
  })

  it('준비 신호가 없으면 timeout', async () => {
    vi.useFakeTimers()
    mockFetch(); fakeUnity({ ready: false })
    const h = startViewer(canvas(), { timeoutMs: 1000 })
    const p = expect(h.ready).rejects.toThrow(MSG_TIMEOUT)
    await vi.advanceTimersByTimeAsync(1100)
    await p
    h.stop(); await vi.advanceTimersByTimeAsync(5000)
  })

  it('로딩 중 닫으면 늦게 온 인스턴스를 바로 Quit하고, 새 시작은 그 종료까지 기다린다', async () => {
    mockFetch(); const u = fakeUnity({ delay: 30 })
    const h = startViewer(canvas())
    await new Promise((r) => setTimeout(r, 5))
    const stopP = h.stop()
    await expect(h.ready).rejects.toThrow('closed')
    const h2 = startViewer(canvas('cv2'))
    await stopP
    expect(u.quits).toBe(1)
    expect(u.created).toHaveLength(1)
    await h2.ready
    expect(u.created).toHaveLength(2)
    await h2.stop()
    expect(u.quits).toBe(2)
  })

  it('새 시작은 이전 인스턴스를 종료한다(동시에 하나)', async () => {
    mockFetch(); const u = fakeUnity()
    const h1 = startViewer(canvas())
    await h1.ready
    const h2 = startViewer(canvas('cv2'))
    expect(h1.closed).toBe(true)
    await h2.ready
    expect(u.quits).toBe(1)
    await h2.stop()
  })
})

describe('ShipViewer3D', () => {
  it('단일: 로딩 → 준비, 카드·시점 버튼, 언마운트 시 종료', async () => {
    mockFetch(); const u = fakeUnity({ delay: 5 })
    const w = mount(ShipViewer3D, { props: { hullNo: '8001' }, attachTo: document.body })
    expect(w.text()).toContain('3D 뷰어 불러오는 중…')
    expect(w.findAll('.vviews button').every((b) => b.element.disabled)).toBe(true)
    await new Promise((r) => setTimeout(r, 30)); await flushPromises()
    expect(w.find('canvas').attributes('id')).toMatch(/^shipviewer-/)
    expect(w.text()).toContain('8001 · N8001')
    expect(w.text()).toContain('미지정')
    expect(w.text()).toContain('가상 조선소 · 예시 선체 형상')
    expect(w.findAll('.vviews button').some((b) => b.element.disabled)).toBe(false)
    await w.findAll('.vviews button')[1].trigger('click')
    expect(u.sent.at(-1)).toEqual(['ShipViewer', 'SetView', 'side'])
    // 호버 카드
    await w.find('.vwrap').trigger('pointerenter')
    w.find('canvas').element.dispatchEvent(new CustomEvent('shipviewer-hover', { detail: true }))
    await flushPromises()
    expect(w.find('.vhover').text()).toContain('건조 · 진척률 65%')
    w.unmount(); await flushPromises(); await new Promise((r) => setTimeout(r, 5))
    expect(u.quits).toBe(1)
  })

  it('실패 덮개와 재시도(새 canvas)', async () => {
    mockFetch({ text: 'not json' }); fakeUnity()
    const w = mount(ShipViewer3D, { props: { hullNo: '8001' }, attachTo: document.body })
    await new Promise((r) => setTimeout(r, 10)); await flushPromises()
    expect(w.text()).toContain('3D 뷰어를 불러오지 못했습니다.')
    expect(w.text()).toContain(MSG_NO_BUILD)
    const id1 = w.find('canvas').attributes('id')
    mockFetch()
    await w.findAll('button').find((b) => b.text() === '재시도').trigger('click')
    await new Promise((r) => setTimeout(r, 20)); await flushPromises()
    expect(w.find('canvas').attributes('id')).not.toBe(id1)
    expect(w.vm.state).toBe('ready')
    w.unmount()
  })

  it('fleet: SetFleet 호출, 슬롯 호버 카드, 클릭 select, 8회 왕복 누적 없음', async () => {
    mockFetch(); const u = fakeUnity()
    const fleet = [H('8001'), H('8002', { progress: null, delivery_dt: null, delay_count: 2 })]
    const w = mount(ShipViewer3D, { props: { fleet }, attachTo: document.body })
    await new Promise((r) => setTimeout(r, 10)); await flushPromises()
    expect(u.sent).toContainEqual(['ShipViewer', 'SetFleet', '2'])
    expect(w.find('.vside').exists()).toBe(false)
    await w.find('.vwrap').trigger('pointerenter')
    w.find('canvas').element.dispatchEvent(new CustomEvent('shipyard-hover', { detail: 1 }))
    await flushPromises()
    const card = w.find('.vhover').text()
    expect(card).toContain('8002 · N8002')
    expect(card).toContain('드라이도크 · 건조')
    expect(card).toContain('계획 없음')
    expect(card).toContain('2건')
    expect(card).toContain('미정')
    expect(card).toContain('클릭하여 상세 보기')
    w.find('canvas').element.dispatchEvent(new CustomEvent('shipyard-select', { detail: 0 }))
    expect(w.emitted('select')[0]).toEqual(['8001'])
    await w.setProps({ fleet: [H('8007')] }); await flushPromises()
    expect(u.sent.at(-1)).toEqual(['ShipViewer', 'SetFleet', '1'])
    w.unmount()
    for (let i = 0; i < 8; i++) {
      const v = mount(ShipViewer3D, { props: { fleet }, attachTo: document.body })
      await flushPromises()
      v.unmount()
    }
    await new Promise((r) => setTimeout(r, 30)); await flushPromises()
    expect(document.querySelectorAll('canvas')).toHaveLength(0)
    expect(document.head.querySelectorAll('script')).toHaveLength(0)
  })
})

describe('호선 화면 3D 연동', () => {
  it('상세 3D 탭: xl, 신규에는 없음, 왕복 시 작성 내용 유지·재조회 없음', async () => {
    const calls = mockApi([['GET', /\/api\/hulls\/8001$/, () => [200, H('8001', { hull_nm: '원래' })]]])
    const w = mount(HullDetailModal, { props: { hullNo: '8001', canWrite: true }, attachTo: document.body, global: { stubs: { ShipViewer3D: { template: '<div class="stub3d"></div>' } } } })
    await flushPromises()
    const tabs = [...document.querySelectorAll('.subtabs button')].map((b) => b.textContent)
    expect(tabs).toContain('3D 보기')
    const name = document.querySelectorAll('.hull-info input')[1]
    name.value = '편집중'; name.dispatchEvent(new Event('input'))
    const n = calls.length
    ;[...document.querySelectorAll('.subtabs button')].find((b) => b.textContent === '3D 보기').click(); await flushPromises()
    expect(document.querySelector('.mpanel').classList.contains('xl')).toBe(true)
    expect(document.querySelector('.stub3d')).not.toBeNull()
    ;[...document.querySelectorAll('.subtabs button')].find((b) => b.textContent === '기본정보').click(); await flushPromises()
    expect(document.querySelectorAll('.hull-info input')[1].value).toBe('편집중')
    expect(calls.length).toBe(n)
    expect(document.querySelector('.mpanel').classList.contains('large')).toBe(true)
    w.unmount()
    const w2 = mount(HullDetailModal, { props: { hullNo: null, canWrite: true }, attachTo: document.body })
    expect(document.body.textContent).not.toContain('3D 보기')
    w2.unmount()
  })

  it('목록: 6척 초과 페이지, 활성·모달 닫힘일 때만 뷰어', async () => {
    const hulls = Array.from({ length: 8 }, (_, i) => H(String(8001 + i)))
    mockApi([['GET', /\/api\/hulls$/, () => [200, hulls]], ['GET', /\/api\/hulls\/8\d+$/, () => [200, H('8001')]]])
    const stub = { props: ['fleet'], emits: ['select'], template: '<div class="stub3d">{{ fleet.map(h => h.hull_no).join(",") }}</div>' }
    const w = mount(HullList, { props: { title: '호선 목록', canWrite: true, active: true }, attachTo: document.body, global: { stubs: { ShipViewer3D: stub } } })
    await flushPromises()
    expect(w.text()).toContain('3D 조선소')
    expect(w.text()).toContain('1 / 2')
    expect(w.find('.stub3d').text()).toBe('8001,8002,8003,8004,8005,8006')
    await w.findAll('button').find((b) => b.text() === '다음').trigger('click')
    expect(w.find('.stub3d').text()).toBe('8007,8008')
    w.findComponent(stub).vm.$emit('select', '8007'); await flushPromises()
    expect(w.find('.stub3d').exists()).toBe(false)
    await w.setProps({ active: false })
    w.unmount()
  })
})
