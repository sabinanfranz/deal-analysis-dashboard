# pages/10_팀별_구성원_집계.py
"""
팀 구성원별 집계 (억 / 기업 수)
────────────────────────────────────────
필터 : 팀(기업교육 1팀, 기업교육 2팀) 선택
"""
import streamlit as st, pandas as pd, re            # 반드시 가장 먼저!
st.set_page_config(page_title="개인별 리텐션 및 신규 체결액(요약)", layout="wide")

from data import load_won_deal, load_retention

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
}
NAME2TEAM = {re.sub(r'B$', '', n): t for t, lst in TEAM_RAW.items() for n in lst}
TEAM_LIST = list(TEAM_RAW.keys())

# ────────── 데이터 ──────────
won = load_won_deal()
won['담당자_name'] = won['담당자_name'].str.replace(r'B$', '', regex=True)
won['팀'] = won['담당자_name'].map(NAME2TEAM)

tier_map   = load_retention().set_index('기업명')['매출 티어'].to_dict()
TYPE_ORDER = ['S0','P0','P1','P2','P3','신규']
won        = won[won['수주예정년도'].isin([2024, 2025])]
won['유형'] = won['기업명'].apply(
    lambda c: tier_map.get(c) if tier_map.get(c) in TYPE_ORDER[:-1] else '신규'
)

# ────────── Sidebar ──────────
st.sidebar.header("팀 선택")
sel_team = st.sidebar.selectbox("기업교육 팀", TEAM_LIST)

df_team      = won[won['팀'] == sel_team]
MEMBER_ORDER = TEAM_RAW[sel_team]

# ────────── 집계 ──────────
def _sum(df, cond):
    return round(df[cond]['수주 예정액(종합)'].sum() / 1e8, 2)

def _cnt(df, cond):
    return (df[cond].groupby('기업명')['수주 예정액(종합)'].sum().gt(0).sum())

tbl1, tbl2, tbl3 = [], [], []
for member in MEMBER_ORDER:
    sub = df_team[df_team['담당자_name'] == member]

    tbl1.append([
        member,
        _sum(sub, (sub['기업 규모']=='대기업') & (sub['수주예정년도']==2024)),
        _sum(sub, (sub['기업 규모']=='대기업') & (sub['수주예정년도']==2025) & (sub['유형']!='신규')),
        _sum(sub, (sub['기업 규모']=='대기업') & (sub['수주예정년도']==2025) & (sub['유형']=='신규')),
    ])
    tbl2.append([
        member,
        _sum(sub, (sub['기업 규모']=='중견기업') & (sub['수주예정년도']==2024)),
        _sum(sub, (sub['기업 규모']=='중견기업') & (sub['수주예정년도']==2025)),
        _sum(sub, (sub['기업 규모']=='중소기업') & (sub['수주예정년도']==2024)),
        _sum(sub, (sub['기업 규모']=='중소기업') & (sub['수주예정년도']==2025)),
    ])
    tbl3.append([
        member,
        _cnt(sub, (sub['기업 규모']=='대기업') & (sub['수주예정년도']==2024) & (sub['유형']!='신규')),
        _cnt(sub, (sub['기업 규모']=='대기업') & (sub['수주예정년도']==2025) & (sub['유형']!='신규')),
        _cnt(sub, (sub['기업 규모']=='대기업') & (sub['수주예정년도']==2025) & (sub['유형']=='신규')),
    ])

df1 = pd.DataFrame(tbl1, columns=['담당자','24 대기업','25 리텐션(대)','25 신규(대)']).set_index('담당자')
df2 = pd.DataFrame(tbl2, columns=['담당자','24 중견','25 중견','24 중소','25 중소']).set_index('담당자')
df3 = pd.DataFrame(tbl3, columns=['담당자','24 리텐션 대기업','25 리텐션 대기업','25 신규 대기업']).set_index('담당자')

# ────────── 탭 출력 ──────────
st.title(f" {sel_team}")

tab_titles = [
    "대기업 체결액 요약 (억)",
    "중견·중소 체결액 요약 (억)",
    "리텐션 및 신규 기업 수 (개)"
]
tabs = st.tabs(tab_titles)

with tabs[0]:
    st.dataframe(df1, use_container_width=True)

with tabs[1]:
    st.dataframe(df2, use_container_width=True)

with tabs[2]:
    st.dataframe(df3, use_container_width=True)