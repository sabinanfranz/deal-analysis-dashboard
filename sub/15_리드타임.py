# pages/23_수주예정월별_리드타임분포(2025).py
import streamlit as st
import pandas as pd
import numpy as np
import re

from data import load_won_deal  # won deal 로더 (data.py)

st.set_page_config(page_title="수주예정월별 리드타임 분포 (2025)", layout="wide")
st.title("수주예정월별 리드타임(M-0~M-5+) 분포 · 2025")
st.caption("행: 2025년 1~10월(수주예정, 수주예정년도/월) · 열: M-5+, M-4, M-3, M-2, M-1, M-0 · 값: 건수")

TARGET_YEAR = 2025
TARGET_MONTHS = list(range(1, 11))  # 1~10월
BUCKET_ORDER = ["M-5~", "M-4", "M-3", "M-2", "M-1", "M-0"]

def _norm(s: str) -> str:
    """공백 제거/소문자 변환으로 비교 안정화"""
    return re.sub(r"\s+", "", str(s)).lower()

@st.cache_data(show_spinner=False)
def load_and_prepare():
    df = load_won_deal().copy()

    # 필수 컬럼 존재/숫자화
    for col in ["수주예정년도", "수주예정월", "생성년도", "생성월"]:
        if col not in df.columns:
            st.error(f"필수 컬럼이 없습니다: {col}")
            st.stop()
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 유효 월 범위
    df = df[
        df["수주예정년도"].notna()
        & df["수주예정월"].between(1, 12, inclusive="both")
        & df["생성년도"].notna()
        & df["생성월"].between(1, 12, inclusive="both")
    ].copy()

    # 정수 캐스팅
    df["수주예정년도"] = df["수주예정년도"].astype(int)
    df["수주예정월"] = df["수주예정월"].astype(int)
    df["생성년도"] = df["생성년도"].astype(int)
    df["생성월"] = df["생성월"].astype(int)

    # 비교용 정규화 컬럼
    df["기업 규모_norm"] = df.get("기업 규모", "").astype(str).map(_norm)
    df["과정포맷(대)_norm"] = df.get("과정포맷(대)", "").astype(str).map(_norm)
    df["딜 전환 유형_norm"] = df.get("딜 전환 유형", "").fillna("미기재").astype(str).map(_norm)

    return df

def month_diff(to_y, to_m, from_y, from_m) -> int:
    """두 연-월 사이 개월 차이(to - from). 예) 2025-07 vs 2025-03 → 4"""
    return (to_y - from_y) * 12 + (to_m - from_m)

def bucket_from_delta(delta: int) -> str | None:
    """개월 차 → 버킷. 음수(수주 후 생성)는 제외(None)."""
    if delta < 0:
        return None
    if delta == 0:
        return "M-0"
    if delta == 1:
        return "M-1"
    if delta == 2:
        return "M-2"
    if delta == 3:
        return "M-3"
    if delta == 4:
        return "M-4"
    return "M-5~"  # 5개월 이상

def filter_df(df: pd.DataFrame, size_label: str, format_label: str, deal_type_label: str) -> pd.DataFrame:
    """
    size_label: '대기업'
    format_label: '출강' 또는 '구독제(온라인)'
    deal_type_label: '리텐션' 또는 '직접교육문의' (공백 유무 무관)
    """
    size_norm = _norm(size_label)
    deal_norm = _norm(deal_type_label)  # '직접 교육 문의'도 '직접교육문의'로 정규화되어 매칭됨

    # 과정포맷(대) 노멀라이즈(정확 매칭 + 부분 포함 보정)
    fmt_norm = _norm(format_label)
    # '구독제(온라인)'은 데이터마다 표기가 다를 수 있어 구독/온라인 키워드도 허용
    def fmt_match(x: str) -> bool:
        if fmt_norm in x:
            return True
        if "구독" in fmt_norm or "온라인" in fmt_norm:
            return ("구독" in x) or ("온라인" in x)
        if "출강" in fmt_norm:
            return "출강" in x
        return False

    m_size = (df["기업 규모_norm"] == size_norm)
    m_fmt  = df["과정포맷(대)_norm"].apply(fmt_match)
    m_deal = (df["딜 전환 유형_norm"] == deal_norm)

    return df[m_size & m_fmt & m_deal].copy()

def build_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    2025년 1~10월 수주예정 기준으로 M-5~/M-4/.../M-0 분포 표 생성
    """
    sub = df[
        (df["수주예정년도"] == TARGET_YEAR) &
        (df["수주예정월"].isin(TARGET_MONTHS))
    ].copy()

    # 빈 구조라도 표시
    if sub.empty:
        return pd.DataFrame(
            0, index=[f"{TARGET_YEAR}년 {m}월" for m in TARGET_MONTHS],
            columns=BUCKET_ORDER
        )

    # 델타/버킷 계산
    sub["delta"] = month_diff(
        sub["수주예정년도"], sub["수주예정월"],
        sub["생성년도"], sub["생성월"]
    )
    sub["bucket"] = sub["delta"].apply(bucket_from_delta)
    sub = sub[sub["bucket"].notna()].copy()

    # 피벗
    sub["row_label"] = sub["수주예정월"].apply(lambda m: f"{TARGET_YEAR}년 {m}월")
    pivot = (
        sub.pivot_table(index="row_label", columns="bucket", values="수주예정월",
                        aggfunc="count", fill_value=0)
          .reindex(columns=BUCKET_ORDER, fill_value=0)
          .reindex(index=[f"{TARGET_YEAR}년 {m}월" for m in TARGET_MONTHS], fill_value=0)
          .astype("Int64")
    )
    return pivot

# ==================== 실행 영역 ====================
df0 = load_and_prepare()

st.subheader("대기업 × 출강")
colA, colB = st.columns(2)

with colA:
    st.markdown("**딜 전환 유형: 리텐션**")
    t1 = build_table(filter_df(df0, size_label="대기업", format_label="출강", deal_type_label="리텐션"))
    st.dataframe(t1, use_container_width=True)

with colB:
    st.markdown("**딜 전환 유형: 직접교육문의**")
    t2 = build_table(filter_df(df0, size_label="대기업", format_label="출강", deal_type_label="직접교육문의"))
    st.dataframe(t2, use_container_width=True)

st.markdown("---")
st.subheader("대기업 × 구독제(온라인)")
colC, colD = st.columns(2)

with colC:
    st.markdown("**딜 전환 유형: 리텐션**")
    t3 = build_table(filter_df(df0, size_label="대기업", format_label="구독제(온라인)", deal_type_label="리텐션"))
    st.dataframe(t3, use_container_width=True)

with colD:
    st.markdown("**딜 전환 유형: 직접교육문의**")
    t4 = build_table(filter_df(df0, size_label="대기업", format_label="구독제(온라인)", deal_type_label="직접교육문의"))
    st.dataframe(t4, use_container_width=True)
