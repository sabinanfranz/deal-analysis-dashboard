---
# Salesmap API Notes

## Purpose
- Salesmap API 문서/샘플 위치와 데이터 모델 개요를 요약해 API 관련 작업의 출발점을 제공합니다.

## Audience
- Primary: 외부 LLM / 신규 투입된 LLM 에이전트
- Secondary: 데이터 파이프라인 담당자, 신규 개발자

## Scope
- In-scope:
  - 주요 엔드포인트, 레이트리밋, 페이지네이션, 시간대 주의점 요약
  - 레포 내 샘플 응답/데이터 모델 문서 위치 안내
- Out-of-scope:
  - 완성된 ETL 구현 상세
  - 배포/시크릿 설정 절차의 세부 단계

## Sources of truth (do not guess)
- (반드시 링크로) 이 문서는 아래 파일만을 근거로 한다:
  - ../README.md
  - ../implementation.md
  - ../data-sources.md
  - ../database.md
  - ../pages.md
  - ../context-bridge.md
  - ../TODO.md
  - ../salesmap_api_data_model.md
  - ../salesmap_api_responses.md
  - (필요 시) ../../<레포 상단의 txt 문서들> (예: B2B 제품/조직/어카운트 전략 문서)

## Update triggers
- Salesmap API 사양/레이트리밋/페이지네이션 규칙이 변경될 때
- 샘플 응답이나 데이터 모델 제안 문서가 갱신될 때

## Open questions / TODO
- TODO: 최신 API 변경 내역 확인 필요 여부 점검
---

## What this API covers (entities)
- 핵심 엔티티: organizations, people, deals, quotes(+items), memos, webforms(+submissions), history, activity (`../salesmap_api_data_model.md`)
- 관계: deal↔organization/people, webform↔submission, memo↔deal/people/org, history/activity는 대상별 타임라인

## Response characteristics
- Base URL `https://salesmap.kr/api/v2`, Bearer 토큰, 커서 기반 페이지네이션(`cursor`, `nextCursor`) (`../salesmap_api_data_model.md`)
- 레이트리밋: 워크스페이스 100req/10s → 최소 요청 간격 확보 필요
- 시간대: ISO UTC 문자열, 한국시간 변환 필요 시 별도 처리
- 목록 응답 키: `organizationList`, `peopleList`, `dealList`, `memoList`, `webFormList`, `webFormSubmitList` 등 (`../salesmap_api_responses.md`)

## Suggested storage mapping (current proposal)
- SQLite 테이블 제안(`../salesmap_api_data_model.md`): organizations(id/name/size/industry/label/manager/집계), people(id/org_id/name/team/title/owner), deals(id/org_id/people_id/name/pipeline/stage/amount/status/expected/contract/기간/팀/owner/raw_json), quotes/quote_items, memos, webforms, webform_submissions, histories, activities
- 현재 구현(utility): `salesmap_sync/fetch_salesmap.py`가 위 스키마대로 DB 작성(`/tmp/salesmap.db`), 인덱스는 id 및 주요 FK에 생성. `salesmap_sync/data_loader.py`가 pandas 로더 제공.
- 앱 본체는 기본 TXT/`deals.db`를 사용하며 Salesmap DB는 별도(필요 시 연동).

## Integration sketch (conceptual)
1. 토큰 로드(`SALESMAP_TOKEN` 환경/`st.secrets`) → 세션 헤더 설정
2. 엔드포인트별 `cursor` 루프 → 데이터 수집 (`_fetch_list`, `_fetch_webform_submissions`)
3. 변환: 날짜/숫자/참조 id 매핑, 배열 JSON 보존, 원본 `raw_json` 저장
4. 저장: SQLite에 replace+인덱스 (`write_db`), WAL 사용
5. 배포/캐싱: GitHub Actions 아티팩트 업로드 후 `salesmap_sync/artifact_fetch.py`로 필요 시 다운로드 (Streamlit Cloud read-only 대응)
6. 앱 반영: 별도 통합 필요 시 `salesmap_sync/data_loader.load_all()` 사용해 tables 튜플 수신 → 추가 전처리 후 pages/에 연결

## Ops & security checklist
- 토큰을 코드에 하드코딩하지 말 것: 환경변수 또는 `st.secrets` 사용 (`../salesmap_api_data_model.md`)
- 레이트리밋 준수: 429 시 백오프(코드에 10s 재시도), 최소 0.12s 간격
- 페이지네이션: `nextCursor` nil까지 반복, 커서 재사용 불가
- 스냅샷: 날짜별 parquet/json 보관 권장(문서 제안), 현 구현은 SQLite 파일만 생성 → TODO 필요 시 스냅샷 추가
- 재현성: `/tmp/salesmap.db` 경로 사용(Streamlit Cloud 호환). 필요 시 `SALES_DB_PATH`로 오버라이드 가능.
