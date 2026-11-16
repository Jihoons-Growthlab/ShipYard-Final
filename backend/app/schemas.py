"""요청 스키마. 형식·길이만 제한하고 업무 검증(순서·메시지)은 서비스가 한다."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

S20, S50, S100, S200, S500, S1000 = 20, 50, 100, 200, 500, 1000


class In(BaseModel):
    model_config = ConfigDict(extra="ignore")


# --- 인증 (F01)
class LoginIn(In):
    emp_no: str = Field("", max_length=S50)
    password: str = Field("", max_length=S200)


class OtpIn(In):
    code: str = Field("", max_length=S20)


class RegisterIn(In):
    last_name: str | None = Field(None, max_length=S50)
    first_name: str | None = Field(None, max_length=S50)
    birth_date: str | None = Field(None, max_length=S20)
    phone: str | None = Field(None, max_length=S20)
    email: str | None = Field(None, max_length=254)
    emp_no: str | None = Field(None, max_length=S50)
    password: str | None = Field(None, max_length=S200)
    password_confirm: str | None = Field(None, max_length=S200)


# --- 셸 (F02)
class MenuAccessIn(In):
    menu_id: str = Field(..., max_length=S20)


# --- 호선 (F04)
class HullIn(In):
    hull_no: str | None = Field(None, max_length=S50)
    hull_nm: str | None = Field(None, max_length=S100)
    ship_type: str | None = Field(None, max_length=S20)
    hull_status: str | None = Field(None, max_length=S20)
    owner_nm: str | None = Field(None, max_length=S100)
    class_society: str | None = Field(None, max_length=S50)
    length_m: float | None = None
    breadth_m: float | None = None
    depth_m: float | None = None
    dead_weight: float | None = None
    dock_no: str | None = Field(None, max_length=S50)
    contract_dt: str | None = Field(None, max_length=S20)
    delivery_dt: str | None = Field(None, max_length=S20)
    remark: str | None = Field(None, max_length=S500)
    use_yn: bool | None = None


class MilestoneItem(In):
    milestone_cd: str | None = Field(None, max_length=S20)
    plan_dt: str | None = Field(None, max_length=S20)
    actual_dt: str | None = Field(None, max_length=S20)


class MilestonesIn(In):
    items: list[MilestoneItem] = Field(default_factory=list, max_length=50)


class BlockIn(In):
    block_cd: str | None = Field(None, max_length=S20)
    block_nm: str | None = Field(None, max_length=S100)
    block_type: str | None = Field(None, max_length=S20)
    parent_block_id: int | None = None
    weight_ton: float | None = None


# --- 공정 계획 (F05)
class PlanIn(In):
    block_id: int | None = None
    proc_cd: str | None = Field(None, max_length=S20)
    plan_start_dt: str | None = Field(None, max_length=S20)
    plan_end_dt: str | None = Field(None, max_length=S20)
    manager_emp_no: str | None = Field(None, max_length=S50)
    remark: str | None = Field(None, max_length=S1000)
    pred_plan_ids: list[int] | None = Field(None, max_length=500)
    confirm_late_preds: bool = False


class PredecessorsIn(In):
    pred_plan_ids: list[int] = Field(default_factory=list, max_length=500)
    confirm_late_preds: bool = False


class PlanLinkIn(In):
    drawing_id: int | None = None
    required: bool = True


class ScheduleIn(In):
    plan_start_dt: str | None = Field(None, max_length=S20)
    plan_end_dt: str | None = Field(None, max_length=S20)
    confirm_late_preds: bool = False


# --- 공정 실적 (F06)
class ProgressIn(In):
    progress_rate: float | None = None
    man_hour: float | None = None
    worker_cnt: int | None = None
    worker_emp_no: str | None = Field(None, max_length=S50)
    remark: str | None = Field(None, max_length=S1000)


# --- 도면 (F07)
class DrawingIn(In):
    drawing_no: str | None = Field(None, max_length=S50)
    drawing_nm: str | None = Field(None, max_length=S200)
    hull_no: str | None = Field(None, max_length=S50)
    block_id: int | None = None
    discipline: str | None = Field(None, max_length=S20)
    designer_emp_no: str | None = Field(None, max_length=S50)


class RevisionIn(In):
    change_desc: str | None = Field(None, max_length=S1000)


class ApprovalRequestIn(In):
    reviewer_emp_no: str | None = Field(None, max_length=S50)
    approver_emp_no: str | None = Field(None, max_length=S50)


class DrawingLinkIn(In):
    plan_id: int | None = None
    required: bool = True


# --- 결재 (F08)
class DecisionIn(In):
    result: str | None = Field(None, max_length=S20)
    comment: str | None = Field(None, max_length=S1000)


# --- 회원관리 (F09)
class UserIn(In):
    emp_no: str | None = Field(None, max_length=S50)
    last_name: str | None = Field(None, max_length=S50)
    first_name: str | None = Field(None, max_length=S50)
    birth_date: str | None = Field(None, max_length=S20)
    phone: str | None = Field(None, max_length=S20)
    email: str | None = Field(None, max_length=254)
    password: str | None = Field(None, max_length=S200)
    status: str | None = Field(None, max_length=S20)
    groups: list[str] | None = Field(None, max_length=10)
    totp_enabled: bool | None = None


class ApproveIn(In):
    groups: list[str] = Field(default_factory=list, max_length=10)


class UserMenuItem(In):
    menu_id: str = Field(..., max_length=S20)
    level: Any = None  # 범위 검사와 메시지는 서비스가 한다


class UserMenusIn(In):
    menus: list[UserMenuItem] = Field(default_factory=list, max_length=100)


# --- 건의·문의 (F12)
class InquiryIn(In):
    category: str | None = Field(None, max_length=S20)
    title: str | None = Field(None, max_length=S1000)
    content: str | None = Field(None, max_length=20000)
    status: str | None = Field(None, max_length=S20)
    answer: str | None = Field(None, max_length=20000)


# --- 데모 (F16)
class DemoRoleIn(In):
    role: str | None = Field(None, max_length=S20)


# --- 챗봇·보고서 (F13·F14)
class ChatMessage(In):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class ChatIn(In):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=12)


class FeedbackIn(In):
    kind: Literal["suggestion", "inquiry"]
    content: str = Field("", max_length=2000)
    request_id: str = Field(..., max_length=64)


class ReportIn(In):
    format: str = Field("", max_length=S20)
    hull_no: str | None = Field(None, max_length=S20)
