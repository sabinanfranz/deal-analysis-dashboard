# pages/21_3개월_예상체결액_히스토그램_리텐션vs신규.py
"""
3개월 이동(롤링) 히스토그램 — 예상 체결액(종합) 분포 (2025.01~08)
- 탭 1: 리텐션 고객(기업명 ∈ retention)
- 탭 2: 신규 고객(기업명 ∉ retention) 중 **기업 규모=대기업**만
- ONLINE_SET(선택구매(온라인)/구독제(온라인)/포팅) 제외
- 각 탭에 3개월 롤링 윈도(1~3월, 2~4월, …, 6~8월) 별 **스택 히스토그램**(막대=금액 구간, 색=카테고리(대))
- 히스토그램 X축: 예상 체결액(종합, 원), **1천만원(=10,000,000원) 단위** 구간
- Y축: 딜 **건수(3개월 묶음 합계)**
※ 용어상 '3개월 이동평균'이라 표현했지만, 히스토그램은 집계 특성상 '3개월 이동(롤링) 묶음 합계'로 시각화합니다.
"""

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from data import load_all_deal, load_retention

# ─────────────────────────── 기본 설정/상수
st.set_page_config(page_title="3개월 히스토그램 — 리텐션 vs 신규(대기업)", layout="wide")

ONLINE_SET = {'선택구매(온라인)','구독제(온라인)','포팅'}
YEAR = 2025
ROLL_WINDOWS = [(1,2,3),(2,3,4),(3,4,5),(4,5,6),(5,6,7),(6,7,8)]  # 1~3 ... 6~8
ROLL_LABELS  = [f"{a}~{c}월" for (a,_,c) in ROLL_WINDOWS]
BIN_STEP = 10_000_000  # 1천만원

# ─────────────────────────── 유틸
def _to_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(',', ''), errors='coerce')

def _prep_base() -> tuple[pd.DataFrame, set]:
    df = load_all_deal().copy()
    ret = load_retention().copy()

    # 기본 전처리
    df['생성년도'] = pd.to_numeric(df.get('생성년도'), errors='coerce')
    df['생성월']   = pd.to_numeric(df.get('생성월'), errors='coerce')
    df = df[(df['생성년도'] == YEAR) & (df['생성월'].between(1, 12))].copy()

    # 포맷/카테고리/규모/금액 정리
    df['과정포맷(대)'] = df.get('과정포맷(대)', '').astype(str).str.strip()
    df = df[~df['과정포맷(대)'].isin(ONLINE_SET)].copy()

    df['카테고리(대)'] = df.get('카테고리(대)', '').astype(str).str.strip().replace({'': '미기재'})
    df['기업 규모']   = df.get('기업 규모', '').astype(str).str.strip()
    df['수주 예정액(종합)'] = _to_number(df.get('수주 예정액(종합)', pd.Series(index=df.index)))
    df['amount'] = df['수주 예정액(종합)']  # 작업용 별칭

    # 히스토그램 대상: 금액이 유효한 건만(>0)
    df = df[df['amount'].notna() & (df['amount'] > 0)].copy()

    # 리텐션 판정 세트
    ret_set = set(ret['기업명'].dropna().astype(str)) if '기업명' in ret.columns else set()

    return df, ret_set

def _subset_by_customer_type(df: pd.DataFrame, ret_set: set, kind: str) -> pd.DataFrame:
    """
    kind: 'retention' or 'new_big'
      - retention: 기업명 ∈ ret_set
      - new_big  : 기업명 ∉ ret_set AND 기업 규모 == '대기업'
    """
    df['기업명'] = df['기업명'].astype(str)
    if kind == 'retention':
        return df[df['기업명'].isin(ret_set)].copy()
    elif kind == 'new_big':
        return df[(~df['기업명'].isin(ret_set)) & (df['기업 규모'] == '대기업')].copy()
    else:
        return df.copy()

def _domain_max_for_bins(df: pd.DataFrame) -> int:
    """모든 윈도 합쳐서의 최대 금액을 기준으로 x축 domain 상한을 BIN_STEP 단위로 올림."""
    if df.empty:
        return BIN_STEP * 10
    mx = float(df['amount'].max())
    if not np.isfinite(mx) or mx <= 0:
        return BIN_STEP * 10
    # BIN_STEP 배수로 올림
    upper = int(np.ceil(mx / BIN_STEP) * BIN_STEP)
    return upper

def _window_hist_chart(df: pd.DataFrame, months: tuple[int,int,int], title: str, x_max: int) -> alt.Chart:
    """단일 3개월 윈도의 스택 히스토그램 생성 (막대: 금액구간, 색: 카테고리(대), y=count)."""
    if df.empty:
        # 빈 차트 Place-holder
        return alt.Chart(pd.DataFrame({'amount':[0], '카테고리(대)':['데이터 없음']})).mark_bar().encode(
            x=alt.X('amount:Q', title='예상 체결액(원) — 1천만원 bin', scale=alt.Scale(domain=[0, x_max]), axis=alt.Axis(format=',d')),
            y=alt.Y('count():Q', title='딜 수(3개월 합)'),
            color=alt.Color('카테고리(대):N', title='카테고리(대)')
        ).properties(title=title, height=260)

    a,b,c = months
    sub = df[df['생성월'].isin([a,b,c])].copy()
    if sub.empty:
        # 해당 윈도 데이터 없음
        return alt.Chart(pd.DataFrame({'amount':[0], '카테고리(대)':['데이터 없음']})).mark_bar().encode(
            x=alt.X('amount:Q', title='예상 체결액(원) — 1천만원 bin', scale=alt.Scale(domain=[0, x_max]), axis=alt.Axis(format=',d')),
            y=alt.Y('count():Q', title='딜 수(3개월 합)'),
            color=alt.Color('카테고리(대):N', title='카테고리(대)')
        ).properties(title=title, height=260)

    # transform_bin으로 구간 시작/끝을 만들고 x/x2로 너비 지정
    ch = (
        alt.Chart(sub)
        .transform_bin(
            'bin_start',
            'amount',
            as_=['bin_start','bin_end'],
            bin=alt.Bin(step=BIN_STEP, extent=[0, x_max])
        )
        .mark_bar()
        .encode(
            x=alt.X('bin_start:Q', title='예상 체결액(원)', scale=alt.Scale(domain=[0, x_max]), axis=alt.Axis(format=',d')),
            x2=alt.X2('bin_end:Q'),
            y=alt.Y('count():Q', title='딜 수(3개월 합)', stack=None),
            color=alt.Color('카테고리(대):N', title='카테고리(대)'),
            tooltip=[
                alt.Tooltip('카테고리(대):N', title='카테고리'),
                alt.Tooltip('count():Q', title='건수'),
                alt.Tooltip('bin_start:Q', title='구간(원) 시작', format=',d'),
                alt.Tooltip('bin_end:Q',   title='구간(원) 끝',   format=',d'),
            ]
        )
        .properties(title=title, height=260)
    )
    return ch

def _render_tab(df_kind: pd.DataFrame, tab_title: str):
    st.subheader(tab_title)
    if df_kind.empty:
        st.info("해당 조건의 데이터가 없습니다.")
        return
    x_max = _domain_max_for_bins(df_kind)
    # 6개 윈도우를 2열 × 3행으로 배치
    rows = [(0,1),(2,3),(4,5)]
    for r_idx, (i, j) in enumerate(rows):
        c1, c2 = st.columns(2)
        with c1:
            a = ROLL_WINDOWS[i]; lab = ROLL_LABELS[i]
            st.altair_chart(_window_hist_chart(df_kind, a, f"{lab} (3개월 묶음)", x_max), use_container_width=True)
        with c2:
            a = ROLL_WINDOWS[j]; lab = ROLL_LABELS[j]
            st.altair_chart(_window_hist_chart(df_kind, a, f"{lab} (3개월 묶음)", x_max), use_container_width=True)

# ─────────────────────────── 데이터 준비
df_all, ret_set = _prep_base()

# 리텐션 / 신규(대기업) 분리
df_ret = _subset_by_customer_type(df_all, ret_set, 'retention')
df_new = _subset_by_customer_type(df_all, ret_set, 'new_big')

# 2025.01~08 범위만 사용(윈도우가 6~8월까지이므로 1~8월이면 충분)
df_ret = df_ret[df_ret['생성월'].between(1, 8)].copy()
df_new = df_new[df_new['생성월'].between(1, 8)].copy()

# ─────────────────────────── UI
st.title("예상 체결액(종합) — 3개월 롤링 히스토그램 (2025.01~08)")

with st.expander("집계/표시 기준", expanded=False):
    st.markdown("""
- **제외:** ONLINE(`선택구매(온라인)`, `구독제(온라인)`, `포팅`)  
- **리텐션:** `retention` 목록의 **기업명** 포함 건  
- **신규:** `retention` 제외 **AND** `기업 규모=대기업`  
- **금액:** `수주 예정액(종합)` **> 0** 인 딜만 히스토그램 포함  
- **윈도우:** 3개월 롤링 묶음 — `1~3월`, `2~4월`, `3~5월`, `4~6월`, `5~7월`, `6~8월`  
- **히스토그램:** X=금액(원, **1천만원 단위 bin**), Y=**딜 수(3개월 합)**, 색=**카테고리(대)**  
    """)

tab_ret, tab_new = st.tabs(["리텐션 고객", "신규 고객(대기업)"])

with tab_ret:
    _render_tab(df_ret, "리텐션 고객 — 3개월 롤링 분포")

with tab_new:
    _render_tab(df_new, "신규 고객(대기업) — 3개월 롤링 분포")
