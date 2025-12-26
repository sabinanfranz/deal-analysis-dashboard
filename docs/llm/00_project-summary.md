---
# Project Summary

## Purpose
- 이 프로젝트가 무엇을 하는지와 데이터 흐름의 큰 그림을 한 장으로 파악할 수 있게 합니다.

## Audience
- Primary: 외부 LLM / 신규 투입된 LLM 에이전트
- Secondary: 신규 개발자, 운영/분석 담당자

## Scope
- In-scope:
  - Streamlit 멀티페이지 앱의 역할과 흐름 요약
  - TXT → SQLite → pages 사용까지의 상위 데이터 플로우
- Out-of-scope:
  - 개별 페이지의 UI/계산 상세
  - 어카운트 전략 룰북 세부 내용

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
- 앱 구조나 데이터 플로우에 변화가 생길 때
- 새로운 주요 데이터 소스가 추가되거나 제거될 때

## Open questions / TODO
- TODO: 최근 변경된 데이터 흐름(있다면) 반영 여부 확인
---

## TL;DR
- Streamlit 멀티페이지 대시보드이며, 모든 데이터는 탭 구분 TXT 4종을 `data.py`가 SQLite(`deals.db`)로 재생성한 뒤 `load_*` 로더로 읽어 사용합니다.
- 캐시 무효화는 TXT mtime + `CODE_SIG` 기반으로 이루어져 import 시 자동 재빌드되며, 페이지는 해당 로더만 통해 데이터를 접근합니다.
- 핵심 뷰는 2026 P&L 시뮬레이션(`pages/01_2026 P&L Projection.py`)과 팀/파트/사업부별 체결률·체결액 모니터링 페이지들입니다.
- 팀/파트 공통 UI는 `_part_view_base.py`가 제공하며, 조직/이름 매핑은 `config.py`에서 관리합니다.

## What users get (outputs)
- 경영/세일즈 대시보드: 월별/연도별 체결액 추이, 기업별/포맷별/팀·파트별 요약 및 상세 테이블
- 시뮬레이션: 2026년 매출/OP Projection(Backlog/삼성 계획/리텐션/업셀/신규 Gap)
- 운영 뷰: 리소스 현황, 누락 리스트, 공공/대학 WIP 차트 등 (pages 폴더 참고)

## System diagram (data flow)
```mermaid
graph TD
  A[TXT 소스\nall deal / won deal / retention corp / accounting data] --> B[data.py import]
  B -->|_pre_accounting 등 전처리| C[SQLite deals.db\n(WAL, 인덱스)]
  C -->|load_all_deal / load_won_deal / load_retention / load_accounting| D[Streamlit pages/]
  D --> E[UI 렌더 및 다운로드]
```

## Repo highlights
- `main.py`: Streamlit page config 및 멀티페이지 엔트리
- `data.py`: TXT→SQLite 재생성, 전처리, 캐시된 로더
- `config.py`: 팀/파트/이름 매핑 및 헬퍼
- `_part_view_base.py`: 팀/파트 공통 렌더링, 리텐션/신규/포맷 표 구성
- `pages/`: 개별 화면 구현(체결액/체결률/리소스/P&L 등)
- `docs/`: 구현/데이터/페이지/P&L 문서화, Salesmap API 노트 포함

## Key concepts
- 딜 원천: `all deal.txt`(전체), `won deal.txt`(Won), `retention corp.txt`(리텐션 기업 리스트), `accounting data.txt`(회계 집계)
- 체결 기준: Won/수주예정 연·월 필터로 집계(억 단위 변환 빈번)
- 포맷/카테고리: `과정포맷(대)` 버킷(출강/온라인 구독·선택·포팅/스킬/기타/미기재)과 `카테고리(대)`
- 조직 맵: 기업교육 1·2팀, 각 파트/온라인셀 구성은 `config.py`에서 정의

## Extension points
- 새 페이지 추가: `pages/`에 파일 생성 + `st.set_page_config` + `data.load_*` 사용 + 필요 시 `config.py` 매핑 활용 (세부는 `docs/llm/04_pages-guide.md`)
- 새 데이터 소스: TXT 스키마 변경 시 `data.py` 전처리·`CODE_SIG` 수정, `docs/llm/03_data-layer.md` 참고
- P&L 가정 조정: `pages/01_2026 P&L Projection.py` 내 SimulationInputs/모듈 로직, `docs/llm/05_pnl-2026.md` 참고

## Non-goals
- 실시간 API 호출/동기화(기본은 사전 생성된 TXT/DB 사용)
- 외부 시장 리서치나 경쟁 분석
- 어카운트 전략 자동 분류 구현(룰북은 문서로만 존재)

## Pitfalls checklist
- TXT 변경 후 캐시가 남아있으면 `CODE_SIG` 변경 또는 재시작 필요 (`data.py`)
- TXT 결측 행은 로딩 시 제거되어 원본 행 수와 DB 행 수 차이 가능 (`docs/data-sources.md`)
- 월 필터: 1~12 범위 외 값은 필터링됨(여러 페이지/공통 베이스)
- 포맷/카테고리 라벨 정확도: 미기재/기타로 떨어질 수 있으므로 정규화 필요 시 확인
- WAL 파일(`deals.db-shm`, `deals.db-wal`) 삭제 금지 (`docs/database.md`)
