# streamlit_app.py
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go

DB_PATH = "deals.db"

@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

con = get_connection()
cur = con.cursor()

st.title("Deal 데이터 분석 대시보드")

# 메뉴바 선택
menu = st.sidebar.selectbox(
    "분석 메뉴",
    ("월별 체결액 분석", "담당자별 체결액 분석")
)

if menu == "월별 체결액 분석":
    st.header("📊 월별 체결액 분석")
    
    # 월별 체결액 데이터 조회
    monthly_data = pd.read_sql_query("""
        SELECT 
            체결년도,
            체결월,
            SUM(CAST([실제 수주액] AS REAL)) as 총_체결액,
            COUNT(*) as 체결건수
        FROM won_deal 
        WHERE 체결년도 IS NOT NULL AND 체결월 IS NOT NULL
        GROUP BY 체결년도, 체결월
        ORDER BY 체결년도, 체결월
    """, con)
    
    if not monthly_data.empty:
        # 월별 체결액 차트
        fig_amount = px.line(monthly_data, 
                            x='체결월', 
                            y='총_체결액',
                            color='체결년도',
                            title='월별 체결액 추이',
                            labels={'총_체결액': '총 체결액', '체결월': '월'})
        st.plotly_chart(fig_amount)
        
        # 월별 체결건수 차트
        fig_count = px.bar(monthly_data, 
                          x='체결월', 
                          y='체결건수',
                          color='체결년도',
                          title='월별 체결건수',
                          labels={'체결건수': '체결 건수', '체결월': '월'})
        st.plotly_chart(fig_count)
        
        # 데이터 테이블
        st.subheader("📋 월별 체결 데이터")
        st.dataframe(monthly_data)
        
        # 요약 통계
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("총 체결액", f"{monthly_data['총_체결액'].sum():,.0f}원")
        with col2:
            st.metric("총 체결건수", f"{monthly_data['체결건수'].sum():,}건")
        with col3:
            st.metric("평균 월 체결액", f"{monthly_data['총_체결액'].mean():,.0f}원")
    else:
        st.warning("체결 데이터가 없습니다.")

elif menu == "담당자별 체결액 분석":
    st.header("👥 담당자별 체결액 분석")
    
    # 담당자별 체결액 데이터 조회
    sales_data = pd.read_sql_query("""
        SELECT 
            담당자_name,
            SUM(CAST([실제 수주액] AS REAL)) as 총_체결액,
            COUNT(*) as 체결건수,
            AVG(CAST([실제 수주액] AS REAL)) as 평균_체결액
        FROM won_deal 
        WHERE 담당자_name IS NOT NULL AND 담당자_name != ''
        GROUP BY 담당자_name
        ORDER BY 총_체결액 DESC
    """, con)
    
    if not sales_data.empty:
        # 담당자별 총 체결액 차트
        fig_total = px.bar(sales_data.head(10), 
                          x='담당자_name', 
                          y='총_체결액',
                          title='담당자별 총 체결액 (상위 10명)',
                          labels={'총_체결액': '총 체결액', '담당자_name': '담당자'})
        fig_total.update_xaxes(tickangle=45)
        st.plotly_chart(fig_total)
        
        # 담당자별 평균 체결액 차트
        fig_avg = px.bar(sales_data.head(10), 
                        x='담당자_name', 
                        y='평균_체결액',
                        title='담당자별 평균 체결액 (상위 10명)',
                        labels={'평균_체결액': '평균 체결액', '담당자_name': '담당자'})
        fig_avg.update_xaxes(tickangle=45)
        st.plotly_chart(fig_avg)
        
        # 데이터 테이블
        st.subheader("📋 담당자별 체결 데이터")
        st.dataframe(sales_data)
        
        # 요약 통계
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("총 담당자 수", f"{len(sales_data)}명")
        with col2:
            st.metric("총 체결액", f"{sales_data['총_체결액'].sum():,.0f}원")
        with col3:
            st.metric("평균 담당자 체결액", f"{sales_data['총_체결액'].mean():,.0f}원")
    else:
        st.warning("담당자 데이터가 없습니다.")