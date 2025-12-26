---
# Data Layer & Refresh

## Purpose
- TXT→전처리→SQLite 적재와 캐시 무효화/갱신 절차를 운영 관점에서 빠르게 이해하도록 합니다.

## Audience
- Primary: 외부 LLM / 신규 투입된 LLM 에이전트
- Secondary: 데이터 운영/분석 담당자, 신규 개발자

## Scope
- In-scope:
  - 데이터 소스 목록과 전처리/적재 흐름 요약
  - DB 재생성 트리거, Streamlit 캐시 무효화 키, 갱신 런북 개요
- Out-of-scope:
  - Salesmap API 수집/ETL 상세(별도 문서)
  - 전처리 함수의 세부 코드

## Sources of truth (do not guess)
- (반드시 링크로) 이 문서는 아래 파일만을 근거로 한다:
  - ../README.md
  - ../implementation.md
  - ../data-sources.md
  - ../database.md
  - ../pages.md
  - ../context-bridge.md
  - ../TODO.md
  - (필요 시) ../../<레포 상단의 txt 문서들> (예: B2B 제품/조직/어카운트 전략 문서)

## Update triggers
- TXT 스키마나 전처리(data.py) 로직이 바뀔 때
- DB 재생성/캐시 무효화 방식이 수정될 때
- 갱신 절차나 준비 스크립트가 변경될 때

## Open questions / TODO
- TODO: 최신 TXT 파일 mtime/스냅샷 정보 확인
---

## Data sources inventory (TXT, UTF-8, 탭)
- `all deal.txt` (5,583행·68열 → 결측만 행 제거 후 5,573행 적재): 전체 딜(생성/파이프라인/상태/금액/포맷/성사 가능성 등)
- `won deal.txt` (1,839행·68열 → DB 1,831행): Won 딜 서브셋, 동일 스키마
- `retention corp.txt` (145행·2열): 리텐션 기업명·매출 티어
- `accounting data.txt` (2,460행·15열 → 전처리 후 2,393행·25열): 결제/집계월/포맷/코스ID/교육기간 등 (B2B_SMB 제거)
- 파일 변경 시 `data.py` import만으로 자동 재적재됨 (`../data-sources.md`, `data.py`)

## SQLite schema overview
- 테이블: `all_deal`(5,573행), `won_deal`(1,831행), `retention`(145행), `accounting`(2,393행)
- 인덱스: `idx_all_deal_name`(`담당자_name`), `idx_won_deal_name`(`담당자_name`), `idx_acc_course`(`코스 ID`), `idx_acc_month`(`집계년`,`집계월`) (`../database.md`)
- WAL 모드(`deals.db`, `.db-shm`, `.db-wal` 유지)

## ETL / preprocessing (data.py 근거)
- 공통: `pd.read_csv(sep='\t')` → 결측만 행 drop
- accounting 전처리(`_pre_accounting`): 헤더 공백/BOM 제거, 숫자형(계약금액/일수) 변환, 불리언/날짜 캐스팅, `매출집계월` 파생(집계년/월/월초), 코스ID 별칭/문자열, 수강시작/종료 파생, 사업구분/포맷 보강, 교육과정명에 `(B2B_SMB)` 포함 행 제외
- 공통 후처리(`_post`/`_post_won`): 담당자_name 끝 `B` 제거, 금액 숫자화, 생성/수주예정 연월 숫자화, 비매출입과 제외
- 캐시 키: TXT mtime + 코드 mtime + `CODE_SIG` (`data.py`)

## Refresh procedure (runbook)
1) 최신 TXT 4종 교체 또는 수정
2) 앱 재시작 또는 `python3 -c "from data import load_to_db; load_to_db()"` 실행 (`../implementation.md`)
3) 필요 시 `CODE_SIG` 업데이트로 Streamlit 캐시 무효화
4) 검증: DB 테이블 행 수/스키마, 주요 컬럼 null/타입 확인 → `sub/query_db.py` 등 사용 가능

## Data validation checklist
- 행 수: docs/database.md 기준과 크게 차이날 경우 입력/필터 확인
- 필수 컬럼 존재 여부: `수주 예정액(종합)`, `과정포맷(대)`, `생성년도/월`, `성사 가능성`, `담당자_name`
- 타입: 날짜(`수주 예정일(종합)`, `수강시작일/종료일`), 숫자(금액, 연/월) 캐스팅 확인
- 리텐션 세트: `retention corp.txt`가 비어있지 않은지, 기업명 정규화 여부
- Accounting: `(B2B_SMB)` 제거 여부, 집계년/월 파생, 포맷 존재 여부

## Troubleshooting
- 증상: 데이터가 옛날 상태 → 원인: 캐시 키 미변경/앱 미재시작 → 조치: `CODE_SIG` 변경 또는 재시작, `load_to_db()` 수동 실행
- 증상: 컬럼 KeyError → 원인: TXT 스키마 변경 → 조치: `data.py` 전처리/후처리 업데이트 + `CODE_SIG` 변경
- 증상: 행 수 급감 → 원인: 결측만 행 drop 또는 필터 조건(연/월 범위) → 조치: 원본 TXT 확인, 필터 범위 점검
- 증상: 회계 포맷 누락 → 원인: `_pre_accounting` 포맷 보강 실패 → 조치: 원본 헤더/값 확인, 보강 로직 수정
- 증상: 리텐션 분류 오동작 → 원인: retention corp.txt 기업명 공백/라벨 → 조치: 기업명 트리밍/대소문자 확인

## Operational notes
- `data.py` import 시마다 DB 재생성(덮어쓰기) → 운영 환경에서 원본 TXT 백업 필수
- 캐시 리소스/데이터는 Streamlit 데코레이터(`@st.cache_resource`, `@st.cache_data`) 사용 → 코드 변경 시 캐시 무효화 필요
- DB 수동 재생성: `sub/prepare_db.py` 또는 `python3 -c "from data import load_to_db; load_to_db()"`
