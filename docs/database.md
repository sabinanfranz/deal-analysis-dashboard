# SQLite DB 현황 (`deals.db`)

## 생성 방식
- `data.py` import 시 `load_to_db()`가 TAB TXT를 읽어 테이블을 교체 저장, PRAGMA(WAL, synchronous=NORMAL)와 인덱스 생성.
- Streamlit 캐시 키(`_files_sig` + `CODE_SIG`)가 TXT/코드 변경을 감지해 연결을 새로 만들고 DB를 다시 읽음.
- 독립 실행 스크립트: `sub/prepare_db.py`(동일 TXT 기반, pandas 의존), 또는 `python3 -c "from data import load_to_db; load_to_db()"`.

## 테이블/인덱스 스냅샷
- `all_deal` — 5,573행, 68열. Won/Lost/확정 등 전체 딜 원본. 인덱스: `idx_all_deal_name`(`담당자_name`).
- `won_deal` — 1,831행, 68열. Won 기준 딜. 인덱스: `idx_won_deal_name`(`담당자_name`).
- `retention` — 145행, 2열. 기업명 × 매출 티어.
- `accounting` — 2,393행, 25열. `accounting data.txt` 전처리 결과(집계년/월 파생, 포맷 보강, 코스 ID 별칭 등). 인덱스: `idx_acc_course`(`코스 ID`), `idx_acc_month`(`집계년`,`집계월`) 생성 시도.

## 사용 시 유의사항
- TXT에서 결측만 있는 행은 로딩 시 제거되므로 원본 행 수와 DB 행 수가 다를 수 있음.
- `load_*` 결과에는 일부 컬럼이 수치/날짜로 재캐스팅되고, `담당자_name`의 끝 `B` 제거, 금액 컬럼 숫자화 등 후처리가 포함됨.
- DB는 WAL 모드이므로 `.db-shm`, `.db-wal` 파일이 함께 생성됨(삭제 금지). 필요한 경우 동일 TXT로 재생성 가능.
