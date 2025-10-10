# pages/22_공공·대학교_월별_체결률.py
"""
공공기관·대학교 – 2025년 월별 체결률 (조합별 탭)
- 조합(10): 기업 규모 × 딜 전환 유형 × 과정포맷(대) × 카테고리(대)
- 각 탭: (1) 월별  (2) 3개월 이동평균  (3) 상세 목록
- 팀 구분/별도 필터 없음
"""

import streamlit as st
import pandas as pd
from data import load_all_deal

st.set_page_config(page_title="공공·대학교 — 2025 월별 체결률", layout="wide")

# ────────── 상수 ──────────
DETAIL_COLS = [
    '생성년도','생성월','기업명','기업 규모','이름','담당자_name','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net','과정포맷(대)','카테고리(대)'
]
MONTHS       = list(range(1, 13))
MONTH_COLS   = [f"{m}월" for m in MONTHS]
ROLL_WINDOWS = [(i, i+1, i+2) for i in range(1, 11)]  # 1~3 ... 10~12
ROLL_COLS    = [f"{a}~{c}월" for a, _, c in ROLL_WINDOWS]

COUNT_ROWS = ['전체','확정+높음','낮음','LOST']
RATE_ROW   = '체결률(%)'
AMOUNT_ROW = '수주예정액(확정+높음, 억)'

ONLINE_SET = {'선택구매(온라인)','구독제(온라인)','포팅'}
STAT_MAP   = {'확정':'확정','높음':'높음','낮음':'낮음','LOW':'낮음','LOST':'LOST','LOST/중단':'LOST'}

# ────────── 데이터 로드 ──────────
df = load_all_deal().copy()

# 기본 전처리
df['담당자_name']   = df['담당자_name'].fillna('').astype(str).str.replace(r'B$', '', regex=True).str.strip()
df['카테고리(대)']   = df['카테고리(대)'].fillna('').astype(str).str.strip()
df['과정포맷(대)']   = df['과정포맷(대)'].fillna('').astype(str).str.strip()
df['기업 규모']     = df['기업 규모'].fillna('').astype(str).str.strip()

# 딜 전환 유형 정규화: '리텐션'이면 리텐션, 그 외(공백 포함)는 '직접 교육 문의'
df['딜 전환 유형'] = df['딜 전환 유형'].fillna('')
df['딜 전환 유형_정리'] = df['딜 전환 유형'].apply(lambda x: '리텐션' if x == '리텐션' else '직접 교육 문의')

# 2025년, 1~12월만 사용
df = df[(df['생성년도'] == 2025) & (pd.to_numeric(df['생성월'], errors='coerce').fillna(0).astype(int).between(1, 12))].copy()
df['생성월'] = pd.to_numeric(df['생성월'], errors='coerce').fillna(0).astype(int)

# 상태 맵
df['status'] = df['성사 가능성'].map(STAT_MAP).fillna('기타')

# 금액 정규화
df['수주 예정액(종합)'] = pd.to_numeric(df['수주 예정액(종합)'], errors='coerce').fillna(0.0)
df['Net']              = pd.to_numeric(df['Net'], errors='coerce')

# ────────── 집계 헬퍼 ──────────
def _bucket(d: pd.DataFrame) -> pd.DataFrame:
    """월별 카운트/비율/금액 표 생성"""
    tbl = pd.DataFrame(0, index=COUNT_ROWS, columns=MONTH_COLS, dtype="Int64")
    tbl.loc[RATE_ROW]   = ''
    tbl.loc[AMOUNT_ROW] = ''

    if d.empty:
        for col in MONTH_COLS:
            tbl.loc[RATE_ROW, col]   = '0.0%'
            tbl.loc[AMOUNT_ROW, col] = '0.0억'
        return tbl

    sub = d.copy()
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

    tbl.loc[COUNT_ROWS] = tbl.loc[COUNT_ROWS].astype("Int64")
    return tbl

def month_tbl(mask_bool: pd.Series) -> pd.DataFrame:
    return _bucket(df[mask_bool])

def roll_tbl(mask_bool: pd.Series) -> pd.DataFrame:
    base = month_tbl(mask_bool)
    res = pd.DataFrame(0, index=COUNT_ROWS, columns=ROLL_COLS, dtype="Int64")
    res.loc[RATE_ROW]   = ''
    res.loc[AMOUNT_ROW] = ''

    if base.empty:
        for col in ROLL_COLS:
            res.loc[RATE_ROW, col]   = '0.0%'
            res.loc[AMOUNT_ROW, col] = '0.0억'
        return res

    md = {m: base[f"{m}월"] for m in MONTHS}
    seg_base = df[mask_bool].copy()

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

        seg = seg_base[seg_base['생성월'].isin([a, b, c])]
        amt_uk = (seg.loc[seg['status'].isin(['확정','높음']), '수주 예정액(종합)'].sum() / 1e8)
        res.loc[AMOUNT_ROW, col] = f"{amt_uk:.1f}억"

    res.loc[COUNT_ROWS] = res.loc[COUNT_ROWS].astype("Int64")
    return res

# ────────── 조합 정의 (탭 라벨은 짧게)
# fmt_key: '구독','선택','출강','전체'
# cat_key: '전체' or '생성형 AI'
COMBOS = [
    # 공공기관 · 직접
    ("공-직/구독",       "공공기관", "직접 교육 문의", "구독",  "전체"),
    ("공-직/선택",       "공공기관", "직접 교육 문의", "선택",  "전체"),
    ("공-직/출강",       "공공기관", "직접 교육 문의", "출강",  "전체"),
    ("공-직/출강·생AI",  "공공기관", "직접 교육 문의", "출강",  "생성형 AI"),
    # 공공기관 · 리텐션
    ("공-리/전체",       "공공기관", "리텐션",       "전체",  "전체"),
    # 대학교 · 직접
    ("대-직/구독",       "대학교",   "직접 교육 문의", "구독",  "전체"),
    ("대-직/선택",       "대학교",   "직접 교육 문의", "선택",  "전체"),
    ("대-직/출강",       "대학교",   "직접 교육 문의", "출강",  "전체"),
    ("대-직/출강·생AI",  "대학교",   "직접 교육 문의", "출강",  "생성형 AI"),
    # 대학교 · 리텐션
    ("대-리/전체",       "대학교",   "리텐션",       "전체",  "전체"),
]

def make_mask(size: str, conv: str, fmt_key: str, cat_key: str) -> pd.Series:
    m = (df['기업 규모'].eq(size)) & (df['딜 전환 유형_정리'].eq(conv))
    # 과정포맷(대)
    if fmt_key == "구독":
        m &= df['과정포맷(대)'].eq('구독제(온라인)')
    elif fmt_key == "선택":
        m &= df['과정포맷(대)'].eq('선택구매(온라인)')
    elif fmt_key == "출강":
        m &= ~df['과정포맷(대)'].isin(ONLINE_SET)  # 온라인 3종 제외 → 오프라인/출강
    elif fmt_key == "전체":
        pass
    # 카테고리(대)
    if cat_key != "전체":
        m &= df['카테고리(대)'].eq(cat_key)
    return m

# ────────── UI ──────────
st.title("공공기관·대학교 — 2025년 월별 체결률")

tabs = st.tabs([label for (label, *_rest) in COMBOS])

for tab, (label, size, conv, fmt_key, cat_key) in zip(tabs, COMBOS):
    with tab:
        mask = make_mask(size, conv, fmt_key, cat_key)

        st.subheader("월별")
        st.dataframe(month_tbl(mask), use_container_width=True)

        st.subheader("3개월 이동평균")
        st.dataframe(roll_tbl(mask), use_container_width=True)

        st.subheader("상세 목록")
        detail = df[mask][DETAIL_COLS].copy()
        if not detail.empty:
            detail['수주 예정액(종합)'] = (detail['수주 예정액(종합)'] / 1e8).round(2)
            detail['Net'] = detail['Net'].fillna(0).astype(float).round(2)
        st.dataframe(detail, use_container_width=True, hide_index=True)