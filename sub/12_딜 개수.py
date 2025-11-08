# pages/21_생성년도별_월별_딜수(2024vs2025).py
import streamlit as st
import pandas as pd
from data import load_all_deal  # TXT→SQLite→DataFrame 로더 (data.py)

st.set_page_config(page_title="2024·2025 생성월별 딜 개수 (연도 비교)", layout="wide")
st.title("2024·2025 생성월별 딜 개수 (연도 비교)")

# ───────────────────────── 상수/표시 설정
YEAR_ORDER = [2025, 2024]  # 연도는 2025 → 2024 (항목별로 붙여서 표시)
CONV_ORDER = [
    "직접 교육 문의",
    "리텐션",
    "콘텐츠 후속 유입",
    "누적 DB 너처링",
    "공공입찰 지원",
    "기타",
    "미기재",
]
MONTHS = list(range(1, 12 + 1))
MONTH_COLS = [f"{m}월" for m in MONTHS]

# ───────────────────────── 데이터 로드 & 공통 전처리
df = load_all_deal()

df["생성년도"] = pd.to_numeric(df["생성년도"], errors="coerce").astype("Int64")
df["생성월"]   = pd.to_numeric(df["생성월"],   errors="coerce").astype("Int64")
df["상태"]     = df["상태"].astype(str)
df["고객사 유형"] = df["고객사 유형"].astype(str).str.strip()
df["딜 전환 유형"] = (
    df["딜 전환 유형"]
      .fillna("미기재")
      .astype(str)
      .str.strip()
      .map(lambda x: x if x in CONV_ORDER else "기타")  # 리스트 밖 값은 '기타'로
)
df["기업 규모"]   = df["기업 규모"].astype(str).str.strip()

# 필터: 2024/2025, 1~12월, 상태 != Convert
df = df[
    df["생성년도"].isin([2024, 2025]) &
    df["생성월"].between(1, 12) &
    (df["상태"] != "Convert")
].copy()

# 고객사 유형 3분류
def _bucket_cust(x: str) -> str:
    if x == "기업 고객":
        return "기업 고객"
    if x == "공공 고객":
        return "공공 고객"
    return "기타"

df["고객사 유형(3분류)"] = df["고객사 유형"].map(_bucket_cust)

# ───────────────────────── 표 생성 함수
def make_year_type_table(d: pd.DataFrame) -> pd.DataFrame:
    """
    행:  (2025 - 유형1)
         (2024 - 유형1)
         (2025 - 유형2)
         (2024 - 유형2)
         ...
    열: 1월 ~ 12월
    값: 생성월별 딜 '개수'
    - None/결측은 0으로 표기
    """
    # 비어있으면 0으로 채운 표 반환(인터리브 순서)
    empty_idx = [f"{y} - {t}" for t in CONV_ORDER for y in YEAR_ORDER]
    empty_tbl = pd.DataFrame(0, index=empty_idx, columns=MONTH_COLS, dtype="Int64")
    if d.empty:
        return empty_tbl

    # (생성년도, 딜 전환 유형, 생성월) → 개수
    grp = (
        d.groupby(["생성년도", "딜 전환 유형", "생성월"])
         .size()
         .rename("cnt")
         .reset_index()
    )

    pivot = (
        grp.pivot_table(
            index=["생성년도", "딜 전환 유형"],
            columns="생성월",
            values="cnt",
            aggfunc="sum",
            fill_value=0,
        )
        .reindex(columns=MONTHS, fill_value=0)  # 1~12월 고정
    )

    # 모든 (연도×유형) 조합 보장
    full_index = pd.MultiIndex.from_product(
        ([2025, 2024], CONV_ORDER), names=["생성년도", "딜 전환 유형"]
    )
    pivot = pivot.reindex(full_index, fill_value=0)

    # 🔑 인터리브 정렬: 유형1의 2025, 2024 → 유형2의 2025, 2024 …
    desired = pd.MultiIndex.from_tuples(
        [(y, t) for t in CONV_ORDER for y in YEAR_ORDER],
        names=["생성년도", "딜 전환 유형"]
    )
    pivot = pivot.reindex(desired, fill_value=0)

    out = pivot.astype("Int64")
    out.index = [f"{y} - {t}" for (y, t) in out.index]
    out.columns = MONTH_COLS
    return out

# ───────────────────────── 탭 구성
tabs = st.tabs(["기업 고객", "공공 고객", "기타"])

# 1) 기업 고객: 기업 규모별 3표
with tabs[0]:
    st.subheader("기업 고객 – 기업 규모별(대기업/중견기업/중소기업) 생성월별 딜 개수")
    corp_df = df[df["고객사 유형(3분류)"] == "기업 고객"].copy()
    for size in ["대기업", "중견기업", "중소기업"]:
        sub = corp_df[corp_df["기업 규모"] == size].copy()
        st.markdown(f"#### {size}")
        st.dataframe(
            make_year_type_table(sub),
            use_container_width=True,
            hide_index=False
        )

# 2) 공공 고객: 세분화 없이 1개 표
with tabs[1]:
    st.subheader("공공 고객 – 생성월별 딜 개수")
    public_df = df[df["고객사 유형(3분류)"] == "공공 고객"].copy()
    st.dataframe(
        make_year_type_table(public_df),
        use_container_width=True,
        hide_index=False
    )

# 3) 기타: 세분화 없이 1개 표
with tabs[2]:
    st.subheader("기타 – 생성월별 딜 개수")
    other_df = df[df["고객사 유형(3분류)"] == "기타"].copy()
    st.dataframe(
        make_year_type_table(other_df),
        use_container_width=True,
        hide_index=False
    )
