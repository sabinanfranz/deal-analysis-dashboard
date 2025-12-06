from __future__ import annotations

import os
import tempfile
import traceback
from pathlib import Path

import requests
import streamlit as st

from salesmap_sync import artifact_fetch

st.set_page_config(page_title="GitHub Artifact Debug", layout="wide")
st.title("🔍 GitHub Artifact 다운로드 디버깅")
st.caption("GitHub Actions에 업로드된 salesmap DB 아티팩트 다운로드 문제를 진단합니다.")


def _mask(val: str | None) -> str:
    if not val:
        return "(none)"
    if len(val) <= 8:
        return "***"
    return f"{val[:4]}...{val[-4:]}"


def _get_secret(name: str) -> str | None:
    try:
        return st.secrets.get(name)
    except Exception:
        return None


st.write("### 1) Secrets / 환경변수 확인")
token = os.getenv("GITHUB_TOKEN") or _get_secret("GITHUB_TOKEN")
repo = os.getenv("GITHUB_REPO") or _get_secret("GITHUB_REPO")
artifact_name = os.getenv("SALES_DB_ARTIFACT") or _get_secret("SALES_DB_ARTIFACT") or artifact_fetch.DEFAULT_ARTIFACT_NAME
db_path_env = os.getenv("SALES_DB_PATH") or _get_secret("SALES_DB_PATH")
db_path = Path(db_path_env) if db_path_env else artifact_fetch.DEFAULT_DB_PATH

rows = [
    ("GITHUB_TOKEN", _mask(token)),
    ("GITHUB_REPO", repo or "(none)"),
    ("SALES_DB_ARTIFACT", artifact_name),
    ("SALES_DB_PATH (effective)", str(db_path)),
    ("SALESMAP_FETCH_ON_DEMAND", os.getenv("SALESMAP_FETCH_ON_DEMAND", "(none)")),
]
st.table(rows)

if not token:
    st.error("GITHUB_TOKEN이 없습니다. 환경변수 또는 Streamlit secrets를 확인하세요.")
    st.stop()
if not repo:
    st.error("GITHUB_REPO가 없습니다. 'owner/repo' 형태로 설정하세요.")
    st.stop()

headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
}

st.write("### 2) GitHub API 호출 테스트 (Artifacts 목록)")
params = {"per_page": 50}
url = f"https://api.github.com/repos/{repo}/actions/artifacts"

list_clicked = st.button("Artifacts 목록 조회")
artifacts: list[dict] = []
last_resp = None

if list_clicked:
    with st.spinner("GitHub API 호출 중..."):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            last_resp = resp
            st.write(f"**Status Code:** `{resp.status_code}`")
            st.json(
                {
                    "ratelimit": {
                        "limit": resp.headers.get("X-RateLimit-Limit"),
                        "remaining": resp.headers.get("X-RateLimit-Remaining"),
                        "reset": resp.headers.get("X-RateLimit-Reset"),
                    },
                    "content_type": resp.headers.get("Content-Type"),
                }
            )
            if resp.status_code == 200:
                st.success("✅ API 접근 성공")
                data = resp.json()
                artifacts = data.get("artifacts", [])
                st.write(f"**총 Artifacts 수:** `{len(artifacts)}`")
                if artifacts:
                    st.dataframe(
                        [
                            {
                                "id": a["id"],
                                "name": a["name"],
                                "expired": a.get("expired", False),
                                "size(MB)": round(a["size_in_bytes"] / 1024 / 1024, 2),
                                "created_at": a.get("created_at"),
                                "updated_at": a.get("updated_at"),
                            }
                            for a in artifacts
                        ]
                    )
            elif resp.status_code == 401:
                st.error("❌ 401 Unauthorized - Token이 유효하지 않습니다.")
            elif resp.status_code == 403:
                st.error("❌ 403 Forbidden - 권한/스코프 문제일 수 있습니다.")
            elif resp.status_code == 404:
                st.error("❌ 404 Not Found - 레포 이름 또는 접근 권한을 확인하세요.")
            else:
                st.error(f"❌ 예상치 못한 에러: {resp.status_code}")
                st.code(resp.text)
        except Exception:
            st.error("❌ API 호출 중 예외가 발생했습니다.")
            st.code(traceback.format_exc())

st.write("---")
st.write("### 3) 다운로드 경로 테스트")
target_artifacts = [a for a in artifacts if a.get("name") == artifact_name and not a.get("expired")]

if artifacts and not target_artifacts:
    st.warning(f"'{artifact_name}' 이름의 만료되지 않은 아티팩트가 목록에 없습니다.")

if target_artifacts:
    target = target_artifacts[0]
    st.success(f"✅ 타겟 아티팩트 확인: {target['name']} (id={target['id']})")
    st.write(f"Download URL: `{target.get('archive_download_url')}`")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("requests로 다운로드 테스트", key="req_download"):
            with st.spinner("다운로드 중..."):
                try:
                    dl_resp = requests.get(
                        target.get("archive_download_url"),
                        headers=headers,
                        stream=True,
                        timeout=60,
                    )
                    st.write(f"Status: {dl_resp.status_code}")
                    if dl_resp.status_code == 200:
                        total_size = 0
                        for chunk in dl_resp.iter_content(chunk_size=8192):
                            total_size += len(chunk)
                        st.success(f"✅ 다운로드 성공 (총 {total_size / 1024 / 1024:.1f} MB)")
                    else:
                        st.error("❌ 다운로드 실패")
                        st.code(dl_resp.text)
                except Exception:
                    st.error("❌ 다운로드 예외 발생")
                    st.code(traceback.format_exc())

    with col2:
        if st.button("artifact_fetch.fetch_artifact_if_missing() 테스트", key="helper_download"):
            test_path = Path(tempfile.gettempdir()) / "artifact_debug" / f"{artifact_name}.db"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            if test_path.exists():
                test_path.unlink()

            with st.spinner(f"{test_path} 로 다운로드 시도..."):
                try:
                    result = artifact_fetch.fetch_artifact_if_missing(
                        db_path=test_path, artifact_name=artifact_name, repo=repo
                    )
                    if result and result.exists():
                        st.success(f"✅ 헬퍼 다운로드 성공: {result}")
                    else:
                        st.error("❌ 헬퍼가 아티팩트를 찾지 못했습니다 (None 반환).")
                except Exception:
                    st.error("❌ 헬퍼 실행 중 예외 발생")
                    st.code(traceback.format_exc())

st.write("---")
st.write("### 4) 원본 에러 메시지 공유")
st.info("Streamlit 앱에서 본 에러 메시지를 붙여 넣어 주세요. (로그 첨부용)")
st.text_area("에러 메시지", height=150)
