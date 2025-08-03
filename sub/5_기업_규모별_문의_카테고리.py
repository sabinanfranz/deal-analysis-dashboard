# pages/18_기업규모별_문의유형.py
"""
기업 규모별 문의 유형 (2024·2025)
- 반기별 집계 (기존)
- 월별 집계: 2024-01 ~ 2025-12
- 카테고리(대) 행 순서 고정
"""

import streamlit as st
import pandas as pd
import numpy as np
from data import load_all_deal

st.set_page_config(page_title="기업 규모별 문의 유형 (2024·2025)", layout="wide")

# ────────── 상수 ──────────
G_SIZE = ['대기업', '중견기업', '중소기업']
HALF_COLS = ['2024 상반기', '2024 하반기', '2025 상반기', '2025 하반기']
BASE_ROWS = [
    '생성형 AI',
    '자유입과(온라인)',
    'DX',
    '스킬',
    '직무별 교육',
    '리더십',
    '기타',
    '미기재',
]
ROW_ORDER = ['전체 합계'] + BASE_ROWS
# 월 컬럼(2024-01 ~ 2025-12)
MONTH_COLS = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1,13)]

# ────────── 데이터 로드 / 전처리 ──────────
df = load_all_deal()

# ① Convert 제외
df = df[df['상태'] != 'Convert'].copy()

# ② 결측 → 미기재
df['카테고리(대)'] = df['카테고리(대)'].fillna('미기재')

# ③ 반기 라벨
df['Half'] = np.where(df['생성월'].between(1,6), '상반기', '하반기')
df['YearHalf'] = df['생성년도'].astype(str) + ' ' + df['Half']

# ④ 월 라벨
df['YearMonth'] = df['생성년도'].astype(str) + '-' + df['생성월'].astype(int).astype(str).str.zfill(2)

# ────────── 집계 함수 ──────────

def tbl_half(sub: pd.DataFrame) -> pd.DataFrame:
    body = (sub.groupby(['카테고리(대)','YearHalf']).size()
              .unstack(fill_value=0)
              .reindex(columns=HALF_COLS, fill_value=0)
              .reindex(BASE_ROWS, fill_value=0))
    total = pd.DataFrame(body.sum(axis=0)).T
    total.index = ['전체 합계']
    t = pd.concat([total, body]).reindex(ROW_ORDER, fill_value=0)
    return t


def tbl_month(sub: pd.DataFrame) -> pd.DataFrame:
    body = (sub.groupby(['카테고리(대)','YearMonth']).size()
              .unstack(fill_value=0)
              .reindex(columns=MONTH_COLS, fill_value=0)
              .reindex(BASE_ROWS, fill_value=0))
    total = pd.DataFrame(body.sum(axis=0)).T
    total.index = ['전체 합계']
    t = pd.concat([total, body]).reindex(ROW_ORDER, fill_value=0)
    return t

# ────────── UI ──────────
st.title("기업 규모별 문의 유형 (건수)")

tabs = st.tabs(G_SIZE)
for tab, size in zip(tabs, G_SIZE):
    with tab:
        sub = df[df['기업 규모'] == size]
        st.markdown(f"### {size} – 반기별")
        st.dataframe(tbl_half(sub), use_container_width=True, hide_index=False)

        st.markdown(f"### {size} – 월별 (2024-01 ~ 2025-12)")
        st.dataframe(tbl_month(sub), use_container_width=True, hide_index=False)
