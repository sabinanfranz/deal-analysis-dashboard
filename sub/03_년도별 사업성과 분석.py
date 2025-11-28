import numpy as np
import pandas as pd
import streamlit as st

from data import load_accounting, load_won_deal

st.set_page_config(page_title="년도별 사업성과 분석", layout="wide")

SEG_COLS = ["과정포맷(대)", "카테고리(대)", "기업 규모", "딜 전환 유형"]
PUBLIC_SCALES = {"공공기관", "대학교"}
ONLINE_FORMATS = {"포팅", "구독제(온라인)", "선택구매(온라인)"}
ANALYSIS_YEAR_START = 2025
ANALYSIS_YEAR_END = 2025


def norm_state(x: str) -> str:
    if pd.isna(x):
        return ""
    t = str(x).strip().lower()
    if t in {"won", "확정", "w"}:
        return "won"
    if t.startswith("lost") or t in {"lost/중단", "lose", "l"}:
        return "lost"
    return t


def enrich_segments(df: pd.DataFrame) -> pd.DataFrame:
    """기업 규모, 고객 도메인(기업/공공/삼성전자), 채널, 온라인 리텐션을 파생."""
    out = df.copy()
    clean_size = (
        out.get("기업 규모", pd.Series("미기재", index=out.index))
        .astype(str)
        .str.strip()
        .replace({"": "미기재"})
    )
    out["기업 규모 정리"] = clean_size
    company = out.get("기업명", pd.Series("", index=out.index)).astype(str).str.strip()
    out["기업명_clean"] = company
    samsung_mask = company.str.contains("삼성전자", case=False, na=False)
    public_mask = clean_size.isin(PUBLIC_SCALES)
    out["고객 도메인"] = np.select(
        [samsung_mask, public_mask],
        ["삼성전자", "공공"],
        default="기업",
    )
    format_series = out.get("과정포맷(대)", pd.Series("", index=out.index)).astype(str).str.strip()
    online_mask = format_series.isin(ONLINE_FORMATS)
    out["채널 구분"] = np.where(online_mask, "온라인", "출강")
    deal_type = out.get("딜 전환 유형", pd.Series("", index=out.index)).astype(str).str.strip()
    retention_mask = online_mask & deal_type.str.contains("리텐션", na=False)
    out["온라인 리텐션"] = retention_mask

    first_col = out.get("(온라인)최초 입과 여부")
    if first_col is not None:
        norm = (
            first_col.astype(str)
            .str.strip()
            .str.lower()
            .map({"true": True, "false": False, "1": True, "0": False})
        )
        drop_mask = (out["채널 구분"] == "온라인") & (norm == False)
        out = out[~drop_mask].copy()

    return out


@st.cache_data(show_spinner=False)
def load_won_hist() -> pd.DataFrame:
    df = load_won_deal().copy()
    df["상태_norm"] = df.get("상태", pd.Series("", index=df.index)).map(norm_state)
    df = df[df["상태_norm"] == "won"].copy()
    df["예정일"] = pd.to_datetime(df.get("수주 예정일(종합)"), errors="coerce")
    df["예정연"] = df["예정일"].dt.year
    df["예정월"] = df["예정일"].dt.month
    df["시작일"] = pd.to_datetime(df.get("수강시작일"), errors="coerce")
    df["종료일"] = pd.to_datetime(df.get("수강종료일"), errors="coerce")
    created = pd.to_datetime(df.get("생성 날짜"), errors="coerce")
    df["리드타임"] = (df["예정일"] - created).dt.days
    df["기간일수"] = (df["종료일"] - df["시작일"]).dt.days + 1
    df.loc[df["기간일수"] <= 0, "기간일수"] = pd.NA

    dur_txt = df.get("교육 기간")
    if dur_txt is not None:
        dur_num = (
            dur_txt.astype(str)
            .str.extract(r"(-?\d+)")
            .iloc[:, 0]
            .pipe(pd.to_numeric, errors="coerce")
        )
        df["기간일수"] = df["기간일수"].combine_first(dur_num)

    amt = pd.to_numeric(df.get("수주 예정액(종합)"), errors="coerce")
    df["체결액"] = amt.fillna(0.0)
    df["체결액_억"] = (df["체결액"] / 1e8).astype(float)

    for col in SEG_COLS:
        if col not in df.columns:
            df[col] = "미기재"
        df[col] = df[col].astype(str).str.strip().replace({"": "미기재"})
    df = enrich_segments(df)
    return df


@st.cache_data(show_spinner=False)
def load_acc_hist() -> pd.DataFrame:
    df = load_accounting().copy()
    df["집계년"] = pd.to_numeric(df.get("집계년"), errors="coerce").astype("Int64")
    df["집계월"] = pd.to_numeric(df.get("집계월"), errors="coerce").astype("Int64")
    df["계약금액"] = pd.to_numeric(df.get("계약금액"), errors="coerce")
    df["계약금액_억"] = (df["계약금액"] / 1e8).astype(float)
    return df


def make_summary() -> dict[str, pd.DataFrame]:
    won = load_won_hist()
    won = won[won["예정연"].between(ANALYSIS_YEAR_START, ANALYSIS_YEAR_END, inclusive="both")]
    acc = load_acc_hist()
    acc = acc[acc["집계년"].between(ANALYSIS_YEAR_START, ANALYSIS_YEAR_END, inclusive="both")]

    won_year = (
        won.groupby("예정연")["체결액_억"]
        .sum()
        .reset_index()
        .rename(columns={"예정연": "연도", "체결액_억": "체결액(억)"})
    )
    won_year = won_year[won_year["연도"].notna()].sort_values("연도")
    won_year["체결 YoY%"] = won_year["체결액(억)"].pct_change().mul(100).round(1)

    acc_year = (
        acc.groupby("집계년")["계약금액_억"]
        .sum()
        .reset_index()
        .rename(columns={"집계년": "연도", "계약금액_억": "매출(억)"})
    )
    acc_year = acc_year[acc_year["연도"].notna()].sort_values("연도")
    acc_year["매출 YoY%"] = acc_year["매출(억)"].pct_change().mul(100).round(1)

    timing = (
        won.groupby("예정연")
        .agg(
            체결액_억=("체결액_억", "sum"),
            리드타임_중앙값=("리드타임", "median"),
            교육기간_중앙값=("기간일수", "median"),
        )
        .reset_index()
        .rename(columns={"예정연": "연도"})
        .sort_values("연도")
    )

    format_timing = (
        won.groupby("과정포맷(대)")
        .agg(
            체결액_억=("체결액_억", "sum"),
            리드타임_중앙값=("리드타임", "median"),
            교육기간_중앙값=("기간일수", "median"),
        )
        .reset_index()
        .sort_values("체결액_억", ascending=False)
    )

    category_timing = (
        won.groupby("카테고리(대)")
        .agg(
            체결액_억=("체결액_억", "sum"),
            리드타임_중앙값=("리드타임", "median"),
            교육기간_중앙값=("기간일수", "median"),
        )
        .reset_index()
        .sort_values("체결액_억", ascending=False)
    )

    seg = (
        won.groupby(SEG_COLS + ["예정연"])
        .agg(체결액_억=("체결액_억", "sum"), 건수=("체결액", "count"))
        .reset_index()
    )
    seg = seg.rename(columns={"예정연": "연도"})
    seg = seg.sort_values(["연도", "체결액_억"], ascending=[True, False])
    scale_year = (
        won.groupby(["예정연", "기업 규모 정리"])["체결액_억"]
        .sum()
        .reset_index()
        .rename(columns={"예정연": "연도", "체결액_억": "체결액(억)"})
    )
    domain_year = (
        won.groupby(["예정연", "고객 도메인"])["체결액_억"]
        .sum()
        .reset_index()
        .rename(columns={"예정연": "연도", "체결액_억": "체결액(억)"})
    )
    channel_year = (
        won.groupby(["예정연", "채널 구분"])["체결액_억"]
        .sum()
        .reset_index()
        .rename(columns={"예정연": "연도", "체결액_억": "체결액(억)"})
    )
    samsung_detail = (
        won[won["고객 도메인"] == "삼성전자"]
        .groupby(["예정연", "과정포맷(대)", "딜 전환 유형"])
        .agg(체결액_억=("체결액_억", "sum"), 건수=("체결액", "count"))
        .reset_index()
        .rename(columns={"예정연": "연도"})
        .sort_values(["연도", "체결액_억"], ascending=[True, False])
    )
    retention_year = (
        won[won["온라인 리텐션"]]
        .groupby("예정연")["체결액_억"]
        .sum()
        .reset_index()
        .rename(columns={"예정연": "연도", "체결액_억": "온라인 리텐션 체결액(억)"})
    )

    return {
        "won_year": won_year,
        "acc_year": acc_year,
        "timing": timing,
        "seg": seg,
        "scale": scale_year,
        "domain": domain_year,
        "channel": channel_year,
        "samsung": samsung_detail,
        "retention": retention_year,
        "timing_format": format_timing,
        "timing_category": category_timing,
    }


def render_report(
    won_year: pd.DataFrame,
    acc_year: pd.DataFrame,
    timing: pd.DataFrame,
    focus_year: int,
) -> None:
    st.markdown("#### 간단 리포트")
    if won_year.empty:
        st.info("Won 기준 연도별 체결액 데이터가 없습니다.")
        return

    if focus_year not in won_year["연도"].values:
        focus_year = int(won_year["연도"].max())
    row = won_year[won_year["연도"] == focus_year].iloc[0]
    won_val = row["체결액(억)"]
    won_yoy = row.get("체결 YoY%", np.nan)

    acc_val = np.nan
    acc_yoy = np.nan
    if not acc_year.empty and focus_year in acc_year["연도"].values:
        acc_row = acc_year[acc_year["연도"] == focus_year].iloc[0]
        acc_val = acc_row["매출(억)"]
        acc_yoy = acc_row.get("매출 YoY%", np.nan)

    timing_row = timing[timing["연도"] == focus_year]
    lead_val = timing_row["리드타임_중앙값"].iloc[0] if not timing_row.empty else np.nan
    dur_val = timing_row["교육기간_중앙값"].iloc[0] if not timing_row.empty else np.nan

    st.markdown(
        f"- {focus_year} 체결액: **{won_val:,.1f}억** (YoY {won_yoy:+.1f}% )"
    )
    st.markdown(
        f"- {focus_year} 회계 집계 매출: **{acc_val:,.1f}억** (YoY {acc_yoy:+.1f}% )"
        if not np.isnan(acc_val)
        else "- 회계 집계 매출 데이터가 없습니다."
    )
    st.markdown(
        f"- 리드타임 중앙값: **{lead_val:.0f}일**, 교육기간 중앙값: **{dur_val:.0f}일**"
        if not np.isnan(lead_val)
        else "- 리드타임/교육기간 정보를 찾을 수 없습니다."
    )
    st.markdown(
        "- 제안: ① 상위 세그먼트(카테고리·포맷·기업규모·딜유형) 중심으로 2026 체결 패턴 가중치 도출 "
        "② 리드타임·교육기간 분포를 기반으로 월별 진행율 매출 모듈 연결 "
        "③ 비용(마케팅/인건비) 시나리오와 결합해 OP/Rule of 40 추적"
    )


def main():
    st.title("년도별 사업성과 분석")
    st.caption("기업/공공/삼성전자, 온라인/출강 구분으로 2024~2025 Won/회계 실적을 정리합니다.")

    summary = make_summary()
    won_year = summary["won_year"]
    acc_year = summary["acc_year"]
    timing = summary["timing"]
    seg = summary["seg"]
    scale_year = summary["scale"]
    domain_year = summary["domain"]
    channel_year = summary["channel"]
    samsung_detail = summary["samsung"]
    retention_year = summary["retention"]
    timing_format = summary["timing_format"]
    timing_category = summary["timing_category"]

    if won_year.empty:
        st.warning("2024~2025 Won 데이터가 없습니다.")
        return

    year_choices = sorted(won_year["연도"].dropna().unique().tolist())
    selected_year = year_choices[-1]
    st.info(f"현재 보고서는 {selected_year}년 데이터만 제공합니다.")

    render_report(won_year, acc_year, timing, selected_year)

    if selected_year is not None and not domain_year.empty:
        dom_latest = (
            domain_year[domain_year["연도"] == selected_year]
            .set_index("고객 도메인")["체결액(억)"]
            .to_dict()
        )
        ch_latest = (
            channel_year[channel_year["연도"] == selected_year]
            .set_index("채널 구분")["체결액(억)"]
            .to_dict()
        )
        st.markdown(f"**{selected_year} 주요 구분 요약**")
        col_dom1, col_dom2, col_dom3 = st.columns(3)
        col_dom1.metric("기업 체결액(억)", f"{dom_latest.get('기업', 0):,.1f}")
        col_dom2.metric("공공 체결액(억)", f"{dom_latest.get('공공', 0):,.1f}")
        col_dom3.metric("삼성전자 체결액(억)", f"{dom_latest.get('삼성전자', 0):,.1f}")
        col_ch1, col_ch2 = st.columns(2)
        col_ch1.metric("온라인 (억)", f"{ch_latest.get('온라인', 0):,.1f}")
        col_ch2.metric("출강 (억)", f"{ch_latest.get('출강', 0):,.1f}")

    tab_summary, tab_timing, tab_seg, tab_scale, tab_domain, tab_samsung, tab_retention = st.tabs(
        ["연도별 요약", "리드타임/교육기간", "세그먼트", "기업 규모", "도메인·채널", "삼성전자", "온라인 리텐션"]
    )

    with tab_summary:
        st.subheader("체결액 / 매출 추이")
        summary_df = pd.merge(won_year, acc_year, on="연도", how="outer").sort_values("연도")
        summary_filtered = summary_df[summary_df["연도"] == selected_year]
        st.dataframe(summary_filtered, use_container_width=True, hide_index=True)

    with tab_timing:
        st.subheader("리드타임 · 교육기간 (중앙값)")
        timing_filtered = (
            timing[timing["연도"] == selected_year]
            .rename(columns={"체결액_억": "체결액 합계(억)"})
            .round(2)
        )
        st.dataframe(timing_filtered, use_container_width=True, hide_index=True)

        st.markdown("**과정포맷(대) 기준**")
        if timing_format.empty:
            st.info("과정포맷(대) 데이터가 없습니다.")
        else:
            st.dataframe(
                timing_format.round(2).rename(columns={"체결액_억": "체결액 합계(억)"}),
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("**카테고리(대) 기준**")
        if timing_category.empty:
            st.info("카테고리(대) 데이터가 없습니다.")
        else:
            st.dataframe(
                timing_category.round(2).rename(columns={"체결액_억": "체결액 합계(억)"}),
                use_container_width=True,
                hide_index=True,
            )

    with tab_seg:
        st.subheader("세그먼트별 체결액 (연도 기준)")
        st.caption("카테고리(대) × 과정포맷(대) × 기업 규모 × 딜 전환 유형 조합 기준")
        st.dataframe(seg[seg["연도"] == selected_year], use_container_width=True, hide_index=True)

    with tab_scale:
        st.subheader("기업 규모별 히스토리")
        scale_filtered = scale_year[scale_year["연도"] == selected_year]
        if scale_filtered.empty:
            st.info("기업 규모 집계가 없습니다.")
        else:
            st.dataframe(
                scale_filtered[["기업 규모 정리", "체결액(억)"]].sort_values("체결액(억)", ascending=False).round(2),
                use_container_width=True,
                hide_index=True,
            )

    with tab_domain:
        st.subheader("도메인(기업·공공·삼성전자) & 채널(온라인/출강)")
        dom_filtered = domain_year[domain_year["연도"] == selected_year]
        ch_filtered = channel_year[channel_year["연도"] == selected_year]
        if dom_filtered.empty:
            st.info("도메인 집계가 없습니다.")
        else:
            st.write("**고객 도메인별 체결액(억)**")
            st.dataframe(
                dom_filtered[["고객 도메인", "체결액(억)"]].sort_values("체결액(억)", ascending=False).round(2),
                use_container_width=True,
                hide_index=True,
            )
        if ch_filtered.empty:
            st.info("채널 집계가 없습니다.")
        else:
            st.write("**온라인 vs 출강 체결액(억)**")
            st.dataframe(
                ch_filtered[["채널 구분", "체결액(억)"]].round(2),
                use_container_width=True,
                hide_index=True,
            )

    with tab_samsung:
        st.subheader("삼성전자 히스토리 (별도)")
        samsung_filtered = samsung_detail[samsung_detail["연도"] == selected_year]
        if samsung_filtered.empty:
            st.info("삼성전자 데이터가 없습니다.")
        else:
            st.caption("삼성전자 관련 딜만 필터링 — 과정포맷/딜 유형별 체결액·건수")
            st.dataframe(samsung_filtered, use_container_width=True, hide_index=True)

    with tab_retention:
        st.subheader("온라인 리텐션 (연도별)")
        retention_filtered = retention_year[retention_year["연도"] == selected_year]
        if retention_filtered.empty:
            st.info("온라인 리텐션 히스토리가 없습니다.")
        else:
            st.dataframe(retention_filtered, use_container_width=True, hide_index=True)
            st.caption("※ 온라인 채널 + '리텐션' 딜 전환 유형 합계 — 2026 프로젝션 시 100% 재계약 가정에 활용.")

    st.info(
        "다음 단계: ① 세그먼트별 월 단위 분포(체결·교육 시작)와 분산도 시각화, "
        "② 극단치/누락 데이터 클리닝, ③ 결과를 00_2026 P&L Projection과 연동해 "
        "자동 보고서 생성 및 다운로드 추가."
    )


if __name__ == "__main__":
    main()
