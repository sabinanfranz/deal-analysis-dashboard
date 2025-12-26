---
# Account Strategy Knowledge Base (v1)

## Purpose
- buyer_type/maturity/genai_stage/cp_pattern/acc_type 등 어카운트 전략 룰북의 출처와 적용 범위를 명시해 LLM이 남용하지 않도록 합니다.

## Audience
- Primary: 외부 LLM / 신규 투입된 LLM 에이전트
- Secondary: 신규 개발자, 영업 전략/분석 담당자

## Scope
- In-scope:
  - 룰북 필드 정의와 활용 경고를 요약 수준으로 정리
  - 적용 범위와 편향(상위 계정 중심 등) 주의사항
- Out-of-scope:
  - 실제 자동 분류/코드 구현
  - 룰 상세 값 목록의 전부

## Sources of truth (do not guess)
- (반드시 링크로) 이 문서는 아래 파일만을 근거로 한다:
  - ../README.md
  - ../implementation.md
  - ../data-sources.md
  - ../database.md
  - ../pages.md
  - ../context-bridge.md
  - ../TODO.md
  - ../../Day1 B2B 어카운트 전략 분석용 지식 베이스 문서 (v1).txt

## Update triggers
- 어카운트 전략 룰북 문서가 업데이트되거나 버전이 변경될 때
- 룰 적용 범위/편향 관련 경고가 바뀔 때

## Open questions / TODO
- TODO: 지식 베이스 문서 최신 버전 경로 확인
---

## Scope & bias warnings
- TODO(근거 필요): 원본 문서(`../../Day1 B2B 어카운트 전략 분석용 지식 베이스 문서 (v1).txt`)가 리포에 없어 룰 편향/범위 기술 불가. 상위계정 중심 편향 여부 확인 필요.

## Field definitions (needs source)
- buyer_type: TODO(근거 필요)
- online_maturity / offline_maturity: TODO(근거 필요)
- genai_stage: TODO(근거 필요)
- cp_pattern: TODO(근거 필요)
- acc_type: TODO(근거 필요)

## Strategy implications
- TODO(근거 필요): 각 분류별 제안/액션 항목 원문 확인 후 요약 필요

## Output template (draft)
- 입력(JSON 예시):
  - `company_profile`: 산업/규모/과거 거래/문의 채널
  - `signals`: 제품 관심도/GenAI 활용/구독 경험 등
- 출력 권장 형식:
  - `classification`: {buyer_type, online_maturity, offline_maturity, genai_stage, cp_pattern, acc_type}
  - `rationale`: 근거 신호 목록(텍스트 인용)
  - `strategy`: 추천 메시지/제안/리스크
  - `next_actions`: 구체 액션 3~5개
- TODO: 원문 근거 확보 후 값 목록/예시 보강

## Examples
- TODO(근거 필요): 원문 예시 확보 후 요약 추가
