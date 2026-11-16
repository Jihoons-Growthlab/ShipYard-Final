// 도면 PDF: 클라이언트 검사·업로드·인증 blob 조회(F07).
import { request } from '../api/client'

export const MAX_PDF = 30 * 1024 * 1024
export const PDF_TYPE_MSG = 'PDF 파일만 업로드할 수 있습니다.'
export const PDF_SIZE_MSG = '파일 크기는 30MB 이하여야 합니다.'

async function headOf(file) {
  const blob = file.slice(0, 5)
  const buf = await new Promise((resolve, reject) => {
    const r = new FileReader()
    r.onload = () => resolve(r.result)
    r.onerror = () => reject(r.error)
    r.readAsArrayBuffer(blob)
  })
  return new Uint8Array(buf)
}

/** 오류 문구 또는 null */
export async function checkPdf(file) {
  if (!file) return null
  const okName = /\.pdf$/i.test(file.name || '') || file.type === 'application/pdf'
  if (!okName) return PDF_TYPE_MSG
  if (file.size > MAX_PDF) return PDF_SIZE_MSG
  const h = await headOf(file)
  if (String.fromCharCode(...h) !== '%PDF-') return PDF_TYPE_MSG
  return null
}

export const pdfPath = (id, rev) => `/drawings/${id}/revisions/${rev}/pdf`

export function uploadPdf(id, rev, file) {
  const blob = file.type ? file : new Blob([file], { type: 'application/pdf' })
  return request('POST', pdfPath(id, rev), { body: blob, query: { filename: file.name } })
}

export async function pdfBlobUrl(id, rev) {
  const res = await request('GET', pdfPath(id, rev), { raw: true })
  const blob = await res.blob()
  return URL.createObjectURL ? URL.createObjectURL(blob) : null
}

export function revokeUrl(u) { if (u && URL.revokeObjectURL) URL.revokeObjectURL(u) }

/** 브라우저 PDF 표시가 꺼져 있으면 false */
export const pdfViewable = () => typeof navigator === 'undefined' || navigator.pdfViewerEnabled !== false

/** 미리볼 리비전: 현재 리비전이 파일 있으면 그것, 아니면 파일 있는 최신 */
export function previewRev(d) {
  const cur = d.revisions.find((r) => r.rev_no === d.current_rev_no)
  if (cur?.has_file) return cur
  return d.revisions.find((r) => r.has_file) || null
}
