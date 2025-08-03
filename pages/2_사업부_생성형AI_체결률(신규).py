# pages/13_생성형AI_월별_체결률_신규.py
"""
생성형 AI – 2025년 월별 체결률 (신규 고객)
- 1월 ~ 12월 월별 집계
- 3개월 이동평균 (1~3월 … 10~12월)
"""

import re
import streamlit as st
import pandas as pd
from data import load_all_deal, load_retention

st.set_page_config(page_title="생성형-AI – 월별 체결률 (2025·신규)", layout="wide")

# ────────── 팀 매핑 ──────────
TEAM_RAW = {
    '기업교육 1팀': ['김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연',
                 '강지선','정하영','하승민','이은서','홍제환','김세연','오진선'],
    '기업교육 2팀': ['박종협','정선희','권노을','강진우','이윤지','김민선','이수빈',
                 '강연정','강다현','방신우','정다혜','임재우','손승완','김윤지','손지훈','홍예진'],
}
NAME2TEAM = {re.sub(r'B$','', n): t for t, lst in TEAM_RAW.items() for n in lst}

# ────────── 상수 ──────────
DETAIL_COLS = [
    '생성년도','생성월','기업명', '기업 규모', '이름','담당자_name','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net','과정포맷(대)','카테고리(대)'
]
MONTHS = list(range(1, 13))
MONTH_COLS = [f"{m}월" for m in MONTHS]
ROLL_WINDOWS = [(i, i+1, i+2) for i in range(1, 11)]  # 1~3 ... 10~12
ROLL_COLS = [f"{a}~{c}월" for a, _, c in ROLL_WINDOWS]
ROW_ORDER = ['전체','확정+높음','낮음','LOST','체결률(%)']
ONLINE_SET = {'선택구매(온라인)','구독제(온라인)','포팅'}
STAT_MAP = {'확정':'확정','높음':'높음','낮음':'낮음','LOW':'낮음','LOST':'LOST','LOST/중단':'LOST'}

# ────────── 데이터 로드 ──────────
df = load_all_deal()
ret_set = set(load_retention()['기업명'].dropna()) if '기업명' in load_retention().columns else set()

# ────────── Sidebar ──────────
st.sidebar.header("필터")
size_opts = ['전체','대기업','중견기업','중소기업']
sel_size = st.sidebar.selectbox("기업 규모", size_opts, 0)

# ────────── 필터링 ──────────
# 기업 고객
mask = df['고객사 유형'].fillna('').eq('기업 고객')
if sel_size != '전체':
    mask &= df['기업 규모'].fillna('').eq(sel_size)

df = df[mask].copy()

# 전처리

df['담당자_name'] = df['담당자_name'].fillna('').astype(str).str.replace(r'B$','', regex=True).str.strip()
df['팀'] = df['담당자_name'].map(NAME2TEAM)

df['카테고리_정리'] = df['카테고리(대)'].fillna('').str.strip()
df['과정포맷_정리'] = df['과정포맷(대)'].fillna('').str.strip()

# 조건: 2025, 생성형 AI, 출강, 신규(리텐션 제외)
df = df[(df['생성년도'] == 2025) &
        (df['생성월'].between(1, 12)) &
        (df['카테고리_정리'] == '생성형 AI') &
        (~df['과정포맷_정리'].isin(ONLINE_SET)) &
        (~df['기업명'].isin(ret_set))].copy()

df['status'] = df['성사 가능성'].map(STAT_MAP).fillna('기타')

# ────────── 헬퍼 ──────────

def _bucket(d: pd.DataFrame) -> pd.DataFrame:
    tbl = pd.DataFrame(0.0, index=ROW_ORDER[:-1], columns=MONTH_COLS)
    tbl.loc['체결률(%)'] = ''
    if d.empty:
        tbl.loc['체결률(%)'] = '0.0%'
        return tbl
    d = d.dropna(subset=['생성월']).copy()
    d['생성월'] = pd.to_numeric(d['생성월'], errors='coerce').dropna().astype(int)
    for m in MONTHS:
        col = f"{m}월"
        sub = d[d['생성월'] == m]
        tot = len(sub)
        tbl.loc['전체', col] = tot
        if tot:
            win = len(sub[sub['status'].isin(['확정','높음'])])
            low = len(sub[sub['status'] == '낮음'])
            lost = len(sub[sub['status'] == 'LOST'])
            tbl.loc['확정+높음', col] = win
            tbl.loc['낮음', col] = low
            tbl.loc['LOST', col] = lost
            tbl.loc['체결률(%)', col] = f"{win / tot * 100:.1f}%"
        else:
            tbl.loc['체결률(%)', col] = '0.0%'
    return tbl


def month_tbl(mask):
    return _bucket(df[mask])


def roll_tbl(mask):
    base = month_tbl(mask)
    res = pd.DataFrame(0.0, index=ROW_ORDER[:-1], columns=ROLL_COLS)
    res.loc['체결률(%)'] = ''
    if base.empty:
        res.loc['체결률(%)'] = '0.0%'
        return res
    md = {m: base[f"{m}월"] for m in MONTHS}
    for (a, b, c), col in zip(ROLL_WINDOWS, ROLL_COLS):
        tot  = md[a]['전체'] + md[b]['전체'] + md[c]['전체']
        win  = md[a]['확정+높음'] + md[b]['확정+높음'] + md[c]['확정+높음']
        low  = md[a]['낮음'] + md[b]['낮음'] + md[c]['낮음']
        lost = md[a]['LOST'] + md[b]['LOST'] + md[c]['LOST']
        res.loc['전체', col]      = tot
        res.loc['확정+높음', col] = win
        res.loc['낮음', col]      = low
        res.loc['LOST', col]      = lost
        res.loc['체결률(%)', col] = f"{win / tot * 100:.1f}%" if tot else '0.0%'
    return res

# ────────── UI ──────────
st.title("생성형 AI — 2025년 월별 체결률 (신규 고객)")

tabs = st.tabs(['전체', '기업교육 1팀', '기업교육 2팀'])
MASKS = {
    '전체': df.index == df.index,
    '기업교육 1팀': df['팀'] == '기업교육 1팀',
    '기업교육 2팀': df['팀'] == '기업교육 2팀'
}

for tab, (label, mask) in zip(tabs, MASKS.items()):
    with tab:
        st.subheader('월별')
        st.dataframe(month_tbl(mask), use_container_width=True)
        st.subheader('3개월 이동평균')
        st.dataframe(roll_tbl(mask), use_container_width=True)

        detail = df[mask][DETAIL_COLS].copy()
        if not detail.empty:
            detail['수주 예정액(종합)'] = (detail['수주 예정액(종합)'] / 1e8).round(2)
            detail['Net'] = detail['Net'].fillna(0).astype(float).round(2)
        st.subheader('상세 목록')
        st.dataframe(detail, use_container_width=True)

        # ───── 팀원별 표 출력 ─────
        if label != '전체':
            st.markdown('---')
            for person in TEAM_RAW[label]:
                p_mask = mask & (df['담당자_name'] == person)
                if p_mask.sum() == 0:
                    continue  # 데이터 없으면 건너뜀
                st.subheader(f"{person} — 월별")
                st.dataframe(month_tbl(p_mask), use_container_width=True)

                st.subheader(f"{person} — 3개월 이동평균")
                st.dataframe(roll_tbl(p_mask), use_container_width=True)

                p_detail = df[p_mask][DETAIL_COLS].copy()
                if not p_detail.empty:
                    p_detail['수주 예정액(종합)'] = (p_detail['수주 예정액(종합)'] / 1e8).round(2)
                    p_detail['Net'] = p_detail['Net'].fillna(0).astype(float).round(2)
                st.subheader(f"{person} — 상세 목록")
                st.dataframe(p_detail, use_container_width=True)