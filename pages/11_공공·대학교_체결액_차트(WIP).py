# pages/24_공공·대학교_체결액_차트.py
"""
공공기관/대학교 — 2025년 체결액 차트 모음 (Won 처리)
1) 공공기관/대학교 월별 체결액(스택)
2) 공공기관: 직접/리텐션 월별 체결액(스택)
3) 공공기관: 과정포맷(대) 월별 체결액(스택)
4) 공공기관: 출강 내 카테고리(대) 월별 체결액(스택)
5) 공공기관: 체결액 500만원(=0.05억) 구간 히스토그램(계약 체결일 2025)
   - 구간별 Won 딜 리스트 (요약표는 제거)
7) 대학교: 직접/리텐션 월별 체결액(스택)
8) 대학교: 과정포맷(대) 월별 체결액(스택)
9) 대학교: 출강 내 카테고리(대) 월별 체결액(스택)
10) 대학교: 체결액 500만원(=0.05억) 구간 히스토그램(계약 체결일 2025)
    - 구간별 Won 딜 리스트 (요약표는 제거)
"""

import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
from data import load_all_deal

st.set_page_config(page_title="공공·대학교 — 2025 체결액 차트", layout="wide")
alt.data_transformers.disable_max_rows()

# ────────── 상수 ──────────
TARGET_YEAR = 2025
ONLINE_SET  = {'선택구매(온라인)','구독제(온라인)','포팅'}
MONTHS      = list(range(1, 13))
BIN_STEP_UK = 0.05   # 500만원 = 0.05억

# ────────── 유틸 ──────────
def norm_state(x: str) -> str:
    if pd.isna(x): return ""
    t = str(x).strip().lower()
    if t in ["won", "w", "확정"]: return "won"
    if t.startswith("lost") or t in ["lose","l","lost/중단"]: return "lost"
    return t

def tidy_money(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False), errors="coerce")

def derive_close_year_month(df: pd.DataFrame) -> pd.DataFrame:
    """계약 체결일에서 year/month 우선, 없으면 체결년도/체결월 보완."""
    cdate = pd.to_datetime(df.get("계약 체결일"), errors="coerce")
    cy = cdate.dt.year
    cm = cdate.dt.month
    fy = pd.to_numeric(df.get("체결년도"), errors="coerce")
    fm = pd.to_numeric(df.get("체결월"), errors="coerce")
    df["_체결연"] = cy.fillna(fy)
    df["_체결월"] = cm.fillna(fm)
    df["_체결연"] = pd.to_numeric(df["_체결연"], errors="coerce").astype("Int64")
    df["_체결월"] = pd.to_numeric(df["_체결월"], errors="coerce").astype("Int64")
    df["_계약일_dt"] = cdate
    return df

def prepare_base() -> pd.DataFrame:
    df = load_all_deal().copy()

    # 기본 정리
    df["기업 규모"] = df["기업 규모"].fillna("").astype(str).str.strip()
    df["딜 전환 유형"] = df["딜 전환 유형"].fillna("").astype(str).str.strip()
    df["딜 전환 유형_정리"] = df["딜 전환 유형"].apply(lambda x: "리텐션" if x == "리텐션" else "직접 교육 문의")
    df["과정포맷(대)"] = df["과정포맷(대)"].fillna("").astype(str).str.strip()
    df["카테고리(대)"] = df["카테고리(대)"].fillna("").astype(str).str.strip()
    df["상태_norm"] = df["상태"].map(norm_state)

    # 체결액: 금액 → 실제 수주액 순
    amt  = tidy_money(df.get("금액"))
    real = tidy_money(df.get("실제 수주액")) if "실제 수주액" in df.columns else pd.Series(index=df.index, dtype="float64")
    df["체결액"] = amt.combine_first(real)

    # 체결연/월 파생
    df = derive_close_year_month(df)

    # Won & 2025년
    won_2025 = (df["상태_norm"] == "won") & (df["_체결연"] == TARGET_YEAR)
    df = df[won_2025].copy()

    # 관할 대상 규모만
    df = df[df["기업 규모"].isin(["공공기관", "대학교"])].copy()

    # 억 단위로 변환(표시·집계 모두 억 단위, 소수 2자리 표기)
    df["체결액_억"] = (df["체결액"] / 1e8).astype(float)

    # 편의 컬럼
    df["_월"] = df["_체결월"].astype("Int64")

    return df

def agg_monthly(df: pd.DataFrame, color_col: str) -> pd.DataFrame:
    """월 × 컬러컬럼 기준 체결액 합계(억, 스택용)."""
    sub = df.copy()
    sub["_월"] = pd.to_numeric(sub["_월"], errors="coerce")
    sub = sub[sub["_월"].between(1, 12, inclusive="both")]
    grp = sub.groupby(["_월", color_col], as_index=False)["체결액_억"].sum()
    grp.rename(columns={"_월":"월"}, inplace=True)
    # 월 누락 보정(0값) — 시각 일관성
    cats = sorted(sub[color_col].dropna().unique())
    if len(cats) == 0:
        return pd.DataFrame(columns=["월", color_col, "체결액_억"])
    all_idx = pd.MultiIndex.from_product([MONTHS, cats], names=["월", color_col])
    grp = grp.set_index(["월", color_col]).reindex(all_idx, fill_value=0).reset_index()
    return grp

def vbar_stacked(df_agg: pd.DataFrame, color_field: str, color_title: str, chart_title: str):
    return (
        alt.Chart(df_agg)
        .mark_bar()
        .encode(
            x=alt.X("월:O", title="월"),
            y=alt.Y("체결액_억:Q", title="체결액(억)", stack="zero"),
            color=alt.Color(f"{color_field}:N", title=color_title),
            tooltip=[
                alt.Tooltip("월:O"),
                alt.Tooltip(f"{color_field}:N", title=color_title),
                alt.Tooltip("체결액_억:Q", title="체결액(억)", format=".2f"),
            ],
        )
        .properties(title=chart_title, height=320)
    )

def histogram_and_lists(df: pd.DataFrame, size_label: str, bin_step_uk: float = BIN_STEP_UK):
    """Won & 계약 체결일이 2025년인 해당 규모 딜의 체결액(억) 히스토그램 + 구간별 리스트 (요약표 제거)."""
    st.subheader(f"{size_label} — 체결액 히스토그램 (계약 체결일 2025, {bin_step_uk:.2f}억 단위)")
    d0 = df[(df["기업 규모"] == size_label)].copy()
    d0 = d0[d0["_계약일_dt"].dt.year == TARGET_YEAR]  # 명시적으로 계약일 기준
    d0 = d0[pd.notna(d0["체결액_억"])]

    if d0.empty:
        st.info("데이터가 없습니다.")
        return

    # Altair 히스토그램 (x: 억, step: 0.05억)
    hist = (
        alt.Chart(d0)
        .mark_bar()
        .encode(
            x=alt.X("체결액_억:Q", bin=alt.Bin(step=bin_step_uk), title="체결액(억)"),
            y=alt.Y("count():Q", title="딜 개수"),
            tooltip=[alt.Tooltip("count():Q", title="딜 개수")]
        )
        .properties(height=300)
    )
    st.altair_chart(hist, use_container_width=True)

    # 구간별 Won 리스트 (요약표 제거)
    max_val = max(d0["체결액_억"].max(), bin_step_uk)
    bins = np.arange(0, (np.floor(max_val / bin_step_uk) + 2) * bin_step_uk, bin_step_uk)
    cut = pd.cut(d0["체결액_억"], bins=bins, right=False, include_lowest=True)
    d0 = d0.assign(구간=cut)

    show_cols = ["기업명","이름","계약 체결일","체결액_억","딜 전환 유형_정리","과정포맷(대)","카테고리(대)","담당자_name"]
    for interval in sorted(d0["구간"].dropna().unique(), key=lambda x: (x.left, x.right)):
        sub = d0[d0["구간"] == interval].copy()
        if sub.empty:
            continue
        left, right = interval.left, interval.right
        st.markdown(f"**구간: [{left:.2f}, {right:.2f})억 — {len(sub)}건**")
        view = sub.copy()
        view["체결액_억"] = view["체결액_억"].map(lambda v: f"{v:.2f}")
        st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

# ────────── 데이터 준비 ──────────
df = prepare_base()

# ────────── 1) 공공기관/대학교 월별 체결액(스택) ──────────
st.header("1) 공공기관/대학교 — 월별 체결액 (억, Won)")
agg1 = agg_monthly(df, "기업 규모")
st.altair_chart(vbar_stacked(agg1, "기업 규모", "기업 규모", "공공기관/대학교 월별 체결액"), use_container_width=True)

st.markdown("---")

# ────────── 공공기관 블록 (2~5 + 구간별 리스트) ──────────
pub = df[df["기업 규모"] == "공공기관"].copy()

st.header("공공기관 — 체결액 분해 (억)")

# 2) 직접/리텐션
agg2 = agg_monthly(pub, "딜 전환 유형_정리")
st.altair_chart(vbar_stacked(agg2, "딜 전환 유형_정리", "딜 전환 유형", "공공기관 월별 체결액 — 직접/리텐션"), use_container_width=True)

# 3) 과정포맷(대)
agg3 = agg_monthly(pub, "과정포맷(대)")
st.altair_chart(vbar_stacked(agg3, "과정포맷(대)", "과정포맷(대)", "공공기관 월별 체결액 — 과정포맷(대)"), use_container_width=True)

# 4) 출강 내 카테고리(대)
pub_off = pub[~pub["과정포맷(대)"].isin(ONLINE_SET)].copy()
agg4 = agg_monthly(pub_off, "카테고리(대)")
st.altair_chart(vbar_stacked(agg4, "카테고리(대)", "카테고리(대)", "공공기관 월별 체결액 — 출강 내 카테고리(대)"), use_container_width=True)

# 5) 히스토그램 + 구간별 Won 리스트 (요약표 없음)
st.header("공공기관 — 체결액 히스토그램/구간별 리스트 (억)")
histogram_and_lists(df, "공공기관", bin_step_uk=BIN_STEP_UK)

st.markdown("---")

# ────────── 대학교 블록 (7~10 + 구간별 리스트) ──────────
uni = df[df["기업 규모"] == "대학교"].copy()

st.header("대학교 — 체결액 분해 (억)")

# 7) 직접/리텐션
agg7 = agg_monthly(uni, "딜 전환 유형_정리")
st.altair_chart(vbar_stacked(agg7, "딜 전환 유형_정리", "딜 전환 유형", "대학교 월별 체결액 — 직접/리텐션"), use_container_width=True)

# 8) 과정포맷(대)
agg8 = agg_monthly(uni, "과정포맷(대)")
st.altair_chart(vbar_stacked(agg8, "과정포맷(대)", "과정포맷(대)", "대학교 월별 체결액 — 과정포맷(대)"), use_container_width=True)

# 9) 출강 내 카테고리(대)
uni_off = uni[~uni["과정포맷(대)"].isin(ONLINE_SET)].copy()
agg9 = agg_monthly(uni_off, "카테고리(대)")
st.altair_chart(vbar_stacked(agg9, "카테고리(대)", "카테고리(대)", "대학교 월별 체결액 — 출강 내 카테고리(대)"), use_container_width=True)

# 10) 히스토그램 + 구간별 Won 리스트 (요약표 없음)
st.header("대학교 — 체결액 히스토그램/구간별 리스트 (억)")
histogram_and_lists(df, "대학교", bin_step_uk=BIN_STEP_UK)
