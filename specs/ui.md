# 디자인 시스템

조밀한 업무용 화면이다. 값은 완성본 기준이며, 공통 스타일은 전역 CSS 한 파일에 두고 화면 전용 배치만 scoped로 둔다. 비교 기준 해상도는 1440x900이다.

## 토큰

| 토큰 | 값 | 토큰 | 값 |
| --- | --- | --- | --- |
| navy / navy2 | #12294a / #1b3a66 | pri / pri-d | #2563eb / #1d4ed8 |
| bg / panel | #f2f4f8 / #fff | line / line2 | #d9dee8 / #edf0f5 |
| ink / muted | #1f2937 / #6b7280 | err / ok / warn | #dc2626 / #16a34a / #d97706 |
| sel / hover / head | #dbeafe / #f4f8ff / #eef1f6 | tabs bg / tab off | #e4e8f0 / #cfd6e4 |

본문 13px, 글꼴 `'Malgun Gothic','Apple SD Gothic Neo','Noto Sans KR',system-ui,sans-serif`, line-height는 지정하지 않는다(normal). h2 16px, 카드 h3 13.5px.

## 셸

- 헤더 50px, navy, 좌우 16px, 항목 간격 14px. 브랜드 `⚓ SWP 조선소 통합관리` 15px 700, 뒤에 `호선 / 공정 / 도면` 11px opacity .65. 오른쪽에 날씨 알약, 사용자(이름 700·`그룹 · 기준일` 11px, 왼쪽 정렬), 로그아웃. 헤더 버튼 높이 26px, 테두리 #3b5a8c.
- 날씨 알약: navy2, radius 18px, padding 4px 12px, 12px, 간격 8px, 온도 14px bold. 샘플 배지 #f59e0b/#3b2600, LIVE 배지 #22c55e/#052e16.
- 메뉴 230px, 흰 배경, 오른쪽 테두리. `MENU` 11px letter-spacing 1px. 항목 padding 7px 14px, 간격 6px, 앞에 12px 폭 표식(그룹 ▼/▶ 9px, 말단 `·`). 항목은 좌우 margin 8px·radius 7px, 하위 항목 padding-left 26px. 선택은 sel 배경 + pri-d 700 + 안쪽 왼쪽 3px pri 선, 호버 #eef3fb.
- 탭바 높이 36px, 배경 tabs bg, padding 6px 8px 0, 간격 2px. 탭 30px, radius 6px 6px 0 0, 12.5px, 비활성 tab off, 활성 흰색 + navy 700. × 버튼은 18px 원형, 호버 시 err. 오른쪽 끝에 `매뉴얼`(항상, F15)과 `다른 탭 닫기`(탭 2개 이상).
- 작업 영역 padding 14px 18px 24px, bg 배경, 스크롤은 이 영역만.

## 요소

- 제목줄 `.ph`: h2 + 12px muted 설명을 baseline 정렬, 아래 12px. 조회 전용이면 `조회 전용` 배지(#fef3c7/#92400e, 11px).
- 버튼 30px, padding 0 13px, radius 6px, 흰 배경 + line 테두리 + 그림자 sm. 호버 테두리 #c5cede, 누르면 1px 내려감, focus-visible 링. 주 버튼 pri 세로 그라데이션(#3b74f0→pri), 호버 pri-d + 파란 그림자. 성공 ok, 위험은 err 글자 + #fecaca 테두리(호버 #fef2f2), 작은 버튼 24px·12px. disabled opacity .45.
- 입력 30px, padding 4px 8px, radius 5px, line 테두리. radius 6px, 호버 테두리 #c5cede, 포커스 pri 테두리 + 링(box-shadow 0 0 0 3px rgba(37,99,235,.18)). 체크·라디오 accent-color pri. readonly/disabled 배경 #f3f4f6, muted 글자. 라벨은 위쪽 12px muted, 간격 3px.
- 폼 그리드: gap 10px 12px, align-items end, 2·4·6열.
- 카드: 흰 배경, #e2e7ef 테두리, radius 10px, 그림자 sm, padding 12px 14px, 아래 12px. h3은 제목과 배지를 양 끝 정렬.
- 표: 전체 폭, 테두리 + radius 6px. th는 head 배경 7px 9px, 600, sticky. td 6px 9px, 아래 line2, nowrap(긴 글은 wrap). 호버 hover(배경 전환), 선택 sel + 첫 칸 안쪽 왼쪽 3px pri 선. th 글자 #374151. 숫자 오른쪽 정렬.
- 표 래퍼 `.tw`: 스크롤 + #e2e7ef 테두리, radius 8px, 그림자 sm. 고정형 `r3`는 높이 140px.
- 배지: 11.5px 600, radius 10px, padding 1px 8px.

| 의미 | 배경/글자 |
| --- | --- |
| 공정 PLAN / READY / WORK / DONE / DELAY | #e2e8f0/#475569, #e0f2fe/#0369a1, #dbeafe/#1d4ed8, #dcfce7/#15803d, #fee2e2/#b91c1c |
| 도면 DRAFT / REVIEW / APPROVED / ISSUED | #e2e8f0/#475569, #fef3c7/#92400e, #e0f2fe/#0369a1, #dcfce7/#15803d |
| 도면 OBSOLETE | #f3f4f6/#9ca3af, 취소선 |
| warn / bad / ok / info | #fef3c7/#92400e, #fee2e2/#b91c1c, #dcfce7/#15803d, #dbeafe/#1d4ed8 |

- 진척 바: 높이 16px, radius 8px, 트랙 #e8ecf2(안쪽 그림자), 채움 가로 그라데이션 #60a5fa→pri(둥근 끝, 로드 시 grow-x), 가운데 10.5px 700 `N%`(흰 글자 그림자), min-width 90px. 공통 컴포넌트 하나로 쓴다.
- 안내 박스: warn #fffbeb/#fde68a/#92400e, ok #f0fdf4/#bbf7d0/#166534, 12.5px.
- 토스트: 오른쪽 아래 20px, radius 8px, 왼쪽 4px 반투명 흰 선, 큰 그림자. 기본 #111827, 오류 #b91c1c, 성공 #15803d. TransitionGroup: 오른쪽에서 밀려 들어오고 아래로 사라짐.

## 모달

- 배경 rgba(15,23,42,.55) + blur 2px(fade-in), 패널 bg 배경, radius 12px, 큰 그림자, pop-in, max-height 94vh.
- 헤더 navy, padding 10px 16px, 제목 14px, 오른쪽 `닫기 ✕` 버튼.
- 크기: 기본 760px, large 1100px(96vw 이내), xl `min(1640px,97vw)`·높이 94vh. 본문 padding 14px 18px 20px, 내부 스크롤.
- 닫기: 버튼, 배경 클릭, Esc. 하나의 공통 컴포넌트로 만든다.
- 서브탭: 아래 2px line, 활성은 흰 배경 + pri 700.

## 반응형

720px 이하에서 메뉴 160px, 폼은 2열, 헤더 부가 문구 숨김. 그 외 화면별 규칙은 해당 명세를 따른다.

## 모션·깊이 (전역 토큰)

`--ease: cubic-bezier(.2,.8,.2,1)`, `--t-fast .15s`, `--t-med .28s`, `--t-slow .7s`, `--shadow-sm 0 1px 2px rgba(15,23,42,.06)`, `--shadow-md 0 4px 14px rgba(15,23,42,.08)`, `--shadow-lg 0 18px 50px rgba(15,23,42,.22)`, `--ring 0 0 0 3px rgba(37,99,235,.18)`.
키프레임: grow-x(scaleX 0→1, 왼쪽 기준), grow-y(아래 기준), fade-in, pop-in(10px 아래·.98→제자리), rise-in(6px 아래→제자리). `prefers-reduced-motion: reduce`면 모든 animation·transition을 1ms로.

## 마우스오버 카드 (공통)

`components/HoverCard.vue` + `utils/hoverPreview.js`(useHoverPreview(loader,{onDispose,ttl})) 하나로 모든 목록 미리보기를 만든다(호선·간트·실적·도면).
- 행에 280ms 머물면 열고, 행·카드 밖으로 나가면 160ms 뒤 닫는다. 카드에 들어가면 닫지 않는다. 같은 키 재진입은 무시.
- 결과는 키별 캐시, 30초가 지나면 다시 불러온다. 목록 재조회 시 비운다(onDispose로 blob URL 해제). 늦은 응답은 현재 키가 아니면 버린다. 언마운트 시 타이머·캐시 정리.
- 카드: body에 Teleport, fixed, z-index 900, 흰 배경, radius 10, 그림자, padding 12px 14px, 12.5px, max-height 70vh 스크롤, rise-in. 행 아래 4px에 놓고 아래 공간(지정 높이)이 모자라면 행 위로. 왼쪽 = 마우스 x-40, 화면 안으로 제한.
- 내용 공통 클래스(전역 CSS): `.pv`(세로 6px 간격), `.pvh`(제목 줄 13.5px), `.pvm`(muted), `.pvr`(78px 라벨 + 값 격자), `.chips/.chip`, `.pvt`(작은 표 12px), `.pvpdf`(높이 260px 회색 상자, iframe pointer-events none), `.pvf`(11.5px 안내).
