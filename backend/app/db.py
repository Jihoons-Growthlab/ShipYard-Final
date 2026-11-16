"""SQLite 연결·트랜잭션·마이그레이션."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    p = Path(path) if path else config.db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    """쓰기 트랜잭션(BEGIN IMMEDIATE). 안쪽 헬퍼는 트랜잭션을 다시 열지 않는다."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def migrate(conn: sqlite3.Connection) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations("
        "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    done = []
    for f in sorted(config.migrations_dir().glob("*.sql")):
        if f.stem in applied:
            continue
        sql = f.read_text(encoding="utf-8")
        conn.executescript(
            "BEGIN;\n" + sql + f"\nINSERT INTO schema_migrations(version) VALUES('{f.stem}');\nCOMMIT;"
        )
        done.append(f.stem)
    return done
