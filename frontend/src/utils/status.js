// 공정·도면 상태 순서·색(F03)·이름(코드 테이블).
import { codeName } from '../stores/session'

export const PLAN_STATUSES = ['PLAN', 'READY', 'WORK', 'DONE', 'DELAY']
export const DWG_STATUSES = ['ISSUED', 'APPROVED', 'REVIEW', 'DRAFT']
export const STATUS_COLORS = {
  PLAN: '#94a3b8', READY: '#0ea5e9', WORK: '#2563eb', DONE: '#16a34a', DELAY: '#dc2626',
  ISSUED: '#16a34a', APPROVED: '#0ea5e9', REVIEW: '#f59e0b', DRAFT: '#94a3b8',
}
export const planStatusName = (c) => codeName('PLANSTAT', c)
export const dwgStatusName = (c) => codeName('DWGSTAT', c)
export const dash = (v) => (v === null || v === undefined || v === '' ? '-' : v)
export const fmtNum = (v) => (v === null || v === undefined || v === '' ? '-' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: 2 }))
