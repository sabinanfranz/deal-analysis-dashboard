---
# Pages Guide

## Purpose
- pages/ 각 화면이 무엇을 다루는지와 공통 패턴(_part_view_base) 사용법을 빠르게 파악하게 합니다.

## Audience
- Primary: 외부 LLM / 신규 투입된 LLM 에이전트
- Secondary: 신규 개발자, 운영/분석 담당자

## Scope
- In-scope:
  - 페이지 카테고리 묶음과 역할 요약
  - 어떤 페이지를 수정해야 목적을 달성할지 맵 제공
  - _part_view_base 활용 지점 안내
- Out-of-scope:
  - 각 페이지의 세부 계산 로직
  - 시각화/차트 설정의 라인별 설명

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
- pages/에 새로운 주요 화면이 추가/삭제되거나 목적이 변경될 때
- _part_view_base 공통 패턴이 바뀔 때

## Open questions / TODO
- TODO: WIP 페이지(110/120/130) 로직 변경 시 본 문서를 다시 동기화
---

## Page taxonomy (purpose-based)
- 시뮬레이션: 01_2026 P&L Projection
- 체결액 추이/피벗: 02_2024~2025_체결액_추이, 03_기업별_2025년_월별_체결액, 88_기업_규모별_체결액
- 체결률(카테고리/포맷/리텐션/신규): 11, 12, 13, 14 시리즈 (생성형 AI/온라인, 리텐션/신규)
- 팀/파트 대시보드: 33_*, 44_* (기업교육 1·2팀 파트별, 온라인셀 포함)
- 리소스/운영 현황: 66_기업팀_리소스_현황, 77_공공팀_리소스_현황, 99_퇴사자_딜_리스트, 100_개인별_세일즈맵_누락_리스트, 110/120/130 WIP

## Page-by-page catalog
- `pages/01_2026 P&L Projection.py`: 2025 Won 데이터로 2026 매출/OP 시뮬레이션. 입력 슬라이더(목표/마진/고정비/삼성 계획), 모듈 A~D, KPI/월별 P&L/모듈별 테이블. 데이터: `load_won_deal()` (업로드 대체 옵션 코드상 존재).
- `pages/02_2024~2025_체결액_추이.py`: Won 기준 연/분기/월별 체결액 스택 차트. 필터: 과정포맷(대). 데이터: `load_won_deal()`.
- `pages/03_기업별_2025년_월별_체결액.py`: 2025년 기업별 월별 체결액 피벗(억), Won 원본/JSON 조회. 필터: 고객사 유형(기업/공공/기타), 연도(2023/2024/2025), 기업명 검색. 데이터: `load_won_deal()`, JSON용 `load_all_deal()`.
- `pages/11_사업부_생성형AI_체결률(리텐션).py`: 생성형 AI, 2025 생성 기준, 리텐션 고객, 출강 포맷(온라인 제외) 월별/3개월 이동평균 체결률 및 상세. 필터: 팀/개인 탭. 데이터: `load_all_deal()`, `load_retention()`, `config.TEAM_RAW/NAME2TEAM`.
- `pages/12_사업부_생성형AI_체결률(신규).py`: 생성형 AI, 2025 생성 기준, 신규(리텐션 제외), 출강 포맷. 필터: 팀/개인 탭 + 사이드바 기업 규모/과정포맷(대). 데이터: `load_all_deal()`, `load_retention()`.
- `pages/13_사업부_온라인_체결률(리텐션).py`: 온라인 포맷, 리텐션 고객 체결률/예정액(생성 기준), 생성형 AI 미최초 입과 필터 코드 포함. 데이터: `load_all_deal()`, `load_retention()`.
- `pages/14_사업부_온라인_체결률(신규).py`: 온라인 포맷, 신규 고객 체결률/예정액(생성 기준). 데이터: `load_all_deal()`, `load_retention()`.
- `pages/33_기업 1팀_1파트.py` / `33_기업 1팀_2파트.py`: `_part_view_base.render_part` 사용. 탭(전체/낮음높음/멤버), Won(수주예정)·생성 기준 표/상세, 포맷별 전용 블록.
- `pages/44_기업 2팀_1파트.py` / `44_기업 2팀_2파트.py` / `44_기업_2팀_온라인셀.py`: 위와 동일 패턴, 팀/파트만 다름.
- `pages/66_기업팀_리소스_현황.py`: 기업교육팀 운영 리소스 & 성사 가능성(2025, 일간/주간). 온라인 제외, won + all 확정 데이터 사용, 가중치 기반 일간/주간 집계와 상세 목록. 데이터: `load_won_deal()`, `load_all_deal()`.
- `pages/77_공공팀_리소스_현황.py`: 공공교육팀 운영 리소스 & 성사 가능성(2025, 일간/주간). 온라인 제외, won + all 확정 데이터 사용, 팀원 전원 포함 요약/상세. 데이터: `load_won_deal()`, `load_all_deal()`.
- `pages/88_기업_규모별_체결액.py`: 기업 규모별 2025 생성 기준 체결률/수주예정액(억) 표, 필터(딜 전환 유형/과정포맷/카테고리), 상세 딜 리스트. 데이터: `load_all_deal()`.
- `pages/99_퇴사자_딜_리스트.py`: 팀 매핑 밖 담당자(퇴사자 등) 2023~2025 연도별 체결액 요약 및 딜 리스트. 데이터: `load_won_deal()`.
- `pages/100_개인별_세일즈맵_누락_리스트.py`: 2024-10 이후 생성 데이터 품질 룰(R1~R15) 검사, 팀/개인/룰 필터, 상세 행 표시. 데이터: `load_all_deal()`.
- `pages/110_월별_FC_백오피스_검수(WIP).py`: accounting vs won 코스ID 정합성 체크(중복, acc-only/won-only/날짜/금액 불일치, 예외 규칙). 데이터: `load_accounting()`, `load_won_deal()`.
- `pages/120_공공_히스토리(WIP).py`: 공공/대학교 2025 월별 체결률(리텐션/직접, 포맷·카테고리 조합별 탭), 상태 Convert 제외. 데이터: `load_all_deal()`.
- `pages/130_공공·대학교_체결액_차트(WIP).py`: 공공기관/대학교 2025 Won 체결액 스택 차트/히스토그램(리텐션/직접, 포맷/카테고리). 데이터: `load_all_deal()`.

## Shared UX patterns
- 공통 탭/레이아웃: `_part_view_base`에서 탭(전체/낮음높음/멤버) + 리텐션/신규 테이블 + 상세 데이터프레임 렌더
- 금액 표시는 억 단위(1e8)로 반올림하여 표시하는 경우 다수(체결액/예정액)
- 월 범위 1~12 고정, 잘못된 월은 필터링
- 리텐션 세트는 `retention corp.txt` 기준(set membership)

## Where to change what
- 팀/파트/멤버 구성 변경: `config.py` → `_part_view_base` 및 33/44 페이지 자동 반영
- 체결률 정의/상태 맵 변경: `_part_view_base.STAT_MAP`, 개별 체결률 페이지의 STAT_MAP 동일 구조 참고
- 포맷 버킷 추가/정규화: `_part_view_base.FMT_LABELS` 및 각 페이지의 ONLINE_SET/포맷 필터 조정
- 2026 P&L 로직: `pages/01_2026 P&L Projection.py` (모듈/입력/산식), `../context-bridge.md`

## Known pitfalls
- 필수 컬럼 누락 시 Streamlit 에러: `성사 가능성`, `과정포맷(대)`, `생성년도/월`, `수주 예정액(종합)`이 없는 입력 데이터 업로드 시 실패 가능
- 리텐션/신규 분류는 기업명 정확도에 의존 → 공백/대소문자 차이 주의
- 월 범위 외 값은 무시되어 표가 비어 보일 수 있음
