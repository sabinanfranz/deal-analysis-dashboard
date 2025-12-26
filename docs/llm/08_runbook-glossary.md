---
# Runbook & Glossary

## Purpose
- 운영/디버깅/개발 시 자주 쓰는 체크리스트와 용어집의 틀을 마련해 빠른 대응을 돕습니다.

## Audience
- Primary: 외부 LLM / 신규 투입된 LLM 에이전트
- Secondary: 운영 담당자, 신규 개발자, 분석 담당자

## Scope
- In-scope:
  - 자주 하는 작업 TOP5와 증상→조치 템플릿의 뼈대
  - 용어집 목차와 참고 위치 안내
- Out-of-scope:
  - 조직 내부 정책/보안 상세
  - 개별 문제 해결의 완료된 절차서

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
- 새로운 운영 런북이 추가되거나 주요 증상/조치 패턴이 바뀔 때
- 용어 정의가 업데이트될 때

## Open questions / TODO
- TODO: 현재 운영 체크리스트 우선순위 수집
---

## Top 5 runbooks

### 1) 데이터 갱신 (TXT 교체 후 반영)
- Preconditions: 최신 `all deal.txt`, `won deal.txt`, `retention corp.txt`, `accounting data.txt` 준비
- Steps:
  1. TXT 4종을 교체
  2. `python3 -c "from data import load_to_db; load_to_db()"` 실행 또는 앱 재시작(`data.py` import 시 자동 재빌드)
  3. 필요 시 `data.py`의 `CODE_SIG` 문자열 업데이트 후 저장
  4. 페이지에서 데이터 새로 고침 확인
- Expected: `deals.db` 재생성, Streamlit 캐시 키 변경으로 최신 데이터 로드
- Rollback: 이전 TXT 백업 복구 후 동일 절차 재실행

### 2) DB 재생성(수동)
- Preconditions: 현행 TXT가 유효하며 스키마 요구사항 충족
- Steps:
  1. `python3 sub/prepare_db.py` 또는 `python3 -c "from data import load_to_db; load_to_db()"`
  2. `deals.db`, `.db-shm`, `.db-wal` 생성 확인
- Expected: 4개 테이블/인덱스가 새로 생성 (`../database.md` 행 수 근사)
- Rollback: 이전 DB 백업 복구

### 3) 캐시 문제 해결(갱신 미반영)
- Preconditions: TXT/코드 변경 후 페이지가 옛 데이터 표시
- Steps:
  1. `data.py`의 `CODE_SIG` 문자열 변경 후 저장
  2. Streamlit 세션/서버 재시작
- Expected: Streamlit cache miss → DB 재로드 후 최신 데이터 반영
- Rollback: 이전 `CODE_SIG`로 복구 (필요 시)

### 4) 새 페이지 추가
- Preconditions: 요구사항/데이터 의존 파악 완료
- Steps:
  1. `pages/<order>_<name>.py` 생성, `st.set_page_config` 설정
  2. 필요한 로더(`load_*`) import, 필터/캐시 구성
  3. 팀/파트 의존 시 `config.py`, 공통 패턴 필요 시 `_part_view_base.render_part` 활용
  4. 문서 반영: `docs/pages.md` 및 `docs/llm/04_pages-guide.md` TODO 처리
- Expected: 사이드바에 새 페이지 노출, 데이터 정상 로드
- Rollback: 파일 삭제/이전 버전 복구

### 5) P&L/핵심 지표가 0 또는 비정상
- Preconditions: pages/01_2026 P&L Projection 결과 이상
- Steps:
  1. 입력 데이터 확인: `load_won_deal()` 결과가 2025 체결/금액>0인지
  2. 리텐션/포맷/채널 필터 확인(삼성/온라인 리텐션 제외 로직)
  3. Median 룩업 샘플 수 확인(<5 여부), 기본값 적용 여부 검토
  4. 사이드바 목표/마진/고정비 입력값 재확인
- Expected: 모듈별 매출이 존재하고 Gap 계산이 정상
- Rollback: 입력값 초기값으로 복귀, 데이터 최신본 재적재

## Troubleshooting matrix (증상 → 원인 → 확인 → 조치)
- 페이지 데이터가 비어 있음 → 월/연 필터 범위 밖(1~12, 2025 등) → 입력 데이터 연월 확인 → 필터 조정 또는 원본 수정
- 리텐션/신규 분류 오동작 → `retention corp.txt` 기업명 불일치 → 기업명 트리밍/대소문자 확인 → 파일 정리 후 재적재
- 체결액이 억 단위 아닌 원 단위 표시 → 숫자 캐스팅/스케일 미적용 → `수주 예정액(종합)` 변환 코드 확인 → 억 단위로 나누는 로직 적용
- accounting 포맷 누락 → `_pre_accounting` 포맷 보강 실패 → 포맷 컬럼 존재 여부 확인 → 로직 보강/기본값 추가
- DB 파일 없음 → 초기 실행 전 `deals.db` 미생성 → `load_to_db()` 실행 → DB/인덱스 생성 확인
- DB 파일 잠김/삭제 → WAL 파일 삭제 → 파일 존재 여부 확인 → TXT 기반 재생성, WAL 파일 유지 안내
- Salesmap 연동 실패 → `/tmp/salesmap.db` 없음/토큰 미설정 → 환경변수/아티팩트 확인 → `salesmap_sync/artifact_fetch.py` 또는 `fetch_salesmap.py` 실행
- Streamlit 캐시 stale → `CODE_SIG`/재시작 미실시 → 코드/파일 mtime 확인 → `CODE_SIG` 변경 후 재시작
- 페이지 KeyError(컬럼 없음) → TXT 스키마 변경 → 데이터 컬럼 리스트 확인 → `data.py`/페이지 전처리 업데이트
- P&L 모듈 금액 0 → 필터로 인해 딜 제외 또는 샘플 부족 → 리텐션/포맷 필터 조건 확인 → 조건 조정/데이터 보강

## Dev checklists
- 변경 전: 관련 문서 확인(`docs/llm/02_repo-architecture.md`, `docs/llm/03_data-layer.md`, `docs/llm/04_pages-guide.md`), 원본 TXT/DB 백업
- 변경 후: Streamlit 실행 확인, 핵심 페이지(00/02/03/11~14/33/44) 스모크 체크, 금액 단위/필터 정상 여부 검토, 캐시 무효화 적용(`CODE_SIG`)
- 문서: 관련 섹션 업데이트, TODO 해소 여부 기록

## Glossary (quick)
- 체결액: `수주 예정액(종합)`을 억 단위 변환한 값 (주요 페이지 공통)
- 리텐션/신규: `retention corp.txt` 포함 여부로 분리
- 과정포맷(대): 출강/복합/구독제(온라인)/선택구매(온라인)/포팅/스킬/기타/미기재
- S-tier: 체결액 규모 등급(S3≥1억, S2≥0.5억, S1≥0.25억, S0 기타)
- CODE_SIG: `data.py` 캐시 무효화용 문자열 (변경 시 캐시 리빌드)

## References
- 데이터/구현: `../implementation.md`, `../data-sources.md`, `../database.md`
- 페이지: `../pages.md`, `pages/01_2026 P&L Projection.py`, `_part_view_base.py`
- P&L 문맥/TODO: `../context-bridge.md`, `../TODO.md`
- Salesmap: `../salesmap_api_data_model.md`, `../salesmap_api_responses.md`
