# 인계
- 완료: P1~P5, P6(T29 Unity 뷰어·3D 탭·3D 조선소, T30 최종 수용 검증)
- 검증: backend 100 passed, frontend 68 passed, build 통과, unity 빌드 통과(Unity 6000.5.10f1, 출력 약 15MB).
- shots 전체 52개: 39 통과, 12 기준 초과(사유 기록 후 수용), 1 오류(drawing-detail-draft, 미해결). --mutating 8개 통과(기본 DB 변경 없음). P6 화면을 직접 봄: 단일 렌더·네 시점·reset 일치·호버 카드(단일·fleet)·fleet 클릭 → 상세·탭 왕복·Esc.
- `.wasm`은 Vite dev(5273)와 preview 모두 application/wasm(curl로 확인).

## 결정 (SOURCEMAP에 없는 것)
- P1~P5 결정 유지(BR-10 단일 함수, sessionStorage `swp_token`·`swp_tabs`, localStorage `swp_region`, 셸 provide openHull/refreshInquiry/openDrawing).
- Unity: manifest에 명세 목록 + `com.unity.modules.physics`(MeshCollider·BoxCollider·Raycast 호버에 필요). 씬·재질은 ViewerBuild가 매번 재생성(Assets/Scenes, Assets/Materials).
  SetView/SetFleet는 [Preserve](관리 코드 스트리핑 High). 반폭 0 정점은 선수 윤곽점(zs=27)으로 모아 선수 계단 결함 제거.
- 수명주기 utils/unityViewer.js(startViewer → {ready, stop, send}; 새 시작은 이전 stop 완료까지 대기, 로딩 중 닫힘은 늦게 온 인스턴스 Quit).
  컴포넌트 components/ShipViewer3D.vue(hullNo=단일, fleet=배열). `.vwrap[data-state=loading|ready|error]`로 shots가 준비를 기다린다.
- 호선 상세: 3D 탭이면 AppModal xl, 3D에서 직전 데이터 탭 복귀는 재조회 없음. 목록: active && 상세 닫힘일 때만 fleet 뷰어, 6척/페이지.
- shots: admin 흐름은 탭이 남으므로 메뉴 클릭 뒤 `다른 탭 닫기`. 챗봇 인사 말풍선이 왼쪽 아래 버튼을 가리므로 그 버튼은 `press Enter`.

## 미해결
- shots drawing-detail-draft: `.dwg-table tbody tr:first-child .btn` 클릭 시간 초과(탭 정리 후에도). 반복 2회 소진으로 원인 미확인 — 같은 단계를 press Enter로 바꿔 보거나 error.png를 확인할 것. P4 기능 테스트는 통과.
- 정당한 차이로 수용: ship-side/front/top 기준 이미지는 배경 없는 모델 단독(명세 F10은 단일 조선소 배경을 요구)·크기 1~2px 차이,
  hull-hover/readonly-hull-list 기준은 3D 조선소 추가 전 화면, drawing-detail은 데모 PDF 적재 여부, hull-3d/hull-yard는 시드 지연 건수·트롤리 움직임.
- 브라우저 창 크기 변경 추종(T07)은 Unity 코드(화면 비율 변경 시 현재 시점 재맞춤)만 있고 shots로는 확인하지 않음.
- 1.5B 모델의 용어 설명 정확도는 명세상 한계.
