# pages/6_개인별_체결률_추이.py
import streamlit as st, pandas as pd, re
from data import load_all_deal

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
TEAM_LIST  = list(TEAM_RAW.keys())

SIZE_ORDER   = ['대기업','중견기업','중소기업','공공기관','대학교','기타','미기재']
TYPE_ORDER   = ['직접 교육 문의','리텐션']
STATUS_ORDER = ['합계','확정','높음','낮음','LOST','미기재','체결률']

# 업종 제거, Net 표시 유지
DETAIL_COLS  = [
    '생성년도','생성월','기업명','이름','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)', 'Net',
    '과정포맷(대)', '카테고리(대)'
]

# ────────── 데이터 ──────────
df = load_all_deal()
df = df[df['생성년도'] >= 2025]
df['팀'] = df['담당자_name'].map(NAME2TEAM).fillna('기타')
df['월'] = df['생성월'].astype(str).str.zfill(2)
MONTHS  = sorted(df['월'].unique())

# ────────── Sidebar ──────────
st.sidebar.header("개인별 체결률 추이")
sel_team   = st.sidebar.selectbox("팀", TEAM_LIST)
persons    = sorted(TEAM_RAW[sel_team])
sel_person = st.sidebar.selectbox("개인", ["전체"] + persons)

df_team   = df[df['팀'] == sel_team]
df_target = df_team if sel_person == "전체" else df_team[df_team['담당자_name'] == sel_person]

# ────────── helper ──────────
def status_table(data: pd.DataFrame) -> pd.DataFrame:
    ct = data.groupby(['월','성사 가능성']).size().unstack(fill_value=0)
    for col in ['확정','높음','낮음','LOST']:
        if col not in ct.columns:
            ct[col] = 0
    ct['미기재'] = (
        data[data['성사 가능성'].isna() | (data['성사 가능성'] == '')]
          .groupby('월').size()
          .reindex(ct.index, fill_value=0)
    )
    ct['합계']   = ct[['확정','높음','낮음','LOST','미기재']].sum(axis=1)
    ct['체결률'] = ((ct['확정'] + ct['높음']) / ct['합계']).round(3) * 100

    tbl = (ct[STATUS_ORDER]
           .T.reindex(STATUS_ORDER)
           .reindex(columns=MONTHS, fill_value=0))

    for stat in STATUS_ORDER[:-1]:
        tbl.loc[stat] = tbl.loc[stat].astype(int).astype(str)
    tbl.loc['체결률'] = tbl.loc['체결률'].apply(lambda x: f"{x:.1f}%")
    return tbl

def detail_table(df_sub: pd.DataFrame) -> pd.DataFrame:
    """
    행 = 딜, 열 = DETAIL_COLS, Net은 소수 둘째 자리.
    """
    det = (
        df_sub
        .sort_values(['생성년도','생성월','기업명'])
        [DETAIL_COLS]
        .copy()
        .reset_index(drop=True)
    )

    # 정수 처리
    int_cols = det.select_dtypes(include='number').columns.difference(['Net'])
    det[int_cols] = det[int_cols].fillna(0).astype(int).astype(str)

    # Net 두 자리
    det['Net'] = det['Net'].fillna(0).astype(float).round(2).map(lambda x: f"{x:.2f}")

    return det

# ────────── 출력 ──────────
title = f"{sel_team} – {sel_person}" if sel_person != "전체" else f"{sel_team} (전체)"
st.markdown(f"### {title} 체결률 및 상세 (2025년~)")

for size in SIZE_ORDER:
    g_size = df_target[df_target['기업 규모'].fillna('미기재') == size]
    if g_size.empty:
        continue
    for dtype in TYPE_ORDER:
        g = g_size[g_size['딜 전환 유형'] == dtype]
        if g.empty:
            continue

        st.markdown(f"#### {size} / {dtype}")
        st.dataframe(status_table(g), use_container_width=True)

        st.markdown("*상세 딜 목록*")
        st.dataframe(detail_table(g), use_container_width=True, hide_index=True)
