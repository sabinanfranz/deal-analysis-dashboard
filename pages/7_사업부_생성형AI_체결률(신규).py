# pages/13_생성형AI_월별_체결률_신규.py
import re, streamlit as st, pandas as pd
from data import load_all_deal, load_retention

st.set_page_config(page_title="생성형-AI – 월별 체결률 (2025·H1·신규)", layout="wide")

TEAM_RAW = {
    '기업교육 1팀':['김별','김솔이','황초롱','김정은','김동찬','정태윤',
                 '서정연','강지선','정하영','하승민','이은서','홍제환'],
    '기업교육 2팀':['박종협','정선희','권노을','강진우','이윤지','김민선',
                 '이수빈','강연정','강다현','방신우','정다혜','임재우',
                 '손승완','김윤지','손지훈','홍예진'],
}
NAME2TEAM={re.sub(r'B$','',n):t for t,l in TEAM_RAW.items() for n in l}

DETAIL_COLS=['생성년도','생성월','기업명','이름','담당자_name','성사 가능성',
             '수주 예정일(종합)','수주 예정액(종합)','Net','과정포맷(대)','카테고리(대)']

df=load_all_deal()
df['담당자_name']=df['담당자_name'].fillna('').astype(str).str.replace(r'B$','',regex=True).str.strip()
df['팀']=df['담당자_name'].map(NAME2TEAM)

ONLINE_SET={'선택구매(온라인)','구독제(온라인)','포팅'}
df['카테고리_정리']=df['카테고리(대)'].fillna('').str.strip()
df['과정포맷_정리']=df['과정포맷(대)'].fillna('').str.strip()
df=df[(df['생성년도']==2025)&(df['생성월'].between(1,6))&
      (df['카테고리_정리']=='생성형 AI')&(~df['과정포맷_정리'].isin(ONLINE_SET))].copy()

ret_set=set(load_retention()['기업명'].dropna()) if '기업명' in load_retention().columns else set()
df=df[~df['기업명'].isin(ret_set)]

STAT_MAP={'확정':'확정','높음':'높음','낮음':'낮음',
          'LOW':'낮음','LOST':'LOST','LOST/중단':'LOST'}
df['status']=df['성사 가능성'].map(STAT_MAP).fillna('기타')

MONTHS=[1,2,3,4,5,6]
MONTH_COLS=[f"{m}월" for m in MONTHS]
ROLL_COLS=['1~3월','2~4월','3~5월','4~6월']
ROW_ORDER=['전체','확정+높음','낮음','LOST','체결률(%)']

def _bucket(d:pd.DataFrame)->pd.DataFrame:
    result=pd.DataFrame('',index=ROW_ORDER,columns=MONTH_COLS)
    for r in ['전체','확정+높음','낮음','LOST']:
        result.loc[r]=0.0
    if d.empty:return result
    d=d.dropna(subset=['생성월']).copy()
    d['생성월']=pd.to_numeric(d['생성월'],errors='coerce').dropna().astype(int)
    for i,m in enumerate(MONTHS):
        col=MONTH_COLS[i]
        sub=d[d['생성월']==m]
        tot=len(sub)
        result.loc['전체',col]=tot
        if tot:
            win=len(sub[sub['status'].isin(['확정','높음'])])
            low=len(sub[sub['status']=='낮음'])
            lost=len(sub[sub['status']=='LOST'])
            result.loc['확정+높음',col]=win
            result.loc['낮음',col]=low
            result.loc['LOST',col]=lost
            result.loc['체결률(%)',col]=f"{win/tot*100:.1f}%"
        else:
            result.loc['체결률(%)',col]="0.0%"
    return result

def month_tbl(mask): return _bucket(df[mask])
def roll_tbl(mask):
    base=month_tbl(mask)
    res=pd.DataFrame('',index=ROW_ORDER,columns=ROLL_COLS)
    for r in ['전체','확정+높음','낮음','LOST']:
        res.loc[r]=0.0
    if base.empty:return res
    md={i+1:base.iloc[:,i] for i in range(6)}
    for a,b,c,col in [(1,2,3,'1~3월'),(2,3,4,'2~4월'),(3,4,5,'3~5월'),(4,5,6,'4~6월')]:
        tot=md[a]['전체']+md[b]['전체']+md[c]['전체']
        win=md[a]['확정+높음']+md[b]['확정+높음']+md[c]['확정+높음']
        low=md[a]['낮음']+md[b]['낮음']+md[c]['낮음']
        lost=md[a]['LOST']+md[b]['LOST']+md[c]['LOST']
        res.loc['전체',col]=tot
        res.loc['확정+높음',col]=win
        res.loc['낮음',col]=low
        res.loc['LOST',col]=lost
        res.loc['체결률(%)',col]=f"{(win/tot*100):.1f}%" if tot else "0.0%"
    return res

st.title("생성형 AI — '25 H1 체결률 (신규 고객)")

tabs=st.tabs(['전체','기업교육 1팀','기업교육 2팀'])
masks={'전체':df.index==df.index,
       '기업교육 1팀':df['팀']=='기업교육 1팀',
       '기업교육 2팀':df['팀']=='기업교육 2팀'}
for tab,(lbl,msk) in zip(tabs,masks.items()):
    with tab:
        st.dataframe(month_tbl(msk), use_container_width=True)
        st.dataframe(roll_tbl(msk),  use_container_width=True)
        detail=df[msk][DETAIL_COLS].copy()
        if not detail.empty:
            detail['수주 예정액(종합)']=(detail['수주 예정액(종합)']/1e8).round(2)
            detail['Net']=detail['Net'].fillna(0).astype(float).round(2)
        st.dataframe(detail, use_container_width=True)
