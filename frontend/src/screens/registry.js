// 화면 토큰 → 컴포넌트. 아직 없는 화면은 자리표시.
import PlaceholderScreen from './PlaceholderScreen.vue'
import HullList from './HullList.vue'
import PlanGantt from './PlanGantt.vue'
import ProgressInput from './ProgressInput.vue'
import DrawingList from './DrawingList.vue'
import ApprovalInbox from './ApprovalInbox.vue'
import Dashboard from './Dashboard.vue'
import UserMgmt from './UserMgmt.vue'
import UsageLog from './UsageLog.vue'
import Inquiry from './Inquiry.vue'

export const SCREENS = {
  dashboard: Dashboard,
  'hull-list': HullList,
  'plan-gantt': PlanGantt,
  progress: ProgressInput,
  'dwg-list': DrawingList,
  'dwg-approval': ApprovalInbox,
  'user-mgmt': UserMgmt,
  'usage-log': UsageLog,
  inquiry: Inquiry,
}

export const screenOf = (token) => SCREENS[token] || PlaceholderScreen
