import streamlit as st
import pandas as pd
import os

st.title("📈 결과 (자동 업데이트)")

# 최신 파일명 탐색
files = sorted([f for f in os.listdir() if f.startswith("daily_result_") and f.endswith(".csv")])
if not files:
    st.warning("❗ 분석된 결과 파일이 없습니다.")
    st.stop()

latest_file = files[-1]
st.info(f"📄 최신 분석 파일: {latest_file}")

# CSV 불러오기
try:
    df = pd.read_csv(latest_file)

    if df.empty:
        st.warning("⚠️ 분석 결과가 없습니다. 분석된 종목이 없거나 저장이 되지 않았습니다.")
    else:
        # 보기 좋게 정리
        df = df.drop(columns=["시총_RAW"], errors="ignore")
        st.dataframe(df)

        st.markdown(f"✅ 총 {len(df)}개 종목 분석 완료")

except pd.errors.EmptyDataError:
    st.error("❌ 파일은 있지만 데이터가 비어 있습니다.")
except Exception as e:
    st.exception(e)
