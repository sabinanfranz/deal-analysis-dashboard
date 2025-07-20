# pages/11_팀별_체결률_요약.py
import streamlit as st, pandas as pd, re
from data import load_all_deal, load_retention

# ────────── 0. 페이지 설정 ──────────
st.set_page_config(page_title="팀별 체결률 (2025·1-6) – 생성형 AI", layout="wide")

# ────────── 1. 조직 매핑 ──────────
TEAM_RAW = {
    '기업교육 1팀': [
        '김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연',
        '강지선','정하영','하승민','이은서','홍제환'
    ],
    '기업교육 2팀': [
        '박종협','정선희','권노을','강진우','이윤지','김민선','이수빈',
        '강연정','강다현','방신우','정다혜','임재우','손승완',
        '김윤지','손지훈','홍예진'
    ],
}
NAME2TEAM = {re.sub(r'B$', '', n): t for t, lst in TEAM_RAW.items() for n in lst}
TEAM_LIST = list(TEAM_RAW.keys())

# ────────── 2. 데이터 로드 ──────────
df = load_all_deal()
df['담당자_name'] = df['담당자_name'].str.replace(r'B$', '', regex=True)
df['팀']          = df['담당자_name'].map(NAME2TEAM)

ONLINE_SET = {'선택구매(온라인)', '구독제(온라인)', '포팅'}
df = df[
    (df['생성년도'] == 2025) &
    (df['생성월'].between(1, 6)) &
    (df['카테고리(대)'] == '생성형 AI') &
    (~df['과정포맷(대)'].isin(ONLINE_SET))
]

ret_cust         = set(load_retention()['기업명'])
df['유형']       = df['기업명'].apply(lambda c: '리텐션' if c in ret_cust else '신규')
df['대기업신규'] = (df['기업 규모'] == '대기업') & (df['유형'] == '신규')

# ────────── 3. Sidebar ──────────
sel_team   = st.sidebar.selectbox("👥 팀 선택", TEAM_LIST)
members     = TEAM_RAW[sel_team]
sel_member  = st.sidebar.selectbox("🧑‍💼 담당자(딜 목록 전용)", ["전체"] + members)

team_df     = df[df['팀'] == sel_team]
succ_mask   = team_df['성사 가능성'].isin(['확정', '높음'])
member_mask = (
    (team_df['담당자_name'] == sel_member)
    if sel_member != "전체" else
    pd.Series(True, index=team_df.index)
)

DETAIL_COLS = [
    '생성년도','생성월','기업명','이름','담당자_name','성사 가능성',
    '수주 예정일(종합)','수주 예정액(종합)','Net',
    '과정포맷(대)','카테고리(대)'
]

# ────────── 4. 헬퍼 ──────────
def total_and_rate(mask: pd.Series) -> tuple[int, str]:
    tot = int(mask.sum())
    if tot == 0:
        return 0, "0.0%"
    win = int((mask & succ_mask).sum())
    return tot, f"{win / tot * 100:.1f}%"

def detail_rows(base_mask: pd.Series) -> pd.DataFrame:
    rows = team_df[base_mask & member_mask][DETAIL_COLS].copy()
    rows['수주 예정액(종합)'] = (rows['수주 예정액(종합)'] / 1e8).round(2)
    rows['Net']              = rows['Net'].fillna(0).astype(float).round(2)
    return rows.sort_values(['생성년도','생성월','기업명']).reset_index(drop=True)

def render_section(idx: int, title: str, base_mask: pd.Series):
    summary = []
    for m in members:
        msel     = team_df['담당자_name'] == m
        tot, rate = total_and_rate(base_mask & msel)
        summary.append([m, tot, rate])

    st.markdown(f"### {idx}) {title} – 생성형 AI - 체결률(%)")
    st.dataframe(
        pd.DataFrame(summary,
            columns=['담당자', '생성형 AI 딜 개수', '체결률(%)']
        ).set_index('담당자'),
        use_container_width=True, hide_index=False
    )

    st.markdown(f"#### {idx}-1) {title} - 비온라인  - 생성형 AI - 딜 목록")
    st.dataframe(
        detail_rows(base_mask),
        use_container_width=True, hide_index=True
    )

# ────────── 5. 출력 ──────────
st.title("개인별 체결률 – 생성형 AI - '25 1~6월")

titles_masks = [
    ("대기업 - 리텐션", (team_df['기업 규모']=='대기업') & (team_df['유형']=='리텐션')),
    ("대기업 - 신규",   team_df['대기업신규']),
    ("중견기업",        team_df['기업 규모']=='중견기업'),
    ("중소기업",        team_df['기업 규모']=='중소기업')
]

tabs = st.tabs([t for t, _ in titles_masks])

for idx, ((title, mask), tab) in enumerate(zip(titles_masks, tabs), start=1):
    with tab:
        render_section(idx, title, mask)
