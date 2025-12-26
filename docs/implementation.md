# 구현 & 데이터 흐름

## 앱 개요
- Streamlit 멀티페이지 앱. `main.py`에서 페이지 설정만 하고, `pages/` 폴더 내 파일이 네비게이션을 구성.
- 모든 데이터 접근은 `data.py`의 로더(`load_all_deal`, `load_won_deal`, `load_retention`, `load_accounting`)를 통해 수행.
- 팀/파트별 공통 UI 로직은 `_part_view_base.py`로 공유하고, 개별 페이지 파일에서 얇게 래핑.

## 핵심 모듈
- `data.py`
  - TAB 구분 TXT(`all deal.txt`, `won deal.txt`, `retention corp.txt`, `accounting data.txt`)를 읽어 `deals.db`로 재생성.
  - `accounting data.txt`는 `_pre_accounting`으로 컬럼/숫자/날짜 파싱, 포맷 보강, B2B_SMB 행 제외 후 저장.
  - `CODE_SIG`와 TXT mtime을 캐시 키에 포함해 로직/파일 변경 시 Streamlit 캐시를 무효화.
  - 인덱스: `idx_all_deal_name`, `idx_won_deal_name`, `idx_acc_course`, `idx_acc_month`(마지막 두 개는 지원될 때만 생성).
- `config.py`
  - 그룹/팀/파트 구조와 이름 매핑(`NAME2TEAM`, `NAME2PART`) 제공. 파트/팀원 리스트를 함수로 조회 가능.
- `_part_view_base.py`
  - 2025년 기준 Won/생성 데이터를 리텐션·신규/포맷별로 집계·상세화하는 공통 뷰.
  - 포맷 구간(`FMT_LABELS`), 상태 표준화(`STAT_MAP`), 리텐션 세트 적용 등 데이터 표준화 포함.
- `context-bridge.md`
  - `pages/01_2026 P&L Projection.py` 로직 설명(Backlog/삼성 계획/온라인 리텐션/Upsell/신규 모듈, P&L 산식, 리드타임 룩업 규칙 등).

## 데이터 플로우
1) TAB TXT 갱신 → 2) `data.py` import 시 `load_to_db()`가 SQLite를 재생성(WAL, 인덱스) →  
3) Streamlit 캐시 키(`_sig`)가 TXT mtime과 `CODE_SIG`를 묶어 최신 DB를 다시 읽음 →  
4) 페이지에서 `load_*` 호출로 DataFrame 수신 후 각 페이지별 전처리/시각화 수행.

## 업데이트 시 체크포인트
- TXT 스키마 변경이나 전처리 로직 수정 시 `data.py`의 `CODE_SIG` 문자열을 바꿔 캐시를 강제 무효화.
- 새 페이지 추가 시 필수: `st.set_page_config(...)` 설정, 공통 로더 사용, 팀/파트 매핑이 필요하면 `config.py` 활용.
- DB를 수동으로 재생성하려면 `sub/prepare_db.py` 실행 또는 `python3 -c "from data import load_to_db; load_to_db()"` 실행(필요 패키지 사전 설치).
