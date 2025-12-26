---
# LLM Onboarding Pack

## Purpose
- 이 폴더 전체를 어떻게 읽고 활용하면 되는지, 5분 안에 온보딩 루트를 안내합니다.

## Audience
- Primary: 외부 LLM / 신규 투입된 LLM 에이전트
- Secondary: 신규 개발자, 운영/분석 담당자

## Scope
- In-scope:
  - LLM 온보딩 팩 문서 맵(링크)과 추천 읽기 순서
  - 빠른 시작 가이드 및 주의사항 요약
- Out-of-scope:
  - 코드/로직의 상세 구현
  - 2026 P&L 세부 산식

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
- 문서 구조/목록이 바뀌거나, 온보딩 순서가 변할 때
- 신규 LLM용 경고/주의사항이 추가될 때

## Open questions / TODO
- TODO: 온보딩 순서에서 강조해야 할 최신 우선순위 확인
---

## Overview
- 목적: 외부 LLM/신규 개발자가 5분 내에 레포 구조, 데이터 흐름, 핵심 페이지, 운영 제약을 파악하고 안전하게 수정 착수하도록 돕습니다.
- 기대 결과: 필요한 문서를 빠르게 찾고, 데이터/캐시/페이지 의존을 이해해 실수 없이 변경할 수 있음.

## 5-Minute Onboarding Route
1. `docs/llm/00_project-summary.md` — 앱/데이터 흐름 큰 그림 확인
2. `docs/llm/02_repo-architecture.md` — 파일/폴더 책임과 실행 경로 파악
3. `docs/llm/03_data-layer.md` — TXT→SQLite 갱신/검증 절차 숙지
4. `docs/llm/04_pages-guide.md` — 필요한 화면 위치와 수정 지점 확인
5. 상황별: P&L 수정은 `docs/llm/05_pnl-2026.md`, Salesmap 연동은 `docs/llm/07_salesmap-api.md`, 운영 체크는 `docs/llm/08_runbook-glossary.md`

## Doc Map (what each file gives you)
- `00_project-summary.md`: 프로젝트 한 장 요약, 데이터/흐름/확장 포인트
- `01_business-context.md`: Day1 B2B 비즈/조직/용어 맥락(TODO 포함)
- `02_repo-architecture.md`: 파일/모듈 책임과 런타임 흐름
- `03_data-layer.md`: TXT 소스, 전처리, DB 재생성/검증 런북
- `04_pages-guide.md`: pages/ 카탈로그, 공통 패턴, 수정 포인터
- `05_pnl-2026.md`: 2026 P&L Projection 개념·입출력·모듈
- `06_account-strategy-knowledge.md`: 어카운트 전략 룰북(v1) 범위/주의(TODO)
- `07_salesmap-api.md`: Salesmap API 문서 위치, 모델/응답 특징
- `08_runbook-glossary.md`: 운영 런북, 트러블슈팅, 용어집

## Where the truth lives
- 1차: `../implementation.md`, `../pages.md`, `../data-sources.md`, `../database.md`
- 2차: 실제 코드 `main.py`, `data.py`, `config.py`, `_part_view_base.py`, `pages/`
- 3차: 레포 루트 TXT(제품/조직/프로필/어카운트 전략) — 현재 리포에 없음 → TODO(확인 필요)

## Common tasks → start here
- 데이터 갱신/DB 재생성/캐시: `docs/llm/03_data-layer.md`
- 페이지 추가/수정: `docs/llm/02_repo-architecture.md` + `docs/llm/04_pages-guide.md`
- 2026 P&L 가정/모듈 수정: `docs/llm/05_pnl-2026.md`
- Salesmap API 연동/DB 최신화: `docs/llm/07_salesmap-api.md`
- 운영/디버깅 체크: `docs/llm/08_runbook-glossary.md`

## Guardrails
- 추측 금지: 근거 없는 내용은 작성하지 말고 `TODO(근거 필요)`로 명시
- 상대경로 링크 사용, 민감정보(.env, 토큰) 노출 금지
- 캐시/DB 부작용 확인: `data.py`는 import 시 DB를 재생성하고 Streamlit 캐시 키에 mtime+`CODE_SIG`를 포함함

## Quick navigation
- 문서: `../README.md`, `../implementation.md`, `../data-sources.md`, `../database.md`, `../pages.md`, `../context-bridge.md`, `../TODO.md`
- 코드: `main.py`, `data.py`, `config.py`, `_part_view_base.py`, `pages/01_2026 P&L Projection.py`
- 데이터: `all deal.txt`, `won deal.txt`, `retention corp.txt`, `accounting data.txt`

## Change log
- v0.1: 초기 온보딩 팩 작성 (LLM용)
