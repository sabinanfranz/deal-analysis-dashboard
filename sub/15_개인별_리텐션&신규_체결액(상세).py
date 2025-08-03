# pages/9_팀별_규모·유형별_체결액.py
import streamlit as st, pandas as pd, re            # 반드시 가장 먼저!
from data import load_won_deal, load_retention

st.set_page_config(page_title="개인별 리텐션 및 신규 체결액(상세)", layout="wide")

# ────────── 조직 매핑 ──────────
TEAM_RAW = {
    '기업교육 1팀': [
        '김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연',
        '강지선','정하영','하승민','이은서','홍제환', '김세연', '오진선'
    ],
    '기업교육 2팀': [
        '박종협','정선희','권노을','강진우','이윤지','김민선','이수빈',
        '강연정','강다현','방신우','정다혜','임재우','손승완',
        '김윤지','손지훈','홍예진'
    ],
}
NAME2TEAM     = {re.sub(r'B$', '', n): t for t, lst in TEAM_RAW.items() for n in lst}
TARGET_TEAMS  = ['기업교육 1팀', '기업교육 2팀']
SIZE_ORDER    = ['대기업','중견기업','중소기업','공공기관','대학교','기타']
TYPE_ORDER    = ['S0','P0','P1','P2','P3','신규']

DETAIL_COLS = [
    '생성년도','생성월','기업명','이름','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net',
    '과정포맷(대)','카테고리(대)'
]

# ────────── 데이터 로드 ──────────
won = load_won_deal()
won['담당자_name'] = won['담당자_name'].str.replace(r'B$', '', regex=True)
won['팀'] = won['담당자_name'].map(NAME2TEAM)

tier_map = load_retention().set_index('기업명')['매출 티어'].to_dict()
map_tier = lambda c: tier_map.get(c) if tier_map.get(c) in TYPE_ORDER[:-1] else '신규'

won = won[
    won['팀'].isin(TARGET_TEAMS) &
    won['수주예정년도'].isin([2024, 2025])
]
won['유형'] = won['기업명'].apply(map_tier)

# ────────── Sidebar ──────────
st.sidebar.header("필터")
sel_team = st.sidebar.selectbox("기업교육 팀", ["전체"] + TARGET_TEAMS, 0)

if sel_team == "전체":
    people = sorted(won['담당자_name'].unique())
else:
    people = sorted(won[won['팀'] == sel_team]['담당자_name'].unique())
sel_person = st.sidebar.selectbox("담당자", ["전체"] + people, 0)

sel_type = st.sidebar.selectbox("대기업 유형(세번째 탭)", TYPE_ORDER, 5)

# ────────── helper ──────────
def tbl_by_size(df):
    return (df.groupby(['기업 규모','수주예정년도'])['수주 예정액(종합)']
              .sum().div(1e8).round(2).reset_index()
              .pivot(index='기업 규모', columns='수주예정년도',
                     values='수주 예정액(종합)').fillna(0)
              .reindex(SIZE_ORDER)
              .rename(columns={2024:'2024', 2025:'2025'}))

def tbl_bigcorp_type(df):
    big = df[df['기업 규모']=='대기업']
    return (big.groupby(['유형','수주예정년도'])['수주 예정액(종합)']
              .sum().div(1e8).round(2).reset_index()
              .pivot(index='유형', columns='수주예정년도',
                     values='수주 예정액(종합)').fillna(0)
              .reindex(TYPE_ORDER)
              .rename(columns={2024:'2024', 2025:'2025'}))

def deal_rows(df, utype):
    rows = df[(df['기업 규모']=='대기업') & (df['유형']==utype)][DETAIL_COLS].copy()
    rows['수주 예정액(종합)'] = (rows['수주 예정액(종합)']/1e8).round(2)
    rows['Net'] = rows['Net'].fillna(0).astype(float).round(2)
    return rows.sort_values(['생성년도','생성월','기업명']).reset_index(drop=True)

def tbl_company_type(df, utype):
    sub = df[df['유형']==utype]
    if utype == '신규':
        sub = sub[sub['기업 규모']=='대기업']
    t = (sub.groupby(['기업명','수주예정년도'])['수주 예정액(종합)']
            .sum().div(1e8).round(2).reset_index()
            .pivot(index='기업명', columns='수주예정년도',
                   values='수주 예정액(종합)').fillna(0)
            .rename(columns={2024:'2024', 2025:'2025'}))
    for col in ['2024','2025']:
        if col not in t.columns:
            t[col] = 0
    return t[['2024','2025']].sort_values(by='2024', ascending=False)

def retention_table(df):
    big = df[df['기업 규모']=='대기업']
    rows=[]
    for u in TYPE_ORDER[:-1]:
        sub = big[big['유형']==u]
        cnt24 = (sub[sub['수주예정년도']==2024]
                 .groupby('기업명')['수주 예정액(종합)'].sum().gt(0).sum())
        cnt25 = (sub[sub['수주예정년도']==2025]
                 .groupby('기업명')['수주 예정액(종합)'].sum().gt(0).sum())
        rate  = (cnt25/cnt24*100) if cnt24 else 0
        rows.append([u,cnt24,cnt25,f"{rate:.1f}%"])
    return (pd.DataFrame(rows,
            columns=['유형','2024 기업수','2025 기업수','리텐션율(%)'])
            .set_index('유형').reindex(TYPE_ORDER[:-1]))

def upsell_table(df):
    big = df[df['기업 규모']=='대기업']
    rows=[]
    for u in TYPE_ORDER[:-1]:
        sub = big[big['유형']==u]
        amt24 = sub[sub['수주예정년도']==2024]['수주 예정액(종합)'].sum()/1e8
        amt25 = sub[sub['수주예정년도']==2025]['수주 예정액(종합)'].sum()/1e8
        rate  = (amt25/amt24*100) if amt24 else 0
        rows.append([u,round(amt24,2),round(amt25,2),f"{rate:.1f}%"])
    return (pd.DataFrame(rows,
            columns=['유형','2024 체결액','2025 체결액','업셀링율(%)'])
            .set_index('유형').reindex(TYPE_ORDER[:-1]))

# ────────── 필터 적용 ──────────
df_filtered = won.copy()
if sel_team != "전체":
    df_filtered = df_filtered[df_filtered['팀'] == sel_team]
if sel_person != "전체":
    df_filtered = df_filtered[df_filtered['담당자_name'] == sel_person]

# ────────── 탭 구성 ──────────
st.title("기업교육 1·2팀 '24-'25 체결액 (억)")

TAB_NAMES = [
    "규모별 체결액",
    "대기업 유형별 체결액",
    "대기업 유형별 딜목록",
    "대기업 유형별 리텐션율",
    "대기업 유형별 업셀링율",
] + [f"{u} (억)" for u in TYPE_ORDER]

tabs = st.tabs(TAB_NAMES)

# 1) 규모별 체결액
with tabs[0]:
    st.dataframe(tbl_by_size(df_filtered), use_container_width=True, hide_index=False)

# 2) 대기업 유형별 체결액
with tabs[1]:
    st.dataframe(tbl_bigcorp_type(df_filtered), use_container_width=True, hide_index=False)

# 3) 대기업 유형별 딜목록 (sel_type)
with tabs[2]:
    st.markdown(f"### 대기업 유형별 딜목록 – {sel_type}")
    st.dataframe(deal_rows(df_filtered, sel_type), use_container_width=True, hide_index=False)

# 4) 리텐션율
with tabs[3]:
    st.dataframe(retention_table(df_filtered), use_container_width=True, hide_index=False)

# 5) 업셀링율
with tabs[4]:
    st.dataframe(upsell_table(df_filtered), use_container_width=True, hide_index=False)

# 6~11) S0~신규 기업별 체결액
for idx, u in enumerate(TYPE_ORDER, start=5):
    with tabs[idx]:
        comp = tbl_company_type(df_filtered, u)
        st.dataframe(comp, use_container_width=True, hide_index=False)
