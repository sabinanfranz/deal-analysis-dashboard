# pages/4_개인별_체결액_추이.py
import streamlit as st, pandas as pd, re
from data import load_won_deal

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
TEAM_LIST = list(TEAM_RAW.keys())

SIZE_ORDER     = ['합계', '대기업', '중견기업', '중소기업']
PRIMARY_TYPES  = ['직접 교육 문의', '리텐션']         # 우선 순서

# ────────── 데이터 ──────────
df = load_won_deal()
df = df[df['수주예정년도'] == 2025]                         # 2025년만
df['팀'] = df['담당자_name'].map(NAME2TEAM).fillna('기타')
df['예정월'] = df['수주예정월'].astype(int).astype(str).str.zfill(2)
MONTHS = sorted(df['예정월'].unique())                     # 고정 x축

# ────────── Sidebar 필터 ──────────
st.sidebar.header("개인별 체결액 추이")

sel_team = st.sidebar.selectbox("팀", TEAM_LIST)
candidates = sorted(TEAM_RAW[sel_team])
sel_person = st.sidebar.selectbox("개인", ["전체"] + candidates)

df_team = df[df['팀'] == sel_team]
df_target = df_team if sel_person == "전체" else df_team[df_team['담당자_name'] == sel_person]

# ────────── helper ──────────
def pivot_sum(data: pd.DataFrame, idx: str) -> pd.DataFrame:
    p = (
        data.groupby([idx, '예정월'])['수주 예정액(종합)'].sum()
          .div(1e8).round(2).reset_index()
          .pivot(index=idx, columns='예정월', values='수주 예정액(종합)')
          .fillna(0).reindex(columns=MONTHS)
    )
    p['합계'] = p.sum(axis=1).round(2)
    total = p.sum(axis=0).to_frame().T
    total.index = ['합계']
    return pd.concat([total, p])

def reorder_types(tbl: pd.DataFrame) -> pd.DataFrame:
    others = [t for t in tbl.index if t not in ['합계'] + PRIMARY_TYPES]
    order  = ['합계'] + [t for t in PRIMARY_TYPES if t in tbl.index] + others
    return tbl.reindex(order)

# ────────── 표 생성 ──────────
size_tbl = pivot_sum(df_target, '기업 규모').reindex(SIZE_ORDER)

tbl_ent = reorder_types(pivot_sum(df_target[df_target['기업 규모']=='대기업'],  '딜 전환 유형'))
tbl_mid = reorder_types(pivot_sum(df_target[df_target['기업 규모']=='중견기업'], '딜 전환 유형'))
tbl_sme = reorder_types(pivot_sum(df_target[df_target['기업 규모']=='중소기업'], '딜 전환 유형'))

# ────────── 출력 ──────────
# 기존 title, subheader 대신 markdown 헤더 레벨만 낮춰서 사용
title_name = f"{sel_team} – {sel_person}" if sel_person != "전체" else f"{sel_team} (전체)"
st.markdown(f"## {title_name} 체결액 추이 (2025년)")          # h2

st.markdown("### 1. 기업 규모별 체결액 – 월별 (억)")          # h3
st.dataframe(size_tbl, use_container_width=True)

st.markdown("### 2. 대기업 – 딜 전환 유형별 체결액 – 월별 (억)")
st.dataframe(tbl_ent, use_container_width=True)

st.markdown("### 3. 중견기업 – 딜 전환 유형별 체결액 – 월별 (억)")
st.dataframe(tbl_mid, use_container_width=True)

st.markdown("### 4. 중소기업 – 딜 전환 유형별 체결액 – 월별 (억)")
st.dataframe(tbl_sme, use_container_width=True)