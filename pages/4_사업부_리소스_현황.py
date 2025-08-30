# pages/20_사업부_운영_리소스_현황_2025.py
"""
사업부 운영 리소스 현황 (2025, 일간/주간)
- won 딜 + all 딜(확정 & 수강시작/종료 유효 & 수주예정액>0)을 합산
- 단, won에 이미 계산된 딜은 all의 확정 집계에서 중복 제외
- ONLINE_SET(선택구매(온라인)/구독제(온라인)/포팅) 제외
- 탭1: 그래프 3종(1팀vs2팀, 1팀 담당자, 2팀 담당자) — 리소스 큰 대상이 아래
- 탭2: 주간 표 3종(금주 기준 -4주~+4주, 월~일) — 팀별/1팀 구성/2팀 구성
"""

import re
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from data import load_won_deal, load_all_deal

# ─────────────────────────── 기본 설정/상수
st.set_page_config(page_title="사업부 운영 리소스 현황 (2025, 일간/주간)", layout="wide")

ONLINE_SET = {'선택구매(온라인)','구독제(온라인)','포팅'}

TEAM_RAW = {
    '기업교육 1팀': [
        '김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연',
        '강지선','정하영','하승민','이은서','홍제환','김세연','오진선'
    ],
    '기업교육 2팀': [
        '박종협','정선희','권노을','강진우','이윤지','김민선','이수빈','강연정',
        '강다현','방신우','정다혜','임재우','송승희','손승완','김윤지','손지훈','홍예진'
    ],
}
NAME2TEAM = {re.sub(r'B$','', n): t for t, lst in TEAM_RAW.items() for n in lst}
TEAMS = list(TEAM_RAW.keys())

START = pd.Timestamp('2025-01-01')
END   = pd.Timestamp('2025-12-31')
DATE_INDEX = pd.date_range(START, END, freq='D', name='date')
POS = pd.Series(np.arange(len(DATE_INDEX)), index=DATE_INDEX)

# 오늘(한국 기준)과 금주(월~일) 범위
TODAY = pd.Timestamp(datetime.now(ZoneInfo('Asia/Seoul')).date())
W0_START = TODAY - pd.Timedelta(days=TODAY.weekday())     # 이번 주 월요일
WEEK_STARTS = [W0_START + pd.Timedelta(weeks=k) for k in range(-4, 5)]  # -4주 ~ +4주
WEEK_ENDS   = [ws + pd.Timedelta(days=6) for ws in WEEK_STARTS]
WEEK_LABELS = [f"{ws:%Y-%m-%d} ~ {we:%m-%d}" for ws, we in zip(WEEK_STARTS, WEEK_ENDS)]

# ─────────────────────────── 유틸
def _to_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(',', ''), errors='coerce')

def _weight_from_amount(won):
    x = 0.0 if pd.isna(won) else float(won)
    if x <=   5_000_000:   return 1.0
    if x <=  25_000_000:   return 2.0
    if x <=  50_000_000:   return 3.0
    if x <= 100_000_000:   return 5.0
    if x <= 300_000_000:   return 7.0
    return 10.0

def _norm_person(s: pd.Series) -> pd.Series:
    return s.fillna('').astype(str).str.replace(r'B$', '', regex=True).str.strip()

def _norm_status(x):
    if pd.isna(x): return '미기재'
    t = str(x).strip().lower()
    if t in ['won','w','확정','confirmed']: return '확정'
    if t in ['high','높음']: return '높음'
    if t in ['low','낮음']: return '낮음'
    if t in ['lost','lose','l']: return 'LOST'
    return str(x).strip()

def _parse_dates(df, start_col, end_col):
    df['시작'] = pd.to_datetime(df[start_col], errors='coerce')
    df['종료'] = pd.to_datetime(df[end_col], errors='coerce')
    # 2025 클리핑 (2024 won이어도 2025와 겹치면 포함)
    df['시작'] = df['시작'].clip(lower=START)
    df['종료'] = df['종료'].clip(upper=END)
    # 유효기간만 남김
    valid = df['시작'].notna() & df['종료'].notna() & (df['시작'] <= df['종료'])
    return df[valid].copy()

def _make_diff_series(n, s_idx, e_idx, w):
    diff = np.zeros(n + 1, dtype=np.float32)
    s = s_idx.astype(int).to_numpy()
    e1 = (e_idx.astype(int) + 1).to_numpy()
    wv = w.astype(float).to_numpy()
    np.add.at(diff, s, wv)            # 시작일 +가중치
    mask = e1 < len(diff)             # 종료 다음날 -가중치
    np.add.at(diff, e1[mask], -wv[mask])
    return np.cumsum(diff[:-1])

def _accumulate_by_key(df, key_col):
    """차분 배열 + 누적합으로 key별 일간 리소스 시계열 생성."""
    n = len(DATE_INDEX)
    out_cols = {}
    for key, sub in df.groupby(key_col, dropna=True):
        if sub.empty: 
            continue
        out_cols[key] = _make_diff_series(n, sub['s_idx'], sub['e_idx'], sub['weight'])
    if not out_cols:
        return pd.DataFrame(index=DATE_INDEX)
    return pd.DataFrame(out_cols, index=DATE_INDEX)

def _order_info_from_pivot(pivot_df):
    """연간 합 기준 내림차순 컬럼 순서 + 스택 order값(-합계)."""
    if pivot_df.empty or pivot_df.shape[1] == 0:
        return [], {}
    totals = pivot_df.sum(axis=0).sort_values(ascending=False)
    order_list = list(totals.index)
    order_val = {k: -float(v) for k, v in totals.items()}  # 큰 값일수록 더 작은(-) 값 → 아래
    return order_list, order_val

def _melt_with_order(pivot_df, var_name):
    order_list, order_val = _order_info_from_pivot(pivot_df)
    long = pivot_df.reset_index().melt('date', var_name=var_name, value_name='리소스')
    long['리소스'] = long['리소스'].fillna(0.0)
    long['order_val'] = long[var_name].map(order_val).fillna(0.0).astype(float)
    return long, order_list

def _stacked_bar(df_long, color_col, title, color_order=None):
    enc_color = alt.Color(f'{color_col}:N', title=color_col)
    if color_order:
        enc_color = enc_color.sort(color_order)
    ch = (
        alt.Chart(df_long)
        .mark_bar()
        .encode(
            x=alt.X('date:T', title='', axis=alt.Axis(format='%m-%d', tickCount=12)),
            y=alt.Y('리소스:Q', title='리소스(가중치 일일합)', stack='zero'),
            color=enc_color,
            order=alt.Order('order_val:Q', sort='ascending'),
            tooltip=[
                alt.Tooltip('date:T', title='날짜'),
                alt.Tooltip(f'{color_col}:N', title=color_col),
                alt.Tooltip('리소스:Q', title='리소스 합', format='.2f')
            ]
        )
        .properties(title=title, height=320)
    )
    return ch

def _weekly_sum(daily_df):
    """일간 피벗을 9개 주(월~일)로 합산. 행=주차, 열=카테고리(팀/담당자)."""
    if daily_df is None or daily_df.empty:
        return pd.DataFrame(index=WEEK_LABELS)
    rows = []
    for ws, we in zip(WEEK_STARTS, WEEK_ENDS):
        s = max(ws, START)
        e = min(we, END)
        if s > e:
            sums = pd.Series(0.0, index=daily_df.columns)
        else:
            sums = daily_df.loc[s:e].sum(axis=0)
        rows.append(sums)
    weekly = pd.DataFrame(rows, index=WEEK_LABELS)
    try:
        weekly = weekly.round(0).astype('Int64')
    except Exception:
        pass
    return weekly

def _reorder_columns_by_total(df):
    if df is None or df.empty or df.shape[1] == 0:
        return df
    order = df.sum(axis=0).sort_values(ascending=False).index.tolist()
    return df.reindex(columns=order)

# ─────────────────────────── 소스 준비: WON + ALL(확정) 병합 (중복 제거)
@st.cache_data(show_spinner=False)
def _prepare_deals():
    """
    최종 집계용 row 생성:
      - 공통 필드: 팀, 담당자_name, 시작, 종료, s_idx, e_idx, weight
      - won_deal: 금액(우선) or 수주예정액(종합)
      - all_deal: 성사 가능성 '확정' & 수강시작/종료 유효 & 수주예정액(종합) > 0
      - ONLINE_SET 제외
      - won 기준으로 all 중복 제거 ('코스 ID'→합성키 순)
    """
    # ── WON
    won = load_won_deal().copy()
    won['담당자_name'] = _norm_person(won['담당자_name'])
    won['팀'] = won['담당자_name'].map(NAME2TEAM)
    won = won[won['팀'].isin(TEAMS)].copy()

    # 온라인 제외
    if '과정포맷(대)' in won.columns:
        won['과정포맷(대)'] = won['과정포맷(대)'].fillna('').astype(str).str.strip()
        won = won[~won['과정포맷(대)'].isin(ONLINE_SET)].copy()

    # 기간 파싱/클리핑
    # (won에도 수강시작/종료가 있다고 가정; 내부 레거시가 '교육...'이면 추가 분기 필요)
    if not {'수강시작일','수강종료일'}.issubset(won.columns):
        st.error("won_deal에 '수강시작일'과 '수강종료일' 컬럼이 필요합니다.")
        return pd.DataFrame()
    won = _parse_dates(won, '수강시작일','수강종료일')

    # 금액 → weight
    amt_col_w = None
    for c in ['금액','수주 예정액(종합)','계약금액','수주금액','총금액']:
        if c in won.columns:
            amt_col_w = c
            break
    won['금액_원'] = _to_number(won[amt_col_w]) if amt_col_w else 0.0
    won['weight'] = won['금액_원'].apply(_weight_from_amount)

    # won 키(코스ID/합성키)
    won['코스ID_key'] = won.get('코스 ID', pd.Series(index=won.index, dtype=object)).astype(str).str.strip()
    won['코스ID_key'] = won['코스ID_key'].mask(won['코스ID_key'].eq('') | won['코스ID_key'].eq('nan'), np.nan)
    def _fallback_key(df):
        comp = (
            df.get('기업명','').astype(str).str.strip() + '|' +
            df.get('담당자_name','').astype(str).str.strip() + '|' +
            df['시작'].dt.strftime('%Y-%m-%d') + '|' +
            df['종료'].dt.strftime('%Y-%m-%d')
        )
        return comp.str.upper()
    won['FB_key'] = _fallback_key(won)

    won['s_idx'] = won['시작'].dt.normalize().map(POS).astype('Int64')
    won['e_idx'] = won['종료'].dt.normalize().map(POS).astype('Int64')
    won_keep = won[['팀','담당자_name','시작','종료','s_idx','e_idx','weight','코스ID_key','FB_key']].copy()

    # ── ALL (확정 + 유효기간 + 수주예정액>0)
    alld = load_all_deal().copy()
    alld['담당자_name'] = _norm_person(alld['담당자_name'])
    alld['팀'] = alld['담당자_name'].map(NAME2TEAM)
    alld = alld[alld['팀'].isin(TEAMS)].copy()

    # 온라인 제외
    if '과정포맷(대)' in alld.columns:
        alld['과정포맷(대)'] = alld['과정포맷(대)'].fillna('').astype(str).str.strip()
        alld = alld[~alld['과정포맷(대)'].isin(ONLINE_SET)].copy()

    # 성사 가능성 '확정'만
    alld['성사 가능성'] = alld['성사 가능성'].apply(_norm_status)
    alld = alld[alld['성사 가능성'] == '확정'].copy()

    # 기간 파싱/클리핑
    if not {'수강시작일','수강종료일'}.issubset(alld.columns):
        st.error("all_deal에 '수강시작일'과 '수강종료일' 컬럼이 필요합니다.")
        return pd.DataFrame()
    alld = _parse_dates(alld, '수강시작일','수강종료일')

    # 수주예정액(종합) > 0
    if '수주 예정액(종합)' not in alld.columns:
        st.error("all_deal에 '수주 예정액(종합)' 컬럼이 필요합니다.")
        return pd.DataFrame()
    alld['금액_원'] = _to_number(alld['수주 예정액(종합)']).fillna(0.0)
    alld = alld[alld['금액_원'] > 0].copy()
    alld['weight'] = alld['금액_원'].apply(_weight_from_amount)

    # all 키(코스ID/합성키)
    alld['코스ID_key'] = alld.get('코스 ID', pd.Series(index=alld.index, dtype=object)).astype(str).str.strip()
    alld['코스ID_key'] = alld['코스ID_key'].mask(alld['코스ID_key'].eq('') | alld['코스ID_key'].eq('nan'), np.nan)
    alld['FB_key'] = _fallback_key(alld)

    # ── won 기준으로 all 중복 제거
    won_id_set = set(won_keep['코스ID_key'].dropna().unique())
    won_fb_set = set(won_keep['FB_key'].dropna().unique())
    alld_dedup = alld[
        ~(
            (alld['코스ID_key'].notna() & alld['코스ID_key'].isin(won_id_set)) |
            (alld['FB_key'].notna() & alld['FB_key'].isin(won_fb_set))
        )
    ].copy()

    # 인덱스 매핑
    alld_dedup['s_idx'] = alld_dedup['시작'].dt.normalize().map(POS).astype('Int64')
    alld_dedup['e_idx'] = alld_dedup['종료'].dt.normalize().map(POS).astype('Int64')

    alld_keep = alld_dedup[['팀','담당자_name','시작','종료','s_idx','e_idx','weight']].copy()
    won_keep2 = won_keep[['팀','담당자_name','시작','종료','s_idx','e_idx','weight']].copy()

    # ── 합치기
    final_df = pd.concat([won_keep2, alld_keep], ignore_index=True)
    return final_df

# ─────────────────────────── UI
st.title("사업부 운영 리소스 현황 — 2025 (일간/주간)")

with st.expander("정책 요약 / 계산 기준", expanded=False):
    st.markdown("""
- **대상**: won 딜 **+** all 딜(성사 가능성=확정, `수강시작일`·`수강종료일` 유효, `수주 예정액(종합)>0`)  
- **중복 제거**: won에 있는 건 all 확정 집계에서 **제외**  
  - 우선순위: `코스 ID` 일치 → 없으면 `기업명+담당자+수강시작일+수강종료일` 합성키  
- **기간**: **수강시작일~수강종료일** (*2024 won/all이라도 2025와 겹치면 포함, 2025년 경계로 클리핑*)  
- **온라인 제외**: `선택구매(온라인)`, `구독제(온라인)`, `포팅`  
- **일일 누적**: 금액 구간별 가중치(1/2/3/5/7/10)를 **매일** 더함  
- **주간 표**: 한국 기준 **금주(월~일)** 중심 **-4주 ~ +4주** 범위 합계
""")

df = _prepare_deals()
if df.empty:
    st.stop()

# ── 팀/담당자 일간 시계열
team_daily = _accumulate_by_key(df, '팀').reindex(columns=TEAMS).fillna(0.0)

df_1 = df[df['팀'] == '기업교육 1팀']
df_2 = df[df['팀'] == '기업교육 2팀']

p1_daily = _accumulate_by_key(df_1, '담당자_name')
p2_daily = _accumulate_by_key(df_2, '담당자_name')

# ── 담당자 컬럼을 팀 정의 순서로 1차 정렬(보기 편의) → 차트/표에서 합계 기준 재정렬
p1_daily = p1_daily.reindex(columns=[n for n in TEAM_RAW['기업교육 1팀'] if n in p1_daily.columns]).fillna(0.0)
p2_daily = p2_daily.reindex(columns=[n for n in TEAM_RAW['기업교육 2팀'] if n in p2_daily.columns]).fillna(0.0)

# ── Quick metrics
m1 = float(team_daily['기업교육 1팀'].sum()) if '기업교육 1팀' in team_daily else 0.0
m2 = float(team_daily['기업교육 2팀'].sum()) if '기업교육 2팀' in team_daily else 0.0

# ========================= TABS =========================
tab_graphs, tab_weeks = st.tabs(["그래프", "주간 표"])

# ────────── 탭 1: 그래프
with tab_graphs:
    c1, c2, c3 = st.columns(3)
    c1.metric("1팀 총 리소스(연간 합)", f"{m1:,.0f}")
    c2.metric("2팀 총 리소스(연간 합)", f"{m2:,.0f}")
    c3.metric("사업부 총 리소스(연간 합)", f"{m1+m2:,.0f}")

    st.markdown("---")

    # 그래프 1: 1팀 vs 2팀 스택 (큰 팀이 아래)
    team_long, team_order = _melt_with_order(team_daily, var_name="팀")
    st.altair_chart(
        _stacked_bar(team_long, color_col="팀", title="그래프 1 — 1팀+2팀 일간 스택 막대", color_order=team_order),
        use_container_width=True
    )

    # 그래프 2: 1팀 담당자 스택 (리소스 상위가 아래)
    if not p1_daily.empty and p1_daily.shape[1] > 0:
        p1_long, p1_order = _melt_with_order(p1_daily, var_name="담당자")
        st.altair_chart(
            _stacked_bar(p1_long, color_col="담당자", title="그래프 2 — 1팀(담당자별) 일간 스택 막대", color_order=p1_order),
            use_container_width=True
        )
    else:
        st.info("1팀 데이터가 없습니다.")

    # 그래프 3: 2팀 담당자 스택 (리소스 상위가 아래)
    if not p2_daily.empty and p2_daily.shape[1] > 0:
        p2_long, p2_order = _melt_with_order(p2_daily, var_name="담당자")
        st.altair_chart(
            _stacked_bar(p2_long, color_col="담당자", title="그래프 3 — 2팀(담당자별) 일간 스택 막대", color_order=p2_order),
            use_container_width=True
        )
    else:
        st.info("2팀 데이터가 없습니다.")

# ────────── 탭 2: 주간 표
with tab_weeks:
    st.subheader("금주 기준 -4주 ~ +4주 (월~일) 주간 리소스 합계")
    st.caption(f"금주(월~일): {WEEK_LABELS[4]} 기준 · 범위: {WEEK_LABELS[0]}  →  {WEEK_LABELS[-1]}")

    # 표 1: 팀별(1팀/2팀) 주간 리소스
    st.markdown("### 표 1 — 팀별(1팀/2팀) 주간 리소스")
    tbl_team = _weekly_sum(team_daily)
    tbl_team = tbl_team.reindex(columns=[c for c in TEAMS if c in tbl_team.columns])
    st.dataframe(tbl_team, use_container_width=True)

    st.markdown("---")

    # 표 2: 1팀 구성원별
    st.markdown("### 표 2 — 1팀 구성원별 주간 리소스")
    if not p1_daily.empty and p1_daily.shape[1] > 0:
        tbl_p1 = _weekly_sum(p1_daily)
        tbl_p1 = _reorder_columns_by_total(tbl_p1)
        st.dataframe(tbl_p1, use_container_width=True)
    else:
        st.info("1팀 구성원 데이터가 없습니다.")

    st.markdown("---")

    # 표 3: 2팀 구성원별
    st.markdown("### 표 3 — 2팀 구성원별 주간 리소스")
    if not p2_daily.empty and p2_daily.shape[1] > 0:
        tbl_p2 = _weekly_sum(p2_daily)
        tbl_p2 = _reorder_columns_by_total(tbl_p2)
        st.dataframe(tbl_p2, use_container_width=True)
    else:
        st.info("2팀 구성원 데이터가 없습니다.")
