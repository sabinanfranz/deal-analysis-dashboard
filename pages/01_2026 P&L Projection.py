from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from pandas.tseries import offsets

from data import load_won_deal

WON_PER_EOK = 100_000_000
TARGET_YEAR = 2026
YEAR_START = pd.Timestamp(f"{TARGET_YEAR}-01-01")
YEAR_END = pd.Timestamp(f"{TARGET_YEAR}-12-31")
MONTH_LABELS = list(range(1, 13))
ONLINE_FORMATS = {"선택구매(온라인)", "구독제(온라인)", "포팅"}
OFFLINE_FORMATS = {
    "출강",
    "복합(출강+온라인)",
    "기타",
    "스킬",
    "기타(미기재)",
    "미기재",
}
DEFAULT_DOMAIN = ["대기업", "중견기업", "중소기업", "공공기관", "대학교", "기타"]
ASSUMED_2025_REVENUE = 150.0  # 억 단위
BASE_DEAL_COLUMNS = [
    "기업명",
    "기업 규모",
    "과정포맷(대)",
    "카테고리(대)",
    "상위채널",
    "체결일",
    "수강시작일",
    "수강종료일",
    "체결액",
    "S-tier",
]
FINAL_DEAL_COLUMNS = BASE_DEAL_COLUMNS + ["module", "monthly_rev", "rev_2026"]


@dataclass
class SimulationInputs:
    online_target: float
    offline_target: float
    monthly_marketing: float
    monthly_payroll: float
    online_margin: float
    offline_margin: float
    samsung_online: float
    samsung_offline: float


@dataclass
class MedianLookup:
    level3: Dict[Tuple[str, str, str], Tuple[float, float, int]]
    level2: Dict[Tuple[str, str], Tuple[float, float, int]]
    level1: Dict[str, Tuple[float, float, int]]
    default_channel: Dict[str, Tuple[float, float]]
    overall_default: Tuple[float, float]
    min_sample: int = 5

    def fetch(self, channel: str, company_size: str, s_tier: str) -> Tuple[float, float]:
        for key in [
            (channel, company_size, s_tier),
            (channel, company_size),
            (channel,),
        ]:
            stats = self._lookup(key)
            if stats:
                return (stats[0], stats[1])

        if channel in self.default_channel:
            return self.default_channel[channel]
        return self.overall_default

    def _lookup(self, key: Tuple[str, ...]) -> Optional[Tuple[float, float, int]]:
        store: Dict
        if len(key) == 3:
            store = self.level3
        elif len(key) == 2:
            store = self.level2
        else:
            store = self.level1
        lookup_key: Any = key if len(key) > 1 else key[0]
        stats = store.get(lookup_key)
        if stats and stats[2] >= self.min_sample:
            return stats
        return None


def set_page() -> None:
    st.set_page_config(page_title="2026 P&L Projection", layout="wide")
    st.title("2026 P&L Projection")


def to_eok(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0) / WON_PER_EOK


def assign_top_channel(fmt: str) -> str:
    if fmt in ONLINE_FORMATS:
        return "온라인"
    return "출강"


def assign_s_tier(amount: float) -> str:
    if amount >= 1.0:
        return "S3"
    if amount >= 0.5:
        return "S2"
    if amount >= 0.25:
        return "S1"
    return "S0"


def round_dataframe(df: Optional[pd.DataFrame], decimals: int = 1) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        return df
    out = df.copy()
    num_cols = out.select_dtypes(include=[np.number]).columns
    out[num_cols] = out[num_cols].round(decimals)
    return out


def safe_mode(series: pd.Series, default: str) -> str:
    cleaned = series.dropna()
    if cleaned.empty:
        return default
    return cleaned.mode().iat[0]


def sanitize_lead(value: float) -> int:
    return max(int(round(value)), 0)


def sanitize_duration(value: float) -> int:
    return max(int(round(value)), 1)


def empty_deals_df() -> pd.DataFrame:
    return pd.DataFrame(columns=FINAL_DEAL_COLUMNS)


def finalize_module(df: pd.DataFrame, module_name: str) -> pd.DataFrame:
    if df.empty:
        return empty_deals_df()
    df = df[BASE_DEAL_COLUMNS].copy()
    df["module"] = module_name
    df = add_revenue_columns(df)
    return df[FINAL_DEAL_COLUMNS]


def parse_bool(series: pd.Series) -> pd.Series:
    normalized = (
        series.astype(str)
        .str.strip()
        .str.upper()
        .replace({"": pd.NA, "NAN": pd.NA})
    )
    truthy = {"TRUE", "T", "Y", "YES", "1"}
    falsy = {"FALSE", "F", "N", "NO", "0"}
    result = pd.Series(pd.NA, index=series.index, dtype="boolean")
    result = result.mask(normalized.isin(truthy), True)
    result = result.mask(normalized.isin(falsy), False)
    return result


def compute_monthly_allocation(
    start: pd.Timestamp,
    end: pd.Timestamp,
    amount: float,
    year: int = TARGET_YEAR,
) -> np.ndarray:
    arr = np.zeros(12, dtype=float)
    if pd.isna(start) or pd.isna(end) or amount <= 0:
        return arr
    total_days = (end - start).days + 1
    if total_days <= 0:
        return arr
    window_start = pd.Timestamp(year=year, month=1, day=1)
    window_end = pd.Timestamp(year=year, month=12, day=31)
    overlap_start = max(start, window_start)
    overlap_end = min(end, window_end)
    if overlap_start > overlap_end:
        return arr

    daily = amount / total_days
    for month in MONTH_LABELS:
        month_start = pd.Timestamp(year=year, month=month, day=1)
        month_end = month_start + offsets.MonthEnd(0)
        seg_start = max(overlap_start, month_start)
        seg_end = min(overlap_end, month_end)
        days = (seg_end - seg_start).days + 1
        if days > 0:
            arr[month - 1] = daily * days
    return arr


def backsolve_booking_amount(
    start: pd.Timestamp, end: pd.Timestamp, target_revenue: float
) -> float:
    """
    Given desired revenue recognized in target year, backsolve booking amount by
    dividing by the in-year recognition factor (overlap_days / total_days).
    """
    if target_revenue <= 0 or pd.isna(start) or pd.isna(end):
        return 0.0
    factor = compute_monthly_allocation(start, end, 1.0).sum()
    if factor <= 0:
        return 0.0
    return target_revenue / factor


def preprocess_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, MedianLookup, pd.DataFrame, pd.DataFrame]:
    work = df.copy()
    rename_map = {
        "과정포맷": "과정포맷(대)",
        "카테고리": "카테고리(대)",
        "계약일": "계약 체결일",
        "Won등록일": "생성 날짜",
    }
    for old, new in rename_map.items():
        if old in work.columns and new not in work.columns:
            work[new] = work[old]

    numeric_col = "수주 예정액(종합)"
    work[numeric_col] = to_eok(work.get(numeric_col, 0))
    work.rename(columns={numeric_col: "체결액"}, inplace=True)

    date_cols = [
        "생성 날짜",
        "수강시작일",
        "수강종료일",
        "계약 체결일",
        "수주 예정일(종합)",
    ]
    for col in date_cols:
        if col in work.columns:
            work[col] = pd.to_datetime(work[col], errors="coerce")

    empty_dt = pd.Series(pd.NaT, index=work.index)
    work["체결일"] = (
        work.get("계약 체결일", empty_dt)
        .combine_first(work.get("수주 예정일(종합)", empty_dt))
        .combine_first(work.get("생성 날짜", empty_dt))
    )
    work = work[work["체결일"].dt.year == 2025]

    work["과정포맷(대)"] = work.get("과정포맷(대)", pd.Series(index=work.index)).fillna(
        work.get("과정포맷")
    ).fillna("기타")
    work["카테고리(대)"] = work.get("카테고리(대)", pd.Series(index=work.index)).fillna(
        work.get("카테고리")
    ).fillna("미기재")
    work["기업 규모"] = work.get("기업 규모", pd.Series(index=work.index)).fillna("미기재")
    work["상위채널"] = work["과정포맷(대)"].apply(assign_top_channel)

    work = work.dropna(subset=["수강시작일", "수강종료일"]).copy()
    work["교육기간"] = (work["수강종료일"] - work["수강시작일"]).dt.days + 1
    work["교육기간"] = work["교육기간"].clip(lower=1)
    work["리드타임"] = (
        work["수주 예정일(종합)"] - work["생성 날짜"]
    ).dt.days
    work["리드타임"] = work["리드타임"].fillna(0).clip(lower=0)
    work["S-tier"] = work["체결액"].apply(assign_s_tier)
    work = work[work["체결액"] > 0].copy()

    median_lookup, median_table, format_table = build_median_lookup(work)
    return work.reset_index(drop=True), median_lookup, median_table, format_table


def build_median_lookup(
    df: pd.DataFrame,
) -> Tuple[MedianLookup, pd.DataFrame, pd.DataFrame]:
    valid = df.dropna(subset=["리드타임", "교육기간"]).copy()
    valid = valid[(valid["리드타임"] > 0) & (valid["교육기간"] > 0)]

    def agg_table(cols: List[str]) -> pd.DataFrame:
        return (
            valid.groupby(cols)
            .agg(
                median_lead=("리드타임", "median"),
                median_duration=("교육기간", "median"),
                sample=("리드타임", "count"),
            )
            .reset_index()
        )

    lvl3_df = agg_table(["상위채널", "기업 규모", "S-tier"])
    lvl2_df = agg_table(["상위채널", "기업 규모"])
    lvl1_df = agg_table(["상위채널"])

    level3 = {
        (row["상위채널"], row["기업 규모"], row["S-tier"]): (
            row["median_lead"],
            row["median_duration"],
            row["sample"],
        )
        for _, row in lvl3_df.iterrows()
    }
    level2 = {
        (row["상위채널"], row["기업 규모"]): (
            row["median_lead"],
            row["median_duration"],
            row["sample"],
        )
        for _, row in lvl2_df.iterrows()
    }
    level1 = {
        row["상위채널"]: (row["median_lead"], row["median_duration"], row["sample"])
        for _, row in lvl1_df.iterrows()
    }

    default_channel = {
        ch: (row["median_lead"], row["median_duration"])
        for ch, row in lvl1_df.set_index("상위채널").iterrows()
    }
    fallback = (
        float(valid["리드타임"].median()) if not valid.empty else 30.0,
        float(valid["교육기간"].median()) if not valid.empty else 30.0,
    )

    format_table = (
        valid.groupby(["과정포맷(대)", "카테고리(대)"])
        .agg(
            median_lead=("리드타임", "median"),
            median_duration=("교육기간", "median"),
            sample=("리드타임", "count"),
        )
        .reset_index()
        .sort_values(["과정포맷(대)", "카테고리(대)"])
    )

    display_table = lvl3_df.rename(
        columns={
            "median_lead": "Median 리드타임(일)",
            "median_duration": "Median 교육기간(일)",
            "sample": "샘플 수",
        }
    )
    format_table = format_table.rename(
        columns={
            "median_lead": "Median 리드타임(일)",
            "median_duration": "Median 교육기간(일)",
            "sample": "샘플 수",
        }
    )

    lookup = MedianLookup(level3, level2, level1, default_channel, fallback)
    return lookup, display_table, format_table


def simulate_backlog(df: pd.DataFrame) -> pd.DataFrame:
    mask = (df["수강종료일"] >= YEAR_START) & (df["수강시작일"] <= YEAR_END)
    base = df.loc[mask, BASE_DEAL_COLUMNS].copy()
    return finalize_module(base, "A. Backlog")


def build_samsung_deals(inputs: SimulationInputs) -> pd.DataFrame:
    records = []
    for month in MONTH_LABELS:
        month_start = pd.Timestamp(year=TARGET_YEAR, month=month, day=1)
        month_end = month_start + offsets.MonthEnd(0)
        for channel, amount in [
            ("온라인", inputs.samsung_online),
            ("출강", inputs.samsung_offline),
        ]:
            if amount <= 0:
                continue
            fmt = "구독제(온라인)" if channel == "온라인" else "출강"
            s_tier = assign_s_tier(amount)
            records.append(
                {
                    "기업명": "삼성전자",
                    "기업 규모": "대기업",
                    "과정포맷(대)": fmt,
                    "카테고리(대)": "삼성 플랜",
                    "상위채널": channel,
                    "체결일": month_start,
                    "수강시작일": month_start,
                    "수강종료일": month_end,
                    "체결액": amount,
                    "S-tier": s_tier,
                }
            )
    base = pd.DataFrame(records, columns=BASE_DEAL_COLUMNS)
    return finalize_module(base, "B. 삼성 계획")


def simulate_online_retention(df: pd.DataFrame) -> pd.DataFrame:
    base = df[
        (df["기업명"] != "삼성전자")
        & (df["상위채널"] == "온라인")
    ].copy()
    if base.empty:
        return empty_deals_df()

    for date_col in ["체결일", "수강시작일", "수강종료일"]:
        base[date_col] = base[date_col] + pd.Timedelta(days=365)

    base = base[(base["수강종료일"] >= YEAR_START) & (base["수강시작일"] <= YEAR_END)]
    return finalize_module(base, "C1. 온라인 리텐션")


def simulate_upsell(df: pd.DataFrame, lookup: MedianLookup) -> pd.DataFrame:
    base = df[
        (df["기업명"] != "삼성전자") & (df["상위채널"] == "출강")
    ].copy()
    if base.empty:
        return pd.DataFrame(columns=df.columns.tolist() + ["module", "monthly_rev", "rev_2026"])

    records = []
    grouped = base.groupby("기업명")
    for company, grp in grouped:
        sum_amount = grp["체결액"].sum()
        if sum_amount <= 0:
            continue
        month_series = grp["체결일"].dt.month.dropna()
        if month_series.empty:
            continue
        avg_month = int(round(month_series.mean()))
        target_month = max(1, min(12, avg_month))
        amount = sum_amount * upsell_multiplier(sum_amount)
        if amount <= 0:
            continue
        contract_date = pd.Timestamp(year=TARGET_YEAR, month=target_month, day=15)
        size = safe_mode(grp["기업 규모"], "대기업")
        channel = "출강"
        s_tier = assign_s_tier(amount)
        lead, duration = lookup.fetch(channel, size, s_tier)
        lead_days = sanitize_lead(lead)
        duration_days = sanitize_duration(duration)
        start = contract_date + pd.Timedelta(days=lead_days)
        end = start + pd.Timedelta(days=duration_days - 1)
        records.append(
            {
                "기업명": company,
                "기업 규모": size,
                "과정포맷(대)": safe_mode(grp["과정포맷(대)"], "출강"),
                "카테고리(대)": safe_mode(grp["카테고리(대)"], "Upsell"),
                "상위채널": channel,
                "체결일": contract_date,
                "수강시작일": start,
                "수강종료일": end,
                "체결액": amount,
                "S-tier": s_tier,
            }
        )
    base = pd.DataFrame(records, columns=BASE_DEAL_COLUMNS)
    return finalize_module(base, "C2. Upsell")


def upsell_multiplier(sum_amount: float) -> float:
    if sum_amount >= 1.0:
        return 1.1
    if sum_amount >= 0.5:
        return 1.25
    if sum_amount >= 0.25:
        return 1.5
    return 2.0


def build_domain_share(df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    grouped = df.groupby(["상위채널", "기업 규모"])["체결액"].sum()
    result: Dict[str, Dict[str, float]] = {}
    for channel in ["온라인", "출강"]:
        try:
            channel_series = grouped.xs(channel, level="상위채널")
        except KeyError:
            channel_series = pd.Series(dtype=float)
        channel_series = channel_series[channel_series > 0]
        total = channel_series.sum()
        if total <= 0:
            sizes = list(channel_series.index) if not channel_series.empty else DEFAULT_DOMAIN
            share = {size: 1 / len(sizes) for size in sizes}
        else:
            share = (channel_series / total).to_dict()
        result[channel] = share
    return result


def channel_month_weights(channel: str) -> Dict[int, float]:
    if channel == "온라인":
        q_weights = [4, 2, 2, 4]
    else:
        q_weights = [5, 3, 2, 2]
    total = sum(q_weights)
    month_weights = {}
    for q_idx, weight in enumerate(q_weights):
        share = weight / total
        for offset_month in range(3):
            month = q_idx * 3 + offset_month + 1
            month_weights[month] = share / 3
    # 정규화(혹시라도 부동소수 오차 방지)
    s = sum(month_weights.values())
    return {m: w / s for m, w in month_weights.items()} if s else month_weights


def simulate_new_deals(
    df: pd.DataFrame,
    lookup: MedianLookup,
    inputs: SimulationInputs,
    existing_online: float,
    existing_offline: float,
) -> pd.DataFrame:
    online_gap = max(inputs.online_target - existing_online, 0)
    offline_gap = max(inputs.offline_target - existing_offline, 0)
    if online_gap == 0 and offline_gap == 0:
        return empty_deals_df()
    domain_share = build_domain_share(df)
    records = []
    for channel, gap in [("온라인", online_gap), ("출강", offline_gap)]:
        if gap <= 0:
            continue
        shares = domain_share.get(channel, {})
        month_weights = channel_month_weights(channel)
        for size, size_ratio in shares.items():
            size_gap = gap * size_ratio
            if size_gap <= 0:
                continue
            month_info = []
            for month, w in month_weights.items():
                contract_date = pd.Timestamp(year=TARGET_YEAR, month=month, day=15)
                # 임시 S-tier는 size_gap*w 로 추정
                lead, duration = lookup.fetch(channel, size, assign_s_tier(size_gap * w))
                lead_days = sanitize_lead(lead)
                duration_days = sanitize_duration(duration)
                start = contract_date + pd.Timedelta(days=lead_days)
                end = start + pd.Timedelta(days=duration_days - 1)
                recog_factor = compute_monthly_allocation(start, end, 1.0).sum()
                month_info.append(
                    {
                        "month": month,
                        "weight": w,
                        "start": start,
                        "end": end,
                        "recog": recog_factor,
                    }
                )
            denom = sum(mi["weight"] * mi["recog"] for mi in month_info)
            if denom <= 0:
                continue
            booking_total = size_gap / denom
            fmt = "구독제(온라인)" if channel == "온라인" else "출강"
            for mi in month_info:
                amount = booking_total * mi["weight"]
                if amount <= 0:
                    continue
                s_tier = assign_s_tier(amount)
                lead, duration = lookup.fetch(channel, size, s_tier)
                lead_days = sanitize_lead(lead)
                duration_days = sanitize_duration(duration)
                start = mi["start"]
                end = mi["end"]
                # 일정은 앞서 계산한 것을 사용
                records.append(
                    {
                        "기업명": f"신규-{channel}-{size}",
                        "기업 규모": size,
                        "과정포맷(대)": fmt,
                        "카테고리(대)": "신규",
                        "상위채널": channel,
                        "체결일": pd.Timestamp(year=TARGET_YEAR, month=mi["month"], day=15),
                        "수강시작일": start,
                        "수강종료일": end,
                        "체결액": amount,
                        "S-tier": s_tier,
                    }
                )
    base = pd.DataFrame(records, columns=BASE_DEAL_COLUMNS)
    return finalize_module(base, "D. 신규 Deals")


def add_revenue_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["monthly_rev"] = df.apply(
        lambda row: compute_monthly_allocation(
            row["수강시작일"], row["수강종료일"], row["체결액"]
        ),
        axis=1,
    )
    df["monthly_rev"] = df["monthly_rev"].apply(
        lambda arr: arr if isinstance(arr, np.ndarray) else np.zeros(12, dtype=float)
    )
    df["rev_2026"] = df["monthly_rev"].apply(np.sum)
    return df


def summarize_monthly(deals: pd.DataFrame) -> pd.DataFrame:
    online = np.zeros(12, dtype=float)
    offline = np.zeros(12, dtype=float)
    for _, row in deals.iterrows():
        if not isinstance(row["monthly_rev"], np.ndarray):
            continue
        if row["상위채널"] == "온라인":
            online += row["monthly_rev"]
        else:
            offline += row["monthly_rev"]
    total = online + offline
    return pd.DataFrame(
        {
            "월": MONTH_LABELS,
            "온라인 매출(억)": online,
            "출강 매출(억)": offline,
            "총매출(억)": total,
        }
    )


def summarize_bookings(deals: pd.DataFrame) -> np.ndarray:
    arr = np.zeros(12, dtype=float)
    for _, row in deals.iterrows():
        close_date = row.get("체결일")
        amount = row.get("체결액", 0)
        if pd.isna(close_date) or amount <= 0 or close_date.year != TARGET_YEAR:
            continue
        arr[close_date.month - 1] += amount
    return arr


def bookings_by_channel(deals: pd.DataFrame) -> Tuple[float, float, float]:
    if deals.empty or "체결일" not in deals.columns:
        return 0.0, 0.0, 0.0
    mask = deals["체결일"].notna() & (deals["체결일"].dt.year == TARGET_YEAR)
    grouped = deals.loc[mask].groupby("상위채널")["체결액"].sum()
    online = grouped.get("온라인", 0.0)
    offline = grouped.get("출강", 0.0)
    return online, offline, online + offline


def aggregate_pnl(
    deals: pd.DataFrame,
    inputs: SimulationInputs,
    hist_2025: float,
) -> Tuple[Dict[str, float], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly_df = summarize_monthly(deals)
    online_total = monthly_df["온라인 매출(억)"].sum()
    offline_total = monthly_df["출강 매출(억)"].sum()
    total_revenue = monthly_df["총매출(억)"].sum()

    online_contribution = online_total * inputs.online_margin
    offline_contribution = offline_total * inputs.offline_margin
    online_variable = online_total - online_contribution
    offline_variable = offline_total - offline_contribution

    production = 0.2 * 12
    annual_marketing = inputs.monthly_marketing * 12
    annual_payroll = inputs.monthly_payroll * 12
    annual_rent = annual_payroll * 0.15
    annual_other = 1 * 12 + offline_total * 0.05
    fixed_total = production + annual_marketing + annual_payroll + annual_rent + annual_other

    total_contribution = online_contribution + offline_contribution
    op = total_contribution - fixed_total
    op_margin = (op / total_revenue) if total_revenue else 0
    growth = (total_revenue / hist_2025 - 1) if hist_2025 else 0
    rule50 = growth * 100 + op_margin * 100
    payroll_ratio = (annual_payroll / total_revenue) if total_revenue else 0

    bookings_online, bookings_offline, bookings_total = bookings_by_channel(deals)
    pnl_summary = pd.DataFrame(
        {
            "구분": ["체결액", "매출", "공헌 비용", "공헌 이익", "고정비", "OP"],
            "온라인(억)": [
                bookings_online,
                online_total,
                online_variable,
                online_contribution,
                np.nan,
                np.nan,
            ],
            "출강(억)": [
                bookings_offline,
                offline_total,
                offline_variable,
                offline_contribution,
                np.nan,
                np.nan,
            ],
            "합계(억)": [
                bookings_total,
                total_revenue,
                online_variable + offline_variable,
                total_contribution,
                fixed_total,
                op,
            ],
        }
    )

    monthly_pnl = build_monthly_pnl_table(monthly_df, deals, inputs)
    fixed_detail = pd.DataFrame(
        {
            "고정비 항목": ["제작비", "마케팅비", "인건비", "임대료", "기타비용"],
            "연간 비용(억)": [production, annual_marketing, annual_payroll, annual_rent, annual_other],
        }
    )

    kpis = {
        "total_revenue": total_revenue,
        "online_revenue": online_total,
        "offline_revenue": offline_total,
        "op": op,
        "op_margin": op_margin,
        "growth": growth,
        "rule50": rule50,
        "payroll_ratio": payroll_ratio,
    }

    return kpis, pnl_summary, monthly_df, monthly_pnl, fixed_detail


def build_monthly_pnl_table(
    monthly_rev: pd.DataFrame,
    deals: pd.DataFrame,
    inputs: SimulationInputs,
) -> pd.DataFrame:
    bookings = summarize_bookings(deals)
    online_bookings = summarize_bookings(deals[deals["상위채널"] == "온라인"])
    offline_bookings = summarize_bookings(deals[deals["상위채널"] == "출강"])
    online = monthly_rev["온라인 매출(억)"].to_numpy()
    offline = monthly_rev["출강 매출(억)"].to_numpy()
    total = monthly_rev["총매출(억)"].to_numpy()

    online_contrib = online * inputs.online_margin
    offline_contrib = offline * inputs.offline_margin
    online_variable = online - online_contrib
    offline_variable = offline - offline_contrib
    contribution_total = online_contrib + offline_contrib
    variable_total = online_variable + offline_variable

    production = np.full(12, 0.2)
    marketing = np.full(12, inputs.monthly_marketing)
    payroll = np.full(12, inputs.monthly_payroll)
    rent = payroll * 0.15
    other = 1 + offline * 0.05
    fixed_total = production + marketing + payroll + rent + other
    op = contribution_total - fixed_total

    metrics = {
        "체결액(억)": bookings,
        "└ 온라인 체결액(억)": online_bookings,
        "└ 출강 체결액(억)": offline_bookings,
        "총매출(억)": total,
        "└ 온라인 매출(억)": online,
        "└ 출강 매출(억)": offline,
        "공헌비용 합계(억)": variable_total,
        "└ 온라인 공헌비용(억)": online_variable,
        "└ 출강 공헌비용(억)": offline_variable,
        "공헌이익 합계(억)": contribution_total,
        "└ 온라인 공헌이익(억)": online_contrib,
        "└ 출강 공헌이익(억)": offline_contrib,
        "고정비 합계(억)": fixed_total,
        "└ 제작비(억)": production,
        "└ 마케팅비(억)": marketing,
        "└ 인건비(억)": payroll,
        "└ 임대료(억)": rent,
        "└ 기타비용(억)": other,
        "OP(억)": op,
    }
    df = pd.DataFrame(metrics).T
    df.columns = [f"{m}월" for m in MONTH_LABELS]
    df.insert(0, "항목", df.index)
    month_cols = [col for col in df.columns if col.endswith("월")]
    df["합계"] = df[month_cols].sum(axis=1)
    return df.reset_index(drop=True)


def module_breakdown_table(deals: pd.DataFrame) -> pd.DataFrame:
    if deals.empty:
        return pd.DataFrame(columns=["모듈", "온라인(억)", "출강(억)", "합계(억)"])
    grouped = (
        deals.groupby(["module", "상위채널"])["rev_2026"].sum().unstack(fill_value=0)
    )
    grouped["합계(억)"] = grouped.sum(axis=1)
    grouped = grouped.rename(columns={"온라인": "온라인(억)", "출강": "출강(억)"})
    for col in ["온라인(억)", "출강(억)"]:
        if col not in grouped.columns:
            grouped[col] = 0.0
    grouped = grouped.reset_index().loc[
        :, ["module", "온라인(억)", "출강(억)", "합계(억)"]
    ]
    return grouped


def carryover_table(all_deals: pd.DataFrame) -> pd.DataFrame:
    if all_deals is None or all_deals.empty:
        return pd.DataFrame(
            {"구분": ["2026→2027 이월"], "온라인(억)": [0.0], "출강(억)": [0.0], "합계(억)": [0.0]}
        )
    mask = all_deals["수강종료일"] > YEAR_END
    future = all_deals.loc[mask]
    if future.empty:
        return pd.DataFrame(
            {"구분": ["2026→2027 이월"], "온라인(억)": [0.0], "출강(억)": [0.0], "합계(억)": [0.0]}
        )
    grouped = future.groupby("상위채널")["체결액"].sum()
    online = grouped.get("온라인", 0.0)
    offline = grouped.get("출강", 0.0)
    total = online + offline
    return pd.DataFrame(
        {
            "구분": ["2026→2027 이월"],
            "온라인(억)": [online],
            "출강(억)": [offline],
            "합계(억)": [total],
        }
    )


def build_deal_table(deals: pd.DataFrame) -> pd.DataFrame:
    if deals.empty:
        return deals
    cols = [
        "module",
        "기업명",
        "기업 규모",
        "과정포맷(대)",
        "카테고리(대)",
        "상위채널",
        "체결일",
        "수강시작일",
        "수강종료일",
        "체결액",
        "rev_2026",
    ]
    table = deals[cols].copy()
    table = table.rename(columns={"rev_2026": "2026 매출(억)", "체결액": "체결액(억)"})
    return table.sort_values(["module", "기업명"])


def sidebar_controls() -> Tuple[
    Optional[pd.DataFrame],
    Optional[MedianLookup],
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Optional[pd.DataFrame],
    Optional[Dict[str, Any]],
]:
    st.sidebar.header("데이터 & 시뮬레이션")

    if "data_bundle" not in st.session_state:
        try:
            raw_df = load_won_deal()
            pre_df, lookup, median_table, format_table = preprocess_data(raw_df)
            domain_pivot = (
                pre_df.groupby(["기업 규모", "상위채널"])["체결액"].sum().unstack(fill_value=0)
            )
            st.session_state["data_bundle"] = {
                "raw": raw_df,
                "pre": pre_df,
                "lookup": lookup,
                "median": median_table,
                "format_table": format_table,
                "domain_pivot": domain_pivot,
            }
        except Exception as err:  # pylint: disable=broad-except
            st.sidebar.error(f"데이터 로드 실패: {err}")
            st.session_state["data_bundle"] = None

    bundle = st.session_state.get("data_bundle")
    pre_df = bundle["pre"] if bundle else None
    lookup = bundle["lookup"] if bundle else None
    median_table = bundle["median"] if bundle else None
    format_table = bundle["format_table"] if bundle else None
    domain_pivot = bundle["domain_pivot"] if bundle else None

    st.sidebar.subheader("시뮬레이션 레버 (억 단위)")
    inputs = SimulationInputs(
        online_target=st.sidebar.number_input("년 온라인 매출 목표", min_value=0.0, value=65.0, step=1.0),
        offline_target=st.sidebar.number_input("년 출강 매출 목표", min_value=0.0, value=150.0, step=1.0),
        monthly_marketing=st.sidebar.number_input("월 마케팅비", min_value=0.0, value=0.3, step=0.1),
        monthly_payroll=st.sidebar.number_input("월 인건비", min_value=0.0, value=5.6, step=0.1),
        online_margin=st.sidebar.slider("온라인 공헌이익률", min_value=0.0, max_value=1.0, value=0.85),
        offline_margin=st.sidebar.slider("출강 공헌이익률", min_value=0.0, max_value=1.0, value=0.55),
        samsung_online=st.sidebar.number_input("삼성 월 온라인 계획", min_value=0.0, value=1.0, step=0.1),
        samsung_offline=st.sidebar.number_input("삼성 월 출강 계획", min_value=0.0, value=2.5, step=0.1),
    )

    results = None
    if pre_df is not None and lookup is not None:
        results = run_simulation(pre_df, lookup, inputs)

    return pre_df, lookup, median_table, format_table, domain_pivot, results


def run_simulation(
    pre_df: pd.DataFrame,
    lookup: MedianLookup,
    inputs: SimulationInputs,
) -> Dict[str, Any]:
    backlog = simulate_backlog(pre_df)
    samsung = build_samsung_deals(inputs)
    retention = simulate_online_retention(pre_df)
    upsell = simulate_upsell(pre_df, lookup)
    existing_online = (
        backlog.loc[backlog["상위채널"] == "온라인", "rev_2026"].sum()
        + samsung.loc[samsung["상위채널"] == "온라인", "rev_2026"].sum()
        + retention.loc[retention["상위채널"] == "온라인", "rev_2026"].sum()
    )
    existing_offline = (
        backlog.loc[backlog["상위채널"] == "출강", "rev_2026"].sum()
        + samsung.loc[samsung["상위채널"] == "출강", "rev_2026"].sum()
        + upsell.loc[upsell["상위채널"] == "출강", "rev_2026"].sum()
    )
    new_deals = simulate_new_deals(pre_df, lookup, inputs, existing_online, existing_offline)

    all_deals = pd.concat(
        [backlog, samsung, retention, upsell, new_deals],
        ignore_index=True,
    )
    if all_deals.empty:
        all_deals = empty_deals_df()
    all_deals["module"] = all_deals["module"].fillna("")
    all_deals["rev_2026"] = all_deals["rev_2026"].fillna(0.0)
    all_deals["monthly_rev"] = all_deals["monthly_rev"].apply(
        lambda arr: arr if isinstance(arr, np.ndarray) else np.zeros(12, dtype=float)
    )

    hist_2025 = ASSUMED_2025_REVENUE
    kpis, pnl_summary, monthly_rev, monthly_pnl, fixed_detail = aggregate_pnl(
        all_deals, inputs, hist_2025
    )
    modules = module_breakdown_table(all_deals)
    deals_table = build_deal_table(all_deals)
    carry_df = carryover_table(all_deals)

    return {
        "kpi": kpis,
        "pnl_summary": pnl_summary,
        "monthly_rev": monthly_rev,
        "monthly_pnl": monthly_pnl,
        "module_table": modules,
        "deals": deals_table,
        "fixed_detail": fixed_detail,
        "carry": carry_df,
    }


def render_tabs(pre_df, median_table, format_table, domain_pivot, results):
    tabs = st.tabs(
        ["시뮬레이션 결과", "데이터 요약", "딜 상세 & 다운로드", "시뮬레이션 로직"]
    )
    with tabs[0]:
        if not results:
            st.info("사이드바에서 시뮬레이션을 실행하세요.")
        else:
            kpi = results["kpi"]
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("2026 총 매출(억)", f"{kpi['total_revenue']:.1f}")
            col1.metric("온라인 매출(억)", f"{kpi['online_revenue']:.1f}")
            col2.metric("출강 매출(억)", f"{kpi['offline_revenue']:.1f}")
            col2.metric("영업이익(OP, 억)", f"{kpi['op']:.1f}")
            col3.metric("OP Margin", f"{kpi['op_margin']*100:.1f}%")
            col3.metric("성장률", f"{kpi['growth']*100:.1f}%")
            col4.metric("Rule of 50", f"{kpi['rule50']:.1f}")
            col4.metric("인건비 비율", f"{kpi['payroll_ratio']*100:.1f}%")

            st.markdown("#### 모듈별 매출 기여 (억)")
            st.dataframe(round_dataframe(results["module_table"]))

            st.markdown("#### 월별 P&L (억)")
            st.dataframe(round_dataframe(results["monthly_pnl"]))

            st.markdown("#### 연간 P&L 요약 (억)")
            st.dataframe(round_dataframe(results["pnl_summary"]))
            st.markdown("#### 고정비 상세 (연간, 억)")
            st.dataframe(round_dataframe(results["fixed_detail"]))
            st.markdown("#### 2026→2027 이월 매출 (억)")
            st.dataframe(round_dataframe(results.get("carry")))

    with tabs[1]:
        if pre_df is None:
            st.warning("먼저 2025 Won 딜 데이터를 불러오세요.")
        else:
            st.markdown("#### 전처리된 데이터 샘플")
            st.dataframe(pre_df.head(20))
            st.markdown("#### 기업 규모 × 상위채널 매출 (억)")
            if domain_pivot is not None:
                st.dataframe(domain_pivot)
            else:
                st.info("기업 규모 피벗 데이터를 찾을 수 없습니다.")
            st.markdown("#### Median 리드타임(상위채널/기업규모/S-tier)")
            if median_table is not None:
                st.dataframe(median_table)
            else:
                st.info("Median 테이블이 없습니다.")
            st.markdown("#### 리드타임 · 교육기간 (과정포맷→카테고리)")
            if format_table is not None:
                st.dataframe(format_table)
            else:
                st.info("세그먼트 요약이 없습니다.")

    with tabs[2]:
        if not results or results["deals"].empty:
            st.info("시뮬레이션을 실행한 뒤 딜 세부 데이터를 확인할 수 있습니다.")
        else:
            st.dataframe(results["deals"])
            csv = results["deals"].to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "딜 데이터 다운로드 (CSV)",
                data=csv,
                file_name="2026_simulated_deals.csv",
                mime="text/csv",
            )

    with tabs[3]:
        tab_logic_details()


def tab_logic_details() -> None:
    st.subheader("시뮬레이션 로직 상세")
    st.markdown(
        """
        ### 데이터 전처리
        - `load_won_deal()`을 기본 데이터 소스로 활용하며 필요 시 업로드 파일로 교체할 수 있습니다.
        - 2025년에 체결된 Won 딜만 사용합니다.
        - 금액은 `수주 예정액(종합)`을 사용해 모두 **억 단위**로 변환합니다.
        - `과정포맷(대)` → 상위 채널(온라인/출강)으로 매핑합니다.
        - 리드타임 = `수주 예정일(종합)` − `생성 날짜`, 교육기간 = `수강종료일` − `수강시작일` + 1.
        - S-tier(S3≥1억, S2≥0.5억, S1≥0.25억, 나머지 S0) 기준으로 리드타임/교육기간의 중앙값 Lookup을 생성합니다.

        ### 모듈별 로직
        1. **A. Backlog**: 2026년과 교육 기간이 겹치는 2025 Won 딜을 일별 안분해 2026 매출을 계산합니다.
        2. **B. 삼성 계획**: 입력한 삼성 월별 온라인/출강 금액(억)을 12개월 반복하여 월 단위 딜을 생성합니다.
        3. **C1. 온라인 리텐션**: 비삼성 온라인 포맷 딜을 +365일 이동 후 2026과 겹치는 건만 포함합니다.
        4. **C2. Upsell**: 비삼성 출강 딜의 연간 실적을 기업별로 P-tier를 부여하고, 2026 동일 월에 업셀 딜을 생성합니다(업셀 금액 = 기존 체결액 × 배수).
        5. **D. 신규 딜**:
           - A~C 매출을 채널별로 합산 후 목표(온라인/출강)와의 Gap을 구합니다(음수는 0).
           - 2025년 채널×기업규모 매출 비중으로 Gap을 기업규모별 분배(없으면 균등).
           - 계절 가중치로 월 분배: 온라인 분기 가중치 4/2/2/4, 출강 5/3/2/2를 12로 나눠 분기 비율을 만들고 분기 내 3개월 균등 분배, 마지막에 총합=1로 정규화 → 결과적으로 체결액 합계가 이 가중치 비율을 따름.
           - 리드타임·교육기간 적용 및 체결액 역산:
             1) 각 월/기업규모/채널 조합에 대해 체결일=그 달 15일, Median Lookup(채널→채널×규모→채널)로 리드타임·교육기간을 가져와 수강시작/종료일을 계산.
             2) 위 일정으로 1억을 체결했을 때 2026에 인식되는 비율(`recog_factor`)을 산출.
             3) `booking_total = size_gap / Σ(weight × recog_factor)`로 해당 규모·채널 전체 체결액을 역산하고, 월별 체결액은 `booking_total × weight`로 분배 → 월별 인식 매출이 Gap을 충족하면서 체결액 분기 비율(4/2/2/4 또는 5/3/2/2)이 유지됩니다.
             4) 온라인 포맷은 “구독제(온라인)”, 출강은 “출강”으로 생성.

        ### P&L 산출
        - 매출 인식은 모든 모듈 딜을 2026년 달력을 기준으로 일별 안분 후 월별 합산합니다.
        - 공헌이익은 채널별 마진(입력값)을 적용해 계산하며, 공헌비용은 매출에서 공헌이익을 제외한 값입니다.
        - 고정비는 ①제작비 0.2억/월, ②마케팅비 입력값, ③인건비 입력값, ④임대료=인건비×15%, ⑤기타비용=1억/월 + 출강 매출의 5%로 구성합니다.
        - 영업이익(OP) = 공헌이익 합계 − 고정비 합계. OP Margin, 성장률(2025 대비), Rule of 50, 인건비 비율 등을 KPI로 제공합니다.
        """
    )


def main() -> None:
    set_page()
    pre_df, lookup, median_table, format_table, domain_pivot, results = sidebar_controls()
    render_tabs(pre_df, median_table, format_table, domain_pivot, results)


if __name__ == "__main__":
    main()
