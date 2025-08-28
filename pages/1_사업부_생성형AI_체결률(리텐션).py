# pages/12_생성형AI_월별_체결률_리텐션.py
"""
생성형 AI – 2025년 월별 체결률 (리텐션 고객)
- 1월 ~ 12월 월별 집계
- 3개월 이동평균(1~3 … 10~12월)
- 팀 탭: 팀 전체 표 3종 + TEAM_RAW 순서 팀원별 표 3종
"""

import re
import streamlit as st
import pandas as pd
from data import load_all_deal, load_retention

st.set_page_config(page_title="생성형-AI – 월별 체결률 (2025·리텐션)", layout="wide")

# ────────── 팀 매핑 ──────────
TEAM_RAW = {
    '기업교육 1팀': ['김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연','강지선','정하영','하승민','이은서','홍제환','김세연','오진선'],
    '기업교육 2팀': ['박종협','정선희','권노을','강진우','이윤지','김민선','이수빈','강연정','강다현','방신우','정다혜','임재우','송승희','손승완','김윤지','손지훈','홍예진'],
}
NAME2TEAM = {re.sub(r'B$','', n): t for t, lst in TEAM_RAW.items() for n in lst}

# ────────── 상수 ──────────
DETAIL_COLS = [
    '생성년도','생성월','기업명','이름','담당자_name','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net','과정포맷(대)','카테고리(대)'
]
MONTHS = list(range(1, 13))
MONTH_COLS = [f"{m}월" for m in MONTHS]
ROLL_WINDOWS = [(i, i+1, i+2) for i in range(1, 11)]
ROLL_COLS = [f"{a}~{c}월" for a, _, c in ROLL_WINDOWS]

# 표 행 구성
COUNT_ROWS = ['전체','확정+높음','낮음','LOST']
RATE_ROW = '체결률(%)'
AMOUNT_ROW = '수주예정액(확정+높음, 억)'

ONLINE_SET = {'선택구매(온라인)','구독제(온라인)','포팅'}
STAT_MAP = {'확정':'확정','높음':'높음','낮음':'낮음','LOW':'낮음','LOST':'LOST','LOST/중단':'LOST'}

# ────────── 데이터 로드 & 필터 ──────────
df = load_all_deal()
ret_df = load_retention()
ret_set = set(ret_df['기업명'].dropna()) if '기업명' in ret_df.columns else set()

df = df[df['고객사 유형'].fillna('').eq('기업 고객')].copy()

# 전처리
df['담당자_name'] = df['담당자_name'].fillna('').astype(str).str.replace(r'B$','', regex=True).str.strip()
df['팀'] = df['담당자_name'].map(NAME2TEAM)

df['카테고리_정리'] = df['카테고리(대)'].fillna('').str.strip()
df['과정포맷_정리'] = df['과정포맷(대)'].fillna('').str.strip()

df = df[(df['생성년도'] == 2025) &
        (df['생성월'].between(1, 12)) &
        (df['카테고리_정리'] == '생성형 AI') &
        (~df['과정포맷_정리'].isin(ONLINE_SET)) &
        (df['기업명'].isin(ret_set))].copy()

df['status'] = df['성사 가능성'].map(STAT_MAP).fillna('기타')

# ────────── 계산 함수 ──────────
def _bucket(sub: pd.DataFrame) -> pd.DataFrame:
    # 정수(Int64)로 초기화하여 1.0 대신 1로 표시 (카운트 행)
    tbl = pd.DataFrame(0, index=COUNT_ROWS, columns=MONTH_COLS, dtype="Int64")
    tbl.loc[RATE_ROW] = ''
    tbl.loc[AMOUNT_ROW] = ''

    if sub.empty:
        for col in MONTH_COLS:
            tbl.loc[RATE_ROW, col] = '0.0%'
            tbl.loc[AMOUNT_ROW, col] = '0.0억'
        return tbl

    sub = sub.dropna(subset=['생성월']).copy()
    sub['생성월'] = pd.to_numeric(sub['생성월'], errors='coerce').astype(int)
    sub['수주 예정액(종합)'] = pd.to_numeric(sub['수주 예정액(종합)'], errors='coerce').fillna(0.0)

    for m in MONTHS:
        col = f"{m}월"
        seg = sub[sub['생성월'] == m]
        tot = int(len(seg))
        tbl.loc['전체', col] = tot
        if tot:
            win_mask = seg['status'].isin(['확정','높음'])
            win  = int(win_mask.sum())
            low  = int((seg['status'] == '낮음').sum())
            lost = int((seg['status'] == 'LOST').sum())
            tbl.loc['확정+높음', col] = win
            tbl.loc['낮음', col]      = low
            tbl.loc['LOST', col]      = lost
            tbl.loc[RATE_ROW, col]    = f"{win / tot * 100:.1f}%"

            amt_uk = (seg.loc[win_mask, '수주 예정액(종합)'].sum() / 1e8)
            tbl.loc[AMOUNT_ROW, col]  = f"{amt_uk:.1f}억"
        else:
            tbl.loc[RATE_ROW, col]   = '0.0%'
            tbl.loc[AMOUNT_ROW, col] = '0.0억'

    # 수치 행 유지 (행 단위로 Int64 유지)
    tbl.loc[COUNT_ROWS] = tbl.loc[COUNT_ROWS].astype("Int64")
    return tbl


def month_tbl(mask):
    return _bucket(df[mask])


def roll_tbl(mask):
    base = month_tbl(mask)
    # 정수(Int64)로 초기화하여 1.0 대신 1로 표시 (카운트 행)
    res = pd.DataFrame(0, index=COUNT_ROWS, columns=ROLL_COLS, dtype="Int64")
    res.loc[RATE_ROW] = ''
    res.loc[AMOUNT_ROW] = ''

    if base.empty:
        for col in ROLL_COLS:
            res.loc[RATE_ROW, col] = '0.0%'
            res.loc[AMOUNT_ROW, col] = '0.0억'
        return res

    md = {m: base[f"{m}월"] for m in MONTHS}
    sub = df[mask].dropna(subset=['생성월']).copy()
    sub['생성월'] = pd.to_numeric(sub['생성월'], errors='coerce').astype(int)
    sub['수주 예정액(종합)'] = pd.to_numeric(sub['수주 예정액(종합)'], errors='coerce').fillna(0.0)

    for (a, b, c), col in zip(ROLL_WINDOWS, ROLL_COLS):
        tot  = int(md[a]['전체'])      + int(md[b]['전체'])      + int(md[c]['전체'])
        win  = int(md[a]['확정+높음']) + int(md[b]['확정+높음']) + int(md[c]['확정+높음'])
        low  = int(md[a]['낮음'])      + int(md[b]['낮음'])      + int(md[c]['낮음'])
        lost = int(md[a]['LOST'])      + int(md[b]['LOST'])      + int(md[c]['LOST'])

        res.loc['전체', col]      = tot
        res.loc['확정+높음', col] = win
        res.loc['낮음', col]      = low
        res.loc['LOST', col]      = lost
        res.loc[RATE_ROW, col]    = f"{win / tot * 100:.1f}%" if tot else '0.0%'

        # 3개월 합계 기준 수주예정액(확정+높음)
        seg = sub[sub['생성월'].isin([a, b, c])]
        amt_uk = (seg.loc[seg['status'].isin(['확정','높음']), '수주 예정액(종합)'].sum() / 1e8)
        res.loc[AMOUNT_ROW, col] = f"{amt_uk:.1f}억"

    # 수치 행 유지 (행 단위로 Int64 유지)
    res.loc[COUNT_ROWS] = res.loc[COUNT_ROWS].astype("Int64")
    return res

# ────────── UI ──────────
st.title("생성형 AI — 2025년 월별 체결률 (리텐션 고객)")

tabs = st.tabs(['전체', '기업교육 1팀', '기업교육 2팀'])
MASKS = {
    '전체': df.index == df.index,
    '기업교육 1팀': df['팀'] == '기업교육 1팀',
    '기업교육 2팀': df['팀'] == '기업교육 2팀'
}

for tab, lbl in zip(tabs, ['전체','기업교육 1팀','기업교육 2팀']):
    with tab:
        team_mask = MASKS[lbl]

        # 팀 전체 3종
        st.subheader('팀 전체 — 월별')
        st.dataframe(month_tbl(team_mask), use_container_width=True)

        st.subheader('팀 전체 — 3개월 이동평균')
        st.dataframe(roll_tbl(team_mask), use_container_width=True)

        st.subheader('팀 전체 — 상세 목록')
        team_detail = df[team_mask][DETAIL_COLS].copy()
        if not team_detail.empty:
            team_detail['수주 예정액(종합)'] = (pd.to_numeric(team_detail['수주 예정액(종합)'], errors='coerce').fillna(0.0) / 1e8).round(2)
            team_detail['Net'] = pd.to_numeric(team_detail['Net'], errors='coerce').fillna(0.0).astype(float).round(2)
        st.dataframe(team_detail, use_container_width=True)

        # 팀원별 3종 (TEAM_RAW 순서)
        if lbl != '전체':
            st.markdown('---')
            for person in TEAM_RAW[lbl]:
                person_mask = team_mask & (df['담당자_name'] == person)
                if person_mask.sum() == 0:
                    continue

                st.subheader(f"{person} — 월별")
                st.dataframe(month_tbl(person_mask), use_container_width=True)

                st.subheader(f"{person} — 3개월 이동평균")
                st.dataframe(roll_tbl(person_mask), use_container_width=True)

                p_detail = df[person_mask][DETAIL_COLS].copy()
                if not p_detail.empty:
                    p_detail['수주 예정액(종합)'] = (pd.to_numeric(p_detail['수주 예정액(종합)'], errors='coerce').fillna(0.0) / 1e8).round(2)
                    p_detail['Net'] = pd.to_numeric(p_detail['Net'], errors='coerce').fillna(0.0).astype(float).round(2)
                st.subheader(f"{person} — 상세 목록")
                st.dataframe(p_detail, use_container_width=True)
