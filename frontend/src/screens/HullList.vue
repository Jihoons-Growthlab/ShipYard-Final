<template>
  <div class="hull-list">
    <PageHead :title="title" :readonly="!canWrite" desc="행에 마우스를 올리면 미리보기가 뜨고, 더블클릭하거나 [상세]를 누르면 호선 상세 팝업이 열립니다." />
    <form class="toolbar" @submit.prevent="load">
      <select v-model="f.status" class="inp w110" aria-label="상태">
        <option value="">상태 전체</option>
        <option v-for="c in codeOptions('HULLSTAT')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <select v-model="f.ship_type" class="inp w110" aria-label="선종">
        <option value="">선종 전체</option>
        <option v-for="c in codeOptions('SHIPTYPE')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <input v-model.trim="f.q" class="inp w150" placeholder="호선번호/호선명/선주" aria-label="검색어" />
      <button class="btn pri" type="submit">조회</button>
      <button class="btn" type="button" @click="reset">초기화</button>
      <div class="grow"></div>
      <button v-if="canWrite" class="btn pri" type="button" @click="openDetail(null)">+ 호선 등록</button>
    </form>

    <div class="tw">
      <table class="t clk hull-table">
        <thead><tr>
          <th>호선번호</th><th>호선명</th><th>선종</th><th>상태</th><th>선주</th><th>선급</th><th>도크</th>
          <th>계약일</th><th>인도예정</th><th class="wbar">진척률</th><th class="num">지연</th><th></th>
        </tr></thead>
        <tbody>
          <tr v-for="h in hulls" :key="h.hull_no" :class="{ sel: selected === h.hull_no }"
              @click="selected = h.hull_no" @dblclick="openDetail(h.hull_no)"
              @mouseenter="preview.enter(h.hull_no, $event, h)" @mouseleave="preview.leave()">
            <td><b>{{ h.hull_no }}</b></td><td>{{ h.hull_nm }}</td><td>{{ codeName('SHIPTYPE', h.ship_type) }}</td>
            <td><span class="b b-info">{{ codeName('HULLSTAT', h.hull_status) }}</span></td>
            <td>{{ h.owner_nm }}</td><td>{{ h.class_society }}</td><td>{{ dash(h.dock_no) }}</td>
            <td>{{ h.contract_dt }}</td><td>{{ h.delivery_dt }}</td>
            <td><ProgressBar v-if="h.progress !== null" :value="h.progress" /><span v-else class="muted">계획 없음</span></td>
            <td class="num">{{ h.delay_count ? h.delay_count : '-' }}</td>
            <td><button class="btn sm" type="button" @click.stop="openDetail(h.hull_no)">상세</button></td>
          </tr>
          <tr v-if="loaded && !hulls.length"><td colspan="12" class="empty">조회된 호선이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="cnt">총 {{ hulls.length }}척</div>

    <section class="yard">
      <div class="yard-h">
        <div>
          <h2>3D 조선소</h2>
          <div class="muted yard-d">선체에 마우스를 올리면 요약, 클릭하면 상세를 볼 수 있습니다. 배치는 시뮬레이션입니다.</div>
        </div>
        <div v-if="pages > 1" class="yard-pg">
          <button class="btn sm" type="button" :disabled="page === 0" @click="page--">이전</button>
          <span>{{ page + 1 }} / {{ pages }}</span>
          <button class="btn sm" type="button" :disabled="page >= pages - 1" @click="page++">다음</button>
        </div>
      </div>
      <ShipViewer3D v-if="active && !detail.open" :fleet="fleet" @select="openDetail" />
      <div v-else class="yard-off"></div>
    </section>

    <HoverCard :preview="preview" :width="380" :height="340">
      <template #default="{ data, ctx: h, loading }">
        <div v-if="h" class="pv">
          <div class="pvh">{{ h.hull_no }} {{ h.hull_nm }} <span class="b b-info">{{ codeName('HULLSTAT', h.hull_status) }}</span></div>
          <div class="pvm">{{ codeName('SHIPTYPE', h.ship_type) }} · {{ dash(h.owner_nm) }} · {{ dash(h.class_society) }} · 도크 {{ dash(h.dock_no) }}</div>
          <div class="pvr">
            <span class="k">진척</span><span><ProgressBar v-if="h.progress !== null" :value="h.progress" /><span v-else class="muted">계획 없음</span></span>
            <span class="k">계약 / 인도</span><span>{{ dash(h.contract_dt) }} → {{ dash(h.delivery_dt) }}</span>
            <template v-if="data">
              <span class="k">공정 {{ data.summary.plan_count }}건</span><StatusChips :counts="data.summary.plan_status" />
              <span class="k">도면 {{ data.summary.drawing_count }}건</span><StatusChips :counts="data.summary.drawing_status" kind="dwg" :dots="false" />
            </template>
          </div>
          <div v-if="loading" class="pvm">불러오는 중…</div>
          <table v-if="data" class="pvt">
            <thead><tr><th>주요 일정</th><th>계획</th><th>실적</th></tr></thead>
            <tbody><tr v-for="m in data.milestones" :key="m.milestone_cd"><td>{{ m.name }}</td><td>{{ dash(m.plan_dt) }}</td><td>{{ dash(m.actual_dt) }}</td></tr></tbody>
          </table>
          <div class="pvf">더블클릭하면 상세를 엽니다.</div>
        </div>
      </template>
    </HoverCard>

    <HullDetailModal v-if="detail.open" :hull-no="detail.hullNo" :can-write="canWrite" @close="closeDetail" @changed="onChanged" />
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { api } from '../api/client'
import { codeOptions, codeName } from '../stores/session'
import { useHoverPreview } from '../utils/hoverPreview'
import { dash } from '../utils/status'
import { toastError } from '../utils/toast'
import PageHead from '../components/PageHead.vue'
import ProgressBar from '../components/ProgressBar.vue'
import HoverCard from '../components/HoverCard.vue'
import StatusChips from '../components/StatusChips.vue'
import HullDetailModal from './HullDetailModal.vue'
import ShipViewer3D from '../components/ShipViewer3D.vue'

defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })

const f = reactive({ status: '', ship_type: '', q: '' })
const hulls = ref([])
const loaded = ref(false)
const selected = ref(null)
const detail = reactive({ open: false, hullNo: null })
const FLEET_SIZE = 6
const page = ref(0)
const pages = computed(() => Math.max(1, Math.ceil(hulls.value.length / FLEET_SIZE)))
const fleet = computed(() => hulls.value.slice(page.value * FLEET_SIZE, (page.value + 1) * FLEET_SIZE))

const preview = useHoverPreview(async (no) => {
  const [summary, milestones] = await Promise.all([api.get(`/hulls/${no}/summary`), api.get(`/hulls/${no}/milestones`)])
  return { summary, milestones }
})

async function load() {
  try {
    hulls.value = await api.get('/hulls', { ...f })
    loaded.value = true
    page.value = Math.min(page.value, pages.value - 1)
    preview.clear()
  } catch (e) { toastError(e) }
}
function reset() { Object.assign(f, { status: '', ship_type: '', q: '' }); load() }
function openDetail(no) { if (no) selected.value = no; detail.hullNo = no; detail.open = true; preview.setDisabled(true) }
function closeDetail() { detail.open = false; preview.setDisabled(false) }
function onChanged(no) { if (no) selected.value = no; load() }

onMounted(load)
</script>

<style scoped>
.w110 { width: 110px; } .w150 { width: 148px; }
.wbar { width: 150px; }
.cnt { font-size: 12px; color: var(--muted); margin-top: 8px; }
.yard { margin-top: 22px; }
.yard-h { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.yard-h h2 { margin: 0; font-size: 17px; }
.yard-d { font-size: 12.5px; margin-top: 2px; }
.yard-pg { display: flex; align-items: center; gap: 8px; font-size: 12.5px; }
.yard-off { height: clamp(260px, 32vw, 410px); border: 1px solid var(--card-line); border-radius: 8px; background: #dde4ee; }
@media (max-width: 760px) { .yard-off { height: clamp(210px, 50vw, 320px); } }
</style>
