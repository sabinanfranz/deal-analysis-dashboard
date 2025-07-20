import streamlit as st, pandas as pd, re
from data import load_won_deal                      # won_deal 로더

# ────────── 조직 매핑 ──────────
TEAM_RAW = {
    '기업교육 1팀': [
        '김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연',
        '강지선','정하영','하승민','이은서','홍제환'
    ],
    '기업교육 2팀': [
        '박종협','정선희','권노을','강진우','이윤지','김민선','이수빈',
        '강연정','강다현','방신우','정다혜','임재우','손승완',
        '김윤지','손지훈','홍예진'
    ],
    '공공사업그룹': ['채선영','황인후','김미송','이준석','김다인'],
}
teams      = {t: [re.sub(r'B$', '', n) for n in lst] for t, lst in TEAM_RAW.items()}
NAME2TEAM  = {n: t for t, lst in teams.items() for n in lst}
ROW_ORDER  = list(teams.keys()) + ['기타', '합계']           # 행 순서

# ────────── 데이터 ──────────
df = load_won_deal()
df = df[df['수주예정년도'] >= 2024]                       # 2024년부터
df['팀'] = df['담당자_name'].map(NAME2TEAM).fillna('기타')

# ────────── 집계 ──────────
# 연도별
yr = (
    df.groupby(['팀', '수주예정년도'])['수주 예정액(종합)'].sum() / 1e8
).round(2).reset_index()

year_tbl = (
    yr.pivot(index='팀', columns='수주예정년도', values='수주 예정액(종합)')
      .fillna(0).sort_index(axis=1)
)
year_tbl.loc['합계'] = year_tbl.sum()
year_tbl = year_tbl.reindex(ROW_ORDER).dropna(how='all').reset_index().rename(columns={'index':'팀'})

# 2025년 월별
mo = (
    df[df['수주예정년도'] == 2025]
      .groupby(['팀', '예정월'])['수주 예정액(종합)'].sum() / 1e8
).round(2).reset_index()

month_tbl = (
    mo.pivot(index='팀', columns='예정월', values='수주 예정액(종합)')
      .fillna(0).sort_index(axis=1)
)
month_tbl.columns = [str(c) for c in month_tbl.columns]
month_tbl.loc['합계'] = month_tbl.sum()
month_tbl = month_tbl.reindex(ROW_ORDER).dropna(how='all').reset_index().rename(columns={'index':'팀'})

# ────────── 출력 ──────────
st.markdown("## 사업부 체결액 추이")                     # h2

st.markdown("### '24-'25 연도별 체결액 (억)")            # h3
st.dataframe(year_tbl, use_container_width=True, hide_index=True)

st.markdown("### 2025년 월별 체결액 (억)")               # h3
st.dataframe(month_tbl, use_container_width=True, hide_index=True)
