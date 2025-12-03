# Salesmap API 데이터 흐름·구조·DB 구성 제안

## 1) 호출되는 리소스와 특징
- 공통: Base `https://salesmap.kr/api/v2`, Bearer 토큰, 커서 기반 페이지네이션(`cursor`), 워크스페이스 레이트리밋 100req/10s. 목록 응답은 `data.{...List}`, `nextCursor`.
- 주요 엔드포인트(읽기):
  - `GET /organization` 회사 목록 → `organizationList`
  - `GET /people` 고객(담당자) 목록 → `peopleList`
  - `GET /deal` 딜 목록 → `dealList`
  - `GET /deal/{dealId}` 딜 단건, `GET /deal/{dealId}/quote` 견적/상품
  - `GET /{organization|people|deal}/history` 변경 이력
  - `GET /{organization|people|deal}/activity` 액티비티(sms/email/todo/memo 링크)
  - `GET /webForm` 웹폼 목록, `GET /webForm/{id}/submit` 제출 내역
  - `GET /memo` 노트(메모) 목록
- 응답 필드 특성(샘플은 `salesmap_api_responses.md` 참고):
  - ISO UTC 시각 문자열(…Z), 한국시간 변환 필요 시 별도 처리.
  - 딜: 조직/고객 참조 id, 파이프라인/단계, 금액, 상태, 코스 ID, 팀 배열, 사용자 참조, 커스텀 필드(한글 키) 다수.
  - 조직: 기본 정보 + 웹폼 제출 목록(최근 n개), 팀, 담당자, 매출/딜/리드 집계.
  - 고객: 기본 인적/조직/직급 필드, 담당자, 커스텀 필드.
  - 웹폼 제출: `contents` 배열(필드 label/value + childFieldList), 제출 메타(createdAt 등).
  - 메모: 긴 텍스트 `text`, deal/people/organization id 연결, ownerId, createdAt/updatedAt.
  - Activity/History: type, target id, 생성 시각, 필드명/값(History), 연결된 메타 id(Activity).

## 2) 추천 DB 테이블 설계 (관계형 기준)
### Core 엔터티
- `organizations` (`id` PK, name, label, size, industry, group_name, web_url, phone, email, lead_count, deal_count, won_deal_count, total_revenue, 담당자_id, created_at, updated_at, raw_json)
- `people` (`id` PK, name, org_id FK, top_org, team, title, 담당교육영역, phone/email 등, created_at, updated_at, raw_json)
- `deals` (`id` PK, org_id FK, people_id FK, name, pipeline_id, pipeline_name, stage_id, stage_name, amount, status, expected_close_at, contract_at, start_at, end_at, course_id, probability, next_todo, team_ids(json), owner_id, created_at, updated_at, raw_json)
- `quotes` (`id` PK, deal_id FK, name, amount, is_main, created_at, updated_at, owner_id, raw_json)
- `quote_items` (`id` PK, quote_id FK, product_id, name?, quantity, amount, discount, start_at, end_at, raw_json)
- `memos` (`id` PK, text, deal_id FK, people_id FK, org_id FK, owner_id, created_at, updated_at, raw_json)
- `webforms` (`id` PK, name, description, folder_name, status, view_count, submit_count, created_at, updated_at, raw_json)
- `webform_submissions` (`id` PK, webform_id FK, created_at, updated_at, submitter meta, contents_json(flat or kv), raw_json)

### 로그·변경 계열
- `*_history` (별도 테이블 3개 또는 통합 테이블 `histories` with `target_type`): id, target_type(org/people/deal), target_id, type, field_name, field_value(json), owner_id, created_at.
- `*_activity` (별도 또는 통합 `activities`): id, target_type, target_id, type, date, webform_id, sms_id, todo_id, memo_id, email_id, deal_status, created_at(=date).

### 정규화/저장 전략
- 원본 JSON을 `raw_json` 컬럼(JSON)으로 보존해 스키마 변경 시 방어.
- 커스텀/한글 필드는 주요 컬럼만 끌어와 별도 컬럼으로 노출, 나머지는 raw_json 참조.
- 팀/제출된 웹폼 목록처럼 배열 필드는 bridge 테이블로 확장하거나 JSON으로 둔 뒤 분석 시 normalize.

## 3) 적재 파이프라인 제안
- 호출: `requests.Session` + 토큰 버킷(<=9 req/s) + 429/5xx 백오프(10초 이상) + cursor 루프.
- 변환: 날짜 UTC→Asia/Seoul 옵션, 중첩 키 flatten, id 관계 맵(join) 후 DB 컬럼 매핑.
- 적재: 트랜잭션 내 upsert(ON CONFLICT UPDATE) 또는 일단 스테이징 테이블 drop+insert 후 스왑.
- 스냅샷: 일자별 parquet/json을 `snapshots/YYYYMMDD/`에 보관해 회귀/리플레이 가능하게.
- 검증: 레코드 수, 최신 created_at, 필수 필드 null 비율 등 간단 health check 후 실패 시 비정상 종료.

## 4) 우선 순위 필드 (보고/페이지 노출 기준)
- Deal: org_id, people_id, name, status, 파이프라인/단계, 금액/예상액, 예상일/계약일/기간, 코스 ID, 팀, 담당자, 상태 변경일, 커스텀 카테고리/포맷/Net(%).
- Organization: 이름, 업종/규모/그룹명, Label, 담당자, 팀, 리드/딜/성사 건수, 총매출, 제출된 웹폼 id/name.
- People: 이름, org_id, 상위 조직, 팀, 직급, 담당 교육 영역, 연락처, 담당자.
- Webform: 이름, 생성/수정, view/submit count, folder, status; Submission은 contents 필드(label/value)까지 보존.
- Memo: text, 연결된 deal/people/org, owner, created_at.
- History/Activity: type/field_name/field_value/date → 변경 추적과 활동 집계에 사용.

## 5) Pages/분석 관점
- BI/Pages는 `deals` 뷰에 org/people 조인한 denorm 테이블(materialized view) 제공하면 빠르게 렌더 가능.
- 활동/이력은 시간순 타임라인 또는 품질 검증(값 변경 검출)에 사용.
- 웹폼 제출은 리드 유입 분석, 메모는 컨텍스트/콜 노트 검색용으로 Elastic/PG trigram 인덱스 고려.

## 6) 주의사항
- 레이트리밋 준수: 중앙 스로틀러 적용, 병렬 호출 시에도 총합 100/10s 이하.
- 페이지네이션: `nextCursor` nil까지 반복, 커서는 다음 호출 시 재사용 불가(스냅샷 불변 아님).
- 날짜: ISO UTC 문자열 → 필요 시 tz 변환 저장; DB timestamp with time zone 권장.
- 토큰 보안: 코드에 하드코딩 금지, Actions 시크릿/로컬 env 사용.

참고 샘플 응답: `docs/salesmap_api_responses.md`.

## 7) 토큰/배포 관리
- 로컬: `.env` 등에 `SALESMAP_TOKEN` 설정 후 `source .env` 혹은 환경변수로 주입.
- Streamlit Cloud: `.streamlit/secrets.toml`에 `SALESMAP_TOKEN = "..."` 저장 (Git 커밋 금지).
- GitHub Actions: `SALESMAP_TOKEN`을 repository secret에 저장 후 워크플로 환경변수로 전달.
- 코드에서는 환경변수/`st.secrets`만 읽고, 평문 토큰은 저장/로그 금지.
- on-demand 호출 차단: `SALESMAP_FETCH_ON_DEMAND=0`이면 앱에서 API를 직접 호출하지 않고, 사전 생성된 DB만 사용합니다(기본 0).
