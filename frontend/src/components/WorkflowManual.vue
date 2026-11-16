<template>
  <AppModal title="조선소 업무 매뉴얼" size="xl" @close="emit('close')">
    <div class="manual">
      <p class="mdesc">업무 단계를 선택하면 실제 화면과 사용 순서를 볼 수 있습니다.</p>
      <div class="steps">
        <button v-for="s in steps" :key="s.id" type="button" class="btn" :class="{ pri: s.id === cur.id }"
                :aria-pressed="s.id === cur.id" @click="currentId = s.id">{{ s.title }}</button>
      </div>
      <div class="mhd">
        <h3 class="mt">{{ cur.title }}</h3>
        <button v-if="cur.token" type="button" class="btn" @click="openScreen">업무 화면 열기</button>
      </div>
      <ol class="mlist"><li v-for="(d, i) in cur.desc" :key="i">{{ d }}</li></ol>
      <figure class="shot">
        <img :src="photo(cur.id)" :alt="`${cur.title} 화면 예시`" />
        <figcaption>화면 예시 · 계정 권한과 등록 데이터에 따라 다르게 표시될 수 있습니다.</figcaption>
      </figure>
    </div>
  </AppModal>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import AppModal from './AppModal.vue'
import { menuByToken } from '../stores/session'
import { MANUAL_STEPS, visibleSteps, startStep } from '../utils/manual'

const props = defineProps({ section: { type: String, default: '' } })
const emit = defineEmits(['close'])
const navigate = inject('navigate', async () => false)

const PHOTOS = import.meta.glob('../assets/manual/*.jpg', { eager: true, import: 'default' })
const photo = (id) => PHOTOS[`../assets/manual/${id}.jpg`]

const steps = computed(() => visibleSteps(MANUAL_STEPS, (t) => !!menuByToken(t)))
const currentId = ref(startStep(steps.value, props.section))
const cur = computed(() => steps.value.find((s) => s.id === currentId.value) || steps.value[0])

async function openScreen() {
  if (await navigate(cur.value.token)) emit('close')
}
</script>

<style scoped>
.manual { display: flex; flex-direction: column; gap: 0; }
.mdesc { margin: 0 0 12px; color: #4b5563; font-size: 12.5px; }
.steps { display: flex; flex-wrap: wrap; gap: 8px; padding-bottom: 16px; border-bottom: 1px solid var(--line); }
.steps .btn { height: 30px; padding: 0 13px; }
.mhd { display: flex; align-items: center; justify-content: space-between; margin: 14px 0 8px; }
.mt { font-size: 17px; }
.mlist { margin: 6px 0 14px; padding-left: 26px; line-height: 1.75; font-size: 12.5px; }
.shot { margin: 0; }
.shot img { width: 100%; display: block; border: 1px solid var(--line); border-radius: 8px; }
.shot figcaption { margin-top: 6px; font-size: 11.5px; color: var(--muted); }
</style>
