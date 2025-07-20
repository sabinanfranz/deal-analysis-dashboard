# pages/14_팀원별_Net_딜_목록.py
import streamlit as st, pandas as pd, re
from data import load_all_deal

st.set_page_config(page_title="팀원별 Net 딜 목록", layout="wide")

# ────────── 상수 ──────────
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
}
ONLINE_SET = {'선택구매(온라인)', '구독제(온라인)', '포팅'}
NAME2TEAM  = {re.sub(r'B$', '', n): t for t, lst in TEAM_RAW.items() for n in lst}

DETAIL_COLS = [
    '생성년도','생성월','기업명','이름','담당자_name','성사 가능성',
    '수주 예정액(종합)','Net', '수주 예정일(종합)',
    '과정포맷(대)','카테고리(대)'
]

# ────────── 데이터 ──────────
df = load_all_deal()
df['담당자_name'] = (
    df['담당자_name'].fillna('').astype(str)
      .str.replace(r'B$', '', regex=True).str.strip()
)
df['팀'] = df['담당자_name'].map(NAME2TEAM)

df = df[
    ~df['과정포맷(대)'].isin(ONLINE_SET) &
    df['Net'].notna() &
    (df['Net'].astype(str).str.strip() != '')
].copy()

df['수주 예정액(종합)'] = (df['수주 예정액(종합)'] / 1e8).round(2)
df['Net']              = df['Net'].astype(float).round(2)

# ────────── 탭 구성 ──────────

st.title("개인별 NET(%) 추이")

tab_titles = ['1팀 요약','1팀 Deals','2팀 요약','2팀 Deals']
tabs       = st.tabs(tab_titles)

TEAM_KEY = { '1팀':'기업교육 1팀', '2팀':'기업교육 2팀' }

for idx, (code, team_name) in enumerate(TEAM_KEY.items()):
    member_list = TEAM_RAW[team_name]
    team_df     = df[df['팀'] == team_name]

    # 평균 표 ---------------------------
    avg_net = (
        team_df.groupby('담당자_name')['Net']
        .mean().round(2)
        .reindex(member_list)
        .reset_index()
        .rename(columns={'Net':'평균 Net'})
    )

    # -------- 요약 탭 --------
    with tabs[idx*2]:        # 0,2
        st.dataframe(avg_net, use_container_width=True, hide_index=True)

    # -------- Deals 탭 --------
    with tabs[idx*2 + 1]:    # 1,3
        sel = st.selectbox(
            "담당자 선택",
            ['전체'] + member_list,
            key=f"sel_{code}"
        )
        if sel == '전체':
            detail = team_df[DETAIL_COLS].copy()
        else:
            detail = team_df[team_df['담당자_name'] == sel][DETAIL_COLS].copy()

        if detail.empty:
            st.info("표시할 데이터가 없습니다.")
        else:
            st.dataframe(detail.reset_index(drop=True), use_container_width=True, hide_index=True)
