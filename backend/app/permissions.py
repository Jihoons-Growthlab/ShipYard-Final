"""BR-10 메뉴 권한 판정 — 유일한 등급 계산 함수. API 검사·메뉴 표시·MCP 도구·보고서가 모두 이것을 쓴다."""
import sqlite3

LEVELS = {"None": 0, "View": 1, "Write": 2, "Admin": 3}
NAMES = {0: None, 1: "View", 2: "Write", 3: "Admin"}


def menu_levels(conn: sqlite3.Connection, emp_no: str) -> dict[str, int]:
    """메뉴별 등급: 그룹 권한(여러 그룹이면 최고값) 위에 회원별 지정이 메뉴 단위로 우선. 회원별 None=0."""
    levels: dict[str, int] = {}
    for mid, gbn in conn.execute(
        "SELECT am.MenuId, am.AuthGbn FROM TB_SYS_AuthMenu am"
        " JOIN TB_SYS_AuthUser au ON au.AuthCd = am.AuthCd WHERE au.EmpNo = ?",
        (emp_no,),
    ):
        levels[mid] = max(levels.get(mid, 0), LEVELS.get(gbn, 0))
    for mid, gbn in conn.execute("SELECT MenuId, AuthGbn FROM TB_SYS_UserMenu WHERE EmpNo = ?", (emp_no,)):
        levels[mid] = LEVELS.get(gbn, 0)
    return levels


def group_levels(conn: sqlite3.Connection, emp_no: str) -> dict[str, int]:
    """회원별 지정을 제외한 그룹 최고값(회원별 지정 저장 시 '그룹과 같은 값은 저장하지 않는다' 판정용)."""
    levels: dict[str, int] = {}
    for mid, gbn in conn.execute(
        "SELECT am.MenuId, am.AuthGbn FROM TB_SYS_AuthMenu am"
        " JOIN TB_SYS_AuthUser au ON au.AuthCd = am.AuthCd WHERE au.EmpNo = ?",
        (emp_no,),
    ):
        levels[mid] = max(levels.get(mid, 0), LEVELS.get(gbn, 0))
    return levels


def menu_level(conn: sqlite3.Connection, emp_no: str, menu_id: str) -> int:
    return menu_levels(conn, emp_no).get(menu_id, 0)
