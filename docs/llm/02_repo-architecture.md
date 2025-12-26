---
# Repo Architecture

## Purpose
- 어떤 폴더/파일을 수정하면 무엇이 바뀌는지 빠르게 파악하도록 책임 구역을 지도화합니다.

## Audience
- Primary: 외부 LLM / 신규 투입된 LLM 에이전트
- Secondary: 신규 개발자, 운영/분석 담당자

## Scope
- In-scope:
  - main.py, pages/, data.py, config.py, _part_view_base.py 등의 역할 맵
  - 상호 의존성과 변경 영향 범주
- Out-of-scope:
  - 함수 단위 구현 상세나 라인별 설명
  - 페이지별 계산 로직 심층 분석

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
- 폴더 구조나 핵심 모듈 책임이 변경될 때
- 새 주요 컴포넌트가 추가되거나 기존 것이 삭제될 때

## Open questions / TODO
- TODO: pages/ 최신 추가 항목 반영 여부 확인
---

## High-level repo map (what to edit for what)
- `main.py`: Streamlit 엔트리, 전체 페이지 설정. 변경 시 앱 타이틀/레이아웃만 영향.
- `data.py`: TXT 읽어 SQLite 재생성 + 캐시 로더. 전처리/스키마/캐시 키 수정 시 모든 페이지 데이터에 영향.
- `config.py`: 팀/파트/이름 매핑. 개인/파트/팀 대시보드 및 체결률 페이지 필터에 영향.
- `_part_view_base.py`: 팀/파트 뷰 공통 로직(2025 Won/생성 기준 표, 리텐션/신규 분리, 포맷 버킷). 변경 시 33/44 계열 페이지 전부 영향.
- `pages/`: 개별 화면. 파일 이름이 사이드바 메뉴가 되며, 각 파일은 독립적으로 `st.set_page_config` + 로더 사용.
- `docs/`: 구조/데이터/페이지/P&L/세일즈맵 문서. 온보딩/운영 참고용.
- `salesmap_sync/`: Salesmap API→SQLite 적재 유틸(앱 직접 사용 아님, 데이터 동기화 시 참조).
- `sub/`: 과거 분석/준비 스크립트(운영 보조, 앱 외부).

## Runtime flow
1. Streamlit 실행 → `main.py`가 페이지 설정 후 `pages/`를 네비게이션으로 노출.
2. 페이지 코드 import 시 `data.py`가 실행되어 TXT→SQLite 재생성 후 캐시된 연결/로더 제공 (`load_*`).
3. 각 페이지는 `load_*` 결과를 전처리/집계/시각화하여 UI 렌더.
4. `_part_view_base` 사용 페이지는 공통 캐시 데이터(`_load_won_2025`, `_load_all_for_chulgang`)를 공유.

## Data access contract (observed)
- 반드시 `data.py`의 `load_all_deal`, `load_won_deal`, `load_retention`, `load_accounting`를 통해 접근 (직접 파일/DB 읽기 금지).
- 캐시 키: TXT mtime + `CODE_SIG` (`data.py`). TXT나 로직이 바뀌면 `CODE_SIG` 변경 권장.
- DB는 WAL 모드이며 인덱스가 생성됨(`../database.md`). `.db-shm/.db-wal` 삭제 금지.

## Shared UI patterns
- `_part_view_base.render_part(team, part)`: Won/생성 데이터 리텐션/신규 분리, 포맷별 테이블(출강/온라인/포팅/스킬), 성사 가능성별 상세 탭. 33/44 계열 페이지에서 thin wrapper로 사용.
- 체결률/체결액 페이지 공통: 월별 1~12 필터, 억 단위 표시, 성사 가능성 맵(`확정/높음/낮음/LOST`).

## Configuration (config.py)
- 그룹/팀/파트 구조 및 이름→팀/파트 매핑 자동 생성(`NAME2TEAM`, `NAME2PART`).
- 이름 끝의 'B' 제거 규칙 포함. 매핑 변경 시 팀/파트/체결률 페이지 필터 및 탭 구성이 모두 변동.

## Extension checklist (new page)
- `pages/<order>_<name>.py` 생성, `st.set_page_config` 호출
- 필요한 로더 import (`from data import load_*`), 캐시 함수 사용 시 `@st.cache_data` 고려
- 팀/파트 의존 시 `config.py` 활용, 공통 패턴 필요 시 `_part_view_base` 재사용
- 금액 단위(억) 여부 명시, 월 범위/필터 확실히 설정
- 문서 업데이트: `docs/pages.md`와 `docs/llm/04_pages-guide.md` TODO 제거 필요

## Safety & pitfalls
- `data.py` import만으로 DB를 덮어쓰기 때문에 테스트 시 원본 TXT 백업 필요
- TXT 스키마 변경 시 전처리 실패/컬럼 누락 가능 → `data.py` 수정 + `CODE_SIG` 변경
- pages/docs 불일치: 예) docs/pages.md는 `pages/02_기업별_2025년_월별_체결액.py`로 표기되나 실제 파일은 `pages/03_기업별_2025년_월별_체결액.py` → TODO: 문서 동기화 필요
- Streamlit 캐시로 인해 수정 후 즉시 반영되지 않을 수 있음 → 캐시 클리어/재시작/`CODE_SIG` 업데이트
