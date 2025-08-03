"""
기업교육 1·2팀 담당자별 성사 가능성 대시보드 (2025년)
- 월별 탭 제거, 연간 요약 테이블 컬럼 구조 변경
- 리소스 현황·중견중소 현황 컬럼 추가
"""

import streamlit as st
import pandas as pd
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from data import load_all_deal

# ────────── 설정 ──────────
st.set_page_config(page_title="담당자별 성사 가능성", layout="wide")

# ────────── 팀 매핑 ──────────
TEAM_RAW = {
    '기업교육 1팀': [
        '김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연',
        '강지선','정하영','하승민','이은서','홍제환','김세연','오진선'
    ],
    '기업교육 2팀': [
        '박종협','정선희','권노을','강진우','이윤지','김민선','이수빈',
        '강연정','강다현','방신우','정다혜','임재우','손승완',
        '김윤지','손지훈','홍예진'
    ],
}
NAME2TEAM = {re.sub(r'B$','',n): t for t, lst in TEAM_RAW.items() for n in lst}
TEAMS = list(TEAM_RAW.keys())
NAME_ORDER = {name: idx for team in TEAMS for idx, name in enumerate(TEAM_RAW[team])}

# ────────── 상수 ──────────
SUB_CONF = ['확정(온라인)','확정(운영 전)','확정(운영 중)','확정(운영 종료)']
BASE_STATUS = ['확정'] + SUB_CONF + ['높음','낮음','미기재','LOST']
DETAIL_COLS = [
    '생성년도','생성월','기업명','기업 규모','담당자_name','이름','상태', '성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net','수강시작일','수강종료일',
    '과정포맷(대)','카테고리(대)'
]
ONLINE_FMT = ['선택구매(온라인)','구독제(온라인)','포팅']
TODAY = pd.Timestamp(datetime.now(ZoneInfo('Asia/Seoul')).date())

# ────────── 데이터 로드 ──────────
df = load_all_deal()
# 이름 정리 및 팀 식별
df['담당자_name'] = df['담당자_name'].str.replace(r'B$','',regex=True)
df['팀'] = df['담당자_name'].map(NAME2TEAM)
df = df[df['팀'].isin(TEAMS) & (df['생성년도']==2025) & df['생성월'].between(1,12)].copy()

# ────────── 성사 가능성 정규화 ──────────

def norm_status(x:str):
    if pd.isna(x) or str(x).strip()=='' : return '미기재'
    t=str(x).strip(); tl=t.lower()
    if tl in ['won','w','확정','confirmed']: return '확정'
    if tl in ['높음','high']: return '높음'
    if tl in ['낮음','low']: return '낮음'
    if tl in ['lost','lose','l']: return 'LOST'
    return t

df['성사 가능성'] = df['성사 가능성'].apply(norm_status)

# ────────── 확정 세분화 ──────────

def classify_conf(r):
    fmt=str(r.get('과정포맷(대)','')).strip()
    if fmt in ONLINE_FMT: return '확정(온라인)'
    start=pd.to_datetime(r.get('수강시작일'),errors='coerce'); end=pd.to_datetime(r.get('수강종료일'),errors='coerce')
    course_id=str(r.get('코스 ID','')).strip(); won=str(r.get('상태','')).strip().lower()=='won'
    if pd.isna(start) or start>TODAY: return '확정(운영 전)'
    if won and course_id:
        if pd.notna(end):
            if start<=TODAY<=end: return '확정(운영 중)'
            if TODAY>end: return '확정(운영 종료)'
        return '확정(운영 중)'
    return '확정(운영 전)'

df['세부상태'] = df.apply(lambda r: classify_conf(r) if r['성사 가능성']=='확정' else r['성사 가능성'], axis=1)

# ────────── Helper ──────────

def ordered_persons(team_df, team_name):
    team_list = TEAM_RAW[team_name]
    return [n for n in team_list if n in team_df['담당자_name'].unique()]

# ────────── 요약 테이블 ──────────

def summary_table(team_df, persons):
    # 기본 상태별 피벗 테이블
    stat_pivot = team_df.groupby(['담당자_name','세부상태']).size().unstack(fill_value=0)
    # 확정 건수(세부상태 제외)
    conf_cnt = team_df[team_df['성사 가능성']=='확정'].groupby('담당자_name').size()
    stat_pivot['확정'] = conf_cnt
    # 누락된 컬럼 보강
    for col in BASE_STATUS:
        if col not in stat_pivot.columns:
            stat_pivot[col] = 0
    # 리소스 현황: 운영 중·높음·낮음·미기재 합
    stat_pivot['리소스 현황'] = stat_pivot[['확정(운영 중)','높음','낮음','미기재']].sum(axis=1)
    # 중견중소 현황: ONLINE 아닐 때 + 기업 규모 중견/중소 & 상태 높음/낮음/미기재
    mask = (
        ~team_df['과정포맷(대)'].isin(ONLINE_FMT) &
        team_df['기업 규모'].isin(['중견기업','중소기업']) &
        team_df['세부상태'].isin(['높음','낮음','미기재'])
    )
    mid_cnt = team_df[mask].groupby('담당자_name').size()
    stat_pivot['중견중소 현황'] = mid_cnt
    # 정렬 및 결측 처리
    stat_pivot = stat_pivot.reindex(persons).fillna(0).astype(int)
    stat_pivot.reset_index(inplace=True)
    stat_pivot['name_rank'] = stat_pivot['담당자_name'].map(NAME_ORDER)
    stat_pivot.sort_values('name_rank', inplace=True)
    stat_pivot.drop(columns=['name_rank'], inplace=True)
    # 컬럼 순서
    COL_ORDER = ['담당자_name','리소스 현황','중견중소 현황'] + BASE_STATUS
    return stat_pivot[COL_ORDER]

# ────────── 상세 테이블 ──────────

def detail_df(team_df, status):
    sub = team_df[team_df['성사 가능성'] == '확정'] if status == '확정' else team_df[team_df['세부상태'] == status]
    if sub.empty:
        return pd.DataFrame(columns=DETAIL_COLS)
    sub = sub.sort_values(['담당자_name','생성월','기업명'], key=lambda s: s.map(NAME_ORDER).fillna(9999) if s.name=='담당자_name' else s)
    return sub[DETAIL_COLS]

# ────────── 불일치 리포트 ──────────

def discrepancy_table(full_df):
    conf = full_df[full_df['성사 가능성']=='확정'].groupby(['팀','담당자_name']).size().rename('확정')
    sub  = full_df[full_df['세부상태'].isin(SUB_CONF)].groupby(['팀','담당자_name']).size().rename('서브합')
    rpt = pd.concat([conf, sub], axis=1).fillna(0).astype(int)
    rpt['차이'] = rpt['확정'] - rpt['서브합']
    rpt = rpt[rpt['차이'] != 0]
    if rpt.empty:
        return pd.DataFrame({'메시지':['모든 담당자의 확정 건수가 서브합과 일치합니다.']})
    rpt = rpt.reset_index()
    rpt['name_rank'] = rpt['담당자_name'].map(NAME_ORDER)
    rpt['team_rank'] = rpt['팀'].map(lambda t: TEAMS.index(t))
    rpt.sort_values(['team_rank','name_rank'], inplace=True)
    rpt.drop(columns=['name_rank','team_rank'], inplace=True)
    return rpt

# ────────── UI ──────────
st.title('담당자별 성사 가능성 – 2025년')

TABS = [
    ('1팀(연간)','기업교육 1팀'),
    ('2팀(연간)','기업교육 2팀'),
    ('불일치 리포트', None)
]
ui_tabs = st.tabs([t[0] for t in TABS])

for tab,(title,team) in zip(ui_tabs,TABS):
    with tab:
        if team is None:
            rpt = discrepancy_table(df)
            st.dataframe(rpt,use_container_width=True,hide_index=True)
            continue
        team_df = df[df['팀']==team]
        persons_all = ordered_persons(team_df,team)
        sel = st.selectbox('담당자',['전체']+persons_all,0,key=title)
        team_df = team_df if sel=='전체' else team_df[team_df['담당자_name']==sel]
        persons  = persons_all if sel=='전체' else [sel]
        tbl = summary_table(team_df, persons)
        st.dataframe(tbl,use_container_width=True,hide_index=True)
        st.markdown('---')
        for stt in ['확정'] + SUB_CONF + ['높음','낮음','미기재','LOST']:
            sub = detail_df(team_df, stt)
            st.markdown(f"#### {stt} 상세")
            st.dataframe(sub,use_container_width=True,hide_index=True)
