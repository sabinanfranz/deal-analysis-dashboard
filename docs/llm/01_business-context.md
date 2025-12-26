---
# Business Context (Day1 B2B)

## Purpose
- B2B 제품/서비스/조직 용어를 정리해 LLM이 비즈니스 맥락을 혼동하지 않도록 합니다.

## Audience
- Primary: 외부 LLM / 신규 투입된 LLM 에이전트
- Secondary: 신규 개발자, 운영/분석 담당자

## Scope
- In-scope:
  - Day1 B2B 제품 4축, 조직 구조, 핵심 용어 요약
  - 사용자 프로필과 역할에 대한 기본 맥락
- Out-of-scope:
  - 시장/경쟁 리서치
  - 외부 자료 인용 및 해석

## Sources of truth (do not guess)
- (반드시 링크로) 이 문서는 아래 파일만을 근거로 한다:
  - ../README.md
  - ../implementation.md
  - ../data-sources.md
  - ../database.md
  - ../pages.md
  - ../context-bridge.md
  - ../TODO.md
  - ../../데이원컴퍼니 B2B 제품 및 서비스 소개.txt
  - ../../데이원컴퍼니 B2B사업부 조직도.txt
  - ../../사용자 프로필.txt

## Update triggers
- 제품 라인업/서비스 축이 바뀌거나 용어 정의가 변경될 때
- 조직 구조나 주요 사용자 프로필 문서가 갱신될 때

## Open questions / TODO
- TODO: 상단 TXT 문서 최신본 존재 여부 확인
---

## Business in one page
- 근거 부족: 레포에 제품/조직/프로필 TXT가 존재하지 않아 구체 제안 불가 → TODO(근거 필요).
- 현재 레포에서 확인 가능한 맥락: 기업교육 B2B 세일즈 대시보드이며, 2025년 Won/생성 데이터를 기반으로 체결액/체결률/리텐션/신규/업셀/2026 P&L 시뮬레이션을 제공합니다 (`../implementation.md`, `pages/01_2026 P&L Projection.py`).

## Product / Service map (서비스 4축)
- TODO(근거 필요): ../../데이원컴퍼니 B2B 제품 및 서비스 소개.txt 부재로 4축/제품군 세부 정의 불가.
- 레포에서 등장하는 포맷/카테고리: `과정포맷(대)` = 출강, 복합, 구독제(온라인), 선택구매(온라인), 포팅, 스킬, 기타/미기재. `카테고리(대)`에 생성형 AI 등이 포함됨(`_part_view_base.py`, `pages/11_...`).

## Org map (light)
- 기업교육그룹 조직(코드 근거: `config.py`):
  - 그룹장: 박종협
  - 팀장: 기업교육 1팀=김별, 기업교육 2팀=정선희
  - 파트: 1팀(1파트/2파트), 2팀(1파트/2파트/온라인셀) — 멤버 목록은 `config.PART_STRUCTURE` 참고
- TODO(근거 필요): ../../데이원컴퍼니 B2B사업부 조직도.txt 부재로 공식 조직도/기타 기능 조직 확인 필요.

## Terminology glossary (repo-observed)
- 출강: 오프라인/대면 교육 포맷 (과정포맷(대) 값)
- 구독제(온라인)/선택구매(온라인)/포팅: 온라인 포맷 유형 (과정포맷(대))
- 스킬: 별도 포맷 라벨, 세부 정의는 근거 부족 → TODO(근거 필요)
- 생성형 AI: 카테고리(대) 값, 리텐션/신규 체결률 페이지 대상
- 리텐션: `retention corp.txt`에 있는 기업을 리텐션으로 취급 (`data.py`, `_part_view_base.py`)
- 신규: 리텐션 기업이 아닌 딜
- S-tier: 체결액 규모에 따른 등급(S3≥1억, S2≥0.5억, S1≥0.25억, S0 그 외) — `pages/01_2026 P&L Projection.py`
- 체결률: 성사 가능성 기준(확정/높음 등)으로 계산하는 월별 지표(여러 pages)
- TODO(근거 필요): AX, SkillMatch, LXP, SCORM/포팅, 구독/자유입 등 세부 정의 → 상단 TXT 미존재

## How used in this repo
- 포맷/카테고리 라벨은 페이지 필터 및 버킷팅에 직접 사용: `_part_view_base.py`, `pages/11_~14_...`, `pages/03_...`
- 팀/파트 매핑은 개인/파트 대시보드와 체결률 탭 구성에 사용: `config.py`, `_part_view_base.py`
- 2026 P&L 시뮬레이션은 2025 Won 딜(억 단위)에서 채널/기업 규모/S-tier를 기반으로 리드타임/교육기간 룩업을 만든 뒤 모듈별 딜을 생성: `pages/01_2026 P&L Projection.py`, `../context-bridge.md`
- TODO: 사용자 프로필/역할 기반 권한 또는 뷰 차등 여부 확인(근거 없음)
