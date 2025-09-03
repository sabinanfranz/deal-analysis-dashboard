# pages/20_사업부_운영리소스_및_성사가능성_통합.py
"""
사업부 운영 리소스 & 성사 가능성 (2025, 일간/주간, 간소화)
- [리소스] won + all(확정 & 수강시작/종료 유효 & 수주예정액>0), won-중복 제거, ONLINE 제외, 2025 경계 클리핑
- [리소스] 탭1(사업부): 팀별 그래프 + 팀별 주간 표 / 탭2·3(1팀·2팀): 담당자 그래프 + 주간 표
- [성사가능성] 상태= {높음, 낮음, 미기재, LOST} 만 사용. 리소스 현황= 높음+낮음+미기재, 중견중소 현황 유지
- [요청 반영]
  · 주간 표: 팀원 모두 노출(합계 0이어도)  · 요약 표: 팀원 모두 노출
  · 주간 표의 이름 순서 == 요약 표의 컬럼 순서
  · 사업부 탭: 팀 레벨 요약(1팀/2팀), 상세 표는 1+2팀 합산
  · 상세 표의 '수주 예정액(종합)'은 억 단위(1e8)로 표시.
    - 다음 중 하나라도 해당되면 '미기재'로 표시:
      (a) '금액' NULL, (b) '예상 체결액' NULL, (c) 수주 예정액(종합) 비었거나 수치화 불가/≤0
  · (신규) 1팀/2팀 요약 표(담당자)는 맨 위에 **'예상 체결액'(억원)** 행 추가
"""

import re
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
from datetime import datetime
from zoneinfo import ZoneInfo
from data import load_won_deal, load_all_deal

# ─────────────────────────── 공통 설정/상수
st.set_page_config(page_title="사업부 운영 리소스 & 성사 가능성 (2025)", layout="wide")

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

# 오늘(한국 기준)과 금주(월~일)
TODAY = pd.Timestamp(datetime.now(ZoneInfo('Asia/Seoul')).date())
W0_START = TODAY - pd.Timedelta(days=TODAY.weekday())
WEEK_STARTS = [W0_START + pd.Timedelta(weeks=k) for k in range(-4, 5)]
WEEK_ENDS   = [ws + pd.Timedelta(days=6) for ws in WEEK_STARTS]
WEEK_LABELS = [f"{ws:%Y-%m-%d} ~ {we:%m-%d}" for ws, we in zip(WEEK_STARTS, WEEK_ENDS)]

# ─────────────────────────── [리소스] 유틸
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
    return s.fillna('').astype(str).str.replace(r'B$','', regex=True).str.strip()

def _norm_status_all(x):
    """all_deal용 상태 정규화 (won/확정/높음/낮음/LOST/미기재)"""
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
    df['시작'] = df['시작'].clip(lower=START)
    df['종료'] = df['종료'].clip(upper=END)
    valid = df['시작'].notna() & df['종료'].notna() & (df['시작'] <= df['종료'])
    return df[valid].copy()

def _make_diff_series(n, s_idx, e_idx, w):
    diff = np.zeros(n + 1, dtype=np.float32)
    s = s_idx.astype(int).to_numpy()
    e1 = (e_idx.astype(int) + 1).to_numpy()
    wv = w.astype(float).to_numpy()
    np.add.at(diff, s, wv)
    mask = e1 < len(diff)
    np.add.at(diff, e1[mask], -wv[mask])
    return np.cumsum(diff[:-1])

def _accumulate_by_key(df, key_col):
    """차분 + 누적합으로 key별 일간 리소스 시계열 생성."""
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
    if pivot_df.empty or pivot_df.shape[1] == 0:
        return [], {}
    totals = pivot_df.sum(axis=0).sort_values(ascending=False)
    order_list = list(totals.index)
    order_val  = {k: -float(v) for k, v in totals.items()}
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
    return (
        alt.Chart(df_long)
        .mark_bar()
        .encode(
            x=alt.X('date:T', title='', axis=alt.Axis(format='%m-%d', tickCount=12)),
            y=alt.Y('리소스:Q', title='리소스(가중치 일일합)', stack='zero'),
            color=enc_color,
            order=alt.Order('order_val:Q', sort='ascending'),
            tooltip=[alt.Tooltip('date:T', title='날짜'),
                     alt.Tooltip(f'{color_col}:N', title=color_col),
                     alt.Tooltip('리소스:Q', title='리소스 합', format='.2f')]
        ).properties(title=title, height=320)
    )

def _weekly_sum(daily_df):
    """일간 피벗을 9개 주(월~일)로 합산. 행=주차, 열=카테고리."""
    if daily_df is None or daily_df.empty:
        return pd.DataFrame(index=WEEK_LABELS)
    rows = []
    for ws, we in zip(WEEK_STARTS, WEEK_ENDS):
        s = max(ws, START)
        e = min(we, END)
        sums = pd.Series(0.0, index=daily_df.columns) if s > e else daily_df.loc[s:e].sum(axis=0)
        rows.append(sums)
    weekly = pd.DataFrame(rows, index=WEEK_LABELS)
    try:
        weekly = weekly.round(0).astype('Int64')
    except Exception:
        pass
    return weekly

def _weekly_with_order(daily_df: pd.DataFrame, full_columns: list[str]):
    """
    주간 합계 테이블(9주) 생성 + 열 순서(9주 합 내림차순) 반환.
    - full_columns 로 모든 팀원 컬럼을 강제 포함(값 없으면 0)
    """
    wk = _weekly_sum(daily_df)
    wk = wk.reindex(columns=full_columns, fill_value=0)   # 팀원 전원 포함
    totals = wk.sum(axis=0)
    order = totals.sort_values(ascending=False, kind='mergesort').index.tolist()
    wk = wk.reindex(columns=order)
    return wk, order

# ─────────────────────────── [리소스] 소스 준비 (WON + ALL 확정, 중복 제거)
@st.cache_data(show_spinner=False)
def _prepare_resource_rows():
    """
    반환: 운영 리소스 산정용 row (중복 제거·필터 적용 후)
      필수 컬럼: ['팀','담당자_name','시작','종료','s_idx','e_idx','weight']
      + 표시용 컬럼:
        ['생성년도','생성월','기업명','기업 규모','이름','상태','성사 가능성','수주 예정액(종합)',
         '수강시작일','수강종료일','과정포맷(대)','카테고리(대)','source','금액_원']
    - won: 금액(우선) or 수주예정액(종합)으로 weight 산정 (금액 미기재면 최소 가중치 1)
    - all(확정): 수강시작/종료 유효 & 수주예정액>0
    - ONLINE 제외, 2025 클리핑
    - won 기준으로 all 중복 제거(코스ID→합성키)
    """
    # ── WON
    won = load_won_deal().copy()
    won['담당자_name'] = _norm_person(won['담당자_name'])
    won['팀'] = won['담당자_name'].map(NAME2TEAM)
    won = won[won['팀'].isin(TEAMS)].copy()

    if '과정포맷(대)' in won.columns:
        won['과정포맷(대)'] = won['과정포맷(대)'].fillna('').astype(str).str.strip()
        won = won[~won['과정포맷(대)'].isin(ONLINE_SET)].copy()

    if not {'수강시작일','수강종료일'}.issubset(won.columns):
        st.error("won_deal에 '수강시작일'과 '수강종료일' 컬럼이 필요합니다.")
        return pd.DataFrame()
    won = _parse_dates(won, '수강시작일','수강종료일')

    amt_col_w = next((c for c in ['금액','수주 예정액(종합)','계약금액','수주금액','총금액'] if c in won.columns), None)
    won['금액_원'] = _to_number(won[amt_col_w]) if amt_col_w else 0.0
    won['weight'] = won['금액_원'].apply(_weight_from_amount)

    won['코스ID_key'] = won.get('코스 ID', pd.Series(index=won.index, dtype=object)).astype(str).str.strip()
    won['코스ID_key'] = won['코스ID_key'].mask(won['코스ID_key'].eq('') | won['코스ID_key'].eq('nan'), np.nan)

    def _fb_key(df):
        return (
            df.get('기업명','').astype(str).str.strip() + '|' +
            df.get('담당자_name','').astype(str).str.strip() + '|' +
            df['시작'].dt.strftime('%Y-%m-%d') + '|' +
            df['종료'].dt.strftime('%Y-%m-%d')
        ).str.upper()
    won['FB_key'] = _fb_key(won)

    won['s_idx'] = won['시작'].dt.normalize().map(POS).astype('Int64')
    won['e_idx'] = won['종료'].dt.normalize().map(POS).astype('Int64')

    # won 표시용 컬럼 채우기(수강시작/종료는 클리핑된 값을 그대로 사용)
    won_keep = won.assign(
        source='WON',
        수강시작일=won['시작'],
        수강종료일=won['종료']
    )[[
        '팀','담당자_name','시작','종료','s_idx','e_idx','weight','코스ID_key','FB_key',
        # 표시용
        '생성년도','생성월','기업명','기업 규모','이름','상태','성사 가능성','수주 예정액(종합)',
        '수강시작일','수강종료일','과정포맷(대)','카테고리(대)','source','금액_원'
    ]].copy()

    # ── ALL (확정 + 유효기간 + 수주예정액>0)
    alld = load_all_deal().copy()
    alld['담당자_name'] = _norm_person(alld['담당자_name'])
    alld['팀'] = alld['담당자_name'].map(NAME2TEAM)
    alld = alld[alld['팀'].isin(TEAMS)].copy()

    if '과정포맷(대)' in alld.columns:
        alld['과정포맷(대)'] = alld['과정포맷(대)'].fillna('').astype(str).str.strip()
        alld = alld[~alld['과정포맷(대)'].isin(ONLINE_SET)].copy()

    alld['성사 가능성'] = alld['성사 가능성'].apply(_norm_status_all)
    alld = alld[alld['성사 가능성'] == '확정'].copy()

    if not {'수강시작일','수강종료일'}.issubset(alld.columns):
        st.error("all_deal에 '수강시작일'과 '수강종료일' 컬럼이 필요합니다.")
        return pd.DataFrame()
    alld = _parse_dates(alld, '수강시작일','수강종료일')

    if '수주 예정액(종합)' not in alld.columns:
        st.error("all_deal에 '수주 예정액(종합)' 컬럼이 필요합니다.")
        return pd.DataFrame()
    alld['금액_원'] = _to_number(alld['수주 예정액(종합)']).fillna(0.0)
    alld = alld[alld['금액_원'] > 0].copy()
    alld['weight'] = alld['금액_원'].apply(_weight_from_amount)

    alld['코스ID_key'] = alld.get('코스 ID', pd.Series(index=alld.index, dtype=object)).astype(str).str.strip()
    alld['코스ID_key'] = alld['코스ID_key'].mask(alld['코스ID_key'].eq('') | alld['코스ID_key'].eq('nan'), np.nan)
    alld['FB_key'] = _fb_key(alld)

    # won 기준으로 all 중복 제거
    won_id_set = set(won_keep['코스ID_key'].dropna().unique())
    won_fb_set = set(won_keep['FB_key'].dropna().unique())
    alld_dedup = alld[~(
        (alld['코스ID_key'].notna() & alld['코스ID_key'].isin(won_id_set)) |
        (alld['FB_key'].notna() & alld['FB_key'].isin(won_fb_set))
    )].copy()

    # 인덱스 매핑 + 표시용 컬럼 준비
    alld_dedup['s_idx'] = alld_dedup['시작'].dt.normalize().map(POS).astype('Int64')
    alld_dedup['e_idx'] = alld_dedup['종료'].dt.normalize().map(POS).astype('Int64')

    alld_keep = alld_dedup.assign(
        source='ALL',
        수강시작일=alld_dedup['시작'],
        수강종료일=alld_dedup['종료']
    )[[
        '팀','담당자_name','시작','종료','s_idx','e_idx','weight','코스ID_key','FB_key',
        # 표시용
        '생성년도','생성월','기업명','기업 규모','이름','상태','성사 가능성','수주 예정액(종합)',
        '수강시작일','수강종료일','과정포맷(대)','카테고리(대)','source','금액_원'
    ]].copy()

    # 합치기
    final_df = pd.concat([won_keep, alld_keep], ignore_index=True)

    # 표시 안정성: 일부 표시 컬럼이 없을 때 대비
    for c in ['생성년도','생성월','기업명','기업 규모','이름','상태','성사 가능성',
              '수주 예정액(종합)','수강시작일','수강종료일','과정포맷(대)','카테고리(대)']:
        if c not in final_df.columns:
            final_df[c] = pd.NA

    return final_df

# ─────────────────────────── [성사가능성] 상수/유틸
SHOW_STATUS = ['높음','낮음','미기재','LOST']
RES_STATUS  = ['높음','낮음','미기재']
ROW_ORDER   = ['리소스 현황','중견중소 현황'] + SHOW_STATUS
DETAIL_COLS = [
    '생성년도','생성월','기업명','기업 규모','담당자_name','이름','상태','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net','수강시작일','수강종료일',
    '과정포맷(대)','카테고리(대)'
]

@st.cache_data(show_spinner=False)
def _prepare_status_df():
    """성사 가능성 간소화용 all_deal 전처리 (2024.10~2025.12)."""
    s = load_all_deal().copy()
    s['담당자_name'] = _norm_person(s['담당자_name'])
    s['팀'] = s['담당자_name'].map(NAME2TEAM)
    s['생성월'] = pd.to_numeric(s['생성월'], errors='coerce')
    s = s[
        s['팀'].isin(TEAMS) &
        ( ((s['생성년도'] == 2024) & (s['생성월'] >= 10)) |
          ((s['생성년도'] == 2025) & (s['생성월'] <= 12)) )
    ].copy()
    s['과정포맷(대)'] = s['과정포맷(대)'].fillna('').astype(str).str.strip()
    s['기업 규모']   = s['기업 규모'].fillna('').astype(str).str.strip()
    s['성사 가능성'] = s['성사 가능성'].apply(_norm_status_all)
    return s

def team_all_persons(team_name: str) -> list[str]:
    return TEAM_RAW.get(team_name, [])

def summary_matrix_team(dept_df: pd.DataFrame) -> pd.DataFrame:
    base = dept_df[dept_df['성사 가능성'].isin(SHOW_STATUS)].copy()
    stat = base.groupby(['팀','성사 가능성']).size().unstack(fill_value=0)
    for stt in SHOW_STATUS:
        if stt not in stat.columns: stat[stt] = 0
    stat['리소스 현황'] = stat[RES_STATUS].sum(axis=1)
    mask = (~dept_df['과정포맷(대)'].isin(ONLINE_SET) &
            dept_df['기업 규모'].isin(['중견기업','중소기업']) &
            dept_df['성사 가능성'].isin(RES_STATUS))
    mid_cnt = dept_df[mask].groupby('팀').size()
    stat['중견중소 현황'] = mid_cnt
    stat = stat.reindex(TEAMS).fillna(0).astype(int)
    mat = stat[['리소스 현황','중견중소 현황'] + SHOW_STATUS].T
    return mat.astype('Int64')

def summary_matrix_people(team_df: pd.DataFrame, team_name: str, col_order: list[str] | None) -> pd.DataFrame:
    """
    행=카운트 항목 + 예상 체결액(억원), 열=담당자(팀원 전체).
    - col_order가 주어지면 그 순서로 열을 정렬(주간 표의 열 순서와 동기화).
    - '예상 체결액'은 리소스 현황을 카운트하는 딜(상태 ∈ {높음,낮음,미기재})의 '수주 예정액(종합)' 합계를 **억원**으로 표기(소수 둘째 자리).
    """
    persons = team_all_persons(team_name)
    base = team_df[team_df['성사 가능성'].isin(SHOW_STATUS)].copy()

    # 상태 카운트 피벗
    stat = base.groupby(['담당자_name','성사 가능성']).size().unstack(fill_value=0)
    for stt in SHOW_STATUS:
        if stt not in stat.columns: stat[stt] = 0

    # 리소스 현황(카운트)
    stat['리소스 현황'] = stat[RES_STATUS].sum(axis=1)

    # 중견중소 현황(오프라인 & 상태∈RES_STATUS & 규모∈중견/중소)
    mask_mid = (~team_df['과정포맷(대)'].isin(ONLINE_SET) &
                team_df['기업 규모'].isin(['중견기업','중소기업']) &
                team_df['성사 가능성'].isin(RES_STATUS))
    mid_cnt = team_df[mask_mid].groupby('담당자_name').size()
    stat['중견중소 현황'] = mid_cnt

    # 열 강제 포함(팀원 전체) + 순서 동기화
    base_cols = col_order if col_order else persons
    full_order = [c for c in base_cols if c in persons] + [c for c in persons if c not in base_cols]
    stat = stat.reindex(full_order).fillna(0).astype(int)

    # ── (신규) 예상 체결액(억원) 행 계산: 상태 ∈ RES_STATUS 의 '수주 예정액(종합)' 합
    if '수주 예정액(종합)' in team_df.columns:
        amt_num = _to_number(team_df['수주 예정액(종합)']).fillna(0.0)
        amt_df = team_df.assign(__amt=amt_num)
        amt_ser = (amt_df[amt_df['성사 가능성'].isin(RES_STATUS)]
                   .groupby('담당자_name')['__amt'].sum())
        amt_ser = amt_ser.reindex(full_order).fillna(0.0)
        amt_row = (amt_ser / 1e8).round(2).map(lambda v: f"{v:.2f}")  # 억 단위 문자열
    else:
        amt_row = pd.Series(['0.00'] * len(full_order), index=full_order)

    # 출력 매트릭스 구성: 첫 행 '예상 체결액' + 기존 카운트 행들
    mat_counts = stat[['리소스 현황','중견중소 현황'] + SHOW_STATUS].T
    mat_amount = pd.DataFrame([amt_row.values], index=['예상 체결액'], columns=full_order)
    mat = pd.concat([mat_amount, mat_counts], axis=0)

    return mat  # (혼합형: 예상 체결액=문자열, 나머지=정수)

def detail_df(team_like_df: pd.DataFrame, persons: list[str] | None, status: str) -> pd.DataFrame:
    """상세 표(상태별). persons=None이면 전 팀 합산, 리스트면 해당 담당자만.
       수주 예정액(종합): 억 단위(두 자리 소수) 문자열로 표시하되,
       아래 중 하나라도 해당되면 '미기재'로 표시:
         · '수주 예정액(종합)' 비었거나 수치화 불가 또는 ≤ 0
         · ('금액'과 '예상 체결액'이 모두 NULL)  ← AND 조건
    """
    if status not in SHOW_STATUS:
        return pd.DataFrame(columns=DETAIL_COLS)
    sub = team_like_df[team_like_df['성사 가능성'] == status].copy()
    if persons is not None:
        sub = sub[sub['담당자_name'].isin(persons)]
    if sub.empty:
        return pd.DataFrame(columns=DETAIL_COLS)

    sub['team_rank'] = sub['팀'].map(lambda t: TEAMS.index(t) if t in TEAMS else 999)
    sub['name_rank'] = sub['담당자_name'].map(
        lambda n: TEAM_RAW.get(NAME2TEAM.get(n,''), []).index(n)
        if n in TEAM_RAW.get(NAME2TEAM.get(n,''), []) else 999
    )
    sub = sub.sort_values(['team_rank','name_rank','생성월','기업명'])
    res = sub.drop(columns=['team_rank','name_rank'])[DETAIL_COLS].copy()

    if '수주 예정액(종합)' in res.columns:
        # ① '수주 예정액(종합)' 자체 체크
        orig = res['수주 예정액(종합)']
        is_blank = orig.isna() | (orig.astype(str).str.strip() == '')
        num = _to_number(orig)  # 콤마 제거 등 숫자화(실패시 NaN)

        # ② '금액' & '예상 체결액' 둘 다 NULL인지(AND) 확인
        def _nullish(colname):
            if colname not in res.columns:
                return pd.Series(False, index=res.index)
            c = res[colname]
            s = c.astype(str).str.strip().str.lower()
            return c.isna() | s.eq('') | s.eq('nan') | s.eq('none')

        null_amount   = _nullish('금액')
        null_expected = _nullish('예상 체결액')
        null_both = null_amount & null_expected

        # ③ 최종 '미기재' 마스크
        missing_or_zero = is_blank | num.isna() | (num <= 0) | null_both

        # ④ 값 있는 경우 억 단위(두 자리 소수)로 문자열 포맷
        formatted = (num / 1e8).round(2).map(lambda v: f"{v:.2f}")
        res['수주 예정액(종합)'] = formatted.mask(missing_or_zero, '미기재')

    return res

# ───── 운영 리소스 산정 딜 표(담당자 필터 반영) 생성 헬퍼
RESOURCE_DISPLAY_COLS = [
    '생성년도','생성월','기업명','기업 규모','담당자_name','이름','상태','성사 가능성',
    '수주 예정액(종합)','일별 가중치','수강시작일','수강종료일','과정포맷(대)','카테고리(대)'
]

def make_resource_selection_table(res_rows: pd.DataFrame, team: str, persons_sel: list[str]) -> pd.DataFrame:
    sub = res_rows[res_rows['팀'] == team].copy()
    if persons_sel and persons_sel != team_all_persons(team):
        sub = sub[sub['담당자_name'].isin(persons_sel)]

    if sub.empty:
        return pd.DataFrame(columns=RESOURCE_DISPLAY_COLS)

    # 표시용 가공
    view = sub.copy()
    # 억 단위 포맷(두 자리), 숫자 없거나 ≤0이면 '미기재'
    if '수주 예정액(종합)' in view.columns:
        num = _to_number(view['수주 예정액(종합)'])
        view['수주 예정액(종합)'] = np.where(num.notna() & (num > 0),
                                          (num/1e8).round(2).map(lambda v: f"{v:.2f}"),
                                          '미기재')
    # 일별 가중치 = weight
    view['일별 가중치'] = view['weight'].round(0).astype('Int64')

    # 수강 시작/종료일(클리핑된 값) 날짜 표기
    view['수강시작일'] = pd.to_datetime(view['수강시작일'], errors='coerce').dt.date
    view['수강종료일'] = pd.to_datetime(view['수강종료일'], errors='coerce').dt.date

    # 필요한 컬럼만, 빈 컬럼 보강
    for c in RESOURCE_DISPLAY_COLS:
        if c not in view.columns:
            view[c] = pd.NA

    view = view[RESOURCE_DISPLAY_COLS].sort_values(
        ['담당자_name','수강시작일','기업명'], na_position='last'
    )

    return view

# ─────────────────────────── 데이터 준비
st.title("사업부 운영 리소스 & 성사 가능성 — 2025")

with st.expander("정책 요약 / 계산 기준", expanded=False):
    st.markdown("""
- **리소스 포함 기준**
  - **WON**: 팀 소속(기업교육 1·2팀), ONLINE 제외, `수강시작일~수강종료일` **유효**(2025 경계로 클리핑)  
    금액 열(우선순위 **금액 → 수주 예정액(종합) → 계약금액 → 수주금액 → 총금액**)로 가중치 산정  
    *(금액 미기재/0이어도 최소 가중치 1로 반영)*  
  - **ALL**: 팀 소속, ONLINE 제외, `성사 가능성=확정`, `수강시작/종료` **유효**, **`수주 예정액(종합) > 0`**  
  - **중복 제거**: WON에 있는 건은 ALL에서 제외 (우선순위 **코스 ID** → 없으면 **기업명|담당자|시작|종료** 합성키)
- **일일 누적**: 각 딜의 **일별 가중치**를 `수강시작일~수강종료일` 동안 **매일** 더함
- **금액 구간별 가중치(원화 기준)**

| 금액(원) 구간                    | 일별 가중치 |
|:---------------------------------|:-----------:|
| ≤ 5,000,000                      | 1 |
| 5,000,001 ~ 25,000,000           | 2 |
| 25,000,001 ~ 50,000,000          | 3 |
| 50,000,001 ~ 100,000,000         | 5 |
| 100,000,001 ~ 300,000,000        | 7 |
| > 300,000,000                    | 10 |

- **요약 표(담당자)**: 맨 위 **'예상 체결액'(억원)** 은 **리소스 현황(상태 ∈ {높음,낮음,미기재})에 포함되는 딜의 `수주 예정액(종합)` 합계**를 **억원(소수 둘째)**로 표시  
- **주간 표**: 한국 기준 **금주(월~일)** 중심 **-4주 ~ +4주**  
- **성사가능성(간소화)**: 상태 = {**높음, 낮음, 미기재, LOST**}, **리소스 현황 = 높음+낮음+미기재**, **중견중소 현황 유지**
""")

# [리소스] 준비
res_rows = _prepare_resource_rows()
if res_rows.empty:
    st.stop()

team_daily = _accumulate_by_key(res_rows, '팀').reindex(columns=TEAMS).fillna(0.0)

rows_t1 = res_rows[res_rows['팀'] == '기업교육 1팀']
rows_t2 = res_rows[res_rows['팀'] == '기업교육 2팀']
p1_daily = _accumulate_by_key(rows_t1, '담당자_name')
p2_daily = _accumulate_by_key(rows_t2, '담당자_name')

# 팀원 전원 포함(값 없으면 0으로 채움)
t1_all = TEAM_RAW['기업교육 1팀']
t2_all = TEAM_RAW['기업교육 2팀']
p1_daily = p1_daily.reindex(columns=t1_all).fillna(0.0)
p2_daily = p2_daily.reindex(columns=t2_all).fillna(0.0)

# 메트릭
m1 = float(team_daily['기업교육 1팀'].sum()) if '기업교육 1팀' in team_daily else 0.0
m2 = float(team_daily['기업교육 2팀'].sum()) if '기업교육 2팀' in team_daily else 0.0
m_bu = float(team_daily.sum(axis=1).sum())

# [성사가능성] 준비
s_df = _prepare_status_df()

# ─────────────────────────── 탭
tab_bu, tab_t1, tab_t2 = st.tabs(["사업부", "1팀", "2팀"])

# ======================= 탭 1: 사업부 =======================
with tab_bu:
    # (리소스) ─────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("1팀 총 리소스(연간 합)", f"{m1:,.0f}")
    c2.metric("2팀 총 리소스(연간 합)", f"{m2:,.0f}")
    c3.metric("사업부 총 리소스(연간 합)", f"{m_bu:,.0f}")

    st.markdown("---")
    team_long, team_order = _melt_with_order(team_daily, var_name="팀")
    st.altair_chart(
        _stacked_bar(team_long, color_col="팀", title="사업부 — 팀별(1팀/2팀) 일간 스택 막대", color_order=team_order),
        use_container_width=True
    )

    st.markdown("### 금주 기준 -4주 ~ +4주 (월~일) 주간 리소스 합계 — 팀별")
    st.caption(f"금주(월~일): {WEEK_LABELS[4]} · 범위: {WEEK_LABELS[0]} → {WEEK_LABELS[-1]}")
    tbl_team_wk = _weekly_sum(team_daily).reindex(columns=TEAMS)
    st.dataframe(tbl_team_wk, use_container_width=True)

    # (성사가능성) ─────────────
    st.markdown("---")
    st.subheader("요약 표 (팀 레벨: 기업교육 1팀 / 기업교육 2팀)")
    mat_team = summary_matrix_team(s_df)
    st.dataframe(mat_team, use_container_width=True)

    st.subheader("상세 표 (1팀 + 2팀 합산)")
    for stt in SHOW_STATUS:
        st.markdown(f"#### {stt} 상세")
        sub_all = detail_df(s_df, persons=None, status=stt)
        st.dataframe(sub_all, use_container_width=True, hide_index=True)

# ======================= 탭 2: 1팀 =======================
with tab_t1:
    # (리소스) ─────────────────
    st.subheader("1팀 — 담당자별 일간 스택 막대")
    if not p1_daily.empty and p1_daily.shape[1] > 0:
        p1_long, p1_order_chart = _melt_with_order(p1_daily, var_name="담당자")
        st.altair_chart(
            _stacked_bar(p1_long, color_col="담당자", title="1팀 — 담당자별 일간 스택 막대", color_order=p1_order_chart),
            use_container_width=True
        )
    else:
        st.info("1팀 데이터가 없습니다.")

    # 주간 표(팀원 전원 + 열 순서 산출)
    st.markdown("### 1팀 — 주간 리소스 합계 (금주 기준 -4주 ~ +4주)")
    st.caption(f"금주(월~일): {WEEK_LABELS[4]} · 범위: {WEEK_LABELS[0]} → {WEEK_LABELS[-1]}")
    tbl_p1_wk, order_p1 = _weekly_with_order(p1_daily, t1_all)  # 팀원 전원 포함 + 정렬
    st.dataframe(tbl_p1_wk, use_container_width=True)

    # (성사가능성) ─────────────
    st.markdown("---")
    st.subheader("요약 표 (x=담당자 / y=카운트 항목) — 팀원 전체")
    s_team1 = s_df[s_df['팀'] == '기업교육 1팀'].copy()
    mat_p1 = summary_matrix_people(s_team1, '기업교육 1팀', col_order=order_p1)  # 열 순서 동기화
    st.dataframe(mat_p1, use_container_width=True)

    st.markdown('---')
    persons_all_1 = TEAM_RAW['기업교육 1팀']
    sel1 = st.selectbox('담당자 필터', ['전체'] + persons_all_1, 0, key='t1_filter')
    persons_sel_1 = persons_all_1 if sel1 == '전체' else [sel1]

    # 운영 리소스 산정 딜 (담당자 필터 적용)
    st.markdown("### 운영 리소스 산정 딜 (담당자 필터 적용)")
    res_tbl_1 = make_resource_selection_table(res_rows, '기업교육 1팀', persons_sel_1)
    st.dataframe(res_tbl_1, use_container_width=True, hide_index=True)

    # 상태 상세 표들
    for stt in SHOW_STATUS:
        st.markdown(f"#### {stt} 상세")
        sub1 = detail_df(s_team1, persons=persons_sel_1, status=stt)
        st.dataframe(sub1, use_container_width=True, hide_index=True)

# ======================= 탭 3: 2팀 =======================
with tab_t2:
    # (리소스) ─────────────────
    st.subheader("2팀 — 담당자별 일간 스택 막대")
    if not p2_daily.empty and p2_daily.shape[1] > 0:
        p2_long, p2_order_chart = _melt_with_order(p2_daily, var_name="담당자")
        st.altair_chart(
            _stacked_bar(p2_long, color_col="담당자", title="2팀 — 담당자별 일간 스택 막대", color_order=p2_order_chart),
            use_container_width=True
        )
    else:
        st.info("2팀 데이터가 없습니다.")

    # 주간 표(팀원 전원 + 열 순서 산출)
    st.markdown("### 2팀 — 주간 리소스 합계 (금주 기준 -4주 ~ +4주)")
    st.caption(f"금주(월~일): {WEEK_LABELS[4]} · 범위: {WEEK_LABELS[0]} → {WEEK_LABELS[-1]}")
    tbl_p2_wk, order_p2 = _weekly_with_order(p2_daily, t2_all)
    st.dataframe(tbl_p2_wk, use_container_width=True)

    # (성사가능성) ─────────────
    st.markdown("---")
    st.subheader("요약 표 (x=담당자 / y=카운트 항목) — 팀원 전체")
    s_team2 = s_df[s_df['팀'] == '기업교육 2팀'].copy()
    mat_p2 = summary_matrix_people(s_team2, '기업교육 2팀', col_order=order_p2)  # 열 순서 동기화
    st.dataframe(mat_p2, use_container_width=True)

    st.markdown('---')
    persons_all_2 = TEAM_RAW['기업교육 2팀']
    sel2 = st.selectbox('담당자 필터', ['전체'] + persons_all_2, 0, key='t2_filter')
    persons_sel_2 = persons_all_2 if sel2 == '전체' else [sel2]

    # 운영 리소스 산정 딜 (담당자 필터 적용)
    st.markdown("### 운영 리소스 산정 딜 (담당자 필터 적용)")
    res_tbl_2 = make_resource_selection_table(res_rows, '기업교육 2팀', persons_sel_2)
    st.dataframe(res_tbl_2, use_container_width=True, hide_index=True)

    # 상태 상세 표들
    for stt in SHOW_STATUS:
        st.markdown(f"#### {stt} 상세")
        sub2 = detail_df(s_team2, persons=persons_sel_2, status=stt)
        st.dataframe(sub2, use_container_width=True, hide_index=True)