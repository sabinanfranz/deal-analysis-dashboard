# pages/99_데이터_품질_체크.py
# ─────────────────────────────────────────────────────────────────────────────
# 팀/개인 필터 + 규칙 기반 데이터 품질 점검 (생성일: 2024-10-01 이후)
# 표시 컬럼 순서: ['생성 날짜','기업명','이름','팀_0_name','담당자_name','상태','성사 가능성',
#                 '수주 예정일','계약 체결일','예상 체결액','금액','수강시작일','수강종료일',
#                 '코스 ID','카테고리','과정포맷']
# R2: 금액은 0 허용(결측=NaN만), 예상 체결액 단독 결측은 미카운트
# R7: 계약 체결일 > 수강시작일 AND (연·월이 다른 경우만 카운트)
#     └ 예외 1) 담당자='강진우' & 기업명 ∈ {'홈앤서비스','엔씨소프트','엘지전자'}
#     └ 예외 2) 과정포맷 ∈ {'구독제(온라인)', '선택구매(온라인)'}
# R12: 성사=높음/확정 & (금액·예상 체결액 모두 없음)
# R13: 상태=Won & (소속/팀/직급/교육영역 중 하나라도 없음)
# R14: 상태=Won & (과정포맷 ∈ {구독제(온라인), 선택구매(온라인)}) &
#      ((온라인)입과 주기 또는 (온라인)최초 입과 여부 없음)
# R15: 상태=Won & (과정포맷 ∈ {출강, 복합(출강+온라인), 비대면 실시간}) &
#      (강사 이름1 또는 강사료1 결측)  ← 강사 정보 누락
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
ONLINE_EXEMPT_FORMATS = {"구독제(온라인)", "선택구매(온라인)"}  # R7 예외
LECTURE_FORMATS = {"출강","복합(출강+온라인)","비대면 실시간"}   # R15 대상 포맷
# (예외) 특정 담당자 R13/R15에서 'n월' 키워드 포함 딜 제외
MONTH_KEYWORD_REGEX = r"(?:1[0-2]|[1-9])월"  # 1월~12월
EXEMPT_OWNERS_R13_R15 = {"김정은", "이은서"}

TEAM_RAW = {
    '기업교육 1팀': ['김별','김솔이','황초롱','김정은','김동찬','정태윤','서정연',
                 '강지선','정하영','하승민','이은서','홍제환','김세연','오진선','박범규'],
    '기업교육 2팀': ['박종협','정선희','권노을','강진우','이윤지','김민선','이수빈','강연정','강다현','방신우',
                    '정다혜','임재우','송승희','손승완','김윤지','손지훈','홍예진','이현진'],
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
    "R13": "Won & 고객사 담당자 정보 부재(소속/팀/직급/교육영역)",
    "R14": "Won & (구독/선택 온라인) & 온라인 입과 정보 부재(입과 주기/최초 여부)",
    "R15": "Won & (출강/복합/비대면 실시간) & 강사 정보 누락(강사 이름1/강사료1)",
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

# 문자열화된 결측표현까지 포함
def missing_str_or_na(s: pd.Series) -> pd.Series:
    base_missing = s.isna()
    s_str = s.astype(str).str.strip().str.lower()
    str_missing = s_str.isin({"", "nan", "<na>", "none", "null", "nat"})
    return base_missing | str_missing

def missing_num_or_na(s: pd.Series) -> pd.Series:
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

# 표준 컬럼 확보
df = ensure_column(df, "수주 예정일",  ["수주 예정일", "수주 예정일(종합)"], transform=parse_date)
df = ensure_column(df, "계약 체결일",  ["계약 체결일", "계약체결일"],     transform=parse_date)
df = ensure_column(df, "수강시작일",   ["수강시작일"],                     transform=parse_date)
df = ensure_column(df, "수강종료일",   ["수강종료일"],                     transform=parse_date)
df = ensure_column(df, "예상 체결액", ["예상 체결액", "수주 예정액(종합)"], transform=lambda s: s.map(to_num))
df = ensure_column(df, "금액",       ["금액", "Net"],                     transform=lambda s: s.map(to_num))
df = ensure_column(df, "카테고리",   ["카테고리", "카테고리(대)"],         transform=lambda s: s.astype(str).str.strip())
df = ensure_column(df, "과정포맷",   ["과정포맷", "과정포맷(대)"],         transform=lambda s: s.astype(str).str.strip())
df = ensure_column(df, "코스 ID",    ["코스 ID"],                          transform=lambda s: s.astype(str).str.strip())

# 숫자형 정규화
df["예상 체결액"] = pd.to_numeric(df["예상 체결액"].astype(str).str.replace(",", ""), errors="coerce")
df["금액"]       = pd.to_numeric(df["금액"].astype(str).str.replace(",", ""), errors="coerce")

if "팀_0_name" not in df.columns:
    df["팀_0_name"] = df["팀"]

# 상태/성사 표준화
df["상태_norm"] = df["상태"].map(norm_state)
df["성사_norm"] = df["성사 가능성"].map(norm_prob)

# (R13, R14, R15)에서 사용할 컬럼 확보 — 원본 타입 유지
CONTACT_FIELDS = ["소속 상위 조직", "팀(명함/메일서명)", "직급(명함/메일서명)", "고객 담당 교육 영역", "고객사 담당자명"]
ONLINE_ENROLL_FIELDS = ["(온라인)입과 주기", "(온라인)최초 입과 여부"]
INSTRUCTOR_FIELDS = ["강사 이름1", "강사료1"]
for c in CONTACT_FIELDS + ONLINE_ENROLL_FIELDS + INSTRUCTOR_FIELDS:
    if c not in df.columns:
        df[c] = pd.NA

# ────────── 규칙 플래그 계산 ──────────
R = {}

R["R1"] = (df["상태_norm"] == "won") & (pd.to_datetime(df["계약 체결일"], errors="coerce").isna())
R["R2"] = (df["상태_norm"] == "won") & (df["금액"].isna())
R["R3"] = (df["상태_norm"] == "won") & (
    pd.to_datetime(df["수강시작일"], errors="coerce").isna() |
    pd.to_datetime(df["수강종료일"], errors="coerce").isna()
)
R["R4"] = (df["상태_norm"] == "won") & missing_str_or_na(df["코스 ID"])
R["R5"] = (df["상태_norm"] == "won") & (df["성사_norm"] != "확정")
R["R6"] = (df["상태_norm"] == "lost") & (df["성사_norm"] != "LOST")

# R7
_contract = pd.to_datetime(df["계약 체결일"], errors="coerce")
_start    = pd.to_datetime(df["수강시작일"], errors="coerce")
mask_both = _contract.notna() & _start.notna()
later_than_start = _contract > _start
same_year_month  = _contract.dt.year.eq(_start.dt.year) & _contract.dt.month.eq(_start.dt.month)
R7_base = mask_both & later_than_start & (~same_year_month)
fmt = df["과정포맷"].astype(str).str.strip()
df["R7_EXEMPT"] = (
    (df["담당자_name"].astype(str).str.strip().eq("강진우") &
     df["기업명"].astype(str).str.strip().isin({'홈앤서비스','엔씨소프트','엘지전자'}))
    | fmt.isin(ONLINE_EXEMPT_FORMATS)
)
R["R7"] = R7_base & (~df["R7_EXEMPT"])

R["R8"]  = (TODAY - df["생성_날짜_std"] >= pd.Timedelta(days=7)) & missing_str_or_na(df["카테고리"])
R["R9"]  = (TODAY - df["생성_날짜_std"] >= pd.Timedelta(days=7)) & missing_str_or_na(df["과정포맷"])
R["R10"] = (df["성사_norm"] == "높음") & (pd.to_datetime(df["수주 예정일"], errors="coerce").isna())
R["R11"] = (df["상태_norm"] == "convert")
R["R12"] = df["성사_norm"].isin(["높음","확정"]) & df["금액"].isna() & df["예상 체결액"].isna()

# (예외 마스크) 김정은/이은서: 딜 이름에 'n월' 포함 시 R13/R15에서 제외
name_series = df["이름"].astype(str)
month_kw_in_name = name_series.str.contains(MONTH_KEYWORD_REGEX, regex=True, na=False)
r13r15_exempt_mask = df["담당자_name"].astype(str).str.strip().isin(EXEMPT_OWNERS_R13_R15) & month_kw_in_name

# R13: Won 전제 + 담당자 정보 4항목 중 하나라도 결측
m13 = pd.concat([
    missing_str_or_na(df["소속 상위 조직"]).rename("소속 상위 조직"),
    missing_str_or_na(df["팀(명함/메일서명)"]).rename("팀(명함/메일서명)"),
    missing_str_or_na(df["직급(명함/메일서명)"]).rename("직급(명함/메일서명)"),
    missing_str_or_na(df["고객 담당 교육 영역"]).rename("고객 담당 교육 영역"),
], axis=1)
R["R13"] = (df["상태_norm"] == "won") & m13.any(axis=1) & (~r13r15_exempt_mask)

# R14: Won & {구독제(온라인), 선택구매(온라인)} & 온라인입과 필드 결측
is_online_paid = fmt.isin(ONLINE_EXEMPT_FORMATS)
m14 = pd.concat([
    missing_str_or_na(df["(온라인)입과 주기"]).rename("(온라인)입과 주기"),
    missing_str_or_na(df["(온라인)최초 입과 여부"]).rename("(온라인)최초 입과 여부"),
], axis=1)
R["R14"] = (df["상태_norm"] == "won") & is_online_paid & m14.any(axis=1)

# R15: Won & {출강, 복합(출강+온라인), 비대면 실시간} & (강사 이름1 OR 강사료1 결측)
m15 = missing_str_or_na(df["강사 이름1"]) | missing_str_or_na(df["강사료1"])
R["R15"] = (df["상태_norm"] == "won") & fmt.isin(LECTURE_FORMATS) & m15 & (~r13r15_exempt_mask)

# 규칙 플래그 컬럼 부착
for code, flag in R.items():
    df[code] = flag

# ────────── 예외 제거 ──────────
EXCLUDE_BY_OWNER = {
    "김민선": {"신세계백화점_직급별 생성형 AI", "우리은행_WLT II DT 평가과정"},
}
def apply_deal_exclusions(df_in: pd.DataFrame) -> pd.DataFrame:
    out = df_in.copy()
    if {"담당자_name","이름"}.issubset(out.columns):
        for owner, names in EXCLUDE_BY_OWNER.items():
            mask = out["담당자_name"].astype(str).str.strip().eq(owner) & out["이름"].astype(str).str.strip().isin(names)
            out = out[~mask]
        mask_prefix = out["담당자_name"].astype(str).str.strip().eq("김윤지") & \
                      out["이름"].astype(str).str.strip().str.startswith("현대씨앤알_콘텐츠 임차_")
        out = out[~mask_prefix]
    return out

# ────────── UI: 필터 ──────────
st.sidebar.header("필터")
sel_team = st.sidebar.selectbox("팀", TEAMS_LABEL, index=0)
if sel_team == "전체":
    person_pool = sorted({n for t, lst in TEAM_RAW.items() for n in lst})
    df_team = df.copy()
else:
    person_pool = TEAM_RAW.get(sel_team, [])
    df_team = df[df["팀"] == sel_team].copy()
sel_person = st.sidebar.selectbox("개인(담당자)", ["전체"] + person_pool, index=0)

df_f = df_team if sel_person == "전체" else df_team[df_team["담당자_name"] == sel_person].copy()
df_f = apply_deal_exclusions(df_f)

# ────────── 표시용 빌더 ──────────
def to_display(df0: pd.DataFrame, rule_code: str | None = None, personal: bool = False) -> pd.DataFrame:
    """
    personal=True 이고 rule_code가 R13/R14/R15일 때만,
    '과정포맷' 옆에 추가 필드를 즉시 붙여서 보여줍니다.
      - R13: 기업명, 고객사 담당자명, 소속 상위 조직, 팀(명함/메일서명), 직급(명함/메일서명), 고객 담당 교육 영역
      - R14: (온라인)입과 주기, (온라인)최초 입과 여부
      - R15: 강사 이름1, 강사료1
    중복 컬럼은 기존 위치에서 제거 후 원하는 위치에 재삽입합니다.
    """
    disp = df0.copy()

    # R7 예외 보정
    if {"R7","R7_EXEMPT"}.issubset(disp.columns):
        disp["R7"] = disp["R7"] & (~disp["R7_EXEMPT"])

    # 날짜 표기
    for c in ["수주 예정일","계약 체결일","수강시작일","수강종료일"]:
        if c in disp.columns:
            disp[c] = pd.to_datetime(disp[c], errors="coerce").dt.date

    # 이슈코드/설명/이슈수
    codes_present = [c for c in RULE_CODES if c in disp.columns]
    def _mk_codes(row):
        codes = [c for c in codes_present if bool(row.get(c, False))]
        labels = [f"{c}:{RULE_LABELS[c]}" for c in codes]
        return pd.Series([", ".join(codes), "; ".join(labels)], index=["이슈코드","이슈설명"])
    extra = disp.apply(_mk_codes, axis=1)
    disp[["이슈코드","이슈설명"]] = extra
    disp["이슈수"] = disp[codes_present].sum(axis=1) if codes_present else 0

    # 기본 컬럼
    cols = [c for c in DISPLAY_COLS if c in disp.columns]

    # 개인 화면 + 특정 규칙일 때만, '과정포맷' 다음에 추가 컬럼 삽입
    if personal and rule_code in {"R13","R14","R15"} and "과정포맷" in cols:
        insert_after = cols.index("과정포맷") + 1
        if rule_code == "R13":
            add_cols = [
                c for c in ["기업명","고객사 담당자명",
                            "소속 상위 조직","팀(명함/메일서명)","직급(명함/메일서명)","고객 담당 교육 영역"]
                if c in disp.columns
            ]
        elif rule_code == "R14":
            add_cols = [c for c in ["(온라인)입과 주기","(온라인)최초 입과 여부"] if c in disp.columns]
        else:  # R15
            add_cols = [c for c in ["강사 이름1","강사료1"] if c in disp.columns]

        # 🔧 중복 제거 후 원하는 위치에 재삽입
        cols = [c for c in cols if c not in add_cols]
        for c in add_cols:
            disp[c] = disp[c].astype(str).str.strip()
        cols = cols[:insert_after] + add_cols + cols[insert_after:]

    cols = cols + ["이슈코드","이슈설명","이슈수"]
    disp = disp[cols]
    return disp.sort_values(by=["이슈수","생성 날짜"], ascending=[False, False])

# ────────── 본문 ──────────
if sel_person == "전체":
    st.subheader("담당자 × 규칙 매트릭스")
    if df_f.empty:
        st.info("선택된 조건에 해당하는 데이터가 없습니다.")
    else:
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
    st.subheader(f"담당자: {sel_person} — 개인 체크리스트")
    base_for_person = df_f.copy()
    if {"R7","R7_EXEMPT"}.issubset(base_for_person.columns):
        base_for_person["R7"] = base_for_person["R7"] & (~base_for_person["R7_EXEMPT"])

    counts = {code: int(base_for_person[base_for_person[code]].shape[0]) for code in RULE_CODES}
    codes_with_issue = [c for c in RULE_CODES if counts[c] > 0]
    codes_with_issue.sort(key=lambda k: counts[k], reverse=True)

    if not codes_with_issue:
        st.success("🎉 현재 선택된 담당자에게는 규칙 위배가 없습니다.")
    else:
        top_show = min(6, len(codes_with_issue))
        cols_metric = st.columns(top_show)
        for col, rc in zip(cols_metric, codes_with_issue[:top_show]):
            col.metric(rc, counts[rc])
        for code in codes_with_issue:
            sub = base_for_person[base_for_person[code]].copy()
            if sub.empty:
                continue
            with st.expander(f"{code} · {RULE_LABELS[code]} — {len(sub)}건", expanded=False):
                st.dataframe(to_display(sub, rule_code=code, personal=True),
                             use_container_width=True, hide_index=True)
