# -*- coding: utf-8 -*-
"""
salesmap_sync.data_loader
-------------------------
- salesmap.db를 읽어 pandas DataFrame으로 반환
- 필요 시 오래된 DB를 자동 갱신(ensure_fresh_db)
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Tuple, Optional

import pandas as pd

try:
    import streamlit as st
except Exception:  # pragma: no cover - streamlit 없는 환경 대응
    st = None

from salesmap_sync.fetch_salesmap import DB_PATH, ensure_fresh_db
from salesmap_sync.artifact_fetch import fetch_artifact_if_missing


def _connect(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(db_path, check_same_thread=False)


def _cache_resource(fn):
    if st:
        return st.cache_resource(fn)
    return fn


def _cache_data(fn):
    if st:
        return st.cache_data(fn)
    return fn


def _allow_fetch_default() -> bool:
    val = os.getenv("SALESMAP_FETCH_ON_DEMAND", "0").lower()
    return val not in ("0", "false", "")


@_cache_resource
def _get_conn(max_age_hours: int, allow_fetch: bool) -> sqlite3.Connection:
    # 1) 캐시 파일이 없으면 GitHub Artifact에서 받아보기 (토큰/레포 필요)
    fetch_artifact_if_missing(db_path=DB_PATH)
    db_path = ensure_fresh_db(max_age_hours=max_age_hours, allow_fetch=allow_fetch)
    return _connect(db_path)


@_cache_data
def load_all(max_age_hours: int = 12, allow_fetch: Optional[bool] = None) -> Tuple[pd.DataFrame, ...]:
    if allow_fetch is None:
        allow_fetch = _allow_fetch_default()
    con = _get_conn(max_age_hours, allow_fetch)
    tables = ["organizations", "people", "deals", "memos", "webforms", "webform_submissions"]
    dfs = []
    for t in tables:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {t}", con)
        except Exception:
            df = pd.DataFrame()
        dfs.append(df)
    return tuple(dfs)


@_cache_data
def load_all_with_leads(max_age_hours: int = 12, allow_fetch: Optional[bool] = None) -> Tuple[pd.DataFrame, ...]:
    """
    load_all 확장판: leads 테이블을 포함하여 반환.
    기존 load_all의 반환 형태에 영향 없이 별도 헬퍼로 제공.
    """
    if allow_fetch is None:
        allow_fetch = _allow_fetch_default()
    con = _get_conn(max_age_hours, allow_fetch)
    tables = ["organizations", "people", "deals", "leads", "memos", "webforms", "webform_submissions"]
    dfs = []
    for t in tables:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {t}", con)
        except Exception:
            df = pd.DataFrame()
        dfs.append(df)
    return tuple(dfs)
