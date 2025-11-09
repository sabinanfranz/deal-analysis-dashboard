# pages/99_데이터_품질_체크.py
# ─────────────────────────────────────────────────────────────────────────────
# 팀/개인 필터 + 규칙 기반 데이터 품질 점검 (생성일: 2024-10-01 이후)
# 표시 컬럼 순서: ['생성 날짜','기업명','이름','팀_0_name','담당자_name','상태','성사 가능성',
#                 '수주 예정일','계약 체결일','예상 체결액','금액','수강시작일','수강종료일',
#                 '코스 ID','카테고리','과정포맷']
# R2: 금액은 0 허용(결측=NaN만), 예상 체결액 단독 결측은 미카운트
# R7: 계약 체결일 > 수강시작일 AND (연·월이 다른 경우만 카운트)  ※ 동년·동월이면 노카운트
#     └ 예외 1) 담당자='강진우' & 기업명 ∈ {'홈앤서비스','엔씨소프트','엘지전자'}
#     └ 예외 2) 과정포맷 ∈ {'구독제(온라인)', '선택구매(온라인)'}
# R12: 성사=높음/확정 & (금액·예상 체결액 모두 없음)  ← AND 조건
# '이름'에 '비매출입과' 포함된 딜은 전부 제외
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import numpy as np
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from data import load_all_deal

# ────────── 페이지 설정 ──────────
st.set_page_config(page_title="데이터 품질 점검 (2024-10 이후)", layout="wide")

# ────────── 상수/매핑 ──────────
TODAY = pd.Timestamp(datetime.now(ZoneInfo("Asia/Seoul")).date())
ONLINE_EXEMPT_FORMATS = {"구독제(온라인)", "선택구매(온라인)"}  # R7 예외: 온라인 구독/선택구매

TEAM_RAW = {
    '기업교육 1팀': ['김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연',
                 '강지선','정하영','하승민','이은서','홍제환','김세연','오진선', '박범규'],
    '기업교육 2팀': ['박종협','정선희','권노을','강진우','이윤지','김민선','이수빈','강연정','강다현','방신우',
                    '정다혜','임재우','송승희','손승완','김윤지','손지훈','홍예진', '이현진'],
    '공공사업그룹': ['채선영','황인후','김미송','이준석','김다인'],
}
TEAMS = list(TEAM_RAW.keys())
TEAMS_LABEL = ['전체'] + TEAMS
NAME2TEAM = {re.sub(r'B$', '', n): t for t, lst in TEAM_RAW.items() for n in lst}

DISPLAY_COLS = [
    "생성 날짜","기업명","이름","팀_0_name","담당자_name","상태","성사 가능성",
    "수주 예정일","계약 체결일","예상 체결액","금액","수강시작일","수강종료일",
    "코스 ID","카테고리","과정포맷"
]

# 규칙 라벨
RULE_LABELS = {
    "R1":  "Won & (계약체결일 없음)",
    "R2":  "Won & 금액 없음(금액=0 허용)",
    "R3":  "Won & 수강시작/종료 누락",
    "R4":  "Won & 코스 ID 누락",
    "R5":  "Won & 성사≠확정",
    "R6":  "Lost & 성사≠LOST",
    "R7":  "계약체결일 > 수강시작일 (동년월 제외, 온라인 구독/선택구매 제외)",
    "R8":  "생성 1주↑ & 카테고리 누락",
    "R9":  "생성 1주↑ & 과정포맷 누락",
    "R10": "성사=높음 & 수주예정일 없음",
    "R11": "상태=Convert",
    "R12": "성사=높음/확정 & (금액·예상 체결액 모두 없음)",
}
RULE_CODES = list(RULE_LABELS.keys())

# ────────── 유틸 ──────────
def parse_date(s): return pd.to_datetime(s, errors="coerce")

def to_num(x):
    if pd.isna(x): return np.nan
    try: return float(str(x).replace(",", ""))
    except: return np.nan

def ensure_column(df: pd.DataFrame, dst: str, src_candidates: list, transform=None, default=None):
    if dst in df.columns: return df
    for c in src_candidates:
        if c in df.columns:
            df[dst] = df[c] if transform is None else transform(df[c])
            return df
    df[dst] = default
    return df

def norm_state(x: str) -> str:
    if pd.isna(x): return ""
    t = str(x).strip().lower()
    if t in ["won", "w", "확정"]: return "won"
    if t.startswith("lost") or t in ["lose", "l", "lost/중단"]: return "lost"
    if t in ["convert", "converted"]: return "convert"
    return t

def norm_prob(x: str) -> str:
    if pd.isna(x) or str(x).strip() == "": return "미기재"
    t = str(x).strip().lower()
    if t in ["won","w","확정","confirmed"]: return "확정"
    if t in ["높음","high"]: return "높음"
    if t in ["낮음","low"]: return "낮음"
    if t in ["lost","lose","l"]: return "LOST"
    return str(x).strip()

def missing_str_or_na(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "") | (s.astype(str).str.lower() == "nan")

def missing_num_or_na(s: pd.Series) -> pd.Series:
    # 0은 허용, NaN만 누락
    return s.isna()

# ────────── 데이터 로드/정규화 ──────────
df = load_all_deal().copy()

# 담당자/팀 매핑
df["담당자_name"] = df["담당자_name"].astype(str).str.replace(r"B$", "", regex=True)
df["팀"] = df["담당자_name"].map(NAME2TEAM)

# 3개 팀 외 인원 제외
df = df[df["팀"].isin(TEAMS)].copy()

# "비매출입과" 포함 딜 전부 제외
df = df[~df["이름"].astype(str).str.contains("비매출입과", na=False)].copy()

# 생성 날짜 표준화
if "생성 날짜" in df.columns:
    df["생성_날짜_std"] = parse_date(df["생성 날짜"])
else:
    y = pd.to_numeric(df.get("생성년도"), errors="coerce")
    m = pd.to_numeric(df.get("생성월"), errors="coerce")
    d = pd.to_numeric(df.get("생성일"), errors="coerce").fillna(1)
    df["생성_날짜_std"] = pd.to_datetime(
        dict(year=y.fillna(1900).astype(int), month=m.fillna(1).astype(int), day=d.astype(int)),
        errors="coerce"
    )
# 2024-10-01 이후만
cutoff = pd.Timestamp("2024-10-01")
df = df[df["생성_날짜_std"] >= cutoff].copy()
df["생성 날짜"] = df["생성_날짜_std"].dt.date

# 표준 컬럼 확보 (날짜/문자/숫자)
df = ensure_column(df, "수주 예정일",  ["수주 예정일", "수주 예정일(종합)"], transform=parse_date)
df = ensure_column(df, "계약 체결일",  ["계약 체결일", "계약체결일"],     transform=parse_date)
df = ensure_column(df, "수강시작일",   ["수강시작일"],                     transform=parse_date)
df = ensure_column(df, "수강종료일",   ["수강종료일"],                     transform=parse_date)

df = ensure_column(df, "예상 체결액", ["예상 체결액", "수주 예정액(종합)"], transform=lambda s: s.map(to_num))
df = ensure_column(df, "금액",       ["금액", "Net"],                     transform=lambda s: s.map(to_num))
df = ensure_column(df, "카테고리",   ["카테고리", "카테고리(대)"],         transform=lambda s: s.astype(str).str.strip())
df = ensure_column(df, "과정포맷",   ["과정포맷", "과정포맷(대)"],         transform=lambda s: s.astype(str).str.strip())
df = ensure_column(df, "코스 ID",    ["코스 ID"],                          transform=lambda s: s.astype(str).str.strip())

# 🔧 숫자형 강제 정규화(0 허용, NaN만 결측 취급)
df["예상 체결액"] = pd.to_numeric(df["예상 체결액"].astype(str).str.replace(",", ""), errors="coerce")
df["금액"]       = pd.to_numeric(df["금액"].astype(str).str.replace(",", ""), errors="coerce")

if "팀_0_name" not in df.columns:
    df["팀_0_name"] = df["팀"]

# 상태/성사 표준화
df["상태_norm"] = df["상태"].map(norm_state)
df["성사_norm"] = df["성사 가능성"].map(norm_prob)

# ────────── 규칙 플래그 계산 ──────────
R = {}

# R1: Won & (계약체결일 없음) → 둘 다 없음 포함
R["R1"] = (df["상태_norm"] == "won") & (pd.to_datetime(df["계약 체결일"], errors="coerce").isna())

# R2: Won & 금액 없음(금액 NaN) → 금액이 NaN일 때만(0은 허용)
R["R2"] = (df["상태_norm"] == "won") & (df["금액"].isna())

# R3: Won & 수강시작/종료 누락
R["R3"] = (df["상태_norm"] == "won") & (
    pd.to_datetime(df["수강시작일"], errors="coerce").isna() |
    pd.to_datetime(df["수강종료일"], errors="coerce").isna()
)

R["R4"] = (df["상태_norm"] == "won") & missing_str_or_na(df["코스 ID"])
R["R5"] = (df["상태_norm"] == "won") & (df["성사_norm"] != "확정")
R["R6"] = (df["상태_norm"] == "lost") & (df["성사_norm"] != "LOST")

# ── R7: 계약체결일 > 수강시작일 & (동년·동월이면 제외) + 예외 반영
_contract = pd.to_datetime(df["계약 체결일"], errors="coerce")
_start    = pd.to_datetime(df["수강시작일"], errors="coerce")
mask_both = _contract.notna() & _start.notna()
later_than_start = _contract > _start
same_year_month  = _contract.dt.year.eq(_start.dt.year) & _contract.dt.month.eq(_start.dt.month)
R7_base = mask_both & later_than_start & (~same_year_month)

# 예외 1: 담당자/기업 조합
exc_companies = {'홈앤서비스','엔씨소프트','엘지전자'}
exc_mask_person = (df["담당자_name"].astype(str).str.strip().eq("강진우")) & (
    df["기업명"].astype(str).str.strip().isin(exc_companies)
)
# 예외 2: 과정포맷 온라인 구독/선택구매
fmt = df["과정포맷"].astype(str).str.strip()
exc_mask_format = fmt.isin(ONLINE_EXEMPT_FORMATS)

# 예외 마스크 컬럼 보관(집계/표시 일관성 보장)
df["R7_EXEMPT"] = exc_mask_person | exc_mask_format

# 최종 R7
R["R7"] = R7_base & (~df["R7_EXEMPT"])

R["R8"]  = (TODAY - df["생성_날짜_std"] >= pd.Timedelta(days=7)) & missing_str_or_na(df["카테고리"])
R["R9"]  = (TODAY - df["생성_날짜_std"] >= pd.Timedelta(days=7)) & missing_str_or_na(df["과정포맷"])
R["R10"] = (df["성사_norm"] == "높음") & (pd.to_datetime(df["수주 예정일"], errors="coerce").isna())
R["R11"] = (df["상태_norm"] == "convert")

# R12: 성사=높음/확정 & (금액·예상 체결액 모두 없음)
R["R12"] = df["성사_norm"].isin(["높음","확정"]) & df["금액"].isna() & df["예상 체결액"].isna()

# 각 규칙 컬럼 붙이기
for code, flag in R.items():
    df[code] = flag

# ────────── (신규) 딜 레벨 예외 정의 — 개인/조직 모두 카운트 제외 ──────────
EXCLUDE_BY_OWNER = {
    "김민선": {"신세계백화점_직급별 생성형 AI", "우리은행_WLT II DT 평가과정"},
}

def apply_deal_exclusions(df_in: pd.DataFrame) -> pd.DataFrame:
    """특정 담당자/이름 및 접두어 기반 예외를 적용해 카운트/표시에서 제외."""
    df_out = df_in.copy()

    # 1) 담당자별 특정 이름(정확 일치) 제외
    if {"담당자_name","이름"}.issubset(df_out.columns):
        for owner, names in EXCLUDE_BY_OWNER.items():
            mask = df_out["담당자_name"].astype(str).str.strip().eq(owner) & \
                   df_out["이름"].astype(str).str.strip().isin(names)
            if mask.any():
                df_out = df_out[~mask]

    # 2) (신규) 담당자=김윤지 & 이름 접두어 '현대씨앤알_콘텐츠 임차_' 제외
    if {"담당자_name","이름"}.issubset(df_out.columns):
        mask_prefix = df_out["담당자_name"].astype(str).str.strip().eq("김윤지") & \
                      df_out["이름"].astype(str).str.strip().str.startswith("현대씨앤알_콘텐츠 임차_")
        if mask_prefix.any():
            df_out = df_out[~mask_prefix]

    return df_out

# ────────── UI: 타이틀 & 사이드바 필터 ──────────
st.sidebar.header("필터")
sel_team = st.sidebar.selectbox("팀", TEAMS_LABEL, index=0)

# 팀 기반 개인 풀
if sel_team == "전체":
    person_pool = sorted({n for t, lst in TEAM_RAW.items() for n in lst})
    df_team = df.copy()
else:
    person_pool = TEAM_RAW.get(sel_team, [])
    df_team = df[df["팀"] == sel_team].copy()

sel_person = st.sidebar.selectbox("개인(담당자)", ["전체"] + person_pool, index=0)

# 선택 반영
df_f = df_team if sel_person == "전체" else df_team[df_team["담당자_name"] == sel_person].copy()

# ────────── 개인/조직 공통: 예외를 명시적으로 적용 ──────────
# 개인 화면에서는 상세/카운트 모두 제외, 조직 요약 매트릭스(전체 보기)도 제외
df_f = apply_deal_exclusions(df_f)

# 공통 표시용 DF (항상 이슈코드/설명/이슈수 재계산)
def to_display(df0: pd.DataFrame) -> pd.DataFrame:
    disp = df0.copy()

    # R7 예외 추가 안전 적용(표시용 보정)
    if {"R7","R7_EXEMPT"}.issubset(disp.columns):
        disp["R7"] = disp["R7"] & (~disp["R7_EXEMPT"])

    # 날짜 보정(표시용)
    for c in ["수주 예정일","계약 체결일","수강시작일","수강종료일"]:
        if c in disp.columns:
            disp[c] = pd.to_datetime(disp[c], errors="coerce").dt.date

    # 항상 이슈코드/설명/이슈수 재계산(표에 반영되는 규칙만)
    codes_present = [c for c in RULE_CODES if c in disp.columns]
    def _mk_codes(row):
        codes = [c for c in codes_present if bool(row.get(c, False))]
        labels = [f"{c}:{RULE_LABELS[c]}" for c in codes]
        return pd.Series([", ".join(codes), "; ".join(labels)], index=["이슈코드","이슈설명"])
    extra = disp.apply(_mk_codes, axis=1)
    disp[["이슈코드","이슈설명"]] = extra
    disp["이슈수"] = disp[codes_present].sum(axis=1) if codes_present else 0

    cols = [c for c in DISPLAY_COLS if c in disp.columns] + ["이슈코드","이슈설명","이슈수"]
    disp = disp[cols]
    return disp.sort_values(by=["이슈수","생성 날짜"], ascending=[False, False])

# ────────── 본문
if sel_person == "전체":
    # 팀/조직 단위 요약: 담당자 × 규칙 매트릭스
    st.subheader("담당자 × 규칙 매트릭스")
    if df_f.empty:
        st.info("선택된 조건에 해당하는 데이터가 없습니다.")
    else:
        # 집계 전 R7 예외 안전 적용(이미 반영되어 있지만 보수적으로 한 번 더)
        base_for_count = df_f.copy()
        if {"R7","R7_EXEMPT"}.issubset(base_for_count.columns):
            base_for_count["R7"] = base_for_count["R7"] & (~base_for_count["R7_EXEMPT"])

        pivot = (
            base_for_count
            .groupby("담당자_name")[RULE_CODES]
            .sum()
            .assign(총이슈=lambda x: x.sum(axis=1))
            .sort_values("총이슈", ascending=False)
        )
        st.dataframe(pivot, use_container_width=True)
else:
    # 개인 체크리스트: 위배가 있는 규칙만 노출
    st.subheader(f"담당자: {sel_person} — 개인 체크리스트")

    # 개인 집계용(예외/ R7 EXEMPT 보정 반영)
    base_for_person = df_f.copy()
    if {"R7","R7_EXEMPT"}.issubset(base_for_person.columns):
        base_for_person["R7"] = base_for_person["R7"] & (~base_for_person["R7_EXEMPT"])

    counts = {code: int(base_for_person[base_for_person[code]].shape[0]) for code in RULE_CODES}
    codes_with_issue = [c for c in RULE_CODES if counts[c] > 0]
    codes_with_issue.sort(key=lambda k: counts[k], reverse=True)

    if not codes_with_issue:
        st.success("🎉 현재 선택된 담당자에게는 규칙 위배가 없습니다.")
    else:
        # 상단 요약 메트릭(최대 6개)
        top_show = min(6, len(codes_with_issue))
        cols_metric = st.columns(top_show)
        for col, rc in zip(cols_metric, codes_with_issue[:top_show]):
            col.metric(rc, counts[rc])

        # 위배 있는 규칙만 익스팬더 + 표
        for code in codes_with_issue:
            sub = base_for_person[base_for_person[code]].copy()
            if sub.empty:
                continue
            with st.expander(f"{code} · {RULE_LABELS[code]} — {len(sub)}건", expanded=False):
                st.dataframe(to_display(sub), use_container_width=True, hide_index=True)
