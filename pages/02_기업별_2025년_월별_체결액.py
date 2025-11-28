# pages/24_기업별_온라인출강구분_매출피벗(Won).py
import streamlit as st
import pandas as pd
import numpy as np
import re
import json

from data import load_won_deal, load_all_deal  # ← all_deal 로더 추가

st.set_page_config(page_title="기업별 온라인/출강 구분 매출 (Won)", layout="wide")
st.title("기업별 온라인·출강 구분 매출 피벗 (Won 기준)")
st.caption("열: 기업명, 체결액 구분, YYYY년 체결액 합, YY01~YY12(수주예정월 기준) · 값: 수주 예정액(종합) 합(억)")

MONTHS = list(range(1, 13))

# 🔒 고정 라벨(정확 일치) — 과정포맷(대) 기준
FMT_LABELS = [
    "출강",
    "복합(출강+온라인)",
    "구독제(온라인)",
    "선택구매(온라인)",
    "포팅",
    "스킬",
]
ROW_ORDER = [
    "전체",
    *FMT_LABELS,
    "기타",
    "미기재",
]

# 상세 행 표시 컬럼(요청 순서)
DETAIL_COLS_ORDER = [
    "생성 날짜","기업명","이름","팀_0_name","담당자_name","다음 연락일","파이프라인_name","파이프라인 단계_name",
    "상태","성사 가능성","수주 예정일(종합)","수주 예정액(종합)","LOST 확정일","딜 전환 유형","SQL 전환일",
    "카테고리","과정포맷","수주 예정일","수주 예정일(지연)","예상 체결액","제안서 발송일","교육 시작월(예상)",
    "수강시작일","수강종료일","코스 ID","계약 체결일","실제 수주액","금액","신규/기존","입찰/PT 여부","운영 담당자",
    "기업 규모","파트 명","업종","기업집단명","Label","생성년도","생성월","생성분기","체결년도","체결월","체결분기",
    "체결 리드타임","id","고객사 유형","과정포맷(대)","카테고리(대)","peopleId","고객사 담당자명","소속 상위 조직",
    "팀(명함/메일서명)","직급(명함/메일서명)","고객 담당 교육 영역","온라인출강 구분","교육 기간","(온라인)입과 주기",
    "(온라인)최초 입과 여부","수주예정년도","수주예정월","real won","생성일","Net"
]

def fmt_eok(v: float) -> str:
    """표시용 억 단위 포맷: 1자리로 0.0인데 2자리로 0.00 초과면 2자리로."""
    v1 = round(v, 1)
    v2 = round(v, 2)
    if np.isclose(v1, 0.0) and (abs(v2) > 0.0):
        return f"{v2:.2f}"
    return f"{v1:.1f}"

@st.cache_data(show_spinner=False)
def load_base():
    """Won Deal 전체 로드 후 공통 전처리(연/월/금액 숫자화, 상태=Won, 보조 컬럼)."""
    df = load_won_deal().copy()

    # 필수 숫자화
    for c in ["수주예정년도", "수주예정월", "수주 예정액(종합)"]:
        if c not in df.columns:
            st.error(f"필수 컬럼이 없습니다: {c}")
            st.stop()
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # 상태=Won
    if "상태" in df.columns:
        df = df[df["상태"].astype(str).str.strip().str.lower() == "won"]

    # 보조 컬럼 정리
    for col in ["기업명", "과정포맷(대)", "고객사 유형"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype(str).str.strip()

    # 월 범위
    df["수주예정년도"] = df["수주예정년도"].astype("Int64")
    df["수주예정월"] = pd.to_numeric(df["수주예정월"], errors="coerce").astype("Int64")
    df = df[df["수주예정월"].between(1, 12, inclusive="both")]

    # 키/정확 일치용
    df["기업명_key"] = df["기업명"].astype(str)
    df["fmt_exact"] = df["과정포맷(대)"].astype(str).str.strip()
    df["cust_type"] = df["고객사 유형"].astype(str).str.strip()

    # 금액(원)
    df["수주 예정액(종합)"] = df["수주 예정액(종합)"].fillna(0.0).astype(float)

    return df

def month_cols_for(year: int):
    """연도에 맞는 월 컬럼 라벨 생성: YY01 ~ YY12."""
    yy = year % 100
    return [f"{yy:02d}{m:02d}" for m in MONTHS]

def type_mask_fmt_only(df: pd.DataFrame, kind: str) -> pd.Series:
    """
    분류 기준(과정포맷(대)만 사용):
      - '전체': True
      - FMT_LABELS: 과정포맷(대) 정확 일치
      - '미기재': 과정포맷(대) null/빈 문자열만
      - '기타': 위 어떤 라벨에도 해당하지 않으면서 null/빈도 아님
    """
    fmt = df["fmt_exact"]

    if kind == "전체":
        return pd.Series(True, index=df.index)

    if kind in FMT_LABELS:
        return fmt == kind

    if kind == "미기재":
        return fmt.isna() | (fmt == "")

    if kind == "기타":
        is_known = pd.Series(False, index=df.index)
        for lab in FMT_LABELS:
            is_known = is_known | (fmt == lab)
        return (~(fmt.isna() | (fmt == ""))) & (~is_known)

    return pd.Series(False, index=df.index)

def summarize_company(df_c: pd.DataFrame, company: str, year: int) -> pd.DataFrame:
    """
    기업 단위 요약:
      - ROW_ORDER 순으로 행 생성
      - 억 단위 표기(월/연: 기본 1자리 표시, 1자리 0.0/2자리>0.00이면 2자리로 표시)
      - '전체' 제외 0합계 행 숨김(판단 기준: 연 합계를 소수점 **둘째자리**로 계산해 0.00이면 숨김)
    """
    yy_cols = month_cols_for(year)
    rows = []

    for kind in ROW_ORDER:
        m = type_mask_fmt_only(df_c, kind)
        sub = df_c[m].copy()

        if sub.empty:
            monthly_disp = {yy_cols[i]: "0.0" for i in range(12)}
            yearly_numeric = 0.0  # 정렬/판단용
            yearly_disp = "0.0"
        else:
            grp = sub.groupby("수주예정월")["수주 예정액(종합)"].sum()
            monthly_raw = {yy_cols[i]: float(grp.get(mnth, 0.0)) / 1e8 for i, mnth in enumerate(MONTHS)}
            yearly_numeric = sum(monthly_raw.values())  # 숫자(억)
            # 표시 문자열 생성(동적 자릿수)
            monthly_disp = {k: fmt_eok(v) for k, v in monthly_raw.items()}
            yearly_disp = fmt_eok(yearly_numeric)

        # 가시성 판단(‘전체’ 제외): 소수점 2자리 기준
        if kind != "전체" and np.isclose(round(yearly_numeric, 2), 0.0):
            continue

        row = {"기업명": company, "체결액 구분": kind, f"{year}년 체결액 합": yearly_disp}
        row.update(monthly_disp)
        # 정렬용 내부 숫자(‘전체’에서만 값, 나머지는 NaN)
        row["_total_numeric_for_sort"] = yearly_numeric if kind == "전체" else np.nan
        rows.append(row)

    return pd.DataFrame(rows)

@st.cache_data(show_spinner=False)
def build_table(df: pd.DataFrame, year: int):
    yy_cols = month_cols_for(year)
    companies = sorted(df["기업명_key"].dropna().unique().tolist())

    blocks = []
    company_total = {}
    for comp in companies:
        df_c = df[df["기업명_key"] == comp]
        block = summarize_company(df_c, comp, year)
        if block.empty:
            continue
        # 정렬 키: ‘전체’의 내부 숫자 합(억)
        total = float(block.loc[block["체결액 구분"] == "전체", "_total_numeric_for_sort"].sum())
        company_total[comp] = total
        block["_sort_total"] = total
        block["_row_order"] = block["체결액 구분"].map({k: i for i, k in enumerate(ROW_ORDER)})
        blocks.append(block)

    out = pd.concat(blocks, ignore_index=True) if blocks else pd.DataFrame(
        columns=["기업명", "체결액 구분", f"{year}년 체결액 합"] + yy_cols
    )

    if not out.empty:
        out = out.sort_values(by=["_sort_total", "기업명", "_row_order"], ascending=[False, True, True])
        out = out.drop(columns=["_sort_total", "_row_order", "_total_numeric_for_sort"])

    out.insert(0, "No.", range(1, len(out) + 1))
    return out, company_total

# ───────────────────── Sidebar Filters ─────────────────────
st.sidebar.header("필터")
# 1) 고객사 유형 (기본: 기업 고객)
df_base = load_base()
cust_options = ["기업 고객","공공 고객","기타"]
selected_cust = st.sidebar.selectbox("고객사 유형", cust_options, index=0)

# 2) 연도
year = st.sidebar.selectbox("연도", [2023, 2024, 2025], index=2)  # 기본 2025

# 3) 기업명 검색
company_query = st.sidebar.text_input("기업명 검색(정확히 입력)")

# ───────────────────── Build Pivot ─────────────────────
# 고객사 유형 필터 적용
df_base = df_base[df_base["cust_type"] == selected_cust].copy()

df_year = df_base[df_base["수주예정년도"] == year].copy()
table, company_total = build_table(df_year, year)

yy_cols = month_cols_for(year)
st.subheader(f"표 · ({selected_cust}) 기업명 × 체결액 구분 × 월별({yy_cols[0]}~{yy_cols[-1]}) · 단위: 억")
st.dataframe(table, use_container_width=True, hide_index=True)

# ───────────────────── Won Raw Rows (검색/기본) ─────────────────────
st.markdown("---")
st.subheader("Won 딜 원본 행")

raw = df_year.copy()
# 정렬 키(기업별 '전체' 합 내림차순)를 원본 행에도 반영
raw["_sort_total"] = raw["기업명_key"].map(company_total).fillna(0.0)

def show_raw(df_in: pd.DataFrame):
    # 요청한 필드 순서 우선, 없는 컬럼은 자동 제외
    cols = [c for c in DETAIL_COLS_ORDER if c in df_in.columns]
    cols += [c for c in df_in.columns if c not in cols]  # 나머지 뒤에
    st.dataframe(df_in[cols].reset_index(drop=True), use_container_width=True, hide_index=True)

if company_query.strip():
    # 특정 기업만
    raw_show = raw[raw["기업명_key"] == company_query.strip()].copy()
    if raw_show.empty:
        st.info("해당 기업명의 Won 행이 없습니다.")
    else:
        raw_show = raw_show.sort_values(
            ["_sort_total","기업명_key","수주예정월","수주 예정액(종합)"],
            ascending=[False, True, True, False]
        )
        show_raw(raw_show)
else:
    # 전체: 기업명(‘전체’ 합 내림차순) → 기업명 → 수주예정월↑ → 금액↓
    raw_show = raw.sort_values(
        ["_sort_total","기업명_key","수주예정월","수주 예정액(종합)"],
        ascending=[False, True, True, False]
    ).copy()
    show_raw(raw_show)

# ───────────────────── 기업명 검색 시 All Deal 요약 JSON (2024/2025) ─────────────────────
def safe_date_str(s):
    dt = pd.to_datetime(s, errors="coerce")
    return None if pd.isna(dt) else str(dt.date())

def build_company_json_all_deal(company_name: str) -> dict:
    """
    all_deal 기준으로 2024, 2025 데이터를 동시에 JSON으로 반환.
    """
    df_all = load_all_deal().copy()

    # 필요한 컬럼만 안전 확보(없으면 생성)
    needed = [
        "생성 날짜","기업명","이름","담당자_name","상태","성사 가능성","수주 예정일(종합)","수주 예정액(종합)",
        "딜 전환 유형","카테고리(대)","과정포맷(대)","수강시작일","수강종료일","기업 규모","고객사 담당자명",
        "소속 상위 조직","팀(명함/메일서명)","직급(명함/메일서명)","고객 담당 교육 영역","Net","생성년도"
    ]
    for c in needed:
        if c not in df_all.columns:
            df_all[c] = pd.NA

    # 생성년도 보정(없으면 생성 날짜에서 추론)
    if df_all["생성년도"].isna().all():
        # 생성 날짜/생성일에서 추론
        if "생성 날짜" in df_all.columns:
            df_all["생성년도"] = pd.to_datetime(df_all["생성 날짜"], errors="coerce").dt.year
        elif "생성일" in df_all.columns:
            df_all["생성년도"] = pd.to_datetime(df_all["생성일"], errors="coerce").dt.year

    df_all["생성년도"] = pd.to_numeric(df_all["생성년도"], errors="coerce")
    sub = df_all[(df_all["기업명"].astype(str) == company_name) & (df_all["생성년도"].isin([2024, 2025]))].copy()

    # 날짜형 문자열로 정리
    for dcol in ["생성 날짜","수주 예정일(종합)","수강시작일","수강종료일"]:
        sub[dcol] = sub[dcol].apply(safe_date_str)

    # JSON 구성
    def rows_for(year: int):
        ss = sub[sub["생성년도"] == year]
        fields = [
            "생성 날짜","기업명","이름","담당자_name","상태","성사 가능성","수주 예정일(종합)","수주 예정액(종합)",
            "딜 전환 유형","카테고리(대)","과정포맷(대)","수강시작일","수강종료일","기업 규모","고객사 담당자명",
            "소속 상위 조직","팀(명함/메일서명)","직급(명함/메일서명)","고객 담당 교육 영역","Net"
        ]
        # 존재 컬럼만
        fields = [f for f in fields if f in ss.columns]
        recs = ss[fields].to_dict(orient="records")
        return recs

    return {"2024": rows_for(2024), "2025": rows_for(2025)}

# 기업명 검색 시 JSON 출력
if company_query.strip():
    st.markdown("### All Deal 요약 JSON (2024 & 2025)")
    data_json = build_company_json_all_deal(company_query.strip())
    st.code(json.dumps(data_json, ensure_ascii=False, indent=2), language="json")
