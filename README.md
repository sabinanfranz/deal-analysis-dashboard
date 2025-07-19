# Deal 데이터 분석 대시보드

B2B 거래 데이터를 분석하는 Streamlit 웹 애플리케이션입니다.

## 🚀 기능

- **월별 체결액 분석**: 월별 체결액 추이 및 체결건수 분석
- **담당자별 체결액 분석**: 담당자별 성과 분석 및 차트 시각화

## 📊 데이터 소스

- `all_deal`: 전체 거래 데이터
- `won_deal`: 성사된 거래 데이터  
- `retention`: 고객 유지 데이터

## 🛠️ 설치 및 실행

### 로컬 실행
```bash
# 패키지 설치
pip install -r requirements.txt

# 앱 실행
streamlit run streamlit_app.py
```

### 웹 배포 (Streamlit Cloud)

1. **GitHub에 코드 업로드**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/yourusername/your-repo-name.git
   git push -u origin main
   ```

2. **Streamlit Cloud에서 배포**
   - [share.streamlit.io](https://share.streamlit.io) 접속
   - GitHub 계정 연결
   - 저장소 선택
   - 배포 완료!

## 📁 파일 구조

```
├── streamlit_app.py      # 메인 앱 파일
├── prepare_db.py         # 데이터베이스 준비
├── query_db.py          # 데이터베이스 조회
├── deals.db             # SQLite 데이터베이스
├── requirements.txt      # Python 패키지 목록
└── README.md           # 프로젝트 설명
```

## 🔧 기술 스택

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: SQLite
- **Visualization**: Plotly
- **Data Processing**: Pandas

## 📈 분석 기능

### 월별 체결액 분석
- 월별 체결액 추이 차트
- 월별 체결건수 분석
- 연도별 구분 시각화

### 담당자별 체결액 분석  
- 담당자별 총 체결액 (상위 10명)
- 담당자별 평균 체결액
- 성과 지표 대시보드 