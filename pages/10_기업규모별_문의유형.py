# pages/18_기업규모별_문의유형.py
import streamlit as st, pandas as pd, numpy as np
from data import load_all_deal

st.set_page_config(page_title="기업 규모별 문의 유형 (2024·2025)", layout="wide")

# ────────── 상수 ──────────
G_SIZE   = ['대기업', '중견기업', '중소기업']
COLS     = ['2024 상반기', '2024 하반기', '2025 상반기', '2025 하반기']

# ────────── 데이터 로드 ──────────
df = load_all_deal()

# ① Convert 제외
df = df[df['상태'] != 'Convert'].copy()

# ② 결측 → '미기재'
df['카테고리(대)'] = df['카테고리(대)'].fillna('미기재')

# ③ 반기 라벨 추가
df['Half'] = np.where(df['생성월'].between(1, 6), '상반기', '하반기')
df['YearHalf'] = df['생성년도'].astype(str) + ' ' + df['Half']

# ────────── 집계 함수 ──────────
def make_table(d: pd.DataFrame) -> pd.DataFrame:
    tbl = (d.groupby(['카테고리(대)', 'YearHalf'])
             .size()
             .unstack(fill_value=0)
             .reindex(columns=COLS, fill_value=0))
    return tbl

# ────────── 탭 출력 ──────────
st.title("기업 규모별 문의 유형 (건수)")

tabs = st.tabs(G_SIZE)
for tab, size in zip(tabs, G_SIZE):
    with tab:
        sub = df[df['기업 규모'] == size]
        st.markdown(f"### {size}")
        st.dataframe(make_table(sub), use_container_width=True, hide_index=False)
