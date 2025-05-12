import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.title("📊 DeMark Setup + Countdown 분석 결과 (자동 업데이트)")

# 가장 최근 CSV 파일 찾기
def get_latest_csv():
    files = [f for f in os.listdir() if f.startswith("daily_result_") and f.endswith(".csv")]
    if not files:
        return None
    files.sort(reverse=True)
    return files[0]

latest_file = get_latest_csv()

if latest_file:
    st.info(f"최신 분석 파일: {latest_file}")
    df = pd.read_csv(latest_file)

    # 업종 필터링 옵션
    sectors = df["업종"].dropna().unique().tolist()
    selected_sector = st.selectbox("업종 필터:", ["전체"] + sorted(sectors))
    if selected_sector != "전체":
        df = df[df["업종"] == selected_sector]

    # Countdown 필터링 옵션
    countdown_only = st.checkbox("Countdown 13만 보기", value=False)
    if countdown_only:
        df = df[df["상태"] == "Countdown 13 (Signal)"]

    # 표 표시
    st.dataframe(df.drop(columns=["시총_RAW"]))
else:
    st.warning("분석된 CSV 파일이 없습니다. GitHub Actions 또는 수동으로 먼저 분석 파일을 생성해주세요.")
