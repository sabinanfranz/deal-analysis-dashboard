# pages/9_체결액_히스토그램.py
"""
3개월 이동(롤링) 히스토그램 — 예상 체결액(종합) 분포 (2025.01~08)
- 탭 1: 리텐션 고객(기업명 ∈ retention)
- 탭 2: 신규 고객(기업명 ∉ retention) 중 **기업 규모=대기업**만
- ONLINE_SET(선택구매(온라인)/구독제(온라인)/포팅) 제외
- 각 탭에 3개월 롤링 윈도(1~3월, 2~4월, …, 6~8월) 별 **스택 히스토그램**(막대=금액 구간, 색=카테고리(대))
- 히스토그램 X축: **예상 체결액(억원)**, **0.1억(=1천만원) 단위 bin**
- Y축: 딜 **건수(3개월 묶음 합계)**
- 요청 반영:
  · 한 줄에 하나의 히스토그램
  · 각 히스토그램 **아래에 구체 수치 표** 출력
  · **1.5억 이상은 한 묶음**으로 집계(Top-coding)
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

# 1~3 ... 6~8 (총 6개 윈도우)
ROLL_WINDOWS = [(1,2,3),(2,3,4),(3,4,5),(4,5,6),(5,6,7),(6,7,8)]
ROLL_LABELS  = [f"{a}~{c}월" for (a,_,c) in ROLL_WINDOWS]

BIN_STEP_UK   = 0.1   # 억원 단위 bin = 0.1억 = 1천만원
TOP_CUT_UK    = 1.5   # 1.5억 이상은 한 묶음
AXIS_MAX_UK   = TOP_CUT_UK + BIN_STEP_UK  # 시각화 상한(마지막 bin을 표현하기 위한 1.6억)

# ─────────────────────────── 유틸
def _to_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(',', ''), errors='coerce')

@st.cache_data(show_spinner=False)
def _prep_base() -> tuple[pd.DataFrame, set]:
    df = load_all_deal().copy()
    ret = load_retention().copy()

    # 연/월 필터
    df['생성년도'] = pd.to_numeric(df.get('생성년도'), errors='coerce')
    df['생성월']   = pd.to_numeric(df.get('생성월'), errors='coerce')
    df = df[(df['생성년도'] == YEAR) & (df['생성월'].between(1, 12))].copy()

    # 포맷/카테고리/규모/금액 정리
    df['과정포맷(대)'] = df.get('과정포맷(대)', pd.Series('', index=df.index)).astype(str).str.strip()
    df = df[~df['과정포맷(대)'].isin(ONLINE_SET)].copy()

    df['카테고리(대)'] = df.get('카테고리(대)', pd.Series('', index=df.index)).astype(str).str.strip().replace({'': '미기재'})
    df['기업 규모']   = df.get('기업 규모',   pd.Series('', index=df.index)).astype(str).str.strip()

    # 금액: 원화 → 숫자 → 억원
    df['수주 예정액(종합)'] = _to_number(df.get('수주 예정액(종합)', pd.Series(index=df.index)))
    df['amount']    = df['수주 예정액(종합)']
    df = df[df['amount'].notna() & (df['amount'] > 0)].copy()
    df['amount_uk'] = df['amount'] / 1e8  # 억원

    # 리텐션 판정 세트
    ret_set = set(ret['기업명'].dropna().astype(str)) if '기업명' in ret.columns else set()

    return df, ret_set

def _subset_by_customer_type(df: pd.DataFrame, ret_set: set, kind: str) -> pd.DataFrame:
    """
    kind: 'retention' or 'new_big'
      - retention: 기업명 ∈ ret_set
      - new_big  : 기업명 ∉ ret_set AND 기업 규모 == '대기업'
    """
    df = df.copy()
    df['기업명'] = df['기업명'].astype(str)
    if kind == 'retention':
        return df[df['기업명'].isin(ret_set)].copy()
    elif kind == 'new_big':
        return df[(~df['기업명'].isin(ret_set)) & (df['기업 규모'] == '대기업')].copy()
    else:
        return df.copy()

def _window_hist_chart(df: pd.DataFrame, months: tuple[int,int,int], title: str) -> alt.Chart:
    """
    단일 3개월 윈도의 스택 히스토그램 (막대: 금액구간, 색: 카테고리(대), y=count).
    X: 억원(0.1억 bin), Y: 건수(3개월 합)
    - 1.5억 이상은 전부 마지막 bin([1.5, 1.6))으로 캡(Top-coding)
    """
    a,b,c = months
    sub = df[df['생성월'].isin([a,b,c])].copy()

    if sub.empty:
        # 빈 데이터 플레이스홀더
        return (
            alt.Chart(pd.DataFrame({'amount_uk':[0], '카테고리(대)':['데이터 없음']}))
            .mark_bar()
            .encode(
                x=alt.X('amount_uk:Q', title='예상 체결액(억원) — 0.1억 bin',
                        scale=alt.Scale(domain=[0, AXIS_MAX_UK]), axis=alt.Axis(format='.1f')),
                y=alt.Y('count():Q', title='딜 수(3개월 합)'),
                color=alt.Color('카테고리(대):N', title='카테고리(대)')
            )
            .properties(title=title, height=260)
        )

    # amount_uk 상한 캡핑: 1.5 이상은 중간값(1.55)에 모아 마지막 bin으로 들어가게 함
    top_mid = TOP_CUT_UK + BIN_STEP_UK/2.0  # 1.55
    ch = (
        alt.Chart(sub)
        .transform_calculate(
            amount_capped=f"datum.amount_uk >= {TOP_CUT_UK} ? {top_mid} : datum.amount_uk"
        )
        .transform_bin(
            field='amount_capped',
            bin=alt.Bin(step=BIN_STEP_UK, extent=[0, AXIS_MAX_UK]),
            as_=['bin_start','bin_end']
        )
        .mark_bar()
        .encode(
            x=alt.X('bin_start:Q', title='예상 체결액(억원)',
                    scale=alt.Scale(domain=[0, AXIS_MAX_UK]),
                    axis=alt.Axis(format='.1f')),
            x2=alt.X2('bin_end:Q'),
            y=alt.Y('count():Q', title='딜 수(3개월 합)', stack='zero'),
            color=alt.Color('카테고리(대):N', title='카테고리(대)'),
            tooltip=[
                alt.Tooltip('카테고리(대):N', title='카테고리'),
                alt.Tooltip('count():Q', title='건수'),
                alt.Tooltip('bin_start:Q', title='구간 시작(억)', format='.1f'),
                alt.Tooltip('bin_end:Q',   title='구간 끝(억)',   format='.1f'),
            ]
        )
        .properties(title=title, height=260)
    )
    return ch

def _window_hist_table(df: pd.DataFrame, months: tuple[int,int,int]) -> pd.DataFrame:
    """
    단일 3개월 윈도의 **구체 수치 표** 생성.
    - 행: 구간(억) [left~right) (0.1억 구간) + 최상단 구간 [1.5, ∞) → '1.5 이상'
    - 열: 카테고리(대) … + 합계
    """
    a,b,c = months
    sub = df[df['생성월'].isin([a,b,c])].copy()

    # 간격 경계: 0.0 ~ 1.5 (0.1 step) + [1.5, ∞)
    # 예: [0.0,0.1), [0.1,0.2), ..., [1.4,1.5), [1.5,∞)
    base_edges = np.round(np.arange(0.0, TOP_CUT_UK, BIN_STEP_UK), 6).tolist()  # 0.0 ... 1.4
    edges = base_edges + [TOP_CUT_UK, np.inf]

    intervals = pd.IntervalIndex.from_breaks(edges, closed='left')

    if sub.empty:
        out = pd.DataFrame(index=intervals)
        out['합계'] = 0
        out['구간(억)'] = [ (f"{iv.left:.1f}~{iv.right:.1f}" if np.isfinite(iv.right) else f"{iv.left:.1f} 이상")
                            for iv in out.index ]
        out = out[['구간(억)', '합계']]
        out['합계'] = out['합계'].astype('Int64')
        return out

    # 구간 할당(표 집계는 마지막 구간을 [1.5, ∞)로 진짜로 묶음)
    bins = pd.cut(sub['amount_uk'].astype(float), bins=edges, right=False, include_lowest=True)
    sub = sub.assign(bin=bins)

    # 카테고리 피벗 (모든 구간 강제 노출)
    pv = (
        sub.groupby(['bin','카테고리(대)'])
           .size()
           .unstack(fill_value=0)
           .reindex(intervals, fill_value=0)
    )

    # 합계 및 보기 좋은 라벨
    pv['합계'] = pv.sum(axis=1)
    pv.insert(
        0, '구간(억)',
        [ (f"{iv.left:.1f}~{iv.right:.1f}" if np.isfinite(iv.right) else f"{iv.left:.1f} 이상")
          for iv in pv.index ]
    )

    # 열 정렬: 구간(억) | (카테고리 알파벳순) | 합계
    cat_cols = sorted([c for c in pv.columns if c not in ['구간(억)','합계']])
    pv = pv[['구간(억)'] + cat_cols + ['합계']]

    # 정수 표기
    for c in cat_cols + ['합계']:
        pv[c] = pv[c].astype('Int64')

    return pv.reset_index(drop=True)

def _render_tab(df_kind: pd.DataFrame, tab_title: str):
    st.subheader(tab_title)
    if df_kind.empty:
        st.info("해당 조건의 데이터가 없습니다.")
        return

    # 6개 윈도우를 **한 줄에 하나씩**: 그래프 → 표 → 구분선
    for idx, win in enumerate(ROLL_WINDOWS):
        lab = ROLL_LABELS[idx]
        st.markdown(f"### {lab} (3개월 묶음)")
        st.altair_chart(_window_hist_chart(df_kind, win, f"{lab} (3개월 묶음)",),
                        use_container_width=True)

        tbl = _window_hist_table(df_kind, win)
        st.dataframe(tbl, use_container_width=True)
        st.markdown('---')

# ─────────────────────────── 데이터 준비
df_all, ret_set = _prep_base()

# 리텐션 / 신규(대기업) 분리 + 2025.01~08 범위 제한
df_ret = _subset_by_customer_type(df_all, ret_set, 'retention')
df_new = _subset_by_customer_type(df_all, ret_set, 'new_big')
df_ret = df_ret[df_ret['생성월'].between(1, 8)].copy()
df_new = df_new[df_new['생성월'].between(1, 8)].copy()

# ─────────────────────────── UI
st.title("예상 체결액(종합) — 3개월 롤링 히스토그램 (2025.01~08)")

with st.expander("집계/표시 기준", expanded=False):
    st.markdown(f"""
- **제외:** ONLINE(`선택구매(온라인)`, `구독제(온라인)`, `포팅`)  
- **리텐션:** `retention` 목록의 **기업명** 포함 건  
- **신규:** `retention` 제외 **AND** `기업 규모=대기업`  
- **금액:** `수주 예정액(종합)` **> 0** 인 딜만 포함, 단위는 **억원**  
- **윈도우:** 3개월 롤링 묶음 — `1~3월`, `2~4월`, `3~5월`, `4~6월`, `5~7월`, `6~8월`  
- **히스토그램:** X=금액(**억원**, 0.1억 bin), Y=**딜 수(3개월 합)**, 색=**카테고리(대)**  
- **상한 처리:** **{TOP_CUT_UK:.1f}억 이상은 한 묶음**으로 표기(차트는 마지막 막대로 집계, 표는 `"1.5 이상"` 행)  
    """)

tab_ret, tab_new = st.tabs(["리텐션 고객", "신규 고객(대기업)"])

with tab_ret:
    _render_tab(df_ret, "리텐션 고객 — 3개월 롤링 분포")

with tab_new:
    _render_tab(df_new, "신규 고객(대기업) — 3개월 롤링 분포")
