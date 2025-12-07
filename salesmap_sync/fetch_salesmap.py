# -*- coding: utf-8 -*-
"""
Salesmap API -> SQLite 적재 유틸
--------------------------------
수정: Streamlit Cloud 호환성을 위해 DB_PATH를 /tmp로 변경
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import requests

BASE_URL = os.getenv("SALESMAP_API_BASE", "https://salesmap.kr/api/v2")

# 변경: Streamlit Cloud의 read-only 파일시스템 문제 해결
# DB_PATH = Path(__file__).parent / "salesmap.db"  # 기존
DB_PATH = Path("/tmp/salesmap.db")  # 수정
USER_AGENT = "salesmap-sync/1.0"


def _load_token() -> str:
    # Streamlit Cloud에서 st.secrets 지원
    try:
        import streamlit as st  # type: ignore
        if "SALESMAP_TOKEN" in st.secrets:
            return st.secrets["SALESMAP_TOKEN"]
    except Exception:
        pass
    token = os.getenv("SALESMAP_TOKEN")
    if not token:
        raise RuntimeError("SALESMAP_TOKEN이 설정되지 않았습니다.")
    return token


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Authorization": f"Bearer {_load_token()}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
    )
    return s


def _throttled_get(session: requests.Session, path: str, params: Optional[dict] = None) -> requests.Response:
    """레이트리밋(100/10s) 대응: 최소 요청 간격 확보 + 429 백오프."""
    url = f"{BASE_URL}{path}"
    while True:
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            time.sleep(10)
            continue
        resp.raise_for_status()
        time.sleep(0.12)  # ~8.3req/s
        return resp


def _fetch_list(session: requests.Session, path: str, list_key: str) -> List[dict]:
    items: List[dict] = []
    cursor: Optional[str] = None
    while True:
        params = {"cursor": cursor} if cursor else None
        resp = _throttled_get(session, path, params=params)
        data = resp.json().get("data", {})
        batch = data.get(list_key, [])
        if batch:
            items.extend(batch)
        cursor = data.get("nextCursor")
        if not cursor:
            break
    return items


def _fetch_webform_submissions(session: requests.Session, webform_ids: List[str]) -> List[dict]:
    submissions: List[dict] = []
    for wf_id in webform_ids:
        cursor: Optional[str] = None
        path = f"/webForm/{wf_id}/submit"
        while True:
            params = {"cursor": cursor} if cursor else None
            resp = _throttled_get(session, path, params=params)
            data = resp.json().get("data", {})
            batch = data.get("webFormSubmitList", [])
            for item in batch:
                item["webFormId"] = wf_id
            if batch:
                submissions.extend(batch)
            cursor = data.get("nextCursor")
            if not cursor:
                break
    return submissions


# ─────────────────────────── 변환기
def _coalesce(d: dict, *keys: str) -> Any:
    for k in keys:
        if k in d:
            return d.get(k)
    return None


def _map_organization(o: dict) -> dict:
    return {
        "id": o.get("id"),
        "name": o.get("이름"),
        "size": o.get("기업 규모"),
        "industry": o.get("업종"),
        "group_name": o.get("기업집단명"),
        "label": o.get("Label"),
        "manager_id": (o.get("담당자") or {}).get("id"),
        "manager_name": (o.get("담당자") or {}).get("name"),
        "created_at": o.get("생성 날짜"),
        "updated_at": o.get("수정 날짜"),
        "raw_json": json.dumps(o, ensure_ascii=False),
    }


def _map_people(p: dict) -> dict:
    return {
        "id": p.get("id"),
        "organization_id": p.get("organizationId"),
        "name": p.get("이름"),
        "top_org": p.get("소속 상위 조직"),
        "team": p.get("팀(명함/메일서명)"),
        "title": p.get("직급(명함/메일서명)"),
        "owner_id": (p.get("담당자") or {}).get("id"),
        "owner_name": (p.get("담당자") or {}).get("name"),
        "created_at": p.get("생성 날짜") or p.get("createdAt"),
        "updated_at": p.get("수정 날짜") or p.get("updatedAt"),
        "raw_json": json.dumps(p, ensure_ascii=False),
    }


def _map_deal(d: dict) -> dict:
    return {
        "id": d.get("id"),
        "organization_id": d.get("organizationId"),
        "people_id": d.get("peopleId"),
        "name": d.get("이름"),
        "status": d.get("상태"),
        "amount": d.get("금액"),
        "expected_close_at": _coalesce(d, "수주 예정일", "수주 예정일(지연)"),
        "contract_at": _coalesce(d, "계약 체결일", "계약체결일"),
        "start_at": d.get("수강시작일"),
        "end_at": d.get("수강종료일"),
        "course_id": d.get("코스 ID"),
        "pipeline_id": (d.get("파이프라인") or {}).get("id"),
        "pipeline_name": (d.get("파이프라인") or {}).get("name"),
        "stage_id": (d.get("파이프라인 단계") or {}).get("id"),
        "stage_name": (d.get("파이프라인 단계") or {}).get("name"),
        "team_names": json.dumps([t.get("name") for t in (d.get("팀") or []) if isinstance(t, dict)], ensure_ascii=False),
        "owner_id": (d.get("담당자") or {}).get("id"),
        "owner_name": (d.get("담당자") or {}).get("name"),
        "created_at": d.get("생성 날짜") or d.get("createdAt"),
        "updated_at": d.get("수정 날짜") or d.get("updatedAt"),
        "raw_json": json.dumps(d, ensure_ascii=False),
    }


def _map_memo(m: dict) -> dict:
    return {
        "id": m.get("id"),
        "text": m.get("text"),
        "deal_id": m.get("dealId"),
        "people_id": m.get("peopleId"),
        "organization_id": m.get("organizationId"),
        "owner_id": m.get("ownerId"),
        "cursor_id": m.get("cursorId"),
        "created_at": m.get("createdAt"),
        "updated_at": m.get("updatedAt"),
        "raw_json": json.dumps(m, ensure_ascii=False),
    }


def _map_webform(w: dict) -> dict:
    return {
        "id": w.get("id"),
        "name": w.get("name"),
        "description": w.get("description"),
        "status": w.get("status"),
        "folder_name": w.get("folderName"),
        "view_count": w.get("viewCount"),
        "submit_count": w.get("submitCount"),
        "created_at": w.get("createdAt"),
        "updated_at": w.get("updatedAt"),
        "raw_json": json.dumps(w, ensure_ascii=False),
    }


def _map_webform_submit(s: dict) -> dict:
    return {
        "id": s.get("id"),
        "webform_id": s.get("webFormId"),
        "created_at": s.get("createdAt"),
        "raw_json": json.dumps(s, ensure_ascii=False),
    }


# ─────────────────────────── DB 적재
def _write_table(con: sqlite3.Connection, name: str, df: pd.DataFrame, index_cols: List[str]) -> None:
    df.to_sql(name, con, if_exists="replace", index=False)
    for col in index_cols:
        try:
            con.execute(f'CREATE INDEX IF NOT EXISTS idx_{name}_{col} ON "{name}" ("{col}")')
        except sqlite3.OperationalError:
            continue


def write_db(payload: Dict[str, List[dict]]) -> Path:
    con = sqlite3.connect(DB_PATH)
    try:
        _write_table(con, "organizations", pd.DataFrame(payload["organizations"]), ["id", "name"])
        _write_table(con, "people", pd.DataFrame(payload["people"]), ["id", "organization_id", "name"])
        _write_table(con, "deals", pd.DataFrame(payload["deals"]), ["id", "organization_id", "people_id", "status"])
        _write_table(con, "memos", pd.DataFrame(payload["memos"]), ["id", "organization_id", "people_id", "deal_id"])
        _write_table(con, "webforms", pd.DataFrame(payload["webforms"]), ["id", "status", "folder_name"])
        _write_table(con, "webform_submissions", pd.DataFrame(payload["webform_submissions"]), ["id", "webform_id"])
        con.commit()
    finally:
        con.close()
    return DB_PATH


def fetch_all() -> Path:
    s = _session()
    orgs_raw = _fetch_list(s, "/organization", "organizationList")
    people_raw = _fetch_list(s, "/people", "peopleList")
    deals_raw = _fetch_list(s, "/deal", "dealList")
    memos_raw = _fetch_list(s, "/memo", "memoList")
    webforms_raw = _fetch_list(s, "/webForm", "webFormList")
    submissions_raw = _fetch_webform_submissions(s, [w.get("id") for w in webforms_raw if w.get("id")])

    payload = {
        "organizations": [_map_organization(o) for o in orgs_raw],
        "people": [_map_people(p) for p in people_raw],
        "deals": [_map_deal(d) for d in deals_raw],
        "memos": [_map_memo(m) for m in memos_raw],
        "webforms": [_map_webform(w) for w in webforms_raw],
        "webform_submissions": [_map_webform_submit(s) for s in submissions_raw],
    }
    return write_db(payload)


# ─────────────────────────── Freshness 관리
def _env_allow_fetch_default() -> bool:
    val = os.getenv("SALESMAP_FETCH_ON_DEMAND", "0").lower()
    return val not in ("0", "false", "")


def ensure_fresh_db(max_age_hours: int = 12, allow_fetch: Optional[bool] = None) -> Path:
    """
    DB가 없거나 오래됐으면 새로 페치.
    allow_fetch=False면 기존 DB만 사용, 없으면 RuntimeError.
    allow_fetch가 None이면 환경변수 SALESMAP_FETCH_ON_DEMAND(기본 0)로 결정.
    """
    if allow_fetch is None:
        allow_fetch = _env_allow_fetch_default()

    if DB_PATH.exists():
        mtime = datetime.fromtimestamp(DB_PATH.stat().st_mtime, tz=timezone.utc)
        if datetime.now(timezone.utc) - mtime < timedelta(hours=max_age_hours):
            return DB_PATH
        # 오래됐더라도 fetch 비허용이면 캐시 사용
        if not allow_fetch:
            return DB_PATH

    if not allow_fetch:
        raise RuntimeError("DB가 없거나 만료되었지만 SALESMAP_FETCH_ON_DEMAND=0 으로 설정되어 API 호출을 하지 않습니다.")
    return fetch_all()


if __name__ == "__main__":
    path = ensure_fresh_db()
    print(f"✅ salesmap synced -> {path}")
