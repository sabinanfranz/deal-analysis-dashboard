import altair as alt
import pandas as pd
import streamlit as st

from data import load_won_deal

st.set_page_config(page_title="월별 체결액 (2024-2025)", layout="wide")
alt.data_transformers.disable_max_rows()

YEAR_START = 2024
YEAR_END = 2025
MONTH_RANGE = pd.period_range(f"{YEAR_START}-01", f"{YEAR_END}-12", freq="M")
MONTH_LABELS = [f"{p.year}-{p.month:02d}" for p in MONTH_RANGE]
YEAR_LABELS = [str(year) for year in range(YEAR_START, YEAR_END + 1)]
QUARTER_RANGE = pd.period_range(f"{YEAR_START}Q1", f"{YEAR_END}Q4", freq="Q")
QUARTER_LABELS = [str(p) for p in QUARTER_RANGE]


def norm_state(x: str) -> str:
    if pd.isna(x):
        return ""
    t = str(x).strip().lower()
    if t in {"won", "확정", "w"}:
        return "won"
    if t.startswith("lost") or t in {"lost/중단", "lose", "l"}:
        return "lost"
    return t

def derive_schedule_year_month(df: pd.DataFrame) -> pd.DataFrame:
    """수주 예정일(종합)을 연/월로 변환, 보조 컬럼(년도/월)로 보완."""
    sched = pd.to_datetime(df.get("수주 예정일(종합)"), errors="coerce")
    sy = sched.dt.year
    sm = sched.dt.month
    fy = pd.to_numeric(df.get("수주예정년도"), errors="coerce")
    fm = pd.to_numeric(df.get("수주예정월"), errors="coerce")
    df["_예정연"] = sy.fillna(fy).astype("Int64")
    df["_예정월"] = sm.fillna(fm).astype("Int64")
    df["_예정일_dt"] = sched
    return df


@st.cache_data(show_spinner=False)
def load_base() -> pd.DataFrame:
    df = load_won_deal().copy()
    df = derive_schedule_year_month(df)

    status_col = df["상태"] if "상태" in df.columns else pd.Series("", index=df.index)
    df["상태_norm"] = status_col.map(norm_state)
    fmt_col = (
        df["과정포맷(대)"]
        if "과정포맷(대)" in df.columns
        else pd.Series("", index=df.index)
    )
    df["과정포맷(대)_정리"] = fmt_col.astype(str).str.strip().replace({"": "미기재"})

    amt_col = (
        pd.to_numeric(df["수주 예정액(종합)"], errors="coerce")
        if "수주 예정액(종합)" in df.columns
        else pd.Series(index=df.index, dtype="float64")
    )
    df["체결액_억"] = (amt_col / 1e8).fillna(0.0).astype(float)

    in_year = df["_예정연"].between(YEAR_START, YEAR_END, inclusive="both").fillna(False)
    valid_month = df["_예정월"].between(1, 12, inclusive="both").fillna(False)

    won_mask = df["상태_norm"] == "won"
    df = df[won_mask & in_year & valid_month].copy()

    df["연월_dt"] = pd.to_datetime(
        dict(year=df["_예정연"], month=df["_예정월"], day=1), errors="coerce"
    )
    df = df[pd.notna(df["연월_dt"])].copy()
    df["연월_label"] = df["연월_dt"].dt.strftime("%Y-%m")
    df["연도_label"] = df["_예정연"].astype("Int64").astype(str)
    df["분기_label"] = df["연월_dt"].dt.to_period("Q").astype(str)
    return df


def pivot_by_period(
    df: pd.DataFrame, period_col: str, labels: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty or period_col not in df.columns:
        return pd.DataFrame(), pd.DataFrame()

    grouped = (
        df.groupby(["과정포맷(대)_정리", period_col])["체결액_억"]
        .sum()
        .unstack(period_col, fill_value=0.0)
    )

    # Ensure all requested labels exist as columns
    for lbl in labels:
        if lbl not in grouped.columns:
            grouped[lbl] = 0.0
    grouped = grouped[labels]

    grouped["합계"] = grouped.sum(axis=1)
    grouped = grouped.sort_values("합계", ascending=False)

    table = grouped.reset_index().rename(columns={"과정포맷(대)_정리": "과정포맷(대)"})
    total_row = {"과정포맷(대)": "전체"}
    for lbl in labels + ["합계"]:
        total_row[lbl] = table[lbl].sum() if not table.empty else 0.0
    table = pd.concat([pd.DataFrame([total_row]), table], ignore_index=True)
    table = table[["과정포맷(대)", *labels, "합계"]].round(2)

    chart_records = []
    for fmt, row in grouped.iterrows():
        for lbl in labels:
            chart_records.append(
                {
                    "과정포맷(대)": fmt,
                    "기간": lbl,
                    "체결액_억": float(row[lbl]),
                }
            )
    chart_df = pd.DataFrame(chart_records)
    return table, chart_df


def render_stacked_chart(
    chart_df: pd.DataFrame, labels: list[str], title: str, x_title: str
) -> None:
    if chart_df.empty:
        st.info("차트로 표시할 데이터가 없습니다.")
        return

    chart_df = chart_df.copy()
    chart_df["기간"] = pd.Categorical(chart_df["기간"], categories=labels, ordered=True)

    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("기간:N", sort=labels, title=x_title),
            y=alt.Y("체결액_억:Q", title="체결액(억)", stack="zero"),
            color=alt.Color("과정포맷(대):N", title="과정포맷(대)"),
            tooltip=[
                alt.Tooltip("기간:N", title=x_title),
                alt.Tooltip("과정포맷(대):N"),
                alt.Tooltip("체결액_억:Q", title="체결액(억)", format=".2f"),
            ],
        )
        .properties(title=title, height=320)
    )
    st.altair_chart(chart, use_container_width=True)


def main():
    st.title("월별 체결액 (2024-2025)")
    st.caption("Won 기준 · 금액 단위: 억 (소수 둘째자리)")

    df = load_base()
    if df.empty:
        st.warning("2024~2025년 Won 데이터가 없습니다.")
        return

    format_options = sorted(df["과정포맷(대)_정리"].unique().tolist())
    st.sidebar.header("필터")
    select_choices = ["전체"] + format_options
    selected = st.sidebar.selectbox(
        "과정포맷(대)",
        options=select_choices,
        index=0,
        help="전체 또는 단일 과정포맷(대)을 선택하세요.",
    )

    if selected == "전체":
        scope = df.copy()
    else:
        scope = df[df["과정포맷(대)_정리"] == selected].copy()

    if scope.empty:
        st.warning("선택한 조건에 해당하는 데이터가 없습니다.")

    tab_year, tab_quarter, tab_month = st.tabs(["연간", "분기", "월별"])

    with tab_year:
        st.subheader(f"연간 체결액 — {selected}")
        year_table, year_chart = pivot_by_period(scope, "연도_label", YEAR_LABELS)
        if year_table.empty:
            st.info("연간 데이터가 없습니다.")
        else:
            st.dataframe(year_table, use_container_width=True, hide_index=True)
            render_stacked_chart(year_chart, YEAR_LABELS, "연간 체결액 (억)", "연도")

    with tab_quarter:
        st.subheader(f"분기 체결액 — {selected}")
        quarter_table, quarter_chart = pivot_by_period(scope, "분기_label", QUARTER_LABELS)
        if quarter_table.empty:
            st.info("분기 데이터가 없습니다.")
        else:
            st.dataframe(quarter_table, use_container_width=True, hide_index=True)
            render_stacked_chart(quarter_chart, QUARTER_LABELS, "분기별 체결액 (억)", "분기")

    with tab_month:
        st.subheader(f"월별 체결액 — {selected}")
        month_table, month_chart = pivot_by_period(scope, "연월_label", MONTH_LABELS)
        if month_table.empty:
            st.info("월별 데이터가 없습니다.")
        else:
            st.dataframe(month_table, use_container_width=True, hide_index=True)
            render_stacked_chart(month_chart, MONTH_LABELS, "월별 체결액 (억)", "월")


if __name__ == "__main__":
    main()
