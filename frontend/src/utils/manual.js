// 업무 매뉴얼(F15) 단계 정의. id = 사진 파일명 = 메뉴 token(챗봇 단계만 token 없음).
export const MANUAL_STEPS = [
  { id: 'dashboard', token: 'dashboard', title: '대시보드', desc: [
    '호선·공정·도면 지표에서 전체 현황과 지연 항목을 확인합니다.',
    '호선별 진척률을 클릭해 해당 호선의 공정계획을 엽니다.',
    '호선 확인 → 공정계획 → 공정 실적 순서로 진행합니다. 도면은 작성 → 결재 → 배포 순서로 처리합니다.'] },
  { id: 'hull-list', token: 'hull-list', title: '호선·3D 조선소', desc: [
    '호선 목록에서 번호·이름으로 검색하거나 상태로 범위를 좁힙니다.',
    '표의 상세 버튼을 누르면 기본정보, 주요일정, 블록 구성과 연계 현황을 확인할 수 있습니다.',
    '목록 아래 3D 야드에서 선체에 마우스를 올리면 요약이 표시됩니다. 선체를 누르면 상세가 열리고 휠로 확대·축소할 수 있습니다.'] },
  { id: 'plan-gantt', token: 'plan-gantt', title: '공정계획', desc: [
    '호선을 선택하고 간트 차트에서 공정의 기간, 순서, 지연을 확인합니다.',
    '공정에 마우스를 올려 요약을 보고, 편집 권한이 있으면 막대를 드래그하거나 상세에서 일정을 조정합니다.'] },
  { id: 'progress', token: 'progress', title: '공정 실적', desc: [
    '호선과 공정을 선택합니다. 완료 공정도 보려면 완료 공정 포함을 선택합니다.',
    '공정에 마우스를 올려 최근 실적을 확인하고, 클릭해 전체 이력을 봅니다.',
    '입력 권한이 있으면 작업일, 누적 진척률, 공수와 인원을 입력하고 실적 저장을 누릅니다.'] },
  { id: 'dwg-list', token: 'dwg-list', title: '도면 관리', desc: [
    '호선·분야·상태를 선택하거나 도면 번호와 이름으로 검색합니다.',
    '도면 상세에서 리비전과 PDF를 확인합니다. 권한이 있으면 새 리비전을 작성하고 결재를 요청합니다.'] },
  { id: 'dwg-approval', token: 'dwg-approval', title: '도면 결재', desc: [
    '결재 목록에서 도면과 리비전을 선택해 검토합니다.',
    '할당된 역할에 따라 승인 또는 반려를 처리합니다. 승인된 도면은 권한이 있는 사용자가 배포합니다.'] },
  { id: 'inquiry', token: 'inquiry', title: '건의·문의', desc: [
    '건의·문의 화면이나 챗봇의 건의하기·문의하기 버튼으로 내용을 접수합니다.',
    '목록에서 접수 상태와 답변을 확인합니다. 관리자는 상태와 답변을 처리할 수 있습니다.'] },
  { id: 'user-mgmt', token: 'user-mgmt', title: '회원 관리', desc: [
    '회원 목록에서 계정과 승인 상태를 확인합니다.',
    '관리 권한이 있으면 그룹과 메뉴별 권한을 조정하고 저장합니다.'] },
  { id: 'usage-log', token: 'usage-log', title: '사용 로그', desc: [
    '조회 기간과 사용자를 선택해 화면별 이용 내역을 확인합니다.'] },
  { id: 'chat', token: null, title: '챗봇', desc: [
    '왼쪽 아래 배 캐릭터를 누르고 호선 정보, 도면 정보, 공정 실적 중 하나를 선택합니다.',
    '결과 카드에서 보고 싶은 항목을 고릅니다. 건의·문의 접수와 매뉴얼 열기도 할 수 있습니다.'] },
]

/** 권한 없는 메뉴의 단계는 숨긴다(token 없는 챗봇 단계는 항상). */
export function visibleSteps(steps, hasMenu) { return steps.filter((s) => !s.token || hasMenu(s.token)) }

/** 요청 섹션이 보이면 그 단계, 아니면 첫 단계. */
export function startStep(steps, section) { return (steps.find((s) => s.id === section) || steps[0])?.id }
