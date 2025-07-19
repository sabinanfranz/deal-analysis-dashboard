import streamlit as st

# ─── 전역 설정 ───
st.set_page_config(page_title="Deal Dashboard", layout="wide")

def set_style():
    st.markdown(
        """
        <style>
            /* 페이지 좌우 여백 축소 */
            .block-container {padding-left: 1rem; padding-right: 1rem;}

            /* 헤더 글꼴 크기 일괄 축소 */
            h1 {font-size:1.1rem;}
            h2 {font-size:0.95rem;}
            h3 {font-size:0.85rem;}
            h4 {font-size:0.8rem;}
            h5 {font-size:0.75rem;}
            h6 {font-size:0.7rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )

set_style()

# ─── 본문 ───
st.title("대시보드")

st.markdown(
    """
B2B 화이팅
    """
)