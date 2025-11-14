# pages/31_기업_1팀_1파트.py
import streamlit as st
from _part_view_base import render_part   # ← 같은 pages 폴더라 이 import가 안정적

st.set_page_config(page_title="기업 1팀 1파트", layout="wide")
render_part("기업교육 1팀", "1파트")
