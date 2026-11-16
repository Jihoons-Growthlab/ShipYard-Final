// Unity Web 뷰어 수명주기(프론트 전용 모듈 하나). 인스턴스는 동시에 하나다.
export const BUILD_BASE = '/unity/ship-viewer/Build/'
export const MSG_NO_BUILD = '3D 뷰어 빌드를 찾을 수 없습니다.'
export const MSG_TIMEOUT = '3D 뷰어가 응답하지 않습니다.'
export const MSG_LOADER = '3D 뷰어 로더를 불러오지 못했습니다.'
export const TIMEOUT_MS = 20000
export const SETTLE_MS = 3000
export const VIEWS = ['front', 'side', 'top', 'reset']

const CLOSED = 'closed'
let loaderPromise = null
let active = null
let lastDone = Promise.resolve()

export function firstLine(e) {
  const msg = typeof e === 'string' ? e : e?.message || String(e ?? '')
  return msg.split('\n')[0].trim()
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

export async function loadBuildInfo() {
  let res, info
  try {
    res = await fetch(BUILD_BASE + 'build.json', { cache: 'no-store' })
    info = JSON.parse(await res.text())
  } catch { throw new Error(MSG_NO_BUILD) }
  // SPA 폴백(index.html)이면 JSON이 아니다.
  if (!res.ok || !info || typeof info !== 'object' || !info.loaderUrl) throw new Error(MSG_NO_BUILD)
  return info
}

export function loadLoader(url) {
  if (typeof window.createUnityInstance === 'function') return Promise.resolve()
  if (!loaderPromise) {
    loaderPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script')
      s.src = url
      s.dataset.unityLoader = '1'
      s.onload = () => resolve()
      s.onerror = () => { s.remove(); loaderPromise = null; reject(new Error(MSG_LOADER)) }
      document.head.appendChild(s)
    })
  }
  return loaderPromise
}

function quit(inst) {
  return Promise.race([Promise.resolve().then(() => inst.Quit()).catch(() => {}), sleep(SETTLE_MS)])
}

function loseContext(canvas) {
  try {
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
    gl?.getExtension('WEBGL_lose_context')?.loseContext()
  } catch { /* 이미 해제됨 */ }
}

/**
 * canvas(id 필수)에 뷰어를 시작한다. 반환: { ready: Promise<instance>, stop(): Promise, send(method, arg) }.
 * ready는 인스턴스와 준비 신호가 모두 와야 이행된다. 닫힌 뒤에는 거부(message 'closed')된다.
 */
export function startViewer(canvas, { onProgress, timeoutMs = TIMEOUT_MS } = {}) {
  if (!canvas?.id) throw new Error('canvas id가 필요합니다.')
  if (active) active.stop()
  const prev = lastDone
  const s = { closed: false, instP: null, instance: null, stopP: null }
  let cancel, finish
  const cancelled = new Promise((_, rej) => { cancel = rej })
  cancelled.catch(() => {})
  const done = new Promise((r) => { finish = r })
  lastDone = done

  const readySignal = new Promise((r) => canvas.addEventListener('shipviewer-ready', () => r(), { once: true }))
  const guard = () => { if (s.closed) throw new Error(CLOSED) }

  async function run() {
    await prev // 이전 인스턴스의 로딩 종료와 Quit()까지 기다린다.
    guard()
    const info = await loadBuildInfo()
    guard()
    await loadLoader(BUILD_BASE + info.loaderUrl)
    guard()
    let bannerFail
    const banner = new Promise((_, rej) => { bannerFail = rej })
    banner.catch(() => {})
    const config = {
      dataUrl: BUILD_BASE + info.dataUrl,
      frameworkUrl: BUILD_BASE + info.frameworkUrl,
      codeUrl: BUILD_BASE + info.codeUrl,
      companyName: info.companyName,
      productName: info.productName,
      productVersion: info.productVersion,
      devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
      showBanner: (msg, type) => { if (type === 'error') bannerFail(new Error(firstLine(msg))) },
    }
    s.instP = new Promise((resolve) => resolve(window.createUnityInstance(canvas, config, (p) => onProgress?.(p))))
    s.instP.then((inst) => { s.instance = inst }, () => {})
    const inst = await Promise.race([s.instP, banner])
    guard()
    await Promise.race([readySignal, banner])
    guard()
    return inst
  }

  let timer
  const timeout = new Promise((_, rej) => { timer = setTimeout(() => rej(new Error(MSG_TIMEOUT)), timeoutMs) })
  timeout.catch(() => {})
  const ready = Promise.race([run(), timeout, cancelled])
    .then((inst) => inst, (e) => { throw new Error(s.closed ? CLOSED : firstLine(e)) })
    .finally(() => clearTimeout(timer))
  ready.catch(() => {})

  const handle = {
    ready,
    get closed() { return s.closed },
    send(method, arg) {
      if (s.closed || !s.instance) return false
      try { s.instance.SendMessage('ShipViewer', method, String(arg)); return true } catch { return false }
    },
    stop() {
      if (s.stopP) return s.stopP
      s.closed = true
      cancel(new Error(CLOSED))
      if (active === handle) active = null
      s.stopP = (async () => {
        await prev
        if (s.instP) {
          // 로딩 중 닫혔으면 늦게 온 인스턴스를 바로 Quit()한다.
          const inst = await Promise.race([s.instP.catch(() => null), sleep(timeoutMs).then(() => null)])
          if (inst) await quit(inst)
          loseContext(canvas)
        }
      })().finally(finish)
      return s.stopP
    },
  }
  active = handle
  return handle
}

/** 테스트용: 모듈 상태 초기화 */
export function _resetForTest() { loaderPromise = null; active = null; lastDone = Promise.resolve() }
