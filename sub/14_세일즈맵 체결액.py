import streamlit as st
import pandas as pd
from data import load_won_deal  # won deal 로더 (data.py)

st.set_page_config(page_title="2024·2025 수주예정월별 수주예정액 (Won Deal)", layout="wide")
st.title("2024·2025 수주예정월별 수주예정액 (Won Deal)")

# ───────────────────────── 상수/표시 설정 (기존 포맷 유지 + '합계' 컬럼 추가)
YEAR_ORDER = [2025, 2024]  # 2025 → 2024 순
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
DISPLAY_COLS = ["합계"] + MONTH_COLS  # ← 1월 앞에 합산 컬럼

# ───────────────────────── 데이터 로드 & 공통 전처리
df = load_won_deal()

# 타입/클린업
df["수주예정년도"] = pd.to_numeric(df.get("수주예정년도"), errors="coerce").astype("Int64")
df["수주예정월"]   = pd.to_numeric(df.get("수주예정월"),   errors="coerce").astype("Int64")
df["상태"]         = df["상태"].astype(str)
df["고객사 유형"]   = df["고객사 유형"].astype(str).str.strip()
df["딜 전환 유형"]   = (
    df["딜 전환 유형"]
      .fillna("미기재")
      .astype(str)
      .str.strip()
      .map(lambda x: x if x in CONV_ORDER else "기타")  # 리스트 밖 값은 '기타'
)
df["기업 규모"]     = df["기업 규모"].astype(str).str.strip()
df["기업명"]        = df["기업명"].astype(str).str.strip()
df["수주 예정액(종합)"] = pd.to_numeric(df["수주 예정액(종합)"], errors="coerce").fillna(0.0)

# 필터: (기준 변경) 2024/2025, 1~12월, 상태 != Convert
df = df[
    df["수주예정년도"].isin([2024, 2025]) &
    df["수주예정월"].between(1, 12) &
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

# ───────────────────────── 표 생성 함수 (합계 금액, 단위: 억/소수점 1자리)
def make_year_type_table(d: pd.DataFrame) -> pd.DataFrame:
    """
    행:  (2025 - 유형1)
         (2024 - 유형1)
         (2025 - 유형2)
         (2024 - 유형2)
         ...
    열: 합계, 1월 ~ 12월
    값: '수주예정월' 기준 '수주 예정액(종합)' 합계 (억, 소수점 1자리, '억' 표기)
    - 비어있으면 '0.0억'
    """
    # 비어있으면 0.0억으로 채운 표 반환(인터리브 순서)
    empty_idx = [f"{y} - {t}" for t in CONV_ORDER for y in YEAR_ORDER]
    empty_tbl = pd.DataFrame("0.0억", index=empty_idx, columns=DISPLAY_COLS)
    if d.empty:
        return empty_tbl

    # (수주예정년도, 딜 전환 유형, 수주예정월) → 수주예정액 합계(원)
    grp = (
        d.groupby(["수주예정년도", "딜 전환 유형", "수주예정월"], dropna=False)["수주 예정액(종합)"]
         .sum()
         .reset_index()
    )

    pivot = (
        grp.pivot_table(
            index=["수주예정년도", "딜 전환 유형"],
            columns="수주예정월",
            values="수주 예정액(종합)",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reindex(columns=MONTHS, fill_value=0.0)  # 1~12월 고정
    )

    # 모든 (연도×유형) 조합 보장
    full_index = pd.MultiIndex.from_product(
        ([2025, 2024], CONV_ORDER), names=["수주예정년도", "딜 전환 유형"]
    )
    pivot = pivot.reindex(full_index, fill_value=0.0)

    # 🔑 인터리브 정렬: 유형1의 2025, 2024 → 유형2의 2025, 2024 …
    desired = pd.MultiIndex.from_tuples(
        [(y, t) for t in CONV_ORDER for y in YEAR_ORDER],
        names=["수주예정년도", "딜 전환 유형"]
    )
    pivot = pivot.reindex(desired, fill_value=0.0)

    # 금액(원) → 억 변환
    month_uk = (pivot / 1e8).round(1)                 # 월별 (억)
    sum_uk   = (pivot.sum(axis=1) / 1e8).round(1)     # 1~12 합계 (억, 월별 반올림 누적 오차 방지)

    # 합계 컬럼을 맨 앞에 삽입하고 '억' 포맷 적용
    out = pd.concat([sum_uk.rename("합계"), month_uk], axis=1)
    out = out.applymap(lambda v: f"{v:.1f}억")

    out.index = [f"{y} - {t}" for (y, t) in out.index]
    out.columns = DISPLAY_COLS
    return out

# ───────────────────────── 탭 구성
tabs = st.tabs(["기업 고객", "공공 고객", "기타"])

# 1) 기업 고객: '삼성전자' 전용 표 + (삼성전자 제외) 기업 규모별 3표
with tabs[0]:
    st.subheader("기업 고객 – 수주예정월별 수주예정액 합계")
    corp_df = df[df["고객사 유형(3분류)"] == "기업 고객"].copy()

    # ── 삼성전자 전용 표
    sams = corp_df[corp_df["기업명"] == "삼성전자"].copy()
    st.markdown("#### 삼성전자")
    st.dataframe(
        make_year_type_table(sams),
        use_container_width=True,
        hide_index=False
    )

    # ── (삼성전자 제외) 규모별 3표
    corp_rest = corp_df[corp_df["기업명"] != "삼성전자"].copy()
    for size in ["대기업", "중견기업", "중소기업"]:
        sub = corp_rest[corp_rest["기업 규모"] == size].copy()
        st.markdown(f"#### {size}")
        st.dataframe(
            make_year_type_table(sub),
            use_container_width=True,
            hide_index=False
        )

# 2) 공공 고객: 세분화 없이 1개 표
with tabs[1]:
    st.subheader("공공 고객 – 수주예정월별 수주예정액 합계")
    public_df = df[df["고객사 유형(3분류)"] == "공공 고객"].copy()
    st.dataframe(
        make_year_type_table(public_df),
        use_container_width=True,
        hide_index=False
    )

# 3) 기타: 세분화 없이 1개 표
with tabs[2]:
    st.subheader("기타 – 수주예정월별 수주예정액 합계")
    other_df = df[df["고객사 유형(3분류)"] == "기타"].copy()
    st.dataframe(
        make_year_type_table(other_df),
        use_container_width=True,
        hide_index=False
    )
