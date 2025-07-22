# pages/17_기업규모별_체결액.py
import streamlit as st, pandas as pd
from data import load_all_deal

st.set_page_config(page_title="기업 규모별 체결액 (2025)", layout="wide")

# ────────── 상수 ──────────
G_SIZE   = ['대기업', '중견기업', '중소기업']
MONTHS   = list(range(1, 13))
COLS     = [f"{m}월" for m in MONTHS]
ROWS     = ['전체', '확정', '높음', '낮음', 'LOST', '미기재',
            '체결률(%)', '수주예정액(종합)']
STAT_MAP = {'확정':'확정','높음':'높음','낮음':'낮음',
            'LOW':'낮음','LOST':'LOST','LOST/중단':'LOST'}

# ────────── 데이터 로드 ──────────
df = load_all_deal()

# ── (★) 참고 코드와 동일한 월 처리 ──
df['생성월'] = (
    pd.to_numeric(df['생성월'], errors='coerce')    # 문자열·공백 → NaN
      .fillna(0)                                   # 필요하면 0 보존
      .astype(int)
)

# ① 2025년 + 상태(Convert) 제외
df = df[(df['생성년도'] == 2025) & (df['상태'] != 'Convert')].copy()

# ② 딜 전환 유형 정리
df['딜 전환 유형'] = (
    df['딜 전환 유형']
      .fillna('미기재')                    # 빈 값 → 미기재
      .apply(lambda x: '리텐션' if x == '리텐션' else '직접 교육 문의')
)

# ③ 과정포맷(대)·카테고리(대) 결측 → 미기재
df['과정포맷(대)'] = df['과정포맷(대)'].fillna('미기재')
df['카테고리(대)'] = df['카테고리(대)'].fillna('미기재')

# ④ 성사 가능성 정규화
df['status2'] = df['성사 가능성'].map(STAT_MAP).fillna('미기재')

# ────────── Sidebar 필터 ──────────
st.sidebar.header("필터")
sel_conv = st.sidebar.selectbox("딜 전환 유형",
                                ['전체', '리텐션', '직접 교육 문의'], 0)
sel_fmt  = st.sidebar.selectbox(
    "과정포맷(대)", ['전체'] + sorted(df['과정포맷(대)'].unique()), 0)
sel_cat  = st.sidebar.selectbox(
    "카테고리(대)", ['전체'] + sorted(df['카테고리(대)'].unique()), 0)

mask = pd.Series(True, index=df.index)
if sel_conv != '전체':
    mask &= df['딜 전환 유형'] == sel_conv
if sel_fmt != '전체':
    mask &= df['과정포맷(대)'] == sel_fmt
if sel_cat != '전체':
    mask &= df['카테고리(대)'] == sel_cat
df = df[mask].copy()

# ────────── 집계 함수 ──────────
def make_table(d: pd.DataFrame) -> pd.DataFrame:
    tbl = pd.DataFrame('', index=ROWS, columns=COLS)
    for m in MONTHS:
        col = f"{m}월"
        sub = d[d['생성월'] == m]

        tot = len(sub)
        win = len(sub[sub['status2'].isin(['확정', '높음'])])

        tbl.loc['전체', col]   = tot
        tbl.loc['확정', col]   = len(sub[sub['status2'] == '확정'])
        tbl.loc['높음', col]   = len(sub[sub['status2'] == '높음'])
        tbl.loc['낮음', col]   = len(sub[sub['status2'] == '낮음'])
        tbl.loc['LOST', col]   = len(sub[sub['status2'] == 'LOST'])
        tbl.loc['미기재', col] = len(sub[sub['status2'] == '미기재'])
        tbl.loc['체결률(%)', col] = f"{round(win / tot * 100, 1)}%" if tot else "0.0%"
        amt = sub[sub['status2'].isin(['확정', '높음'])]['수주 예정액(종합)'].sum() / 1e8
        tbl.loc['수주예정액(종합)', col] = round(amt, 2)
    return tbl

# ────────── 탭 출력 ──────────
st.title("기업 규모별 체결액 (2025)")

tabs = st.tabs(G_SIZE)
for tab, size in zip(tabs, G_SIZE):
    with tab:
        st.markdown(f"### {size}")
        st.dataframe(make_table(df[df['기업 규모'] == size]),
                     use_container_width=True, hide_index=False)
