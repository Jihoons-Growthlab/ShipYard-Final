<template>
  <div class="rcard">
    <template v-if="!result">
      <div class="rlbl">범위</div>
      <div class="pills">
        <button type="button" class="pill" :class="{ on: hullNo === '' }" :aria-pressed="hullNo === ''" @click="hullNo = ''">전체 호선</button>
        <button v-for="h in opts.hulls" :key="h.hull_no" type="button" class="pill" :class="{ on: hullNo === h.hull_no }"
                :aria-pressed="hullNo === h.hull_no" :title="h.hull_nm" @click="hullNo = h.hull_no">{{ h.hull_no }}</button>
      </div>
      <div class="rlbl">형식</div>
      <div class="fmts">
        <button type="button" class="fmt" :class="{ on: format === 'pdf' }" :aria-pressed="format === 'pdf'" @click="format = 'pdf'">
          <span class="ico pdf">PDF</span><span>문서로 보기·인쇄</span>
        </button>
        <button type="button" class="fmt" :class="{ on: format === 'xlsx' }" :aria-pressed="format === 'xlsx'" @click="format = 'xlsx'">
          <span class="ico xls">XLS</span><span>Excel로 편집</span>
        </button>
      </div>
      <button type="button" class="go" :disabled="busy" @click="build">{{ busy ? '보고서를 만드는 중…' : '보고서 작성하기' }}</button>
    </template>
    <template v-else>
      <div class="res">
        <span class="ico big" :class="result.format === 'pdf' ? 'pdf' : 'xls'">{{ result.format === 'pdf' ? 'PDF' : 'XLS' }}</span>
        <div class="rinfo">
          <b class="rt">{{ result.title }}</b>
          <div class="rs">{{ result.filename }} · {{ sizeText(result.size) }}</div>
          <div class="rs">{{ summaryText }}</div>
        </div>
      </div>
      <div class="racts">
        <button type="button" class="dl" :disabled="busy" @click="download">다운로드</button>
        <button type="button" class="again" @click="result = null">다른 보고서</button>
      </div>
    </template>
    <div v-if="error" class="rerr" role="alert">{{ error }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api, request } from '../api/client'
import { sizeText } from '../utils/chat'

const opts = reactive({ hulls: [], formats: [] })
const hullNo = ref('')
const format = ref('pdf')
const busy = ref(false)
const error = ref('')
const result = ref(null)

const dash = (v) => (v === null || v === undefined ? '-' : v)
const summaryText = computed(() => {
  const s = result.value?.summary || {}
  return `호선 ${dash(s.hulls)} · 공정 ${dash(s.plans)} · 지연 ${dash(s.delay)} · 도면 ${dash(s.drawings)}`
})

async function build() {
  busy.value = true; error.value = ''
  try {
    result.value = await api.post('/chat/report', { format: format.value, ...(hullNo.value ? { hull_no: hullNo.value } : {}) })
  } catch (e) { error.value = e.message } finally { busy.value = false }
}

async function download() {
  busy.value = true; error.value = ''
  try {
    const res = await request('GET', result.value.download_url, { raw: true })
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement('a')
    a.href = url; a.download = result.value.filename
    document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (e) { error.value = e.message } finally { busy.value = false }
}

onMounted(async () => {
  try { Object.assign(opts, await api.get('/chat/report/options')) } catch (e) { error.value = e.message }
})
</script>

<style scoped>
.rcard { border: 1px solid #a8d6e0; background: #f5fbfd; border-radius: 8px; padding: 10px; display: flex; flex-direction: column; gap: 7px; }
.rlbl { font-size: 11px; font-weight: 700; color: #3c5566; }
.pills { display: flex; flex-wrap: wrap; gap: 5px; }
.pill { height: 26px; padding: 0 10px; border-radius: 13px; border: 1px solid #a8d6e0; background: #fff; font: inherit; font-size: 12px; cursor: pointer; color: #1d3f55; }
.pill.on { background: #1f5878; border-color: #1f5878; color: #fff; font-weight: 700; }
.fmts { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.fmt { display: flex; align-items: center; gap: 7px; padding: 7px; border: 1px solid #c9dfe6; border-radius: 7px; background: #fff; font: inherit; font-size: 11.5px; cursor: pointer; text-align: left; }
.fmt.on { border-color: #1f5878; box-shadow: inset 0 0 0 1px #1f5878; background: #eef8fb; }
.ico { flex: none; width: 30px; height: 30px; border-radius: 5px; color: #fff; font-size: 10px; font-weight: 800; display: inline-flex; align-items: center; justify-content: center; }
.ico.big { width: 38px; height: 46px; font-size: 11px; }
.ico.pdf { background: #dc2626; }
.ico.xls { background: #16a34a; }
.go, .dl { height: 32px; border: 0; border-radius: 7px; background: #1f5878; color: #fff; font: inherit; font-weight: 700; cursor: pointer; }
.go:disabled, .dl:disabled { opacity: .6; cursor: default; }
.res { display: flex; gap: 10px; align-items: center; }
.rinfo { min-width: 0; }
.rt { font-size: 13px; display: block; }
.rs { font-size: 10.5px; color: #475569; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.racts { display: flex; gap: 6px; }
.dl { flex: 1; }
.again { height: 32px; padding: 0 10px; border: 1px solid #a8b8c4; border-radius: 7px; background: #fff; font: inherit; font-size: 12px; cursor: pointer; }
.rerr { background: #fef2f2; border: 1px solid #fca5a5; color: #b91c1c; border-radius: 6px; padding: 6px 8px; font-size: 12px; }
</style>
