# 데이터 소스 & 전처리 현황

## 원본 TXT 스냅샷 (UTF-8, 탭 구분)
- `all deal.txt`: 5,583행·68열, mtime 2025-12-03 06:08:28. 주요 컬럼 예시: 생성 날짜, 기업명, 이름, 팀_0_name, 담당자_name, 파이프라인/단계, 상태, 성사 가능성 등. `data.py` 로딩 시 완전 결측 행을 제거해 DB에는 5,573행이 적재됨.
- `won deal.txt`: 1,839행·68열, mtime 2025-12-03 06:08:54. 컬럼 구성은 `all deal`과 동일, Won 기준 딜 서브셋.
- `retention corp.txt`: 145행·2열, mtime 2025-07-19 19:23:02. 컬럼: 기업명, 매출 티어.
- `accounting data.txt`: 2,460행·15열, mtime 2025-11-06 22:47:24. 결제/집계월/금액/포맷/코스ID/교육과정명 등 포함.

## 전처리 포인트
- `data.py` `_pre_accounting`:
  - 헤더 공백·BOM 제거, 숫자형(계약금액/코스일수/일수당결제금액) 표준화, 불리언/날짜 파싱.
  - `매출집계월` → 집계년/집계월/월초 파생, `코스 ID` 별칭·문자열 컬럼 추가, 수강 시작/종료 파생.
  - 포맷 컬럼 보강, 교육과정명에 `(B2B_SMB)` 포함 시 제외.
- `load_*` 호출은 Streamlit 캐시에 올라가며, TXT mtime 변화 또는 `CODE_SIG` 변경 시 자동 새로고침 후 DB 재생성.

## 데이터 갱신 방법
1) 위 TXT 파일을 최신 데이터로 교체/수정.  
2) 앱을 재시작하거나 `data.py`를 다시 import → `load_to_db()`가 자동 실행되어 `deals.db` 재빌드.  
   - 필요 시 수동 실행: `python3 -c "from data import load_to_db; load_to_db()"` 또는 `python3 sub/prepare_db.py`.

## 기타 소스
- `fc_b2b_salesmap_api (3).py`: Salesmap API → Google Sheets 전송용 Colab 스크립트(구글 서비스 계정 키 필요). 앱 로직과 직접 연결되지는 않으나 데이터 추출 경로로 추정.
