# -*- coding: utf-8 -*-
"""
GitHub Actions에서 업로드한 salesmap.db 아티팩트를 내려받는 헬퍼.
수정: Streamlit Cloud 호환성을 위해 DB_PATH를 /tmp로 변경
"""
from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import requests

DEFAULT_ARTIFACT_NAME = os.getenv("SALES_DB_ARTIFACT", "salesmap-db")

# 변경: Streamlit Cloud의 read-only 파일시스템 문제 해결
# DEFAULT_DB_PATH = Path(os.getenv("SALES_DB_PATH", Path(__file__).parent / "salesmap.db"))  # 기존
DEFAULT_DB_PATH = Path(os.getenv("SALES_DB_PATH", "/tmp/salesmap.db"))  # 수정


def _get_secret(name: str) -> Optional[str]:
    """환경변수 우선, 없으면 streamlit secrets에서 조회."""
    val = os.getenv(name)
    if val:
        return val
    try:
        import streamlit as st  # type: ignore

        return st.secrets.get(name)  # type: ignore[attr-defined]
    except Exception:
        return None


def _get_auth_header() -> dict:
    token = _get_secret("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN이 설정되지 않아 아티팩트를 다운로드할 수 없습니다.")
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def _find_latest_artifact(repo: str, name: str, headers: dict) -> Optional[dict]:
    url = f"https://api.github.com/repos/{repo}/actions/artifacts"
    params = {"per_page": 50}
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    artifacts = resp.json().get("artifacts", [])
    for art in artifacts:
        if art.get("name") == name and not art.get("expired", False):
            return art
    return None


def _download_and_extract(db_path: Path, artifact: dict, headers: dict) -> Path:
    dl_url = artifact.get("archive_download_url")
    if not dl_url:
        raise RuntimeError("아티팩트 다운로드 URL을 찾을 수 없습니다.")

    with tempfile.TemporaryDirectory() as td:
        zip_path = Path(td) / "artifact.zip"
        with requests.get(dl_url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            target = None
            for m in members:
                if m.endswith(".db"):
                    target = m
                    break
            if not target:
                raise RuntimeError("압축파일 내에 .db 파일이 없습니다.")
            zf.extract(target, Path(td))
            extracted = Path(td) / target
            db_path.parent.mkdir(parents=True, exist_ok=True)
            extracted.replace(db_path)
    return db_path


def fetch_artifact_if_missing(
    db_path: Path = DEFAULT_DB_PATH,
    artifact_name: str = DEFAULT_ARTIFACT_NAME,
    repo: Optional[str] = None,
) -> Optional[Path]:
    """
    로컬에 db_path가 없을 때 GitHub Actions 아티팩트를 내려받아 저장.
    성공 시 db_path 반환, 실패 시 None 반환(호출 측에서 처리).
    """
    if db_path.exists():
        return db_path

    repo = repo or _get_secret("GITHUB_REPO")
    if not repo:
        return None

    try:
        headers = _get_auth_header()
        art = _find_latest_artifact(repo, artifact_name, headers)
        if not art:
            return None
        return _download_and_extract(db_path, art, headers)
    except Exception:
        return None


if __name__ == "__main__":
    path = fetch_artifact_if_missing()
    print(f"downloaded: {path}")
