# pages/_part_view_base.py
# 공통 베이스 모듈: 팀/파트별 뷰를 한 파일에서 렌더링
# 사용법(래퍼 파일 예시):
#   import streamlit as st
#   from pages._part_view_base import render_part
#   st.set_page_config(page_title="기업 1팀 1파트")
#   render_part("기업교육 1팀", "1파트")

import re
import streamlit as st
import pandas as pd
import numpy as np

from data import load_won_deal, load_retention, load_all_deal
from config import PART_STRUCTURE

# ─────────────────────────────────────────────────────────────────────────────
# 상수/라벨
YEAR = 2025
MONTHS = list(range(1, 13))
MONTH_COLS = [f"{m:02d}" for m in MONTHS]  # '01' ~ '12' 형태

# 상단 Won 표용 포맷 라벨
FMT_LABELS = [
    "출강",
    "복합(출강+온라인)",
    "구독제(온라인)",
    "선택구매(온라인)",
    "포팅",
    "스킬",
]
ROW_ORDER = ["전체", *FMT_LABELS, "기타", "미기재"]

# 생성 기준(출강 전용)에서 사용할 성사 가능성 맵
STAT_MAP = {
    "확정": "확정",
    "높음": "높음",
    "낮음": "낮음",
    "LOW":  "낮음",
    "LOST": "LOST",
    "LOST/중단": "LOST",
}

DETAIL_COLS_ORDER = [
    "생성 날짜", "기업명", "기업 규모", "이름",
    "과정포맷(대)", "카테고리(대)", "담당자_name",
    "상태", "성사 가능성", "수주 예정일(종합)", "수주 예정액(종합)"
]

# ─────────────────────────────────────────────────────────────────────────────
# 유틸
def _norm_name(n: str) -> str:
    return re.sub(r"B$", "", str(n).strip())

def _make_display_detail(df: pd.DataFrame) -> pd.DataFrame:
    """상세 표 컬럼 구성 + 날짜/정리."""
    if df.empty:
        return pd.DataFrame(columns=DETAIL_COLS_ORDER)
    d = df.copy()

    # 생성 날짜 만들기 (없으면 생성년도/월/일 추정)
    if "생성 날짜" not in d.columns:
        y = pd.to_numeric(d.get("생성년도"), errors="coerce")
        m = pd.to_numeric(d.get("생성월"), errors="coerce")
        day = pd.to_numeric(d.get("생성일"), errors="coerce").fillna(1)
        d["생성 날짜"] = pd.to_datetime(
            dict(year=y, month=m, day=day), errors="coerce"
        ).dt.date

    # 수주 예정일(종합) 날짜화(보이는 용도)
    if "수주 예정일(종합)" in d.columns:
        d["수주 예정일(종합)"] = pd.to_datetime(d["수주 예정일(종합)"], errors="coerce").dt.date

    # 담당자 정리
    if "담당자_name" in d.columns:
        d["담당자_name"] = d["담당자_name"].astype(str).map(_norm_name)

    cols = [c for c in DETAIL_COLS_ORDER if c in d.columns]
    out = d[cols].copy()
    return out.reset_index(drop=True)

def _reorder_first_owner(df: pd.DataFrame) -> pd.DataFrame:
    """담당자_name을 맨 앞으로 이동(있을 때만)."""
    if df.empty:
        return df
    cols = list(df.columns)
    if "담당자_name" in cols:
        cols = ["담당자_name"] + [c for c in cols if c != "담당자_name"]
        return df[cols]
    return df

def _format_bucket(fmt_val: str) -> str:
    """과정포맷(대) → 체결 유형 구분 라벨(정확 일치, null→미기재, 그 외→기타)"""
    s = str(fmt_val).strip()
    if s in FMT_LABELS:
        return s
    if s == "" or s.lower() in {"nan", "<na>", "none", "null"}:
        return "미기재"
    return "기타"

# ─────────────────────────────────────────────────────────────────────────────
# 데이터 로더 (캐시)
@st.cache_data(show_spinner=False)
def _load_won_2025():
    """상단(수주예정 기준, Won)용 데이터"""
    won = load_won_deal().copy()
    for c in ["수주예정년도", "수주예정월", "수주 예정액(종합)"]:
        if c in won.columns:
            won[c] = pd.to_numeric(won[c], errors="coerce")
    won["담당자_name"] = won["담당자_name"].astype(str).map(_norm_name)
    won["과정포맷(대)"] = won.get("과정포맷(대)", "").astype(str).str.strip()
    won["기업명"] = won.get("기업명", "").astype(str).str.strip()

    # 상태=Won, 2025 수주예정
    if "상태" in won.columns:
        won = won[won["상태"].astype(str).str.strip().str.lower() == "won"]
    won = won[
        (won["수주예정년도"] == YEAR)
        & (won["수주예정월"].between(1, 12, inclusive="both"))
    ].copy()

    # 리텐션 세트
    ret = load_retention().copy()
    ret_set = set(ret.get("기업명", pd.Series([], dtype=str)).astype(str).str.strip().tolist())
    won["is_retention"] = won["기업명"].isin(ret_set)

    won["수주 예정액(종합)"] = won["수주 예정액(종합)"].fillna(0.0).astype(float)
    return won

@st.cache_data(show_spinner=False)
def _load_all_for_chulgang():
    """하단(생성년도/월 기준)용 데이터(출강 전용 파생에 사용)."""
    df = load_all_deal().copy()
    df["담당자_name"] = df.get("담당자_name", "").astype(str).map(_norm_name)
    df["기업명"] = df.get("기업명", "").astype(str).str.strip()
    df["기업 규모"] = df.get("기업 규모", "").astype(str).str.strip()
    df["과정포맷(대)"] = df.get("과정포맷(대)", "").astype(str).str.strip()
    df["카테고리(대)"] = df.get("카테고리(대)", "").astype(str).str.strip()
    df["성사 가능성"] = df.get("성사 가능성", "").astype(str).str.strip()

    # 숫자화
    df["생성년도"] = pd.to_numeric(df.get("생성년도"), errors="coerce")
    df["생성월"]  = pd.to_numeric(df.get("생성월"),  errors="coerce")
    df["수주 예정액(종합)"] = pd.to_numeric(df.get("수주 예정액(종합)"), errors="coerce").fillna(0.0)

    # 2025 생성, 유효 월
    df = df[
        (df["생성년도"] == YEAR)
        & (df["생성월"].between(1, 12, inclusive="both"))
    ].copy()

    # 리텐션 세트
    ret = load_retention().copy()
    ret_set = set(ret.get("기업명", pd.Series([], dtype=str)).astype(str).str.strip().tolist())
    df["is_retention"] = df["기업명"].isin(ret_set)

    # 상태 맵
    df["status"] = df["성사 가능성"].map(STAT_MAP).fillna("기타")
    return df

@st.cache_data(show_spinner=False)
def _load_all_for_prob(prob_value: str):
    """
    상단 상세용 데이터(생성년도 필터 없음).
    prob_value: '낮음' 또는 '높음'
    """
    df = load_all_deal().copy()
    df["담당자_name"] = df.get("담당자_name", "").astype(str).map(_norm_name)
    df["기업명"]      = df.get("기업명",      "").astype(str).str.strip()
    df["기업 규모"]    = df.get("기업 규모",    "").astype(str).str.strip()
    df["과정포맷(대)"] = df.get("과정포맷(대)", "").astype(str).str.strip()
    df["카테고리(대)"]  = df.get("카테고리(대)",  "").astype(str).str.strip()
    df["성사 가능성"]  = df.get("성사 가능성",  "").astype(str).str.strip()

    if "수주 예정일(종합)" in df.columns:
        df["수주 예정일(종합)"] = pd.to_datetime(df["수주 예정일(종합)"], errors="coerce")

    df = df[df["성사 가능성"] == prob_value].copy()

    ret = load_retention().copy()
    ret_set = set(ret.get("기업명", pd.Series([], dtype=str)).astype(str).str.strip().tolist())
    df["is_retention"] = df["기업명"].isin(ret_set)
    return df

# ─────────────────────────────────────────────────────────────────────────────
# 테이블 빌더
def _build_table_won(df: pd.DataFrame) -> pd.DataFrame:
    """상단 Won 표: ROW_ORDER × (01~12) + '25년 체결액 합' (수주예정 기준, 억 1자리)"""
    if df.empty:
        out = pd.DataFrame({"체결 유형 구분": ROW_ORDER, "25년 체결액 합": [0.0]*len(ROW_ORDER)})
        for col in MONTH_COLS:
            out[col] = 0.0
        return out

    df = df.copy()
    df["bucket"] = df["과정포맷(대)"].map(_format_bucket)

    rows = []
    for kind in ROW_ORDER:
        sub = df if kind == "전체" else df[df["bucket"] == kind]
        grp = sub.groupby("수주예정월")["수주 예정액(종합)"].sum()
        monthly = {f"{m:02d}": grp.get(m, 0.0) for m in MONTHS}
        monthly_eok = {k: round(v/1e8, 1) for k, v in monthly.items()}
        yearly = round(sum(monthly.values())/1e8, 1)
        row = {"체결 유형 구분": kind, "25년 체결액 합": yearly}
        row.update(monthly_eok)
        rows.append(row)

    out = pd.DataFrame(rows)
    for c in ["25년 체결액 합"] + MONTH_COLS:
        out[c] = out[c].astype(float)
        out[c] = out[c].where(~np.isclose(out[c], 0.0), 0.0)
    return out

def _build_table_chulgang_creation(df: pd.DataFrame) -> pd.DataFrame:
    """하단 출강 전용(생성년도/월 기준) 표: 6행 × '01'~'12'"""
    idx_rows = ["전체", "확정+높음", "낮음", "LOST", "체결률(%)", "수주예정액(확정+높음, 억)"]
    rows = []
    for r in idx_rows:
        row_dict = {"항목": r}
        for m in MONTH_COLS:
            if r in ["전체", "확정+높음", "낮음", "LOST"]:
                row_dict[m] = 0
            elif r == "체결률(%)":
                row_dict[m] = "0.0%"
            else:
                row_dict[m] = "0.0"
        rows.append(row_dict)

    if df.empty:
        return pd.DataFrame(rows)[["항목"] + MONTH_COLS]

    d = df.copy()
    d["생성월"] = d["생성월"].astype(int)

    for m in MONTHS:
        col = f"{m:02d}"
        seg = d[d["생성월"] == m]
        tot = int(len(seg))
        rows[0][col] = tot
        if tot > 0:
            win_mask = seg["status"].isin(["확정", "높음"])
            rows[1][col] = int(win_mask.sum())
            rows[2][col] = int((seg["status"] == "낮음").sum())
            rows[3][col] = int((seg["status"] == "LOST").sum())
            rows[4][col] = f"{rows[1][col] / tot * 100:.1f}%"
            amt_eok = seg.loc[win_mask, "수주 예정액(종합)"].sum() / 1e8
            rows[5][col] = f"{amt_eok:.1f}"

    return pd.DataFrame(rows)[["항목"] + MONTH_COLS]

def _apply_compact_layout():
    """메인 컨테이너 좌우 패딩/컴포넌트 간격을 줄여 데이터 영역을 극대화."""
    st.markdown(
        """
        <style>
        .block-container {padding-left: 8px !important; padding-right: 8px !important;}
        [data-testid="stVerticalBlock"] {gap: 0.35rem !important;}
        [data-testid="stHorizontalBlock"] {gap: 0.5rem !important;}
        [data-testid="stTabs"] button {padding-left: 10px !important; padding-right: 10px !important;}
        h1, h2, h3, h4 {margin-top: 0.35rem !important; margin-bottom: 0.35rem !important;}
        [data-testid="stDataFrame"] {margin-top: 0.25rem !important; margin-bottom: 0.25rem !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# 블록 렌더러 (상세/요약)
def _show_prob_details(df_in: pd.DataFrame, title_prefix: str, label: str, members: list[str]):
    """성사 가능성 '낮음'/'높음' 상세(리텐션/신규) — '담당자_name'을 가장 앞으로."""
    df_scope = df_in[df_in["담당자_name"].isin(members)].copy()
    st.markdown(f"### 성사 가능성 '{label}' 상세")
    colL, colR = st.columns(2)
    with colL:
        st.markdown(f"**{title_prefix} · 리텐션 · {label}(생성 기준)**")
        view = _reorder_first_owner(_make_display_detail(df_scope[df_scope["is_retention"]]))
        st.dataframe(view, use_container_width=True, hide_index=True)
    with colR:
        st.markdown(f"**{title_prefix} · 신규 · {label}(생성 기준)**")
        view = _reorder_first_owner(_make_display_detail(df_scope[~df_scope["is_retention"]]))
        st.dataframe(view, use_container_width=True, hide_index=True)

def _show_two_tables_won(df_in: pd.DataFrame, title_prefix: str, members: list[str]):
    """Won(수주예정 기준) 리텐션/신규 두 표 + 상세"""
    df_scope = df_in[df_in["담당자_name"].isin(members)].copy()
    colL, colR = st.columns(2)
    with colL:
        st.markdown(f"#### {title_prefix} · 리텐션 (수주예정 기준)")
        view = df_scope[df_scope["is_retention"]]
        st.dataframe(_build_table_won(view), use_container_width=True, hide_index=True)
        st.markdown("**상세 (리텐션·Won)**")
        st.dataframe(_make_display_detail(view), use_container_width=True, hide_index=True)
    with colR:
        st.markdown(f"#### {title_prefix} · 신규 (수주예정 기준)")
        view = df_scope[~df_scope["is_retention"]]
        st.dataframe(_build_table_won(view), use_container_width=True, hide_index=True)
        st.markdown("**상세 (신규·Won)**")
        st.dataframe(_make_display_detail(view), use_container_width=True, hide_index=True)

def _show_two_tables_chulgang_creation(df_in: pd.DataFrame, title_prefix: str, members: list[str]):
    """출강 전용(생성 기준) 리텐션/신규 두 표 + 상세"""
    df_scope = df_in[df_in["담당자_name"].isin(members)].copy()
    base = df_scope[df_scope["과정포맷(대)"] == "출강"].copy()
    st.markdown("---")
    st.markdown(f"### {title_prefix} · **출강** 전용 (생성년도/월 기준)")
    colL, colR = st.columns(2)
    with colL:
        st.markdown("#### 출강 · 리텐션")
        view = base[base["is_retention"]]
        st.dataframe(_build_table_chulgang_creation(view), use_container_width=True, hide_index=True)
        st.markdown("**상세 (출강·리텐션·생성 기준)**")
        st.dataframe(_make_display_detail(view), use_container_width=True, hide_index=True)
    with colR:
        st.markdown("#### 출강 · 신규")
        view = base[~base["is_retention"]]
        st.dataframe(_build_table_chulgang_creation(view), use_container_width=True, hide_index=True)
        st.markdown("**상세 (출강·신규·생성 기준)**")
        st.dataframe(_make_display_detail(view), use_container_width=True, hide_index=True)

def _show_two_tables_chulgang_creation_ai(df_in: pd.DataFrame, title_prefix: str, members: list[str]):
    """출강 × 생성형 AI 전용(생성 기준) 리텐션/신규 두 표 + 상세"""
    df_scope = df_in[df_in["담당자_name"].isin(members)].copy()
    base = df_scope[(df_scope["과정포맷(대)"] == "출강") & (df_scope["카테고리(대)"] == "생성형 AI")].copy()
    st.markdown("---")
    st.markdown(f"### {title_prefix} · **출강 × 생성형 AI** 전용 (생성년도/월 기준)")
    colL, colR = st.columns(2)
    with colL:
        st.markdown("#### 출강 × 생성형 AI · 리텐션")
        view = base[base["is_retention"]]
        st.dataframe(_build_table_chulgang_creation(view), use_container_width=True, hide_index=True)
        st.markdown("**상세 (출강×생성형 AI·리텐션·생성 기준)**")
        st.dataframe(_make_display_detail(view), use_container_width=True, hide_index=True)
    with colR:
        st.markdown("#### 출강 × 생성형 AI · 신규")
        view = base[~base["is_retention"]]
        st.dataframe(_build_table_chulgang_creation(view), use_container_width=True, hide_index=True)
        st.dataframe(_make_display_detail(view), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────────────────────────
# 진입점
def render_part(team_name: str, part_name: str):
    _apply_compact_layout()  # 좌우 여백 축소

    # 멤버 수집
    members = [ _norm_name(n) for n in PART_STRUCTURE[team_name][part_name] ]

    # 데이터 적재
    won           = _load_won_2025()
    alldeal       = _load_all_for_chulgang()
    alldeal_low   = _load_all_for_prob("낮음")
    alldeal_high  = _load_all_for_prob("높음")

    # ─────────── 상위 탭: ['전체', '낮음높음', <개별 이름들>...] ───────────
    top_tabs = st.tabs(["전체", "낮음높음", *members])

    # (1) 전체 탭: Won / 출강 / 출강×생성형AI
    with top_tabs[0]:
        title_prefix = f"{team_name} {part_name}(전체)"
        _show_two_tables_won(won, title_prefix, members)
        _show_two_tables_chulgang_creation(alldeal, title_prefix, members)
        _show_two_tables_chulgang_creation_ai(alldeal, title_prefix, members)

    # (2) 낮음높음 탭: ‘낮음’ 상세 2표 + ‘높음’ 상세 2표
    with top_tabs[1]:
        title_prefix = f"{team_name} {part_name}(전체)"
        _show_prob_details(alldeal_low,  title_prefix, "낮음", members)
        _show_prob_details(alldeal_high, title_prefix, "높음", members)

    # (3) 개별 이름 탭들: 기존 구성 유지(상단 낮음/높음 상세 → Won → 출강)
    for i, person in enumerate(members, start=2):
        with top_tabs[i]:
            title_prefix = f"{person}"
            _show_prob_details(alldeal_low,  title_prefix, "낮음", [person])
            _show_prob_details(alldeal_high, title_prefix, "높음", [person])
            _show_two_tables_won(won, title_prefix, [person])
            _show_two_tables_chulgang_creation(alldeal, title_prefix, [person])
            # 필요 시 개인별 AI 전용도 가능:
            # _show_two_tables_chulgang_creation_ai(alldeal, title_prefix, [person])
