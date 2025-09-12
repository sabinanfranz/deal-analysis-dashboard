# pages/97_어카운팅_정합성_체크.py
# ─────────────────────────────────────────────────────────────────────────────
# 목적
# - accounting data 와 won deal 을 코스ID 기준으로 비교/정합성 점검
# - 탭 1: accounting data 내 코스ID 중복 목록(코스ID별 블록: acc 표 + won 표)
# - 탭 2: won deal 내 코스 ID 중복 목록(코스ID별 블록: won 표 + acc 표)
# - 탭 3: (탭1·탭2·탭4에 표시된 won 코스ID 및 사전 제외 ID 제거 후) 정합성 표 5개
#     1) acc-only (단, 코스개강일2·코스 종강일 둘 다 pre-2025면 제외)
#     2) won-only (단, 수강시작일·수강종료일 둘 다 pre-2025면 제외)
#     3) 날짜 불일치 (단, 종료일 둘 다 pre-2025면 제외)
#     4) 금액 불일치 (단, won 종료일이 pre-2025면 제외)
#     5) 완전 일치
# - 탭 4: [Tab① 후보 중] 아래 조건을 만족하는 코스ID를 “정합성 OK(분할=단일)”로 이동 표기
#   · (기존 규칙) acc 중복(2건↑) + won 1건 + acc 모든 행이 won 기간에 포함 + 최장 acc구간 == won 기간 + acc 계약금액 합계 == won 금액(±1원)
#   · (신규 규칙) Tab① 표시용 acc에서 '콜로소 매출 배분' pre-2025 행 제외 후 acc=1건 & won=1건이 남고, 금액/시작/종료가 모두 동일
#
# [유지/추가]
# - EXCLUDE_IDS: 중복 코스ID 중 양쪽 모두 2025-01-01 미만(시작/종료)의 코스ID는 전 탭에서 제외
# - Tab① 표시 전용 추가 제외: won 미일치 & acc 중복행 모두 pre‑2025면 Tab①에서만 숨김
# - accounting '포맷'='캠프' 제외
# - accounting 교육과정명에 "(B2B)[오프라인] & 원데이 클래스" 또는 "(B2B)[매출집계] & 원데이 클래스" 동시 포함 시 제외
# - won 이름에 "(비매출입과)" 또는 "(비매출)" 포함 시 제외
# - 모든 탭에서 won 표에 '이름' 뒤에 '담당자_name', '수주 예정일(종합)' 컬럼을 항상 노출
# - Tab②에서 Accounting rows가 표시된 코스ID는 Tab③의 1) acc-only에서 제외
# - Tab③의 acc-only 계산은 won **유니크가 아닌 전체(won0)** 기준
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import numpy as np

from data import load_won_deal, load_accounting

st.set_page_config(page_title="어카운팅 정합성 체크", layout="wide")

# ────────── 유틸 ──────────
def to_num(s: pd.Series) -> pd.Series:
    if s is None:
        return pd.Series(dtype=float)
    x = (
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace(" ", "", regex=False)
         .str.replace("−", "-", regex=False)  # 특수 하이픈
         .str.strip()
    )
    x = x.replace({"-": np.nan, "": np.nan})
    return pd.to_numeric(x, errors="coerce")

def to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce").dt.date

def normalize_course_id(s: pd.Series) -> pd.Series:
    x = s.astype(str).str.strip()
    x = x.str.replace(r"\.0$", "", regex=True)
    x = x.str.replace(",", "", regex=False)
    x = x.replace({"nan": np.nan, "": np.nan})
    return x

def ensure_col(df: pd.DataFrame, dst: str, candidates: list[str]):
    for c in candidates:
        if c in df.columns:
            if c != dst:
                df[dst] = df[c]
            return
    if dst not in df.columns:
        df[dst] = np.nan

# ────────── 데이터 로드 ──────────
acc_raw = load_accounting().copy()
won_raw = load_won_deal().copy()

# ────────── 표준화 (Accounting) ──────────
ensure_col(acc_raw, "코스ID",       ["코스ID"])
ensure_col(acc_raw, "교육과정명",   ["교육과정명"])
ensure_col(acc_raw, "사업 구분",    ["사업 구분","사업구분"])
ensure_col(acc_raw, "포맷",         ["포맷"])
ensure_col(acc_raw, "계약금액",     ["계약금액"])
ensure_col(acc_raw, "코스개강일2",  ["코스개강일2","코스 개강일2","코스 개강일"])
ensure_col(acc_raw, "코스 종강일",  ["코스 종강일","코스종강일"])

acc0 = acc_raw.copy()
acc0["코스ID"]      = normalize_course_id(acc0["코스ID"])
acc0["계약금액"]     = to_num(acc0["계약금액"])
acc0["코스개강일2"]  = to_date(acc0["코스개강일2"])
acc0["코스 종강일"]  = to_date(acc0["코스 종강일"])

# 회계 '포맷' = '캠프' 제외
acc0 = acc0[~acc0["포맷"].astype(str).str.strip().eq("캠프")].copy()

# 교육과정명 복합 제외 조건
course_name = acc0["교육과정명"].astype(str)
cond_offline = course_name.str.contains(r"\(B2B\)\[오프라인\]", na=False)
cond_agg     = course_name.str.contains(r"\(B2B\)\[매출집계\]", na=False)
cond_oneday  = course_name.str.contains("원데이 클래스", na=False)
acc0 = acc0[~((cond_offline & cond_oneday) | (cond_agg & cond_oneday))].copy()

# ────────── 표준화 (Won) ──────────
ensure_col(won_raw, "코스ID",            ["코스 ID","코스ID"])
ensure_col(won_raw, "이름",              ["이름","기업명"])
ensure_col(won_raw, "담당자_name",       ["담당자_name"])
ensure_col(won_raw, "수주 예정일(종합)", ["수주 예정일(종합)","수주 예정일"])
ensure_col(won_raw, "금액",              ["금액","Net"])
ensure_col(won_raw, "수강시작일",        ["수강시작일"])
ensure_col(won_raw, "수강종료일",        ["수강종료일"])
ensure_col(won_raw, "id",                ["id","Deal ID","레코드ID","record_id"])

won0 = won_raw.copy()
won0["코스ID"]            = normalize_course_id(won0["코스ID"])
won0["금액"]              = to_num(won0["금액"])
won0["수강시작일"]         = to_date(won0["수강시작일"])
won0["수강종료일"]         = to_date(won0["수강종료일"])
won0["수주 예정일(종합)"]   = to_date(won0["수주 예정일(종합)"])
won0["id"]                = won0["id"].astype(str)

# won 이름에 "(비매출입과)" 또는 "(비매출)" 포함 시 제외
won_name = won0["이름"].astype(str)
won0 = won0[~won_name.str.contains(r"\(비매출입과\)|\(비매출\)", na=False)].copy()

# ────────── 결측 코스ID 제거(양쪽) ──────────
acc0 = acc0[acc0["코스ID"].notna()].copy()
won0 = won0[won0["코스ID"].notna()].copy()

# ────────── 사전 제외 집합(EXCLUDE_IDS) 산출 ──────────
CUTOFF = pd.Timestamp("2025-01-01")

def _all_pre2025(df: pd.DataFrame, cid: str, start_col: str, end_col: str) -> bool:
    sub = df[df["코스ID"] == cid]
    if sub.empty:
        return False
    ok = sub[start_col].notna() & sub[end_col].notna()
    if not ok.any():
        return False
    s = pd.to_datetime(sub.loc[ok, start_col])
    e = pd.to_datetime(sub.loc[ok, end_col])
    return bool((s < CUTOFF).all() and (e < CUTOFF).all())

# 원본(acc0, won0)에서 중복 ID 파악
acc_dup_ids0 = set(acc0.groupby("코스ID").size()[lambda s: s > 1].index)
won_dup_ids0 = set(won0.groupby("코스ID").size()[lambda s: s > 1].index)
acc_ids0     = set(acc0["코스ID"].unique())
won_ids0     = set(won0["코스ID"].unique())

EXCLUDE_IDS = set()

# 1) accounting 중복 + won에도 존재 + 양쪽 날짜 모두 pre-2025 → 제외
for cid in (acc_dup_ids0 & won_ids0):
    if _all_pre2025(acc0, cid, "코스개강일2", "코스 종강일") and _all_pre2025(won0, cid, "수강시작일", "수강종료일"):
        EXCLUDE_IDS.add(cid)

# 2) won 중복 + accounting에도 존재 + 양쪽 날짜 모두 pre-2025 → 제외
for cid in (won_dup_ids0 & acc_ids0):
    if _all_pre2025(won0, cid, "수강시작일", "수강종료일") and _all_pre2025(acc0, cid, "코스개강일2", "코스 종강일"):
        EXCLUDE_IDS.add(cid)

# 사전 제외 반영(전 탭 공통)
if EXCLUDE_IDS:
    acc0 = acc0[~acc0["코스ID"].isin(EXCLUDE_IDS)].copy()
    won0 = won0[~won0["코스ID"].isin(EXCLUDE_IDS)].copy()

# ────────── 이후 로직(사전 제외 후 데이터 기준) ──────────
# 중복/유니크 분류
acc_cnt = acc0.groupby("코스ID").size()
won_cnt = won0.groupby("코스ID").size()

acc_unique_ids = set(acc_cnt[acc_cnt == 1].index)
acc_dup_ids    = set(acc_cnt[acc_cnt > 1].index)
won_unique_ids = set(won_cnt[won_cnt == 1].index)
won_dup_ids    = set(won_cnt[won_cnt > 1].index)

acc_unique   = acc0[acc0["코스ID"].isin(acc_unique_ids)].copy()
won_unique   = won0[won0["코스ID"].isin(won_unique_ids)].copy()
acc_dups_all = acc0[acc0["코스ID"].isin(acc_dup_ids)].copy().sort_values(["코스ID","코스개강일2","코스 종강일"])
won_dups_all = won0[won0["코스ID"].isin(won_dup_ids)].copy().sort_values(["코스ID","수강시작일","수강종료일"])

# Tab① 표시 전용 추가 제외: won 미일치 & acc 중복행 모두 pre‑2025면 Tab① 숨김
acc_dup_ids_display = []
for cid in sorted(acc_dup_ids):
    won_has = cid in won0["코스ID"].values
    if (not won_has) and _all_pre2025(acc0, cid, "코스개강일2", "코스 종강일"):
        continue  # Tab①에서만 제외
    acc_dup_ids_display.append(cid)
acc_dups_tab1_all = (
    acc_dups_all[acc_dups_all["코스ID"].isin(acc_dup_ids_display)]
    .copy()
    .sort_values(["코스ID","코스개강일2","코스 종강일"])
)

# ────────── 보조 유틸: Tab① 표시용 acc에서 '콜로소 매출 배분' pre-2025 행 제외
def _filter_acc_kmb_pre2025(acc_rows: pd.DataFrame) -> pd.DataFrame:
    if acc_rows.empty:
        return acc_rows
    s = pd.to_datetime(acc_rows["코스개강일2"], errors="coerce")
    e = pd.to_datetime(acc_rows["코스 종강일"], errors="coerce")
    is_kmb = acc_rows["사업 구분"].astype(str).str.strip().eq("콜로소 매출 배분")
    excl = is_kmb & s.notna() & e.notna() & (s < CUTOFF) & (e < CUTOFF)
    return acc_rows.loc[~excl].copy()

# ────────── Tab④ 후보 식별
# (A) 기존 규칙: 최장구간 포함 + 합계금액=Won(±1)
def _longest_interval(acc_rows: pd.DataFrame):
    valid = acc_rows["코스개강일2"].notna() & acc_rows["코스 종강일"].notna()
    if not valid.any():
        return None, None, None
    s = pd.to_datetime(acc_rows.loc[valid, "코스개강일2"])
    e = pd.to_datetime(acc_rows.loc[valid, "코스 종강일"])
    dur = (e - s).dt.days
    imax = dur.idxmax()
    return imax, s.loc[imax], e.loc[imax]

def _covers_all(acc_rows: pd.DataFrame, S_won: pd.Timestamp, E_won: pd.Timestamp) -> bool:
    valid = acc_rows["코스개강일2"].notna() & acc_rows["코스 종강일"].notna()
    if not valid.any():
        return False
    s = pd.to_datetime(acc_rows.loc[valid, "코스개강일2"])
    e = pd.to_datetime(acc_rows.loc[valid, "코스 종강일"])
    return bool((s >= S_won).all() & (e <= E_won).all())

tab4_ids_long = set()
for cid in sorted(acc_dups_tab1_all["코스ID"].dropna().unique()):
    acc_rows = acc0[acc0["코스ID"] == cid].copy()
    won_rows = won0[won0["코스ID"] == cid].copy()
    if acc_rows.empty or won_rows.shape[0] != 1:
        continue
    idx, S_max, E_max = _longest_interval(acc_rows)
    if S_max is None or E_max is None:
        continue
    S_won = pd.to_datetime(won_rows["수강시작일"].iloc[0], errors="coerce")
    E_won = pd.to_datetime(won_rows["수강종료일"].iloc[0], errors="coerce")
    if pd.isna(S_won) or pd.isna(E_won):
        continue
    if not _covers_all(acc_rows, S_won, E_won):
        continue
    if (S_won != S_max) or (E_won != E_max):
        continue
    amt_acc = to_num(acc_rows["계약금액"]).sum()
    amt_won = float(to_num(won_rows["금액"]).iloc[0] or 0)
    if pd.isna(amt_won):
        continue
    if abs(amt_acc - amt_won) <= 1.0:
        tab4_ids_long.add(cid)

# (B) 신규 규칙: '콜로소 매출 배분' pre-2025 제외 후 acc=1 & won=1, 금액/시작/종료 동일
tab4_ids_simple = set()
for cid in sorted(acc_dups_tab1_all["코스ID"].dropna().unique()):
    acc_rows_full = acc_dups_tab1_all[acc_dups_tab1_all["코스ID"] == cid][
        ["코스ID","교육과정명","사업 구분","포맷","계약금액","코스개강일2","코스 종강일"]
    ].copy()
    won_rows = won0[won0["코스ID"] == cid].copy()
    if acc_rows_full.empty or won_rows.empty:
        continue

    # 표시용 acc에서 '콜로소 매출 배분' pre-2025 제외
    acc_rows_after = _filter_acc_kmb_pre2025(acc_rows_full)

    # 신규 이동 조건
    if (acc_rows_after.shape[0] == 1) and (won_rows.shape[0] == 1):
        ar = acc_rows_after.iloc[0]
        wr = won_rows.iloc[0]
        # 금액/날짜 동일성 체크 (금액은 실수 오차 방지용 근사 비교)
        amt_equal = (pd.notna(ar["계약금액"]) and pd.notna(wr["금액"]) and abs(float(ar["계약금액"]) - float(wr["금액"])) <= 1e-6)
        s_equal = (pd.to_datetime(ar["코스개강일2"], errors="coerce") == pd.to_datetime(wr["수강시작일"], errors="coerce"))
        e_equal = (pd.to_datetime(ar["코스 종강일"], errors="coerce") == pd.to_datetime(wr["수강종료일"], errors="coerce"))
        if amt_equal and s_equal and e_equal:
            tab4_ids_simple.add(cid)

# Tab④ 최종 후보 = (A)기존 규칙 ∪ (B)신규 규칙
tab4_ids_all = tab4_ids_long | tab4_ids_simple

# Tab① 최종 노출용: Tab④로 이동하는 코스ID는 Tab①에서 제거
acc_dups_tab1 = acc_dups_tab1_all[~acc_dups_tab1_all["코스ID"].isin(tab4_ids_all)].copy()

# ────────── 상단 안내(사전 제외 목록만) ──────────
st.title("어카운팅 정합성 체크")
if EXCLUDE_IDS:
    with st.expander(f"사전 제외된 코스ID(중복 & 양쪽 날짜 모두 2025-01-01 미만) — {len(EXCLUDE_IDS)}개", expanded=False):
        st.write(sorted(EXCLUDE_IDS))

# ────────── 탭 구성 ──────────
tab1, tab2, tab3, tab4 = st.tabs([
    "① accounting 중복(코스ID별 2건↑)",
    "② won deal 중복(코스ID별 2건↑)",
    "③ 정합성 체크 (유니크 ID만)",
    "④ 정합성 OK (Acc 분할 합계 = Won 단일)"
])

# ───────────────────────────
# Tab 1: 코스ID별 블록 (acc 표 + won 표). 이후 이 탭에 노출된 won 코스ID는 Tab2·Tab3에서 제외
# ───────────────────────────
with tab1:
    st.caption("accounting data에서 코스ID가 여러 개인 경우 (※ won 미일치 & 전부 pre-2025 중복 ID는 숨김 처리, 포맷=캠프 제외, Tab④ 이동 ID 제외)")
    tab1_won_ids = set()
    if acc_dups_tab1.empty:
        st.info("표시할 accounting 중복 행이 없습니다.")
    else:
        for cid in acc_dups_tab1["코스ID"].dropna().unique():
            st.markdown(f"### 코스 ID: `{cid}`")
            acc_rows = acc_dups_tab1[acc_dups_tab1["코스ID"] == cid][
                ["코스ID","교육과정명","사업 구분","포맷","계약금액","코스개강일2","코스 종강일"]
            ].copy()
            # 표시용: '콜로소 매출 배분' pre-2025 행 제외
            acc_rows_disp = _filter_acc_kmb_pre2025(acc_rows)

            st.markdown("**Accounting rows**")
            st.dataframe(acc_rows_disp, use_container_width=True, hide_index=True)

            won_rows = won0[won0["코스ID"] == cid].copy()
            if won_rows.empty:
                st.markdown("**Won rows** — *won deal row 부재*")
            else:
                cols_won = ["코스ID","이름","담당자_name","수주 예정일(종합)","금액","수강시작일","수강종료일"]
                if "id" in won_rows.columns:
                    cols_won += ["id"]
                st.markdown("**Won rows**")
                st.dataframe(won_rows[cols_won].sort_values(["코스ID","수강시작일"]), use_container_width=True, hide_index=True)
                tab1_won_ids.add(cid)

# ───────────────────────────
# Tab 2: won 중복 — 코스ID별 블록 (won 표 + acc 표).
#        Tab①에서 이미 노출된 won 코스ID 제외. (Tab④는 won=1건이라 원칙상 영향 없음)
#        이 탭에 "Accounting rows"가 표시된 코스ID는 Tab③의 acc-only에서 제외.
# ───────────────────────────
with tab2:
    st.caption("won deal에서 코스ID가 여러 개인 경우 (※ Tab①에서 노출된 won 코스ID 제외)")
    won_dups_disp = won_dups_all[~won_dups_all["코스ID"].isin(tab1_won_ids)].copy()
    tab2_won_ids = set()
    tab2_acc_shown_ids = set()

    if won_dups_disp.empty:
        st.info("표시할 won deal 중복 행이 없습니다.")
    else:
        for cid in won_dups_disp["코스ID"].dropna().unique():
            st.markdown(f"### 코스 ID: `{cid}`")
            # Won rows (필수)
            won_rows = won_dups_disp[won_dups_disp["코스ID"] == cid].copy()
            cols_won = ["코스ID","이름","담당자_name","수주 예정일(종합)","금액","수강시작일","수강종료일"]
            if "id" in won_rows.columns:
                cols_won += ["id"]
            st.markdown("**Won rows**")
            st.dataframe(won_rows[cols_won].sort_values(["코스ID","수강시작일"]), use_container_width=True, hide_index=True)
            tab2_won_ids.add(cid)

            # Accounting rows (있으면 표시, 없으면 안내)
            acc_rows = acc0[acc0["코스ID"] == cid][
                ["코스ID","교육과정명","사업 구분","포맷","계약금액","코스개강일2","코스 종강일"]
            ].copy()
            if acc_rows.empty:
                st.markdown("**Accounting rows** — *accounting row 부재*")
            else:
                st.markdown("**Accounting rows**")
                st.dataframe(acc_rows.sort_values(["코스ID","코스개강일2"]), use_container_width=True, hide_index=True)
                tab2_acc_shown_ids.add(cid)

# ───────────────────────────
# Tab 4: 정합성 OK (Acc 분할 합계 = Won 단일) — 기존 규칙 ∪ 신규 규칙
#        (Tab③에서는 이 코스ID도 won 제외 집합에 더해 제외 처리)
# ───────────────────────────
with tab4:
    st.caption("Tab①의 accounting 중복 코스ID 중, (1) 분할합계=Won 단일 또는 (2) '콜로소 매출 배분' pre-2025 제외 후 단일=단일 완전일치 케이스")
    tab4_won_ids = set()
    if not tab4_ids_all:
        st.info("이동할 코스ID가 없습니다.")
    else:
        for cid in sorted(tab4_ids_all):
            st.markdown(f"### 코스 ID: `{cid}`")
            if cid in tab4_ids_simple:
                # 신규 규칙 케이스: 표시용 acc는 필터 적용 후의 1행을 보여줌
                acc_rows_all = acc0[acc0["코스ID"] == cid][
                    ["코스ID","교육과정명","사업 구분","포맷","계약금액","코스개강일2","코스 종강일"]
                ].copy()
                acc_rows_disp = _filter_acc_kmb_pre2025(acc_rows_all)
                won_rows = won0[won0["코스ID"] == cid].copy()

                st.markdown("**Accounting row (필터 적용 후 단일 & Won과 완전 일치)**")
                st.dataframe(acc_rows_disp.sort_values(["코스ID","코스개강일2","코스 종강일"]),
                             use_container_width=True, hide_index=True)

                st.markdown("**Won row (단일)**")
                cols_won = ["코스ID","이름","담당자_name","수주 예정일(종합)","금액","수강시작일","수강종료일"]
                if "id" in won_rows.columns:
                    cols_won += ["id"]
                st.dataframe(won_rows[cols_won],
                             use_container_width=True, hide_index=True)
                tab4_won_ids.add(cid)
            else:
                # 기존 규칙 케이스: acc 전체를 보여줌(분할 합계 = Won)
                acc_rows = acc0[acc0["코스ID"] == cid][
                    ["코스ID","교육과정명","사업 구분","포맷","계약금액","코스개강일2","코스 종강일"]
                ].copy()
                won_rows = won0[won0["코스ID"] == cid].copy()

                st.markdown("**Accounting rows (합계 금액 = Won 금액)**")
                st.dataframe(acc_rows.sort_values(["코스ID","코스개강일2","코스 종강일"]),
                             use_container_width=True, hide_index=True)

                st.markdown("**Won row (단일)**")
                cols_won = ["코스ID","이름","담당자_name","수주 예정일(종합)","금액","수강시작일","수강종료일"]
                if "id" in won_rows.columns:
                    cols_won += ["id"]
                st.dataframe(won_rows[cols_won],
                             use_container_width=True, hide_index=True)
                tab4_won_ids.add(cid)

# 탭3에서 제외할 won 코스ID = Tab① 노출 ∪ Tab② 노출 ∪ Tab④ 이동
tab1_won_ids = tab1_won_ids if 'tab1_won_ids' in locals() else set()
tab2_won_ids = tab2_won_ids if 'tab2_won_ids' in locals() else set()
tab4_won_ids = tab4_won_ids if 'tab4_won_ids' in locals() else set()
won_ids_exclude_for_tab3 = tab1_won_ids | tab2_won_ids | tab4_won_ids

# ✅ Tab③의 acc-only에서 추가로 제외할 코스ID = “Tab②에서 Accounting rows를 표시했던 코스ID”
tab2_acc_shown_ids = tab2_acc_shown_ids if 'tab2_acc_shown_ids' in locals() else set()

# ───────────────────────────
# Tab 3: 정합성 체크 (유니크 ID만) — Tab①/②/④ 노출 won 코스ID 제외 + pre-2025 제외 조건 반영
# ───────────────────────────
with tab3:
    st.info("※ 아래 모든 표는 Tab①·Tab②·Tab④ 중복/특수 케이스 및 사전 제외 코스ID를 제거한 뒤, 코스ID가 유니크한 행만 대상으로 계산합니다. 또한 accounting의 포맷=캠프 행은 전 구간 제외됩니다.")

    # Tab①/②/④에서 노출된 won 코스ID 제외 후 유니크 집합 재정의
    acc_u = acc_unique.copy()
    won_u = won_unique[~won_unique["코스ID"].isin(won_ids_exclude_for_tab3)].copy()

    acc_u_ids = set(acc_u["코스ID"])
    won_u_ids = set(won_u["코스ID"])

    # acc-only: won 전체(won0) 기준 + Tab②에서 acc rows 보인 코스ID 제외
    won_all_ids = set(won0["코스ID"])
    acc_only_ids = sorted(list((acc_u_ids - won_all_ids) - tab2_acc_shown_ids))
    acc_only = acc_u[acc_u["코스ID"].isin(acc_only_ids)].copy()

    # (부가 필터) 코스개강일2·코스 종강일 둘 다 pre-2025면 제외
    if not acc_only.empty:
        acc_start = pd.to_datetime(acc_only["코스개강일2"], errors="coerce")
        acc_end   = pd.to_datetime(acc_only["코스 종강일"], errors="coerce")
        both_pre  = acc_start.notna() & acc_end.notna() & (acc_start < CUTOFF) & (acc_end < CUTOFF)
        acc_only  = acc_only[~both_pre].copy()
    acc_only = acc_only.sort_values("코스ID")

    st.subheader("1) accounting data에는 있는데 won deal에는 없는 코스ID")
    st.dataframe(
        acc_only[["코스ID","교육과정명","사업 구분","포맷","계약금액","코스개강일2","코스 종강일"]],
        use_container_width=True, hide_index=True
    )

    # 2) won-only (수강시작일·수강종료일 둘 다 pre-2025는 제외)
    won_only_ids = sorted(list(won_u_ids - set(acc0["코스ID"])))
    won_only = won_u[won_u["코스ID"].isin(won_only_ids)].copy()
    if not won_only.empty:
        w_start = pd.to_datetime(won_only["수강시작일"], errors="coerce")
        w_end   = pd.to_datetime(won_only["수강종료일"], errors="coerce")
        both_pre_w = w_start.notna() & w_end.notna() & (w_start < CUTOFF) & (w_end < CUTOFF)
        won_only   = won_only[~both_pre_w].copy()
    won_only = won_only.sort_values("코스ID")

    st.subheader("2) won deal에는 있는데 accounting data에는 없는 코스ID")
    cols_won_only = ["코스ID","이름","담당자_name","수주 예정일(종합)","금액","수강시작일","수강종료일"]
    if "id" in won_only.columns:
        cols_won_only += ["id"]
    st.dataframe(
        won_only[cols_won_only],
        use_container_width=True, hide_index=True
    )

    # 3) 날짜 불일치 — 유니크 간 inner join (종료일 둘 다 pre-2025는 제외)
    join_cols_acc = ["코스ID","코스개강일2","코스 종강일","계약금액","교육과정명","사업 구분","포맷"]
    join_cols_won = ["코스ID","수강시작일","수강종료일","금액","이름","담당자_name","수주 예정일(종합)","id"] if "id" in won_u.columns else \
                    ["코스ID","수강시작일","수강종료일","금액","이름","담당자_name","수주 예정일(종합)"]

    inner = pd.merge(
        won_u[join_cols_won], acc_u[join_cols_acc],
        on="코스ID", how="inner", suffixes=("_won","_acc")
    )

    both_start_ok = inner["수강시작일"].notna() & inner["코스개강일2"].notna()
    both_end_ok   = inner["수강종료일"].notna() & inner["코스 종강일"].notna()

    start_diff_days = (pd.to_datetime(inner["수강시작일"]) - pd.to_datetime(inner["코스개강일2"])).dt.days.where(both_start_ok, np.nan)
    end_diff_days   = (pd.to_datetime(inner["수강종료일"]) - pd.to_datetime(inner["코스 종강일"])).dt.days.where(both_end_ok,   np.nan)

    start_err = (both_start_ok) & (start_diff_days.fillna(0) != 0)
    end_err   = (both_end_ok)   & (end_diff_days.fillna(0)   != 0)
    any_err   = start_err | end_err

    # 종료일 둘 다 pre-2025 필터
    won_end_ts = pd.to_datetime(inner["수강종료일"], errors="coerce")
    acc_end_ts = pd.to_datetime(inner["코스 종강일"], errors="coerce")
    end_both_pre = won_end_ts.notna() & acc_end_ts.notna() & (won_end_ts < CUTOFF) & (acc_end_ts < CUTOFF)

    keep_mask = any_err & (~end_both_pre)
    mism_date = inner[keep_mask].copy()

    st.subheader("3) 날짜 불일치 (코스개강일2 ≠ 수강시작일 또는 코스 종강일 ≠ 수강종료일)")
    cols3 = ["코스ID","이름","담당자_name","수주 예정일(종합)","금액",
         "수강시작일","수강종료일","코스개강일2","코스 종강일",
         "시작일 에러 여부","종강일 에러 여부","비고"]

    if mism_date.empty:
        st.success("날짜 불일치 없음")
    else:
        mism_date["시작일 에러 여부"] = np.where(start_err[keep_mask], "O", "")
        mism_date["종강일 에러 여부"] = np.where(end_err[keep_mask],   "O", "")

        def _diff_note(sd, ed):
            msg = []
            if pd.notna(sd) and sd != 0:
                msg.append(f"시작일 {abs(int(sd))}일 " + ("늦음" if sd > 0 else "빠름"))
            if pd.notna(ed) and ed != 0:
                msg.append(f"종강일 {abs(int(ed))}일 " + ("늦음" if ed > 0 else "빠름"))
            return " / ".join(msg)

        mism_date["비고"] = [
            _diff_note(sd, ed) for sd, ed in zip(start_diff_days[keep_mask], end_diff_days[keep_mask])
        ]
        st.dataframe(mism_date[cols3].sort_values(["코스ID","수강시작일"]), use_container_width=True, hide_index=True)

    # 4) 금액 불일치 (모두 값 존재 & 다름) — won 종료일이 pre-2025면 제외
    amt_both = inner[inner["금액"].notna() & inner["계약금액"].notna()].copy()
    amt_mismatch = amt_both[amt_both["금액"] != amt_both["계약금액"]].copy()

    amt_won_end_ts = pd.to_datetime(amt_mismatch["수강종료일"], errors="coerce")
    amt_keep_mask = amt_won_end_ts.isna() | (amt_won_end_ts >= CUTOFF)
    amt_mismatch = amt_mismatch[amt_keep_mask].copy()

    def _amt_note(won_amt, acc_amt):
        delta = float(won_amt) - float(acc_amt)
        sign  = "높음" if delta > 0 else "낮음"
        pct   = (delta / acc_amt) if (acc_amt not in [0, np.nan]) else np.nan
        if pd.notna(pct) and np.isfinite(pct):
            return f"won 금액이 회계 계약금액보다 {abs(delta):,.0f}원 {sign} ({pct:+.1%})"
        else:
            return f"won 금액이 회계 계약금액보다 {abs(delta):,.0f}원 {sign}"

    if not amt_mismatch.empty:
        amt_mismatch["비고"] = [
            _amt_note(w, a) for w, a in zip(amt_mismatch["금액"], amt_mismatch["계약금액"])
        ]

    st.subheader("4) 금액 불일치 (계약금액 ≠ 금액)")
    cols4 = ["코스ID","이름","담당자_name","수주 예정일(종합)","수강시작일","수강종료일","금액","계약금액","비고"]
    if amt_mismatch.empty:
        st.success("금액 불일치 없음")
    else:
        st.dataframe(amt_mismatch[cols4].sort_values(["코스ID","수강시작일"]), use_container_width=True, hide_index=True)

    # 5) 모든 핵심 값 일치
    full_match = inner[
        (inner["수강시작일"] == inner["코스개강일2"]) &
        (inner["수강종료일"] == inner["코스 종강일"]) &
        (inner["금액"].fillna(np.nan) == inner["계약금액"].fillna(np.nan))
    ].copy()

    st.subheader("5) 완전 일치 (코스ID·시작·종료·금액 모두 일치)")
    cols5 = ["코스ID","이름","담당자_name","수주 예정일(종합)","금액","수강시작일","코스개강일2","수강종료일","코스 종강일","계약금액"]
    if full_match.empty:
        st.info("완전 일치 행이 없습니다.")
    else:
        st.dataframe(full_match[cols5].sort_values(["코스ID","수강시작일"]), use_container_width=True, hide_index=True)
