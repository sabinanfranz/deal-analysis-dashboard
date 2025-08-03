# pages/8_기타_담당자_체결액.py
"""
퇴사자 체결액 추이 대시보드
- 2023·2024·2025 연도별 체결액 요약 (담당자_name 포함)
- 각 연도별 퇴사자 딜 리스트 (담당자 필터 반영)
- 담당자 선택 시 상세 딜 목록
"""

import re
import streamlit as st  # Streamlit 반드시 먼저
import pandas as pd
from data import load_won_deal

st.set_page_config(page_title="퇴사자 체결액 추이", layout="wide")

# ────────── 조직 매핑 (퇴사자 제외) ──────────
TEAM_RAW = {
    '기업교육 1팀': ['김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연','강지선','정하영','하승민','이은서','홍제환'],
    '기업교육 2팀': ['박종협','정선희','권노을','강진우','이윤지','김민선','이수빈','강연정','강다현','방신우','정다혜','임재우','손승완','김윤지','손지훈','홍예진'],
    '공공사업그룹': ['채선영','황인후','김미송','이준석','김다인'],
}
NAME2TEAM = {re.sub(r'B$','', n): t for t, lst in TEAM_RAW.items() for n in lst}

# ────────── 상수 ──────────
DETAIL_COLS = [
    '생성년도','생성월','담당자_name','기업명','이름','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net',
    '과정포맷(대)','카테고리(대)'
]
YEARS = [2025, 2024, 2023]  # 출력 순서

# ────────── 데이터 로드 ──────────
df = load_won_deal()
df['담당자_name'] = df['담당자_name'].str.replace(r'B$', '', regex=True)
df['팀'] = df['담당자_name'].map(NAME2TEAM)

# 팀 None → 퇴사자/기타
extra = df[df['팀'].isna() & df['수주예정년도'].isin(YEARS)].copy()

# ────────── 연도별 집계 ──────────
year_tbl = (
    extra.groupby(['담당자_name','수주예정년도'])['수주 예정액(종합)']
         .sum().div(1e8).round(2).reset_index()
         .pivot(index='담당자_name', columns='수주예정년도', values='수주 예정액(종합)')
         .fillna(0)
         .rename(columns={2023:'2023년', 2024:'2024년', 2025:'2025년'})
         .sort_values(by=['2025년','2024년','2023년'], ascending=[False]*3)
         .reset_index()  # 담당자_name 컬럼 유지
)

# ────────── Sidebar ──────────
st.sidebar.header("기타 담당자 상세")
all_people = sorted(extra['담당자_name'].unique())
person_sel = st.sidebar.selectbox("담당자", ["전체"] + all_people)

# ────────── helper ──────────

def make_detail(data: pd.DataFrame) -> pd.DataFrame:
    d = data.sort_values(['생성년도','생성월','기업명'])[DETAIL_COLS].copy().reset_index(drop=True)
    num_cols = d.select_dtypes(include='number').columns.difference(['Net'])
    d[num_cols] = d[num_cols].fillna(0).astype(int).astype(str)
    d['Net'] = d['Net'].fillna(0).astype(float).round(2).map(lambda x: f"{x:.2f}")
    return d

# ────────── 출력 ──────────
st.title("퇴사자 딜카드 체결액 (억)")

st.markdown("### 연도별 체결액 요약")
st.dataframe(year_tbl, use_container_width=True, hide_index=True)

# ────────── 각 연도별 퇴사자 딜 리스트 ──────────
for yr in YEARS:
    base = extra[extra['수주예정년도'] == yr]
    lst = base if person_sel == "전체" else base[base['담당자_name'] == person_sel]
    st.markdown(f"### {yr}년 퇴사자 딜 리스트")
    if lst.empty:
        st.info(f"조건에 맞는 {yr}년 딜이 없습니다.")
    else:
        st.dataframe(make_detail(lst), use_container_width=True, hide_index=True)

# ────────── 선택 담당자 상세 ──────────
if person_sel != "전체":
    sel_data = extra[extra['담당자_name'] == person_sel]
    if sel_data.empty:
        st.info("해당 담당자의 2023~2025 체결 데이터가 없습니다.")
    else:
        st.markdown(f"### {person_sel} 상세 딜 목록 (2023~2025)")
        st.dataframe(make_detail(sel_data), use_container_width=True, hide_index=True)
