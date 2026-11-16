// 결재 결과·단계 표시(F07·F08 공통).
export const RESULT = { WAIT: { name: '대기', cls: 'b-warn' }, APPROVE: { name: '승인', cls: 'b-ok' }, REJECT: { name: '반려', cls: 'b-bad' } }
export const stepName = (s) => (s === 1 ? '검토' : '승인')
