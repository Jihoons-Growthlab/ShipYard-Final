<template>
  <div class="dwg-list">
    <PageHead :title="title" :readonly="!canWrite" desc="행에 마우스를 올리면 정보·PDF 미리보기가 뜹니다. 행 더블클릭 또는 [상세]로 도면 상세·PDF 뷰어·리비전·결재 팝업을 엽니다. Rev는 현재 배포(유효) 리비전입니다." />
    <form class="toolbar" @submit.prevent="load">
      <select v-model="f.hull_no" class="inp w165" aria-label="호선">
        <option value="">호선 전체</option>
        <option v-for="h in hulls" :key="h.hull_no" :value="h.hull_no">{{ h.hull_no }} {{ h.hull_nm }}</option>
      </select>
      <select v-model="f.discipline" class="inp w110" aria-label="분야">
        <option value="">분야 전체</option>
        <option v-for="c in codeOptions('DWGDISC')" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <select v-model="f.status" class="inp w110" aria-label="상태">
        <option value="">상태 전체</option>
        <option v-for="c in statusOptions" :key="c.code" :value="c.code">{{ c.name }}</option>
      </select>
      <input v-model.trim="f.q" class="inp w148" placeholder="도면번호/도면명" aria-label="검색어" />
      <button class="btn pri" type="submit">조회</button>
      <button class="btn" type="button" @click="reset">초기화</button>
      <div class="grow"></div>
      <button v-if="canWrite" class="btn pri" type="button" @click="openDetail(null)">+ 도면 등록</button>
    </form>

    <div class="tw">
      <table class="t clk dwg-table">
        <thead><tr>
          <th>도면번호</th><th>도면명</th><th>호선</th><th>블록</th><th>분야</th><th>Rev</th><th>상태</th><th>설계자</th><th class="num">연계공정</th><th></th>
        </tr></thead>
        <tbody>
          <tr v-for="d in items" :key="d.drawing_id" :class="{ sel: selected === d.drawing_id }"
              @click="selected = d.drawing_id" @dblclick="openDetail(d.drawing_id)"
              @mouseenter="preview.enter(d.drawing_id, $event, d)" @mouseleave="preview.leave()">
            <td><b>{{ d.drawing_no }}</b></td><td>{{ d.drawing_nm }}</td><td>{{ d.hull_no }}</td><td>{{ dash(d.block_cd) }}</td>
            <td>{{ codeName('DWGDISC', d.discipline) }}</td>
            <td>Rev{{ d.current_rev_no }}<span v-if="d.latest_rev_no !== d.current_rev_no" class="muted"> (최신 Rev{{ d.latest_rev_no }})</span></td>
            <td><StatusBadge :value="d.dwg_status" kind="dwg" /></td>
            <td>{{ dash(d.designer_nm) }}</td>
            <td class="num">{{ d.link_count || '-' }}</td>
            <td><button class="btn sm" type="button" @click.stop="openDetail(d.drawing_id)">상세</button></td>
          </tr>
          <tr v-if="loaded && !items.length"><td colspan="10" class="empty">조회된 도면이 없습니다.</td></tr>
        </tbody>
      </table>
    </div>
    <div class="cnt">총 {{ items.length }}건</div>

    <HoverCard :preview="preview" :width="440" :height="470">
      <template #default="{ data, ctx: d, loading }">
        <div v-if="d" class="pv dpv" @click="openDetail(d.drawing_id)">
          <div class="pvh">{{ d.drawing_no }} <StatusBadge :value="d.dwg_status" kind="dwg" /></div>
          <div>{{ d.drawing_nm }}</div>
          <div class="pvm">{{ d.hull_no }} · {{ d.block_cd ? `${d.block_cd} ${data?.detail.block_nm || ''}`.trim() : '블록 없음' }} · {{ codeName('DWGDISC', d.discipline) }} · 설계 {{ dash(d.designer_nm) }}</div>
          <div class="pvpdf">
            <template v-if="data?.rev">
              <span class="pvtag">Rev{{ data.rev.rev_no }} · {{ dwgStatusName(data.rev.rev_status) }}</span>
              <iframe v-if="data.url && viewable" :src="data.url + '#toolbar=0&navpanes=0&view=FitH'" title="PDF 미리보기"></iframe>
              <div v-else-if="data.url" class="pvno">이 브라우저는 PDF를 화면에 표시하지 않도록 설정되어 있습니다. <a :href="data.url" target="_blank" rel="noopener" @click.stop>PDF 열기</a></div>
            </template>
            <span v-else-if="loading">불러오는 중…</span>
            <span v-else>첨부된 PDF가 없습니다.</span>
          </div>
          <table v-if="data" class="pvt">
            <thead><tr><th>Rev</th><th>상태</th><th>변경 내용</th><th>배포일</th></tr></thead>
            <tbody><tr v-for="r in data.detail.revisions.slice(0, 3)" :key="r.rev_no">
              <td>Rev{{ r.rev_no }}</td><td><StatusBadge :value="r.rev_status" kind="dwg" /></td>
              <td class="ell" :title="r.change_desc">{{ r.change_desc }}</td><td>{{ dash(r.issue_dt) }}</td>
            </tr></tbody>
          </table>
          <div class="pvf">연계 공정 {{ d.link_count }}건 · 클릭하면 상세를 엽니다.</div>
        </div>
      </template>
    </HoverCard>

    <DrawingModal v-if="detail.open" :drawing-id="detail.id" :can-write="canWrite" @close="closeDetail" @changed="onChanged" />
  </div>
</template>

<script setup>
import { reactive, ref, computed, watch, onMounted } from 'vue'
import { api } from '../api/client'
import { codeOptions, codeName } from '../stores/session'
import { useHoverPreview } from '../utils/hoverPreview'
import { dash, dwgStatusName } from '../utils/status'
import { pdfBlobUrl, revokeUrl, previewRev, pdfViewable } from '../utils/pdf'
import { toastError } from '../utils/toast'
import PageHead from '../components/PageHead.vue'
import HoverCard from '../components/HoverCard.vue'
import StatusBadge from '../components/StatusBadge.vue'
import DrawingModal from './DrawingModal.vue'

const props = defineProps({ title: String, canWrite: Boolean, param: null, ctx: Number, active: Boolean })

const EMPTY = { hull_no: '', discipline: '', status: '', q: '' }
const f = reactive({ ...EMPTY })
const hulls = ref([])
const items = ref([])
const loaded = ref(false)
const selected = ref(null)
const detail = reactive({ open: false, id: null })
const viewable = pdfViewable()
const statusOptions = computed(() => codeOptions('DWGSTAT').filter((c) => c.code !== 'OBSOLETE'))

const preview = useHoverPreview(async (id) => {
  const d = await api.get(`/drawings/${id}`)
  const rev = previewRev(d)
  let url = null
  if (rev) { try { url = await pdfBlobUrl(id, rev.rev_no) } catch { url = null } }
  return { detail: d, rev: url ? rev : null, url }
}, { onDispose: (v) => revokeUrl(v?.url) })

async function load() {
  try {
    items.value = await api.get('/drawings', { ...f })
    loaded.value = true
    preview.clear()
  } catch (e) { toastError(e) }
}
function reset() { Object.assign(f, EMPTY); load() }
function applyParam() { if (props.param) { Object.assign(f, EMPTY, { hull_no: String(props.param) }) } }
function openDetail(id) { if (id) selected.value = id; preview.hide(); detail.id = id; detail.open = true; preview.setDisabled(true) }
function closeDetail() { detail.open = false; preview.setDisabled(false) }
function onChanged(id) { if (id) selected.value = id; load() }

watch(() => props.ctx, () => { applyParam(); load() })
onMounted(async () => {
  applyParam()
  try { hulls.value = await api.get('/hulls') } catch (e) { toastError(e) }
  load()
})
</script>

<style scoped>
.w110 { width: 110px; } .w148 { width: 148px; } .w165 { width: 165px; }
.cnt { font-size: 12px; color: var(--muted); margin-top: 8px; }
.dpv { cursor: pointer; }
.dpv .pvpdf { position: relative; }
.pvtag { position: absolute; top: 6px; right: 8px; background: rgba(15,23,42,.75); color: #fff; font-size: 11px; padding: 1px 7px; border-radius: 4px; z-index: 1; }
.pvno { padding: 16px; text-align: center; }
.ell { max-width: 170px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
