"""init-db CLI: 마이그레이션 적용 후 시드·예시 데이터(옵션). 반복 실행 안전."""
import argparse

from . import config, db
from .seed import load_seed
from .services import demo


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="init-db", description="SWP Shipyard DB 초기화")
    ap.add_argument("--seed", action="store_true", help="reference/seed/seed.json 적재")
    ap.add_argument("--demo-pdfs", action="store_true", help="예시 PDF 생성(F16)")
    ap.add_argument("--demo-usage", action="store_true", help="예시 사용 로그 생성(F16)")
    args = ap.parse_args(argv)
    conn = db.connect()
    try:
        applied = db.migrate(conn)
        print(f"[init-db] db={config.db_path()} migrations applied={applied or 'none'}")
        if args.seed:
            counts = load_seed(conn)
            print(f"[init-db] seed tables={len(counts)}")
        if args.demo_pdfs:
            print(f"[init-db] demo pdfs={demo.load_demo_pdfs(conn)}")
        if args.demo_usage:
            print(f"[init-db] demo usage={demo.load_demo_usage(conn)}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
