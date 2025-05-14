import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# S&P 500 종목 리스트
@st.cache_data(ttl=86400)
def get_sp500_symbols():
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = table[0]
    return df[['Symbol', 'GICS Sector']]

# 시가총액 가져오기
def get_market_cap(symbol):
    try:
        ticker = yf.Ticker(symbol)
        cap = ticker.info.get("marketCap", None)
        if cap:
            return cap, f"{cap / 1_000_000_000:.2f}B"
        return None, None
    except:
        return None, None

# DeMark 분석 함수
def current_demark_status(symbol):
    df = yf.download(symbol, period="3mo")
    if df.empty or len(df) < 30:
        return "데이터 부족", None, None

    df['Close-4'] = df['Close'].shift(4)
    df['Close-2'] = df['Close'].shift(2)
    df['Setup'] = None
    df['Countdown'] = 0

    setup_count = 0
    setup_indices = []

    for i in range(4, len(df)):
        try:
            if df['Close'][i] < df['Close-4'][i]:
                setup_count += 1
                if setup_count == 9:
                    df.loc[df.index[i], 'Setup'] = "하락"
                    setup_indices.append(i)
                    setup_count = 0
            else:
                setup_count = 0
        except:
            continue

    if not setup_indices:
        return "Setup 미완료", df, None

    setup_done_index = setup_indices[-1]
    countdown_count = 0

    for j in range(setup_done_index + 1, len(df)):
        try:
            if df['Close'][j] < df['Close-2'][j]:
                countdown_count += 1
                df.loc[df.index[j], 'Countdown'] = countdown_count
        except:
            continue

    if countdown_count >= 13:
        status = "Countdown 13 (Signal)"
    elif countdown_count > 0:
        status = f"Countdown {countdown_count}/13"
    else:
        status = "Setup 완료 (Countdown 시작 전)"

    return status, df, "하락"

# Streamlit 앱
st.title("📊 S&P 500 DeMark Setup + Countdown")

if st.button("전체 분석 시작"):
    sp500 = get_sp500_symbols()
    results = []

    with st.spinner("분석 중..."):
        for _, row in sp500.iterrows():
            symbol = row['Symbol']
            sector = row['GICS Sector']
            try:
                status, _, direction = current_demark_status(symbol)
                print(symbol, status)
                if ("Setup" in status or "Countdown" in status) and "미완료" not in status and status != "데이터 부족":
                    cap_raw, cap_str = get_market_cap(symbol)
                    results.append({
                        "종목": symbol,
                        "상태": status,
                        "방향": direction,
                        "업종": sector,
                        "시가총액": cap_str,
                        "시총_RAW": cap_raw
                    })
            except:
                continue

    if results:
        df_result = pd.DataFrame(results)
        df_result = df_result.sort_values(by="시총_RAW", ascending=False)

        st.subheader("🔍 분석 결과 (클릭해서 차트 확인)")
        gb = GridOptionsBuilder.from_dataframe(df_result.drop(columns=["시총_RAW"]))
        gb.configure_selection(selection_mode="single", use_checkbox=False)
        grid_options = gb.build()

        grid_response = AgGrid(
            df_result.drop(columns=["시총_RAW"]),
            gridOptions=grid_options,
            update_mode=GridUpdateMode.SELECTION_CHANGED,
            height=400,
            allow_unsafe_jscode=True
        )

        selected = grid_response['selected_rows']
        if selected:
            selected_symbol = selected[0]['종목']
            st.markdown(f"### 📈 {selected_symbol} 차트")
            status, df, direction = current_demark_status(selected_symbol)

            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(df.index, df['Close'], label='Close')

            setup_df = df[df['Setup'].notnull()]
            ax.scatter(setup_df.index, setup_df['Close'], color='orange', label=f"Setup 9 ({direction})")

            if 13 in df['Countdown'].values:
                countdown_df = df[df['Countdown'] == 13]
                ax.scatter(countdown_df.index, countdown_df['Close'], color='red', label="Countdown 13")

            ax.legend()
            ax.set_title(f"{selected_symbol} DeMark 차트")
            st.pyplot(fig)
    else:
        st.warning("Setup이 완료된 종목이 없습니다. 다시 시도하거나 조건을 완화해 보세요.")
