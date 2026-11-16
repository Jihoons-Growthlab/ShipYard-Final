<template>
  <div v-if="session.loaded" class="shell">
    <header class="hd">
      <div class="brand">⚓ SWP 조선소 통합관리 <small>호선 / 공정 / 도면</small></div>
      <div class="grow"></div>
      <WeatherWidget />
      <div class="who">
        <b>{{ session.me.display_name }} 님</b>
        <small>{{ groupText }} · {{ session.me.today }}</small>
      </div>
      <button class="hbtn" type="button" @click="doLogout">로그아웃</button>
    </header>

    <nav class="menu" aria-label="메뉴">
      <div class="menu-cap">MENU</div>
      <template v-for="m in menuTree" :key="m.menu_id">
        <div class="mi" :class="{ on: m.token && m.token === activeToken }" role="button" tabindex="0"
             @click="clickMenu(m)" @keydown.enter="clickMenu(m)">
          <span class="mk">{{ m.children.length ? (collapsed[m.menu_id] ? '▶' : '▼') : '·' }}</span>{{ m.title }}
        </div>
        <template v-if="m.children.length && !collapsed[m.menu_id]">
          <div v-for="c in m.children" :key="c.menu_id" class="mi sub" :class="{ on: c.token === activeToken }" role="button" tabindex="0"
               @click="clickMenu(c)" @keydown.enter="clickMenu(c)">
            <span class="mk">·</span>{{ c.title }}
          </div>
        </template>
      </template>
    </nav>

    <div class="main">
      <div class="tabbar">
        <div v-for="t in tabs.tabs" :key="t.key" class="tab" :class="{ on: t.key === tabs.active }" @click="tabs.active = t.key">
          <span>{{ titleOf(t.token) }}</span>
          <button type="button" class="tx" aria-label="탭 닫기" @click.stop="close(t.key)">×</button>
        </div>
        <div class="grow"></div>
        <button type="button" class="tbtn" @click="openManual()">매뉴얼</button>
        <button v-if="tabs.tabs.length > 1" type="button" class="tbtn" @click="closeOthersTabs">다른 탭 닫기</button>
      </div>
      <div class="work">
        <div v-for="t in tabs.tabs" v-show="t.key === tabs.active" :key="t.key" class="screen">
          <component :is="screenOf(t.token)" :title="titleOf(t.token)" :can-write="canWrite(t.token)"
                     :param="t.param" :ctx="t.ctx" :active="t.key === tabs.active && !overlayOpen" />
        </div>
      </div>
    </div>

    <ShipChat ref="chatRef" />
    <WorkflowManual v-if="manualSection !== null" :section="manualSection" @close="closeManual" />
    <HullDetailModal v-if="hullNo !== null" :hull-no="hullNo" :can-write="canWrite('hull-list')" @close="closeHull" />
    <DrawingModal v-if="drawingId !== null" :drawing-id="drawingId" :can-write="drawingReadonly ? false : canWrite('dwg-list')" @close="closeDrawing" />
  </div>
</template>

<script setup>
import { computed, reactive, ref, provide, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import { session, loadSession, logout, menuByToken, canWrite, TABS_KEY, FORBIDDEN_MSG } from '../stores/session'
import { openTab, closeTab, closeOthers, serialize, restore } from '../utils/tabs'
import { toast, toastError } from '../utils/toast'
import { screenOf } from '../screens/registry'
import WeatherWidget from '../components/WeatherWidget.vue'
import ShipChat from '../components/ShipChat.vue'
import WorkflowManual from '../components/WorkflowManual.vue'
import HullDetailModal from '../screens/HullDetailModal.vue'
import DrawingModal from '../screens/DrawingModal.vue'

const router = useRouter()
const tabs = reactive({ tabs: [], active: null })
const collapsed = reactive({})
const manualSection = ref(null)
const overlayOpen = ref(false)
const drawingId = ref(null)
const drawingReadonly = ref(false)
const hullNo = ref(null)
const chatRef = ref(null)

const groupText = computed(() => (session.me?.groups || []).map((g) => g.name).join(', '))
const menuTree = computed(() => {
  const items = [...session.menu].sort((a, b) => a.seq - b.seq)
  return items.filter((m) => !m.parent_id).map((m) => ({ ...m, children: items.filter((c) => c.parent_id === m.menu_id) }))
})
const activeToken = computed(() => tabs.tabs.find((t) => t.key === tabs.active)?.token)
const titleOf = (token) => menuByToken(token)?.title || token

function persist() { try { sessionStorage.setItem(TABS_KEY, serialize(tabs)) } catch { /* 무시 */ } }
watch(tabs, persist, { deep: true })

async function navigate(token, param = null) {
  const m = menuByToken(token)
  if (!m) { toast(FORBIDDEN_MSG, 'error'); return false }
  const res = openTab(tabs, token, param)
  if (res.error) { toast(res.error, 'error'); return false }
  if (!res.created) { res.tab.ctx++; return true }
  try { await api.post('/me/menu-access', { menu_id: m.menu_id }) } catch (e) {
    if (e.status === 403) { closeTab(tabs, res.tab.key); toast(e.message || FORBIDDEN_MSG, 'error'); return false }
  }
  return true
}

function clickMenu(m) {
  if (!m.token) { collapsed[m.menu_id] = !collapsed[m.menu_id]; return }
  navigate(m.token)
}
function close(key) { closeTab(tabs, key) }
function closeOthersTabs() { closeOthers(tabs) }
// 매뉴얼(F15): 섹션이 없으면 현재 활성 탭, 없으면 대시보드. 열 때 챗봇은 닫는다.
function openManual(section = '') {
  chatRef.value?.close()
  manualSection.value = section || activeToken.value || 'dashboard'; overlayOpen.value = true
}
function closeManual() { manualSection.value = null; overlayOpen.value = false }
// 어느 화면에서든 도면 상세 모달을 연다(공정 패널·결재함·대시보드·챗봇=읽기 전용).
function openDrawing(id, { readonly = false } = {}) {
  if (!menuByToken('dwg-list')) { toast(FORBIDDEN_MSG, 'error'); return }
  drawingReadonly.value = readonly; drawingId.value = Number(id); overlayOpen.value = true
}
function closeDrawing() { drawingId.value = null; overlayOpen.value = false }
// 챗봇 호선 카드 → 호선 상세 모달.
function openHull(no) {
  if (!menuByToken('hull-list')) { toast(FORBIDDEN_MSG, 'error'); return }
  hullNo.value = String(no); overlayOpen.value = true
}
function closeHull() { hullNo.value = null; overlayOpen.value = false }
// 챗봇 건의·문의 접수 후 열린 건의·문의 탭 새로고침.
function refreshInquiry() { tabs.tabs.filter((t) => t.token === 'inquiry').forEach((t) => { t.ctx++ }) }

async function doLogout() {
  await logout()
  router.push('/login')
}

provide('navigate', navigate)
provide('openManual', openManual)
provide('openDrawing', openDrawing)
provide('openHull', openHull)
provide('refreshInquiry', refreshInquiry)
provide('setOverlay', (v) => { overlayOpen.value = !!v })

onMounted(async () => {
  try { await loadSession() } catch (e) { if (e.status !== 401) toastError(e); return }
  let raw = null
  try { raw = sessionStorage.getItem(TABS_KEY) } catch { raw = null }
  const allowed = session.menu.filter((m) => m.token).sort((a, b) => a.seq - b.seq).map((m) => m.token)
  Object.assign(tabs, restore(raw, allowed))
  if (!raw && tabs.tabs[0]) {
    const m = menuByToken(tabs.tabs[0].token)
    api.post('/me/menu-access', { menu_id: m.menu_id }).catch(() => {})
  }
})

defineExpose({ navigate, tabs, openManual, refreshInquiry })
</script>

<style scoped>
.shell { height: 100%; display: grid; grid-template-columns: 230px 1fr; grid-template-rows: 50px 1fr; }
.hd { grid-column: 1 / -1; background: var(--navy); color: #fff; display: flex; align-items: center; gap: 14px; padding: 0 16px; min-width: 0; }
.brand { font-size: 15px; font-weight: 700; white-space: nowrap; }
.brand small { font-size: 11px; opacity: .65; font-weight: 400; margin-left: 6px; }
.who { display: flex; flex-direction: column; align-items: flex-start; line-height: 1.25; white-space: nowrap; }
.who small { font-size: 11px; opacity: .85; }
.hbtn { height: 26px; background: transparent; color: #fff; border: 1px solid #3b5a8c; border-radius: 6px; font: inherit; padding: 0 10px; cursor: pointer; }
.hbtn:hover { background: rgba(255,255,255,.08); }
.menu { background: #fff; border-right: 1px solid var(--line); overflow: auto; padding: 10px 0; }
.menu-cap { font-size: 11px; letter-spacing: 1px; color: var(--muted); padding: 4px 14px 8px; }
.mi { display: flex; align-items: center; gap: 6px; padding: 7px 14px; margin: 1px 8px; border-radius: 7px; cursor: pointer; transition: background var(--t-fast) var(--ease); }
.mi:hover { background: #eef3fb; }
.mi.sub { padding-left: 26px; }
.mi.on { background: var(--sel); color: var(--pri-d); font-weight: 700; box-shadow: inset 3px 0 0 var(--pri); }
.mk { width: 12px; display: inline-block; text-align: center; font-size: 9px; flex: none; }
.main { display: flex; flex-direction: column; min-width: 0; min-height: 0; }
.tabbar { height: 36px; background: var(--tabs-bg); padding: 6px 8px 0; display: flex; gap: 2px; align-items: flex-end; flex: none; overflow: hidden; }
.tab { height: 30px; display: flex; align-items: center; gap: 6px; padding: 0 8px 0 12px; border-radius: 6px 6px 0 0; background: var(--tab-off); font-size: 12.5px; cursor: pointer; white-space: nowrap; transition: background var(--t-fast) var(--ease); }
.tab.on { background: #fff; color: var(--navy); font-weight: 700; }
.tx { width: 18px; height: 18px; border-radius: 50%; border: 0; background: transparent; cursor: pointer; font-size: 13px; line-height: 1; color: var(--muted); padding: 0; }
.tx:hover { background: var(--err); color: #fff; }
.tbtn { height: 24px; align-self: center; margin-bottom: 4px; background: #fff; border: 1px solid var(--line); border-radius: 5px; font: inherit; font-size: 12px; padding: 0 8px; cursor: pointer; }
.tbtn:hover { border-color: #c5cede; }
.work { flex: 1; min-height: 0; overflow: auto; padding: 14px 18px 24px; background: var(--bg); }
.screen { height: 100%; animation: fade-in var(--t-fast) var(--ease); }
@media (max-width: 720px) {
  .shell { grid-template-columns: 160px 1fr; }
  .brand small, .who small { display: none; }
}
</style>
