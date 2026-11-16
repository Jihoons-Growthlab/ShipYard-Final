"""업로드 파일 저장소(SHIPYARD_FILE_DIR). BR-08: DB 커밋 후 지우고, 새 파일은 커밋 전에 쓰고 실패하면 제거."""
import sqlite3
from pathlib import Path
from typing import Iterable

from . import config


def file_path(file_id: str) -> Path:
    name = Path(file_id).name  # 경로 조작 방지
    return config.file_dir() / name


def remove_files(file_ids: Iterable[str | None]) -> None:
    for fid in file_ids:
        if fid:
            try:
                file_path(fid).unlink(missing_ok=True)
            except OSError:
                pass


def revision_file_ids(conn: sqlite3.Connection, where: str, params: tuple) -> list[str]:
    """TB_DWG_Drawing d / TB_DWG_Revision r 조인에서 조건에 맞는 FileId."""
    return [r[0] for r in conn.execute(
        "SELECT r.FileId FROM TB_DWG_Revision r JOIN TB_DWG_Drawing d ON d.DrawingId = r.DrawingId"
        f" WHERE r.FileId IS NOT NULL AND {where}", params)]
