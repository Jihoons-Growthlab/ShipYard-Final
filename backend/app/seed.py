"""seed.json 적재. PK 값 그대로, 이미 있는 행은 건너뛴다(반복 실행 안전). 상태값은 재계산하지 않는다."""
import json
import sqlite3

from . import config, db
from .security import hash_password


def load_seed(conn: sqlite3.Connection) -> dict[str, int]:
    data = json.loads(config.seed_path().read_text(encoding="utf-8"))
    counts = {}
    existing_users = {r[0] for r in conn.execute("SELECT emp_no FROM users")}
    with db.tx(conn):
        for table, spec in data.items():
            cols = list(spec["columns"])
            rows = spec["rows"]
            if table == "users":
                pw = cols.index("demo_password")
                emp = cols.index("emp_no")
                cols = [c for c in cols if c != "demo_password"] + ["password_hash"]
                rows = [
                    [v for i, v in enumerate(r) if i != pw] + [hash_password(r[pw])]
                    for r in rows
                    if r[emp] not in existing_users
                ]
            sql = f"INSERT OR IGNORE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
            conn.executemany(sql, rows)
            counts[table] = len(spec["rows"])
    return counts


def seed_users() -> dict[str, dict]:
    """시드 사용자 원본(데모 비밀번호 포함). 테스트·화면 검증 도구용."""
    spec = json.loads(config.seed_path().read_text(encoding="utf-8"))["users"]
    return {r[spec["columns"].index("emp_no")]: dict(zip(spec["columns"], r)) for r in spec["rows"]}
