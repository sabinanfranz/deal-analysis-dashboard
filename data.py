import pandas as pd, sqlite3, re
import streamlit as st

DB = "deals.db"  # SQLite 경로
# ────────── 연결 ──────────
@st.cache_resource
def conn():
    return sqlite3.connect(DB, check_same_thread=False)

# ────────── all_deal ──────────
@st.cache_data
def load_all_deal() -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM all_deal", conn())

    df['담당자_name'] = df['담당자_name'].str.replace(r'B$', '', regex=True)
    df['수주 예정액(종합)'] = pd.to_numeric(
        df['수주 예정액(종합)'].astype(str).str.replace(',', ''), errors='coerce'
    ).fillna(0)

    # 생성 · 수주 예정 필드 정수 변환
    df = df.dropna(subset=['생성년도', '생성월', '수주예정년도', '수주예정월'])
    df[['생성년도', '생성월', '수주예정년도', '수주예정월']] = (
        df[['생성년도', '생성월', '수주예정년도', '수주예정월']].astype(int)
    )

    df['예정월'] = (
        df['수주예정년도'].astype(str) + '-' +
        df['수주예정월'].astype(str).str.zfill(2)
    )
    return df

# ────────── won_deal ──────────
@st.cache_data
def load_won_deal() -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM won_deal", conn())

    df['담당자_name'] = df['담당자_name'].str.replace(r'B$', '', regex=True)
    df['수주 예정액(종합)'] = pd.to_numeric(
        df['수주 예정액(종합)'].astype(str).str.replace(',', ''), errors='coerce'
    ).fillna(0)

    df = df.dropna(subset=['생성년도', '생성월', '수주예정년도', '수주예정월'])
    df[['생성년도', '생성월', '수주예정년도', '수주예정월']] = (
        df[['생성년도', '생성월', '수주예정년도', '수주예정월']].astype(int)
    )

    df['예정월'] = (
        df['수주예정년도'].astype(str) + '-' +
        df['수주예정월'].astype(str).str.zfill(2)
    )
    return df

# ────────── retention ──────────
@st.cache_data
def load_retention() -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM retention", conn())
