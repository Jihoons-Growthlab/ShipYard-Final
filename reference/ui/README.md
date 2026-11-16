# UI 기준 자료

뷰포트 1440x900(login-mobile 390x844), `ship-*`는 canvas 영역만. 화면 값은 예시이며 하드코딩하지 않는다.

- 2026-11-04 원본 캡처(시드 직후): login, login-error, login-mobile, signup, otp, hull-new, hull-info, hull-milestones, hull-blocks, hull-summary, readonly-hull-list(choi.qa), plan-selected(8001 [201] 탑재), plan-new, plan-drawing-wait(8003 [101]), drawing-new, drawing-detail(8001-PIPE-501), drawing-detail-draft(8002-PIPE-401), approvals, users-new, ship-*.
- 2026-11-13 최신 캡처(`init-db --seed --demo-pdfs --demo-usage` 데이터, admin): dashboard, hull-list, hull-hover, hull-yard, hull-3d, plan-gantt(8001), plan-hover([201] 탑재), plan-zoom(확대·휴일), progress, progress-hover, drawing-list, drawing-hover(8001-HULL-101 예시 PDF), users(choi.qa 메뉴 권한), usage-log(30일), inquiry-admin, manual(공정계획). park.pm: inquiry-user(새 글), chat, chat-hulls, chat-report.
- 2026-11-13 캡처에는 UI 다듬기(ui.md 모션·깊이)와 왼쪽 아래 챗봇 런처·말풍선이 들어 있다. 원본 캡처와 버튼 그림자·radius가 조금 다르면 ui.md를 따른다.

| 자산 | 용도 |
| --- | --- |
| `assets/auth-scene.svg` | 로그인 배경(자체 제작 SVG, 동작 줄이기 대응) |
| `../manual/*.jpg` | 매뉴얼(F15) 예시 사진. `frontend/src/assets/manual/`로 복사 |
| `../seed/seed.json` | 초기 데이터(메뉴 M92·M95 포함). 비밀번호·TOTP secret은 데모 전용 |
