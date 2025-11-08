# pages/22_매출_집계(월별)_사업구분.py
import streamlit as st
import pandas as pd
import numpy as np
import re

from data import load_accounting  # data.py 로더 사용

st.set_page_config(page_title="매출 집계(월별) - 사업 구분 (2024·2025)", layout="wide")
st.title("매출 집계(월별) - 사업 구분 (2024·2025)")
st.caption("단위: 억, 소수점 1자리 · 결측은 0 · ‘사업 구분’은 공백 제거 기준으로 unique · 삼성전자는 배타 처리(전체에만 포함) + 세부 유형/상세 표 · 모든 월 합계(총합) 열 추가")

MONTHS = list(range(1, 13))
MONTH_COLS = [f"{m}월" for m in MONTHS]

# -------------------- 공통 유틸 --------------------
def _to_eok_round(x: pd.Series) -> pd.Series:
    """원→억 변환 후 소수점 1자리 반올림, -0.0은 0.0으로 정리"""
    v = np.round(x.values / 100_000_000.0, 1)
    v[np.isclose(v, 0.0)] = 0.0
    return pd.Series(v, index=x.index)

def _norm(s: str) -> str:
    return re.sub(r"\s+", "", str(s))  # 공백 제거

def _find_course_col(df: pd.DataFrame) -> str | None:
    """교육과정명 컬럼 자동 탐지"""
    candidates = list(df.columns)
    norm_map = {c: _norm(c) for c in candidates}
    # 우선순위
    for pref in ["교육과정명", "과정명", "코스명"]:
        for c in candidates:
            if _norm(pref) in norm_map[c]:
                return c
    # 넓게: '과정'+'명' 포함 또는 '코스' 포함
    for c in candidates:
        n = norm_map[c]
        if ("과정" in n and "명" in n) or ("코스" in n):
            return c
    return None

@st.cache_data(show_spinner=False)
def get_acc():
    """
    data.py 전처리 기준 컬럼:
      - 집계년(Int), 집계월(Int), 사업 구분(str), 계약금액(float), (교육과정명 계열 1개)
    """
    df = load_accounting().copy()

    # 숫자 캐스팅
    for c in ["집계년", "집계월", "계약금액"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["집계년"] = df["집계년"].astype("Int64")
    df["집계월"] = df["집계월"].astype("Int64")

    # '사업 구분' 명칭 정리
    if "사업 구분" not in df.columns and "사업구분" in df.columns:
        df["사업 구분"] = df["사업구분"].astype(str)
    else:
        df["사업 구분"] = df["사업 구분"].astype(str)

    # 공백 제거 키(유형 통합용)
    df["사업 구분 키"] = df["사업 구분"].apply(_norm)

    # 교육과정명 컬럼 탐지
    course_col = _find_course_col(df)

    return df, course_col

def _overall_row_from_grouped(sub: pd.DataFrame, measure: str, label: str) -> pd.DataFrame:
    """월별 그룹합으로 '전체' 1행 생성(항상 생성) — 원단위"""
    by_m = sub.groupby("집계월", dropna=False)[measure].sum()
    by_m = by_m.reindex(MONTHS, fill_value=0.0)
    row = pd.DataFrame([by_m.values], columns=MONTHS)
    row.insert(0, "사업 구분 키", "전체")
    row.insert(1, "항목", label)
    return row

def _special_block_from_subset(sub: pd.DataFrame, label: str) -> pd.DataFrame:
    """특정 라벨(예: 삼성전자 세부 유형)에 대한 [양수 합/음수 합/양수+음수 합] 3행 블록 생성 — 원단위"""
    if sub.empty:
        base = pd.DataFrame({"사업 구분 키": [label, label, label],
                             "항목": ["양수 합", "음수 합", "양수+음수 합"]})
        for m in MONTHS:
            base[m] = 0.0
        return base

    sub = sub.copy()
    def _one(measure: str, item: str) -> pd.DataFrame:
        by_m = sub.groupby("집계월", dropna=False)[measure].sum()
        by_m = by_m.reindex(MONTHS, fill_value=0.0)
        row = pd.DataFrame([by_m.values], columns=MONTHS)
        row.insert(0, "사업 구분 키", label)
        row.insert(1, "항목", item)
        return row

    pos = _one("pos", "양수 합")
    neg = _one("neg", "음수 합")
    net = _one("net", "양수+음수 합")
    return pd.concat([pos, neg, net], ignore_index=True)

def _add_total_column_eok(df_: pd.DataFrame) -> pd.DataFrame:
    """월 컬럼(억 단위로 변환된 상태)을 합산하여 '총합'을 1월 앞에 추가"""
    if df_.empty:
        df_["총합"] = 0.0
        # 재정렬: 총합, 1월~12월
        df_ = df_[["총합"] + [c for c in MONTH_COLS if c in df_.columns]]
        return df_
    # 합계 계산
    df_["총합"] = df_[MONTH_COLS].sum(axis=1)
    # -0.0 정리
    df_["총합"] = df_["총합"].where(~np.isclose(df_["총합"], 0.0), 0.0)
    # 컬럼 순서: 총합, 1~12월
    df_ = df_[["총합"] + MONTH_COLS]
    return df_

def make_year_table(df: pd.DataFrame, year: int, course_col: str | None) -> pd.DataFrame:
    """
    행: (일반 사업 구분 키 × [양수 합, 음수 합, 양수+음수 합])  ← 삼성전자 제외(배타)
        + (삼성전자 세부 3유형 × 동일 3행)                     ← 집계 표에 추가
        + (전체 × 동일 3행)                                   ← 삼성전자 포함(전체에는 포함)
    열: 총합, 1월~12월
    값: 계약금액 합(억, 소수점 1자리) / 결측=0
    """
    sub = df[df["집계년"] == year].copy()

    # 연도 데이터가 없으면 '전체' 3행만 0으로 리턴
    if sub.empty:
        base = pd.DataFrame(
            {"사업 구분 키": ["전체", "전체", "전체"],
             "항목": ["양수 합", "음수 합", "양수+음수 합"]}
        )
        for m in MONTHS:
            base[m] = 0.0
        base = base.rename(columns={m: f"{m}월" for m in MONTHS})
        # 억 변환 + 총합
        out = base.set_index(["사업 구분 키", "항목"])
        for c in MONTH_COLS:
            out[c] = 0.0
        out = _add_total_column_eok(out.assign(**{c: out[c].astype(float) for c in MONTH_COLS}))
        return out.astype("float")

    # 금액 분해(원단위)
    sub["pos"] = sub["계약금액"].where(sub["계약금액"] > 0, 0.0)
    sub["neg"] = sub["계약금액"].where(sub["계약금액"] < 0, 0.0)
    sub["net"] = sub["계약금액"]

    # ── 삼성전자 마스크 생성 ──
    if course_col and course_col in sub.columns:
        s = sub[course_col].astype(str)

        mask_sam_all = s.str.contains("삼성전자", na=False)

        # ✅ 오프라인(출강) 키워드에 'Gen AI 인텐시브' / 'GenAI 인텐시브' 추가
        pattern_offline = r"(Citizen\s*Developer|AI\s*/?\s*Bigdata|Vision\s*Detection|Gen\s*AI\s*인텐시브|GenAI\s*인텐시브)"
        mask_sam_offline = mask_sam_all & s.str.contains(pattern_offline, flags=re.IGNORECASE, regex=True, na=False)

        # 온라인(구독)
        mask_sam_online = mask_sam_all & s.str.contains(r"온라인\s*구독", regex=True, na=False)

        # 신규
        mask_sam_new = mask_sam_all & ~(mask_sam_offline | mask_sam_online)
    else:
        # 교육과정명 컬럼이 없으면 삼성전자 관련은 모두 비어있는 것으로 처리
        mask_sam_all = pd.Series(False, index=sub.index)
        mask_sam_offline = mask_sam_online = mask_sam_new = mask_sam_all

    # ── 배타 처리: 일반 사업 구분 집계에서는 삼성전자 행 제외 ──
    sub_ns = sub[~mask_sam_all].copy()

    # 일반 사업 구분 키 순서(최초 출현 순서)
    order_keys = pd.unique(sub_ns["사업 구분 키"])
    if len(order_keys) > 0:
        sub_ns["사업 구분 키"] = pd.Categorical(sub_ns["사업 구분 키"],
                                              categories=order_keys,
                                              ordered=True)

    # --- 일반 유형(삼성전자 제외) 집계 — 원단위를 월로 피벗 ---
    def _pivot(measure: str, label: str, src: pd.DataFrame) -> pd.DataFrame:
        if src.empty:
            p = pd.DataFrame({"사업 구분 키": [], "항목": []})
            for m in MONTHS:
                p[m] = []
            return p
        p = src.pivot_table(index="사업 구분 키",
                            columns="집계월",
                            values=measure,
                            aggfunc="sum",
                            fill_value=0.0)
        p = p.reindex(columns=MONTHS, fill_value=0.0).reset_index().assign(항목=label)
        return p

    p_pos = _pivot("pos", "양수 합", sub_ns)
    p_neg = _pivot("neg", "음수 합", sub_ns)
    p_net = _pivot("net", "양수+음수 합", sub_ns)
    long = pd.concat([p_pos, p_neg, p_net], ignore_index=True)

    # 각 일반 카테고리마다 [양수, 음수, 양수+음수] 순서
    if len(order_keys) > 0 and not long.empty:
        cat_order  = {cat: i for i, cat in enumerate(order_keys)}
        type_order = {"양수 합": 0, "음수 합": 1, "양수+음수 합": 2}
        long["_co"] = long["사업 구분 키"].map(cat_order)
        long["_to"] = long["항목"].map(type_order)
        long = long.sort_values(by=["_co", "_to"]).drop(columns=["_co", "_to"])

    # --- 삼성전자 세부 3유형 블록(배타 집계) — 원단위 ---
    sam_offline = _special_block_from_subset(sub[mask_sam_offline], "삼성전자 기존 과정 - 출강")
    sam_online  = _special_block_from_subset(sub[mask_sam_online],  "삼성전자 기존 과정 - 온라인")
    sam_new     = _special_block_from_subset(sub[mask_sam_new],     "삼성전자 신규 과정")

    # --- 전체 3행: 전체(sub) 기준(삼성전자 포함) — 원단위 ---
    over_pos = _overall_row_from_grouped(sub, "pos", "양수 합")
    over_neg = _overall_row_from_grouped(sub, "neg", "음수 합")
    over_net = _overall_row_from_grouped(sub, "net", "양수+음수 합")
    overall = pd.concat([over_pos, over_neg, over_net], ignore_index=True)

    # --- 결합(원단위) & 억 단위 변환 + 총합 열 추가 ---
    out = pd.concat([long, sam_offline, sam_online, sam_new, overall], ignore_index=True)

    # 월 컬럼 이름 통일
    out = out.rename(columns={m: f"{m}월" for m in MONTHS})

    # 월 금액 억 변환
    for c in MONTH_COLS:
        if c not in out.columns:
            out[c] = 0.0
        out[c] = _to_eok_round(out[c])

    # 인덱스 설정
    out = out.set_index(["사업 구분 키", "항목"])

    # 🔹 총합 컬럼 추가(억 단위 합산) → 1월 앞에 배치
    out = _add_total_column_eok(out)

    # 컬럼 순서 최종 보장
    out = out[["총합"] + MONTH_COLS]
    return out.astype("float")

# -------------------- UI --------------------
df_acc, course_col = get_acc()

tab24, tab25 = st.tabs(["2024년", "2025년"])

with tab24:
    st.subheader("2024년 · (공백 제거) 사업 구분별 월간 계약금액 합계")
    t24 = make_year_table(df_acc, 2024, course_col)
    st.dataframe(t24.reset_index().rename(columns={"사업 구분 키": "사업 구분(공백제거)"}),
                 use_container_width=True)

    # ── 삼성전자 상세 표(세부 유형별로 각각) ──
    st.markdown("##### 2024년 '삼성전자' 상세 행")
    if course_col and course_col in df_acc.columns:
        sam = df_acc[(df_acc["집계년"] == 2024) &
                     (df_acc[course_col].astype(str).str.contains("삼성전자", na=False))]
        if sam.empty:
            st.info("2024년 '삼성전자' 행이 없습니다.")
        else:
            s = sam[course_col].astype(str)
            pattern_offline = r"(Citizen\s*Developer|AI\s*/?\s*Bigdata|Vision\s*Detection|Gen\s*AI\s*인텐시브|GenAI\s*인텐시브)"
            mask_off = s.str.contains(pattern_offline, flags=re.IGNORECASE, regex=True, na=False)
            mask_on  = s.str.contains(r"온라인\s*구독", regex=True, na=False)

            st.markdown("**삼성전자 기존 과정 - 출강**")
            st.dataframe(sam[mask_off], use_container_width=True)
            st.markdown("**삼성전자 기존 과정 - 온라인**")
            st.dataframe(sam[~mask_off & mask_on], use_container_width=True)
            st.markdown("**삼성전자 신규 과정**")
            st.dataframe(sam[~mask_off & ~mask_on], use_container_width=True)
    else:
        st.info("교육과정명 컬럼을 찾을 수 없어 삼성전자 상세 표를 생성할 수 없습니다.")

with tab25:
    st.subheader("2025년 · (공백 제거) 사업 구분별 월간 계약금액 합계")
    t25 = make_year_table(df_acc, 2025, course_col)
    st.dataframe(t25.reset_index().rename(columns={"사업 구분 키": "사업 구분(공백제거)"}),
                 use_container_width=True)

    # ── 삼성전자 상세 표(세부 유형별로 각각) ──
    st.markdown("##### 2025년 '삼성전자' 상세 행")
    if course_col and course_col in df_acc.columns:
        sam = df_acc[(df_acc["집계년"] == 2025) &
                     (df_acc[course_col].astype(str).str.contains("삼성전자", na=False))]
        if sam.empty:
            st.info("2025년 '삼성전자' 행이 없습니다.")
        else:
            s = sam[course_col].astype(str)
            pattern_offline = r"(Citizen\s*Developer|AI\s*/?\s*Bigdata|Vision\s*Detection|Gen\s*AI\s*인텐시브|GenAI\s*인텐시브)"
            mask_off = s.str.contains(pattern_offline, flags=re.IGNORECASE, regex=True, na=False)
            mask_on  = s.str.contains(r"온라인\s*구독", regex=True, na=False)

            st.markdown("**삼성전자 기존 과정 - 출강**")
            st.dataframe(sam[mask_off], use_container_width=True)
            st.markdown("**삼성전자 기존 과정 - 온라인**")
            st.dataframe(sam[~mask_off & mask_on], use_container_width=True)
            st.markdown("**삼성전자 신규 과정**")
            st.dataframe(sam[~mask_off & ~mask_on], use_container_width=True)
    else:
        st.info("교육과정명 컬럼을 찾을 수 없어 삼성전자 상세 표를 생성할 수 없습니다.")
