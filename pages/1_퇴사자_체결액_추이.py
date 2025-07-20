# pages/8_기타_담당자_체결액.py

import streamlit as st            # 1) 반드시 가장 먼저!

st.set_page_config(page_title="퇴사자 체결액 추이", layout="wide")

import pandas as pd, re
from data import load_won_deal                     # won_deal DB 로더

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
NAME2TEAM = {re.sub(r'B$', '', n): t for t, lst in TEAM_RAW.items() for n in lst}

DETAIL_COLS = [
    '생성년도','생성월','기업명','이름','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net',
    '과정포맷(대)','카테고리(대)'
]

# ────────── won_deal 데이터 ──────────
df = load_won_deal()
df['담당자_name'] = df['담당자_name'].str.replace(r'B$', '', regex=True)
df['팀'] = df['담당자_name'].map(NAME2TEAM).fillna('기타')

extra = df[df['팀'] == '기타']                        # 팀 미배정 인원
extra = extra[extra['수주예정년도'].isin([2023, 2024, 2025])]

# ────────── 연도별 집계 ──────────
year_tbl = (
    extra.groupby(['담당자_name','수주예정년도'])['수주 예정액(종합)'].sum()
         .div(1e8).round(2).reset_index()
         .pivot(index='담당자_name', columns='수주예정년도', values='수주 예정액(종합)')
         .fillna(0)
         .rename(columns={2023:'2023년', 2024:'2024년', 2025:'2025년'})
)

# 정렬: 2025 ↓, 2024 ↓, 2023 ↓
year_tbl = year_tbl.sort_values(
    by=['2025년','2024년','2023년'],
    ascending=[False,False,False]
)

# ────────── Sidebar ──────────
st.sidebar.header("기타 담당자 상세")
person_sel = st.sidebar.selectbox(
    "담당자", ["전체"] + sorted(year_tbl.index.tolist())
)

# ────────── 상세 표 helper ──────────
def make_detail(data: pd.DataFrame) -> pd.DataFrame:
    d = (
        data.sort_values(['생성년도','생성월','기업명'])[DETAIL_COLS]
          .copy().reset_index(drop=True)
    )
    int_cols = d.select_dtypes(include='number').columns.difference(['Net'])
    d[int_cols] = d[int_cols].fillna(0).astype(int).astype(str)
    d['Net'] = d['Net'].fillna(0).astype(float).round(2).map(lambda x: f"{x:.2f}")
    return d

# ────────── 출력 ──────────
st.title("퇴사자 딜카드 체결액 (억)")
st.dataframe(year_tbl, use_container_width=True)

# 선택한 담당자 상세
if person_sel != "전체":
    sub = extra[extra['담당자_name'] == person_sel]
    if not sub.empty:
        st.markdown(f"### {person_sel} 상세 딜 목록")
        st.dataframe(make_detail(sub), use_container_width=True, hide_index=True)
    else:
        st.info("해당 담당자의 2023~2025 체결 데이터가 없습니다.")