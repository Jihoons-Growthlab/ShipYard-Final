<!-- srcmap:0e2788146eab -->
# SOURCEMAP (scripts/wf.py srcmap가 생성. 직접 고치지 않는다)
## API (openapi)
POST /api/auth/login body=LoginIn
POST /api/auth/otp/verify body=OtpIn
POST /api/auth/register body=RegisterIn
POST /api/auth/logout
GET /api/auth/me
POST /api/auth/demo-role body=DemoRoleIn
GET /api/me/menu
POST /api/me/menu-access body=MenuAccessIn
GET /api/weather ?region
GET /api/codes
GET /api/users/options
GET /api/hulls ?status,ship_type,q
POST /api/hulls body=HullIn
GET /api/hulls/{hull_no}
PATCH /api/hulls/{hull_no} body=HullIn
DELETE /api/hulls/{hull_no}
GET /api/hulls/{hull_no}/milestones
PUT /api/hulls/{hull_no}/milestones body=MilestonesIn
GET /api/hulls/{hull_no}/blocks
POST /api/hulls/{hull_no}/blocks body=BlockIn
DELETE /api/blocks/{block_id}
GET /api/hulls/{hull_no}/summary
GET /api/procs
GET /api/plan-hulls
GET /api/hulls/{hull_no}/plans ?block_id
POST /api/hulls/{hull_no}/plans body=PlanIn
GET /api/plans/{plan_id}
PATCH /api/plans/{plan_id} body=PlanIn
DELETE /api/plans/{plan_id}
PUT /api/plans/{plan_id}/predecessors body=PredecessorsIn
PATCH /api/plans/{plan_id}/schedule body=ScheduleIn
GET /api/plans/{plan_id}/drawings
POST /api/plans/{plan_id}/drawings body=PlanLinkIn
DELETE /api/plans/{plan_id}/drawings/{drawing_id}
GET /api/progress-hulls
GET /api/hulls/{hull_no}/progress-targets ?include_done
GET /api/plans/{plan_id}/progress
PUT /api/plans/{plan_id}/progress/{work_dt} body=ProgressIn
DELETE /api/progress/{progress_id}
GET /api/drawings ?hull_no,discipline,status,q
POST /api/drawings body=DrawingIn
GET /api/drawings/{drawing_id}
PATCH /api/drawings/{drawing_id} body=DrawingIn
DELETE /api/drawings/{drawing_id}
GET /api/drawings/{drawing_id}/revisions
POST /api/drawings/{drawing_id}/revisions body=RevisionIn
POST /api/drawings/{drawing_id}/revisions/{rev_no}/pdf ?filename
GET /api/drawings/{drawing_id}/revisions/{rev_no}/pdf
DELETE /api/drawings/{drawing_id}/revisions/{rev_no}/pdf
POST /api/drawings/{drawing_id}/revisions/{rev_no}/request-approval body=ApprovalRequestIn
POST /api/drawings/{drawing_id}/revisions/{rev_no}/issue
GET /api/drawings/{drawing_id}/plans
POST /api/drawings/{drawing_id}/plans body=DrawingLinkIn
DELETE /api/drawings/{drawing_id}/plans/{plan_id}
GET /api/approvals/inbox
POST /api/approvals/{approval_id}/decision body=DecisionIn
GET /api/approvals/history
GET /api/users ?status,q
POST /api/users body=UserIn
GET /api/auth-groups
GET /api/users/{emp_no}
PATCH /api/users/{emp_no} body=UserIn
DELETE /api/users/{emp_no}
POST /api/users/{emp_no}/approve body=ApproveIn
POST /api/users/{emp_no}/reject
GET /api/users/{emp_no}/menus
PUT /api/users/{emp_no}/menus body=UserMenusIn
GET /api/dashboard/summary
GET /api/usage/summary ?days,emp_no
GET /api/inquiries ?status,q,mine
POST /api/inquiries body=InquiryIn
GET /api/inquiries/{inquiry_id}
PATCH /api/inquiries/{inquiry_id} body=InquiryIn
DELETE /api/inquiries/{inquiry_id}
POST /api/chat body=ChatIn
POST /api/chat/feedback body=FeedbackIn
GET /api/chat/report/options
POST /api/chat/report body=ReportIn
GET /api/chat/reports/{report_id} ?format
GET /api/health
## Python
backend/app/cli.py: main
backend/app/config.py: db_path, file_dir, report_dir, migrations_dir, seed_path, app_secret, token_ttl, otp_token_ttl, weather_provider, ollama_base_url, ollama_model, ollama_timeout, report_font, demo_enabled
backend/app/db.py: connect, tx, get_db, migrate
backend/app/deps.py: bearer, current_user, forbidden, require
backend/app/errors.py: AppError, validation, not_found, duplicate, unauthorized, body, install
backend/app/hull_mcp.py: BadArgs, search_hulls, list_drawings, list_progress_hulls, submit_feedback, build_report, handle, main
backend/app/main.py: health
backend/app/permissions.py: menu_levels, group_levels, menu_level
backend/app/routers/approvals.py: inbox, decision, history
backend/app/routers/auth.py: login, otp_verify, register, logout, me, demo_role
backend/app/routers/chat.py: chat, feedback, report_options, create_report, download_report
backend/app/routers/dashboard.py: summary
backend/app/routers/drawings.py: list_drawings, create_drawing, get_drawing, update_drawing, delete_drawing, revisions, create_revision, upload_pdf, get_pdf, delete_pdf, request_approval, issue, linked_plans, link_plan, unlink_plan
backend/app/routers/hulls.py: list_hulls, create_hull, get_hull, update_hull, delete_hull, milestones, save_milestones, blocks, create_block, delete_block, summary
backend/app/routers/inquiries.py: list_inquiries, create_inquiry, get_inquiry, update_inquiry, delete_inquiry
backend/app/routers/plans.py: procs, plan_hulls, hull_plans, create_plan, get_plan, update_plan, delete_plan, set_predecessors, schedule, plan_drawings, link_drawing, unlink_drawing
backend/app/routers/progress.py: progress_hulls, targets, plan_progress, save_progress, delete_progress
backend/app/routers/shell.py: my_menu, menu_access, weather, codes, user_options
backend/app/routers/usage.py: summary
backend/app/routers/users.py: list_users, create_user, auth_groups, get_user, update_user, delete_user, approve, reject, user_menus, set_user_menus
backend/app/schemas.py: In, LoginIn, OtpIn, RegisterIn, MenuAccessIn, HullIn, MilestoneItem, MilestonesIn, BlockIn, PlanIn, PredecessorsIn, PlanLinkIn, ScheduleIn, ProgressIn, DrawingIn, RevisionIn, ApprovalRequestIn, DrawingLinkIn, DecisionIn, UserIn, ApproveIn, UserMenuItem, UserMenusIn, InquiryIn, DemoRoleIn, ChatMessage, ChatIn, FeedbackIn, ReportIn
backend/app/security.py: hash_password, verify_password, create_token, decode_token, current_step, totp_at, match_totp
backend/app/seed.py: load_seed, seed_users
backend/app/services/approvals.py: waiting, ready, inbox, decide, history
backend/app/services/auth.py: reset_otp_state, groups_of, me, start_session, login, verify_otp, logout, normalize_phone, validate_user_fields, register, switch_demo_role
backend/app/services/chat.py: call_tool, answer, save_feedback, submit_feedback, ollama_chat
backend/app/services/dashboard.py: summary
backend/app/services/demo.py: render_pdf, load_demo_pdfs, load_demo_usage, prepare_demo_accounts
backend/app/services/drawings.py: drawing_not_found, rev_state, list_drawings, revisions, linked_plans, get_drawing, create_drawing, update_drawing, delete_drawing, create_revision, request_approval, issue, clean_filename, check_upload_target, too_large, save_upload, pdf_file, delete_pdf, link_plan, unlink_plan
backend/app/services/hulls.py: hull_not_found, ensure_hull, list_hulls, get_hull, create_hull, update_hull, delete_hull, milestones, save_milestones, blocks, create_block, delete_block, summary
backend/app/services/inquiries.py: is_admin, list_inquiries, create_inquiry, get_inquiry, update_inquiry, delete_inquiry
backend/app/services/plans.py: plan_not_found, load_plans, get_plan, hull_plans, procs, plan_hulls, check_preds, create_plan, update_plan, set_predecessors, delete_plan, schedule, plan_drawings, link_drawing, unlink_drawing
backend/app/services/progress.py: progress_hulls, targets, plan_progress, save_progress, delete_progress
backend/app/services/reports.py: pct, collect, user_dir, report_path, find, build, font_path, write_pdf, write_xlsx
backend/app/services/rules.py: weighted_progress, progress_by, blockers_map, pred_map, plan_status, recalc_hull, recalc_plan_hull, apply_progress, plan_label, code_sort_key, plan_sort_key, revision_impacts
backend/app/services/shell.py: visible_menus, record_menu_access, codes, code_set, approved_user, user_options
backend/app/services/usage.py: feature_of, should_log, record, summary
backend/app/services/users.py: user_not_found, list_users, get_user, auth_groups, create_user, update_user, approve, reject, delete_user, user_menus, set_user_menus
backend/app/services/weather.py: get_weather
backend/app/storage.py: file_path, remove_files, revision_file_ids
backend/app/usage_log.py: UsageLogMiddleware
backend/app/util.py: parse_date, is_date, add_days, days_between, utc_now, blank_to_none
## Vue (props/emits/scoped css)
frontend/src/App.vue: props[] emits[]
frontend/src/components/AppModal.vue: props[title,size] emits[close] css[large mbg mbody mclose mhead mpanel mtitle xl]
frontend/src/components/AppToasts.vue: props[] emits[] css[error success toast toast-enter-active toast-enter-from toast-leave-active toast-leave-to toasts]
frontend/src/components/ChatReport.vue: props[] emits[] css[again big dl fmt fmts go ico on pdf pill pills racts rcard rerr res rinfo rlbl rs rt xls]
frontend/src/components/HoverCard.vue: props[preview,width,height] emits[] css[hcard]
frontend/src/components/PageHead.vue: props[title,desc,readonly] emits[]
frontend/src/components/ProgressBar.vue: props[value] emits[] css[pbar pfill plabel]
frontend/src/components/ShipChat.vue: props[] emits[] css[boat bot bridge cards cbody ccard cfoot chead cin cpanel csend cx err fbar fcancel funnel hello hull launch-wrap launcher me msg qb quick rep ship-chat wait]
frontend/src/components/ShipViewer3D.vue: props[hullNo,fleet] emits[select] css[card fleet v3d vbar vcanvas verr verr-t vh-f vh-kv vh-t vhover vkv vname vnote vover vreason vside vviews vwrap]
frontend/src/components/StatusBadge.vue: props[value,kind] emits[]
frontend/src/components/StatusChips.vue: props[counts,kind,dots] emits[]
frontend/src/components/WeatherWidget.vue: props[] emits[] css[live sample wx wx-badge wx-sel wx-sub wx-t]
frontend/src/components/WorkflowManual.vue: props[section] emits[close] css[btn manual mdesc mhd mlist mt shot steps]
frontend/src/screens/ApprovalInbox.vue: props[title,canWrite,param,ctx,active] emits[] css[b card w150]
frontend/src/screens/Dashboard.vue: props[title,canWrite,param,ctx,active] emits[] css[dcol deliv disc dm donut-wrap ds dt ell err flow g3 hbar hp kl kpi kpis kv legend li none row stack warn]
frontend/src/screens/DrawingList.vue: props[title,canWrite,param,ctx,active] emits[] css[cnt dpv ell pvno pvpdf pvtag w110 w148 w165]
frontend/src/screens/DrawingModal.vue: props[drawingId,canWrite] emits[close,changed] css[act acts cd chk dgrid ell file fn fname imp intro meta mt revs rv side vbody viewer vnone vtool w110 w230]
frontend/src/screens/HullDetailModal.vue: props[hullNo,canWrite] emits[close,changed] css[acts addrow card chk inp sub sum viewer-tab w110 wbar]
frontend/src/screens/HullList.vue: props[title,canWrite,param,ctx,active] emits[] css[cnt w110 w150 wbar yard yard-d yard-h yard-off yard-pg]
frontend/src/screens/Inquiry.vue: props[title,canWrite,param,ctx,active] emits[] css[abody answer body c-BUG c-ETC c-FEATURE c-QUESTION cat chk content ed emp inq list on on-DONE on-IN_PROGRESS on-OPEN on-REJECTED panel pending proc seg sm st stbtns ttl vw w180]
frontend/src/screens/PlaceholderScreen.vue: props[title,canWrite,param,ctx,active] emits[]
frontend/src/screens/PlanGantt.vue: props[title,canWrite,param,ctx,active] emits[] css[bar bc dep drag-lbl dragging fill g-bg g-body g-corner g-deps g-empty g-head g-hmark g-inner g-label g-mline g-month g-months g-off g-row g-scroll g-today g-today-lbl g-track hd hl hol hov l legend lg od plan-screen plbl pre r rel rw sat sel]
frontend/src/screens/PlanPanel.vue: props[hullNo,plan,plans,blocks,procs,users,canWrite,defaultBlockId,today] emits[close,saved,deleted] css[f-acts f-block f-m f-pred f-proc f-rm h66 linkrow note pf plan-panel pp-body pp-head pp-new pp-right pp-title]
frontend/src/screens/ProgressInput.vue: props[title,canWrite,param,ctx,active] emits[] css[fg hist-h pick prog-detail tw w165 wbar]
frontend/src/screens/UsageLog.vue: props[title,canWrite,param,ctx,active] emits[] css[ax bar chart clk dot ell er err err-row errt grid guide hb hcol hours kl kpi kpis ks kv lg line m-del m-get m-post m-put mb mt mv none on pri r21 r3 sm tip top ub w120 w180]
frontend/src/screens/UserMgmt.vue: props[title,canWrite,param,ctx,active] emits[] css[bottom btns bwrap c chk cnt list perm perm-h perm-table pick ptable sub top user-form users w110 w148 withperm]
frontend/src/views/LoginView.vue: props[] emits[] css[ac-foot ac-logo ac-sub ai-list ai-logo ai-title auth auth-card auth-err auth-intro auth-scene auth-wrap btn inp otp signup wide]
frontend/src/views/ShellView.vue: props[] emits[] css[brand hbtn hd main menu menu-cap mi mk on screen shell sub tab tabbar tbtn tx who work]
## JS exports
frontend/src/api/client.js: TOKEN_KEY, getToken, setToken, clearToken, onUnauthorized, ApiError, request, api
frontend/src/router.js: router
frontend/src/screens/registry.js: SCREENS, screenOf
frontend/src/stores/session.js: TABS_KEY, FORBIDDEN_MSG, session, loadSession, endSession, logout, menuByToken, canWrite, codeOptions, codeName
frontend/src/utils/approval.js: RESULT, stepName
frontend/src/utils/chart.js: PALETTE, niceMax, labelStep, CH, lineGeom, methodClass
frontend/src/utils/chat.js: GREETING, REPORT_GUIDE, WAITING, QUICK, FEEDBACK_LABEL, MAX_HISTORY, MAX_LEN, manualIntent, historyPayload, hullCard, drawingCard, progressHullCard, planCard, progressText, sizeText
frontend/src/utils/date.js: parseDate, fmtDate, addDays, diffDays, dow, monthStart, addMonths, minDate, maxDate, localDateTime
frontend/src/utils/gantt.js: LEFT, ROW_H, HEAD_H, SCALES, ganttLayout, months, barGeom, dragDates, depPaths
frontend/src/utils/holidays.js: HOLIDAYS, dayKind, offDays
frontend/src/utils/hoverPreview.js: OPEN_DELAY, CLOSE_DELAY, DEFAULT_TTL, useHoverPreview
frontend/src/utils/manual.js: MANUAL_STEPS, visibleSteps, startStep
frontend/src/utils/menuPerm.js: LEVELS, levelName, permRows, effective, isCustom, setLevel, resetToGroup, menusPayload, permChanged
frontend/src/utils/pdf.js: MAX_PDF, PDF_TYPE_MSG, PDF_SIZE_MSG, checkPdf, pdfPath, uploadPdf, pdfBlobUrl, revokeUrl, pdfViewable, previewRev
frontend/src/utils/status.js: PLAN_STATUSES, DWG_STATUSES, STATUS_COLORS, planStatusName, dwgStatusName, dash, fmtNum
frontend/src/utils/tabs.js: MAX_TABS, TAB_LIMIT_MSG, tabKey, openTab, closeTab, closeOthers, serialize, restore
frontend/src/utils/toast.js: toasts, toast, toastError, toastOk
frontend/src/utils/unityViewer.js: BUILD_BASE, MSG_NO_BUILD, MSG_TIMEOUT, MSG_LOADER, TIMEOUT_MS, SETTLE_MS, VIEWS, firstLine, loadBuildInfo, loadLoader, startViewer, _resetForTest
frontend/src/utils/weather.js: REGIONS, REGION_KEY, weatherIcon
## CSS classes
frontend/src/styles/global.css: b b-APPROVED b-DELAY b-DONE b-DRAFT b-ISSUED b-OBSOLETE b-PLAN b-READY b-REVIEW b-WORK b-bad b-info b-ok b-warn btn c2 c4 c6 card card-h chip chips clk danger desc empty fg fld grow inp k lb muted note num ok on ph pri pv pvf pvh pvm pvpdf pvr pvt r3 right ro-badge row s2 s3 sall sel sm sp subtabs t toolbar tw warn wrap
## Unity
unity/ShipyardViewer/Assets/Editor/ViewerBuild.cs: ViewerBuild, Build
unity/ShipyardViewer/Assets/Plugins/WebGL/ShipViewer.jslib: 
unity/ShipyardViewer/Assets/Scripts/FleetSlot.cs: FleetSlot
unity/ShipyardViewer/Assets/Scripts/ShipModel.cs: ShipModel, HalfWidth, Buf, Tri, Quad, HullMesh, Box, BuildShip, BuildSingleYard, BuildFleetYard
unity/ShipyardViewer/Assets/Scripts/ShipViewer.cs: ShipViewer, SetView, SetFleet
## Tests (count)
backend/tests/__init__.py (0)
backend/tests/conftest.py (0)
backend/tests/helpers.py (0)
backend/tests/test_approvals.py (6)
backend/tests/test_auth.py (11)
backend/tests/test_chat.py (9)
backend/tests/test_dashboard.py (4)
backend/tests/test_demo.py (5)
backend/tests/test_drawings.py (8)
backend/tests/test_foundation.py (9)
backend/tests/test_hulls.py (10)
backend/tests/test_inquiries.py (5)
backend/tests/test_plans.py (10)
backend/tests/test_progress.py (6)
backend/tests/test_shell.py (7)
backend/tests/test_usage.py (4)
backend/tests/test_users.py (6)
