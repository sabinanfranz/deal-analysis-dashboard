# pages/기업구분별_체결액.py
"""
기업 구분별 체결액 대시보드 – 오류 수정
- 검색 필터 + 리셋 버튼 (SessionState 오류·no‑op 해결)
- Won Deal, 2025년 Won 제외 All Deal 리스트 출력 (정렬·중복 제거)
"""

import streamlit as st
import pandas as pd
from data import load_won_deal, load_retention, load_all_deal

# ────────── Page Config ──────────
st.set_page_config(page_title="기업 구분별 체결액", layout="wide")

# ────────── 상수 ──────────
TYPE_ORDER = ['S0', 'P0', 'P1', 'P2', 'P3']
ONLINE_FMT = ['선택구매(온라인)', '구독제(온라인)', '포팅']
DETAIL_COLS = [
    '생성년도','생성월','기업명','기업 규모','담당자_name','소속 상위 조직','이름','상태','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net','수강시작일','수강종료일',
    '과정포맷(대)','카테고리(대)'
]
YEARS = [2023, 2024, 2025]
STATUS_ORDER = ['확정','높음','낮음','LOST']

# ────────── 데이터 로드 ──────────
won = load_won_deal()
retention = load_retention()
all_deal_raw = load_all_deal()

# All Deal: retention corp & 생성년도 2025만
all_deal = all_deal_raw[(all_deal_raw['기업명'].isin(retention['기업명'])) & (all_deal_raw['생성년도'] == 2025)].copy()

# Won 데이터 전처리
won = won[(won['수주예정년도'].isin(YEARS)) & (won['기업명'].isin(retention['기업명']))].copy()
won['유형'] = won['기업명'].map(lambda c: retention.set_index('기업명')['매출 티어'].get(c) if retention.set_index('기업명')['매출 티어'].get(c) in TYPE_ORDER else '신규')
won = won[won['유형'].isin(TYPE_ORDER)].copy()

# ────────── Sidebar – 검색 ──────────
st.sidebar.header('필터')
search_query = st.sidebar.text_input('기업명 검색', key='search_query')
st.sidebar.caption('텍스트 삭제 후 Enter 시 리셋')

q = search_query.strip()
if q:
    won_filtered = won[won['기업명'] == q].copy()
    all_filtered = all_deal[all_deal['기업명'] == q].copy()
else:
    won_filtered = won.copy()
    all_filtered = all_deal.copy()
    all_filtered = all_deal.copy()

# ────────── 요약 테이블 ──────────

def make_company_type_table(data: pd.DataFrame) -> pd.DataFrame:
    g = data.groupby(['유형','기업명','기업 규모','수주예정년도'])['수주 예정액(종합)'].sum().reset_index()
    pv = g.pivot_table(index=['유형','기업명','기업 규모'], columns='수주예정년도', values='수주 예정액(종합)', fill_value=0)
    pv = (pv/1e8).round(2).reset_index().rename(columns={2023:'2023년 체결액', 2024:'2024년 체결액', 2025:'2025년 체결액', '유형':'기업 구분'})
    for y in YEARS:
        col = f'{y}년 체결액'
        if col not in pv.columns:
            pv[col] = 0.0
    pv['기업 구분'] = pd.Categorical(pv['기업 구분'], categories=TYPE_ORDER, ordered=True)
    pv = pv.sort_values(['기업 구분','2024년 체결액'], ascending=[True, False]).reset_index(drop=True)
    pv.insert(0, 'No.', range(1, len(pv)+1))
    return pv[['No.','기업 구분','기업명','기업 규모','2023년 체결액','2024년 체결액','2025년 체결액']]

# ────────── 딜 리스트 함수 ──────────

def deal_list(df: pd.DataFrame, year: int, online: bool) -> pd.DataFrame:
    sub = df[df['수주예정년도'] == year].copy()
    sub = sub[sub['과정포맷(대)'].isin(ONLINE_FMT)] if online else sub[~sub['과정포맷(대)'].isin(ONLINE_FMT)]
    if sub.empty:
        return pd.DataFrame(columns=[c for c in DETAIL_COLS if c in sub.columns])
    return sub[[c for c in DETAIL_COLS if c in sub.columns]].sort_values(['기업명','생성월']).reset_index(drop=True)

# ────────── Main 출력 ──────────
st.title('기업 구분별 체결액 (억원)')

st.markdown('### 23·24·25 체결액 요약')
st.dataframe(make_company_type_table(won_filtered), use_container_width=True, hide_index=True)

# Won 전체 key (23~25, 출강·온라인)
JOIN_COLS = ['기업명','과정포맷(대)','수주 예정일(종합)','수주 예정액(종합)','이름']
won_keys_all = won_filtered[JOIN_COLS].drop_duplicates()

ORDER = [(2023, False), (2024, False), (2025, False), (2023, True), (2024, True), (2025, True)]
for yr, online in ORDER:
    lbl = '온라인' if online else '출강'
    df_won = deal_list(won_filtered, yr, online)
    st.markdown(f"#### {yr}년 {lbl} Won Deal 리스트")
    st.dataframe(df_won, use_container_width=True, hide_index=True)

    if yr == 2025:
        df_all = all_filtered.copy()
        df_all = df_all[df_all['과정포맷(대)'].isin(ONLINE_FMT)] if online else df_all[~df_all['과정포맷(대)'].isin(ONLINE_FMT)]
        df_rem = df_all.merge(won_keys_all, on=JOIN_COLS, how='left', indicator=True)
        df_rem = df_rem[df_rem['_merge']=='left_only'].drop(columns='_merge')
        if '성사 가능성' in df_rem.columns:
            df_rem['성사 가능성'] = pd.Categorical(df_rem['성사 가능성'].fillna(''), categories=STATUS_ORDER, ordered=True)
            df_rem.sort_values(['성사 가능성','기업명','생성월'], inplace=True)
        cols_show = [c for c in DETAIL_COLS if c in df_rem.columns]
        st.markdown(f"#### 2025년 {lbl} Won 제외 All Deal 리스트")
        st.dataframe(df_rem[cols_show].reset_index(drop=True), use_container_width=True, hide_index=True)
