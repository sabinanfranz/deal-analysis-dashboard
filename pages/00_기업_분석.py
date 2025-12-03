# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from salesmap_sync.data_loader import load_all

st.set_page_config(page_title="기업-고객-딜-메모 뷰", layout="wide")

st.markdown("## 기업 → 고객 → 딜 → 메모/웹폼 요약")
st.caption(
    "기업을 선택하면 해당 기업의 고객, 연결 딜, 메모, 웹폼 제출 내역을 한 번에 봅니다. "
    "데이터는 Salesmap API를 통해 갱신되며, 토큰이 필요합니다."
)

# ─────────────────────────── 데이터 로드
try:
    orgs, people, deals, memos, webforms, webform_subs = load_all()
except RuntimeError as e:
    st.error(f"토큰을 읽지 못했습니다: {e}")
    st.stop()

if orgs.empty:
    st.warning("Salesmap 데이터를 찾을 수 없습니다. 토큰 설정 및 API 접근을 확인하세요.")
    st.stop()


def _safe_dt(series, col):
    if col in series:
        return pd.to_datetime(series[col], errors="coerce")
    return pd.Series([], dtype="datetime64[ns]")


org_names = sorted(orgs["name"].dropna().unique())
default_sel = org_names[:3]
selected_names = st.multiselect("기업명 선택", org_names, default=default_sel, key="org_selector")

if not selected_names:
    st.info("왼쪽에서 기업을 하나 이상 선택하세요.")
    st.stop()

# ─────────────────────────── 필터링
sel_orgs = orgs[orgs["name"].isin(selected_names)]
org_ids = set(sel_orgs["id"])

sel_people = people[people["organization_id"].isin(org_ids)]
people_ids = set(sel_people["id"])

sel_deals = deals[
    deals["organization_id"].isin(org_ids)
    | deals["people_id"].isin(people_ids)
]
deal_ids = set(sel_deals["id"])

sel_memos = memos[
    memos["organization_id"].isin(org_ids)
    | memos["people_id"].isin(people_ids)
    | memos["deal_id"].isin(deal_ids)
]

# 웹폼 제출은 조직/고객 연결 정보가 없으므로 전체 노출 후 필터 없음
sel_webforms = webforms.copy()
sel_webform_subs = webform_subs.copy()

# 날짜 파싱
for df, col in [
    (sel_deals, "updated_at"),
    (sel_deals, "contract_at"),
    (sel_deals, "expected_close_at"),
    (sel_memos, "created_at"),
]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
if "created_at" in sel_webform_subs.columns:
    sel_webform_subs["created_at"] = pd.to_datetime(sel_webform_subs["created_at"], errors="coerce")


# ─────────────────────────── 요약 탭
tabs = st.tabs(["요약 보고서", "상세 보기"])

with tabs[0]:
    st.subheader("기업별 요약")
    for _, org in sel_orgs.iterrows():
        oid = org["id"]
        o_people = sel_people[sel_people["organization_id"] == oid]
        o_deals = sel_deals[sel_deals["organization_id"] == oid]
        o_memos = sel_memos[sel_memos["organization_id"] == oid]

        latest_memo = o_memos["created_at"].max() if not o_memos.empty else None
        latest_memo_str = latest_memo.strftime("%Y-%m-%d") if pd.notnull(latest_memo) else "-"

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("고객 수", len(o_people))
        col2.metric("딜 수", len(o_deals))
        col3.metric("메모 수", len(o_memos))
        col4.metric("Won 딜", int((o_deals["status"] == "Won").sum()))
        col5.metric("최근 메모", latest_memo_str)
        st.markdown(f"**{org['name']}** — 업종: {org.get('industry','-')} / 규모: {org.get('size','-')} / Label: {org.get('label','-')}")
        st.divider()


# ─────────────────────────── 상세 탭
with tabs[1]:
    for _, org in sel_orgs.iterrows():
        oid = org["id"]
        st.markdown(f"### {org['name']}")
        st.caption(f"업종: {org.get('industry','-')} / 규모: {org.get('size','-')} / 담당자: {org.get('manager_name','-')}")

        o_people = sel_people[sel_people["organization_id"] == oid]
        o_deals = sel_deals[sel_deals["organization_id"] == oid]
        o_memos = sel_memos[sel_memos["organization_id"] == oid]

        st.write(f"- 고객 {len(o_people)}명 / 딜 {len(o_deals)}건 / 메모 {len(o_memos)}건")

        for _, person in o_people.iterrows():
            pid = person["id"]
            p_deals = sel_deals[
                (sel_deals["people_id"] == pid)
                | (sel_deals["organization_id"] == oid)
            ]
            p_memos = sel_memos[
                (sel_memos["people_id"] == pid)
                | (sel_memos["deal_id"].isin(p_deals["id"]))
            ]

            with st.expander(f"👤 {person.get('name','(이름없음)')} — {person.get('title','-')} / {person.get('team','-')}", expanded=False):
                st.markdown("**딜 목록**")
                if p_deals.empty:
                    st.info("연결된 딜 없음")
                else:
                    show_cols = ["name", "status", "amount", "expected_close_at", "contract_at", "pipeline_name", "stage_name"]
                    show_cols = [c for c in show_cols if c in p_deals.columns]
                    st.dataframe(p_deals[show_cols].sort_values(by="updated_at", ascending=False), use_container_width=True)

                st.markdown("**메모 타임라인**")
                if p_memos.empty:
                    st.info("연결된 메모 없음")
                else:
                    pm = p_memos.copy()
                    if "text" in pm.columns:
                        pm["text"] = pm["text"].astype(str).str.slice(0, 300)
                    if "created_at" in pm.columns:
                        pm = pm.sort_values(by="created_at", ascending=False)
                    st.dataframe(pm[["created_at", "text", "deal_id", "owner_id"]], use_container_width=True)

                st.markdown("**웹폼 제출**")
                # 웹폼 제출에 고객 ID가 없는 경우가 많아 전체를 보여주고 필터 안내
                if sel_webform_subs.empty:
                    st.info("웹폼 제출 데이터 없음")
                else:
                    st.info("웹폼 제출에는 고객 ID가 없어 전체 목록을 표시합니다.")
                    wf_join = sel_webform_subs.merge(sel_webforms, left_on="webform_id", right_on="id", how="left", suffixes=("", "_wf"))
                    st.dataframe(wf_join[["created_at", "webform_id", "name"]], use_container_width=True)

        if o_people.empty:
            st.info("해당 기업에 연결된 고객이 없습니다.")

        st.divider()

st.caption("시퀀스 데이터는 현재 API 문서에 없어서 연동하지 않았습니다. 제공되면 people_id 기준으로 확장 예정입니다.")
