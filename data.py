# data.py
"""
TXT ↔ SQLite 로드 + Streamlit 로더
────────────────────────────────────────
· TXT 수정 → data.py import 시 자동 DB 재생성 & 캐시 무효화
· 사용 법:   from data import (
      load_all_deal, load_won_deal, load_retention, load_accounting
  )
"""

import pathlib, sys, sqlite3, re, os
import pandas as pd
import streamlit as st

# ─────────────────────────── TXT → DB
BASE = pathlib.Path(__file__).parent
FILES = {
    "all_deal":   BASE / "all deal.txt",
    "won_deal":   BASE / "won deal.txt",
    "retention":  BASE / "retention corp.txt",
    "accounting": BASE / "accounting data.txt",
}
DB = "deals.db"

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
DROP INDEX IF EXISTS idx_all_deal_name;
DROP INDEX IF EXISTS idx_won_deal_name;
CREATE INDEX IF NOT EXISTS idx_all_deal_name ON all_deal ("담당자_name");
CREATE INDEX IF NOT EXISTS idx_won_deal_name ON won_deal ("담당자_name");
"""

def _read_txt(path: pathlib.Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t").dropna(how="all")

# ─────────────────────────── accounting 전용 전처리
def _pre_accounting(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    accounting data.txt를 DB에 넣기 전에 컬럼/타입/파생값을 표준화합니다.
    - 헤더 공백/한글 BOM 제거 및 통일
    - 금액/일수 등 숫자형 변환(음수 기호 보존, 단독 하이픈만 결측→0)
    - 날짜형 변환
    - '매출집계월' → 집계년/집계월/월초 파생
    - '코스 ID' 별칭, 표준 수강 시작/종료 파생
    - '사업 구분' 별칭, '포맷' 보장
    - 교육과정명 '(B2B_SMB)' 포함 행 제외
    """
    df = df_raw.copy()

    # 1) 헤더 정리
    clean_cols = []
    for c in df.columns:
        cc = str(c).replace("\ufeff", "").strip()
        cc = re.sub(r"\s+", "", cc)
        clean_cols.append(cc)
    df.columns = clean_cols

    # 2) 스키마 통일
    keep_order = [
        "매출집계월","결제일자","코스ID","계약금액","금액검증","사업구분","교육과정명",
        "카테고리","포맷","코스개강일","코스개강일2","코스종강일","수익인식방법","코스일수","일수당결제금액"
    ]
    for k in keep_order:
        if k not in df.columns:
            df[k] = pd.NA
    df = df[keep_order]

    # 3) 숫자형 변환(음수 기호 보존)
    def _to_num(s: pd.Series) -> pd.Series:
        x = (
            s.astype(str)
             .str.replace(",", "", regex=False)
             .str.replace(" ", "", regex=False)
             .str.replace(r"[−–—]", "-", regex=True)
             .str.strip()
        )
        x = x.replace({"": pd.NA})
        x = x.where(~x.isin({"-", "--"}), pd.NA)
        return pd.to_numeric(x, errors="coerce").fillna(0)

    df["계약금액"] = _to_num(df["계약금액"])
    df["코스일수"] = _to_num(df["코스일수"]).astype("Int64")
    df["일수당결제금액"] = _to_num(df["일수당결제금액"])

    # 4) 불리언
    df["금액검증"] = (
        df["금액검증"].astype(str).str.strip().str.upper().map({"TRUE": True, "FALSE": False})
    ).fillna(False)

    # 5) 날짜
    for dcol in ["결제일자","코스개강일","코스개강일2","코스종강일"]:
        df[dcol] = pd.to_datetime(df[dcol], errors="coerce")

    # 6) 매출집계월 파싱
    def _parse_kr_month(x):
        s = str(x)
        m = re.search(r"(\d{2,4})\s*년\s*(\d{1,2})\s*월", s)
        if not m:
            return pd.Series([pd.NA, pd.NA, pd.NaT], index=["집계년","집계월","집계월_월초"])
        y = int(m.group(1))
        if y < 100:
            y += 2000
        mm = int(m.group(2))
        return pd.Series([y, mm, pd.Timestamp(year=y, month=mm, day=1)], index=["집계년","집계월","집계월_월초"])

    extra = df["매출집계월"].apply(_parse_kr_month)
    df = pd.concat([df, extra], axis=1)

    # 7) 키/수강일 파생
    df["코스ID"] = pd.to_numeric(df["코스ID"], errors="coerce")
    df["코스 ID"] = df["코스ID"].astype("Int64")
    df["코스 ID(str)"] = df["코스 ID"].astype(str)
    df["수강시작일"] = df["코스개강일2"].combine_first(df["코스개강일"])
    df["수강종료일"] = df["코스종강일"]

    # 8) 별칭/포맷 보장
    df["사업 구분"] = df["사업구분"]
    if "포맷" not in df.columns:
        df["포맷"] = pd.NA

    # 9) 교육과정명 필터
    df = df[~df["교육과정명"].astype(str).str.contains("(B2B_SMB)", regex=False, na=False)]

    # 10) 표시용 별칭
    df["코스 개강일2"] = df["코스개강일2"]
    df["코스 종강일"] = df["코스종강일"]

    return df

def load_to_db() -> None:
    con = sqlite3.connect(DB)
    try:
        for table, txt in FILES.items():
            if not txt.exists():
                sys.stderr.write(f"[WARN] {txt} not found – skip\n")
                continue
            df = _read_txt(txt)
            if table == "accounting":
                df = _pre_accounting(df)
            df.to_sql(table, con, if_exists="replace", index=False)

        # 인덱스
        con.executescript(SCHEMA_SQL)
        try:
            con.execute('CREATE INDEX IF NOT EXISTS idx_acc_course ON accounting ("코스 ID")')
            con.execute('CREATE INDEX IF NOT EXISTS idx_acc_month  ON accounting ("집계년","집계월")')
        except sqlite3.OperationalError:
            pass

        con.commit()
    finally:
        con.close()

# ─────────────────────────── 캐시 Key (TXT mtime + 코드 변경)
CODE_SIG = "acc-num-sign-fix-2025-09-10"  # 로직 바꿀 때마다 문자열 변경

def _files_sig() -> tuple:
    txt_mtimes = tuple(int(os.path.getmtime(p)) if p.exists() else 0 for p in FILES.values())
    code_mtime = int(os.path.getmtime(__file__))
    return txt_mtimes + (code_mtime, hash(CODE_SIG))

# ─────────────────────────── SQLite 연결 (자동 최신화)
@st.cache_resource
def _conn(sig: tuple) -> sqlite3.Connection:
    load_to_db()
    return sqlite3.connect(DB, check_same_thread=False)

# ─────────────────────────── 공통 후처리
def _post(df: pd.DataFrame) -> pd.DataFrame:
    if "담당자_name" in df.columns:
        df["담당자_name"] = df["담당자_name"].str.replace(r"B$", "", regex=True)
    if "수주 예정액(종합)" in df.columns:
        df["수주 예정액(종합)"] = pd.to_numeric(
            df["수주 예정액(종합)"].astype(str).str.replace(",", ""), errors="coerce"
        ).fillna(0)
    for col in ["생성년도","생성월","수주예정년도","수주예정월"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

def _post_won(df: pd.DataFrame) -> pd.DataFrame:
    df = _post(df)
    if "이름" in df.columns:
        df = df[~df["이름"].astype(str).str.contains("[비매출입과]", regex=False, na=False)]
    return df

def _sig() -> tuple:
    return _files_sig()

@st.cache_data
def _load_all(sig: tuple) -> pd.DataFrame:
    return _post(pd.read_sql_query("SELECT * FROM all_deal", _conn(sig)))

@st.cache_data
def _load_won(sig: tuple) -> pd.DataFrame:
    return _post_won(pd.read_sql_query("SELECT * FROM won_deal", _conn(sig)))

@st.cache_data
def _load_ret(sig: tuple) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM retention", _conn(sig))

def _post_accounting(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for d in ["결제일자","코스개강일","코스개강일2","코스종강일","수강시작일","수강종료일","집계월_월초","코스 개강일2","코스 종강일"]:
        if d in out.columns:
            out[d] = pd.to_datetime(out[d], errors="coerce")
    for n in ["계약금액","일수당결제금액","코스ID","코스 ID"]:
        if n in out.columns:
            out[n] = pd.to_numeric(out[n], errors="coerce")
    if "사업구분" in out.columns and "사업 구분" not in out.columns:
        out["사업 구분"] = out["사업구분"]
    if "포맷" not in out.columns:
        out["포맷"] = pd.NA
    return out

@st.cache_data
def _load_accounting(sig: tuple) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM accounting", _conn(sig))
    return _post_accounting(df)

# 사용자 API
def load_all_deal() -> pd.DataFrame:
    return _load_all(_sig())

def load_won_deal() -> pd.DataFrame:
    return _load_won(_sig())

def load_retention() -> pd.DataFrame:
    return _load_ret(_sig())

def load_accounting() -> pd.DataFrame:
    return _load_accounting(_sig())
