# data.py
"""
TXT ↔ SQLite 로드 + Streamlit 로더
────────────────────────────────────────
· TXT 수정 → data.py import 시 자동 DB 재생성 & 캐시 무효화
· 사용 법:   from data import load_all_deal, load_won_deal, load_retention
"""

import pathlib, sys, sqlite3, re, os
import pandas as pd
import streamlit as st

# ─────────────────────────── TXT → DB
BASE = pathlib.Path(__file__).parent
FILES = {
    "all_deal":  BASE / "all deal.txt",
    "won_deal":  BASE / "won deal.txt",
    "retention": BASE / "retention corp.txt",
}
DB = "deals.db"

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
DROP INDEX IF EXISTS idx_all_deal_name;
DROP INDEX IF EXISTS idx_won_deal_name;
CREATE INDEX idx_all_deal_name ON all_deal ("담당자_name");
CREATE INDEX idx_won_deal_name ON won_deal ("담당자_name");
"""

def _read_txt(path: pathlib.Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t").dropna(how="all")

def load_to_db() -> None:
    con = sqlite3.connect(DB)
    try:
        for table, txt in FILES.items():
            if not txt.exists():
                sys.stderr.write(f"[WARN] {txt} not found – skip\n")
                continue
            df = _read_txt(txt)
            df.to_sql(table, con, if_exists="replace", index=False)
        con.executescript(SCHEMA_SQL)
        con.commit()
    finally:
        con.close()

# ─────────────────────────── 캐시 Key (TXT mtime)
def _files_sig() -> tuple:
    """모든 TXT 수정시각 튜플 → 캐시 무효화 키"""
    return tuple(int(os.path.getmtime(p)) for p in FILES.values())

# ─────────────────────────── SQLite 연결 (자동 최신화)
@st.cache_resource
def _conn(sig: tuple) -> sqlite3.Connection:        # sig = _files_sig()
    load_to_db()                                    # TXT → DB 재생성
    return sqlite3.connect(DB, check_same_thread=False)

# ─────────────────────────── 공통 후처리
def _post(df: pd.DataFrame) -> pd.DataFrame:
    df['담당자_name'] = df['담당자_name'].str.replace(r'B$', '', regex=True)
    df['수주 예정액(종합)'] = pd.to_numeric(
        df['수주 예정액(종합)'].astype(str).str.replace(',', ''), errors='coerce'
    ).fillna(0)

    num = ['생성년도','생성월','수주예정년도','수주예정월']
    df = df.dropna(subset=num)
    df[num] = df[num].astype(int)

    df['예정월'] = (
        df['수주예정년도'].astype(str) + '-' +
        df['수주예정월'].astype(str).str.zfill(2)
    )
    return df

# ─────────────────────────── 로더 (sig 자동 전달)
def _sig() -> tuple:        # 내부 헬퍼
    return _files_sig()

@st.cache_data
def _load_all(sig: tuple) -> pd.DataFrame:
    return _post(pd.read_sql_query("SELECT * FROM all_deal", _conn(sig)))

@st.cache_data
def _load_won(sig: tuple) -> pd.DataFrame:
    return _post(pd.read_sql_query("SELECT * FROM won_deal", _conn(sig)))

@st.cache_data
def _load_ret(sig: tuple) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM retention", _conn(sig))

# 사용자 API ──────────────────────────────────────
def load_all_deal() -> pd.DataFrame:
    return _load_all(_sig())

def load_won_deal() -> pd.DataFrame:
    return _load_won(_sig())

def load_retention() -> pd.DataFrame:
    return _load_ret(_sig())
