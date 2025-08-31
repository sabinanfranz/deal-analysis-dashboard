"""
기업교육 1·2팀 담당자별 성사 가능성 대시보드 (간소화, 2025년)
- 요약표(팀 탭): 항상 팀원 전체 표시(담당자 필터 영향 없음)
- 담당자 필터: 요약표 아래에 위치, '상세 표(높음/낮음/미기재/LOST)'에만 적용
- 사업부 탭: 팀 레벨 요약표(1팀/2팀), 상세 표는 1+2팀 합산으로 표시
- 상태 체계: '높음','낮음','미기재','LOST'만 사용
- '리소스 현황' = 높음 + 낮음 + 미기재, '중견중소 현황' 유지
"""

import re
import streamlit as st
import pandas as pd
from data import load_all_deal

# ────────── 설정 ──────────
st.set_page_config(page_title="담당자별 성사 가능성(간소화)", layout="wide")

# ────────── 팀 매핑 ──────────
TEAM_RAW = {
    '기업교육 1팀': [
        '김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연',
        '강지선','정하영','하승민','이은서','홍제환','김세연','오진선'
    ],
    '기업교육 2팀': [
        '박종협','정선희','권노을','강진우','이윤지','김민선','이수빈','강연정',
        '강다현','방신우','정다혜','임재우','송승희','손승완','김윤지','손지훈','홍예진'
    ],
}
NAME2TEAM = {re.sub(r'B$','', n): t for t, lst in TEAM_RAW.items() for n in lst}
TEAMS = list(TEAM_RAW.keys())
NAME_ORDER = {name: idx for team in TEAMS for idx, name in enumerate(TEAM_RAW[team])}

# ────────── 상수 ──────────
SHOW_STATUS = ['높음','낮음','미기재','LOST']   # 화면 노출 상태
RES_STATUS  = ['높음','낮음','미기재']          # 리소스 현황 산식
ROW_ORDER   = ['리소스 현황','중견중소 현황'] + SHOW_STATUS
DETAIL_COLS = [
    '생성년도','생성월','기업명','기업 규모','담당자_name','이름','상태','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net','수강시작일','수강종료일',
    '과정포맷(대)','카테고리(대)'
]
ONLINE_FMT = ['선택구매(온라인)','구독제(온라인)','포팅']

# ────────── 데이터 로드/전처리 ──────────
df = load_all_deal()
df['담당자_name'] = df['담당자_name'].astype(str).str.replace(r'B$','', regex=True).str.strip()
df['팀'] = df['담당자_name'].map(NAME2TEAM)

# 기간: 2024.10 ~ 2025.12
df['생성월'] = pd.to_numeric(df['생성월'], errors='coerce')
df = df[
    df['팀'].isin(TEAMS) &
    (
        ((df['생성년도'] == 2024) & (df['생성월'] >= 10)) |
        ((df['생성년도'] == 2025) & (df['생성월'] <= 12))
    )
].copy()

# 결측 방지
df['과정포맷(대)'] = df['과정포맷(대)'].fillna('').astype(str).str.strip()
df['기업 규모']   = df['기업 규모'].fillna('').astype(str).str.strip()

# 성사 가능성 정규화 (확정류는 화면 미표시지만 정규화는 유지)
def norm_status(x: str):
    if pd.isna(x) or str(x).strip() == '':
        return '미기재'
    t = str(x).strip(); tl = t.lower()
    if tl in ['won','w','확정','confirmed']: return '확정'  # 화면에서는 미사용
    if tl in ['높음','high']:                 return '높음'
    if tl in ['낮음','low']:                  return '낮음'
    if tl in ['lost','lose','l']:             return 'LOST'
    return t

df['성사 가능성'] = df['성사 가능성'].apply(norm_status)

# ────────── Helper ──────────
def team_all_persons(team_name: str) -> list[str]:
    """팀 정의상 전체 구성원(데이터 유무 무관)."""
    return TEAM_RAW.get(team_name, [])

def _person_order(names: list[str]) -> list[str]:
    return sorted(names, key=lambda x: NAME_ORDER.get(x, 9999))

# ────────── 요약표(팀 레벨) ──────────
def summary_matrix_team(dept_df: pd.DataFrame) -> pd.DataFrame:
    """행=카운트 항목, 열=팀(1팀/2팀)."""
    base = dept_df[dept_df['성사 가능성'].isin(SHOW_STATUS)].copy()
    stat = base.groupby(['팀','성사 가능성']).size().unstack(fill_value=0)

    # 누락 상태 보강
    for stt in SHOW_STATUS:
        if stt not in stat.columns:
            stat[stt] = 0

    # 리소스 현황
    stat['리소스 현황'] = stat[RES_STATUS].sum(axis=1)

    # 중견중소 현황 (오프라인 & 중견/중소 & 상태 ∈ RES_STATUS)
    mask = (
        ~dept_df['과정포맷(대)'].isin(ONLINE_FMT) &
        dept_df['기업 규모'].isin(['중견기업','중소기업']) &
        dept_df['성사 가능성'].isin(RES_STATUS)
    )
    mid_cnt = dept_df[mask].groupby('팀').size()
    stat['중견중소 현황'] = mid_cnt

    stat = stat.reindex(TEAMS).fillna(0).astype(int)
    mat = stat[['리소스 현황','중견중소 현황'] + SHOW_STATUS].T  # 행: 항목, 열: 팀
    return mat.astype('Int64')

# ────────── 요약표(담당자 레벨) ──────────
def summary_matrix_people(team_df: pd.DataFrame, team_name: str) -> pd.DataFrame:
    """행=카운트 항목, 열=담당자(팀원 전체). 필터 영향 없음."""
    persons = team_all_persons(team_name)
    base = team_df[team_df['성사 가능성'].isin(SHOW_STATUS)].copy()
    stat = base.groupby(['담당자_name','성사 가능성']).size().unstack(fill_value=0)

    for stt in SHOW_STATUS:
        if stt not in stat.columns:
            stat[stt] = 0

    stat['리소스 현황'] = stat[RES_STATUS].sum(axis=1)

    mask = (
        ~team_df['과정포맷(대)'].isin(ONLINE_FMT) &
        team_df['기업 규모'].isin(['중견기업','중소기업']) &
        team_df['성사 가능성'].isin(RES_STATUS)
    )
    mid_cnt = team_df[mask].groupby('담당자_name').size()
    stat['중견중소 현황'] = mid_cnt

    persons_ord = _person_order(persons)
    stat = stat.reindex(persons_ord).fillna(0).astype(int)
    mat = stat[['리소스 현황','중견중소 현황'] + SHOW_STATUS].T  # 행: 항목, 열: 담당자
    return mat.astype('Int64')

# ────────── 상세 표 ──────────
def detail_df(team_like_df: pd.DataFrame, persons: list[str] | None, status: str) -> pd.DataFrame:
    """status 상세표. persons가 None이면 (사업부 탭) 전 팀 합산."""
    if status not in SHOW_STATUS:
        return pd.DataFrame(columns=DETAIL_COLS)
    sub = team_like_df[team_like_df['성사 가능성'] == status].copy()
    if persons is not None:  # 팀 탭에서 담당자 필터 적용
        sub = sub[sub['담당자_name'].isin(persons)]
    if sub.empty:
        return pd.DataFrame(columns=DETAIL_COLS)
    # 정렬: 팀 → 담당자 → 생성월 → 기업명
    sub['team_rank'] = sub['팀'].map(lambda t: TEAMS.index(t) if t in TEAMS else 999)
    sub['name_rank'] = sub['담당자_name'].map(NAME_ORDER)
    sub = sub.sort_values(['team_rank','name_rank','생성월','기업명'])
    return sub.drop(columns=['team_rank','name_rank'])[DETAIL_COLS]

# ────────── UI ──────────
st.title('담당자별 성사 가능성 – 2025년 (간소화)')

tab_bu, tab_t1, tab_t2 = st.tabs(['사업부', '1팀(연간)', '2팀(연간)'])

# ────────── 탭 1: 사업부 (팀 요약표 + 전사 상세)
with tab_bu:
    dept_df = df[df['팀'].isin(TEAMS)].copy()

    st.subheader('요약 표 (팀 레벨: 기업교육 1팀 / 기업교육 2팀)')
    mat_team = summary_matrix_team(dept_df)
    st.dataframe(mat_team, use_container_width=True)

    st.markdown('---')
    st.subheader('상세 표 (1팀 + 2팀 합산)')
    for stt in SHOW_STATUS:
        st.markdown(f"#### {stt} 상세")
        sub = detail_df(dept_df, persons=None, status=stt)  # 전 팀 합산
        st.dataframe(sub, use_container_width=True, hide_index=True)

# ────────── 탭 2: 1팀 (요약표→담당자 필터→상세)
with tab_t1:
    team = '기업교육 1팀'
    team_df = df[df['팀'] == team].copy()
    persons_all = team_all_persons(team)

    st.subheader('요약 표 (x=담당자 / y=카운트 항목) — 팀원 전체')
    mat = summary_matrix_people(team_df, team)
    st.dataframe(mat, use_container_width=True)

    st.markdown('---')
    sel = st.selectbox('담당자 필터', ['전체'] + persons_all, 0, key='t1_filter')
    persons_sel = persons_all if sel == '전체' else [sel]

    for stt in SHOW_STATUS:
        st.markdown(f"#### {stt} 상세")
        sub = detail_df(team_df, persons=persons_sel, status=stt)
        st.dataframe(sub, use_container_width=True, hide_index=True)

# ────────── 탭 3: 2팀 (요약표→담당자 필터→상세)
with tab_t2:
    team = '기업교육 2팀'
    team_df = df[df['팀'] == team].copy()
    persons_all = team_all_persons(team)

    st.subheader('요약 표 (x=담당자 / y=카운트 항목) — 팀원 전체')
    mat = summary_matrix_people(team_df, team)
    st.dataframe(mat, use_container_width=True)

    st.markdown('---')
    sel = st.selectbox('담당자 필터', ['전체'] + persons_all, 0, key='t2_filter')
    persons_sel = persons_all if sel == '전체' else [sel]

    for stt in SHOW_STATUS:
        st.markdown(f"#### {stt} 상세")
        sub = detail_df(team_df, persons=persons_sel, status=stt)
        st.dataframe(sub, use_container_width=True, hide_index=True)
