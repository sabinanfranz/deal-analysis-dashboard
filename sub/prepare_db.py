# prepare_db.py
"""
매일 all deal / won deal / retention txt 파일을 갱신한 뒤
이 스크립트를 실행하면 SQLite DB(deals.db)를 항상 최신 상태로 재생성한다.
"""

import pandas as pd
import sqlite3
import pathlib
import sys

BASE = pathlib.Path(__file__).parent
FILES = {
    "all_deal":  BASE / "all deal.txt",
    "won_deal":  BASE / "won deal.txt",
    "retention": BASE / "retention corp.txt",
}

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

/* 인덱스 재생성 */
DROP INDEX IF EXISTS idx_all_deal_name;
DROP INDEX IF EXISTS idx_won_deal_name;

CREATE INDEX idx_all_deal_name ON all_deal ("담당자_name");
CREATE INDEX idx_won_deal_name ON won_deal ("담당자_name");
"""

def _read_txt(path: pathlib.Path) -> pd.DataFrame:
    """UTF-8 탭 구분 txt → DataFrame, 빈 행 제거"""
    return pd.read_csv(path, sep="\t").dropna(how="all")

def load_to_db(db_path: str = "deals.db") -> None:
    con = sqlite3.connect(db_path)
    try:
        for table, txt in FILES.items():
            if not txt.exists():
                sys.stderr.write(f"[WARN] {txt} not found – skip\n")
                continue
            df = _read_txt(txt)
            df.to_sql(table, con, if_exists="replace", index=False)
            print(f"[OK] {table} : {len(df):,} rows")

        # 인덱스 및 PRAGMA 적용
        con.executescript(SCHEMA_SQL)
        con.commit()
    finally:
        con.close()

if __name__ == "__main__":
    load_to_db()
