import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

@st.cache_data(ttl=86400)
def get_sp500_symbols():
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = table[0]
    return df[['Symbol', 'GICS Sector']]

def get_market_cap(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        cap = info.get("marketCap", None)
        if cap is not None:
            return cap, f"{cap / 1_000_000_000:.2f}B"
        return None, None
    except:
        return None, None

def current_demark_status(symbol):
    df = yf.download(symbol, period="6mo")
    if df.empty or len(df) < 30:
        return "데이터 부족", None, None

    df = df.copy()
    df['Close-4'] = df['Close'].shift(4)
    df['Close-2'] = df['Close'].shift(2)
    df['Setup'] = None
    df['Countdown'] = 0

    setup_count = 0
    setup_indices = []
    setup_direction = None

    for i in range(4, len(df)):
        try:
            close = float(df.iloc[i]['Close'])
            close_4 = float(df.iloc[i]['Close-4'])
        except:
            continue

        if close < close_4:
            setup_count += 1
            if setup_count == 9:
                df.loc[df.index[i], 'Setup'] = "하락"
                setup_indices.append(i)
                setup_count = 0
        else:
            setup_count = 0

    if not setup_indices:
        return "최근 90일 기준 Setup 미완료", df, None

    setup_done_index = setup_indices[-1]
    setup_direction = "하락"

    countdown_count = 0
    for j in range(setup_done_index + 1, len(df)):
        try:
            close = float(df.iloc[j]['Close'])
            close_2 = float(df.iloc[j]['Close-2'])
        except:
            continue

        if close < close_2:
            countdown_count += 1
            df.loc[df.index[j], 'Countdown'] = countdown_count

    if countdown_count >= 13:
        status = "Countdown 13 (Signal)"
    elif countdown_count > 0:
        status = f"Countdown {countdown_count}/13"
    else:
        status = "Countdown 시작 전"

    return status, df, setup_direction

def backtest_countdown13(df):
    if df is None or 13 not in df['Countdown'].values:
        return "백테스트 불가"

    entry_index = df[df['Countdown'] == 13].index[-1]
    try:
        entry_price = df.loc[entry_index, 'Close']
        future_index = df.index.get_loc(entry_index) + 10
        if future_index >= len(df):
            return "10일 후 데이터 없음"
        future_price = df.iloc[future_index]['Close']
        return f"📈 10일 후 수익률: {(future_price - entry_price) / entry_price * 100:.2f}%"
    except:
        return "백테스트 계산 실패"

# 앱 시작
st.set_page_config(layout="wide")
st.title("📊 S&P 500 DeMark + 이동평균선 + 백테스트 자동 분석기")

if "setup_results" not in st.session_state:
    st.session_state.setup_results = []
if "df_result" not in st.session_state:
    st.session_state.df_result = pd.DataFrame()

if st.button("전체 S&P 500 분석 시작"):
    sp500_df = get_sp500_symbols()
    setup_results = []

    with st.spinner("분석 중입니다..."):
        for _, row in sp500_df.iterrows():
            symbol = row['Symbol']
            sector = row['GICS Sector']
            try:
                status, df, direction = current_demark_status(symbol)
                if "Setup 미완료" not in status and status != "데이터 부족":
                    cap_raw, cap_str = get_market_cap(symbol)
                    setup_results.append({
                        "Symbol": symbol,
                        "Status": status,
                        "Direction": direction,
                        "Sector": sector,
                        "MarketCap": cap_str,
                        "MarketCap_RAW": cap_raw
                    })
            except:
                continue

    if setup_results:
        df_result = pd.DataFrame(setup_results)
        df_result = df_result.sort_values(by="MarketCap_RAW", ascending=False)
        st.session_state.setup_results = setup_results
        st.session_state.df_result = df_result
        st.success(f"총 {len(df_result)}개 종목이 Setup 완료 상태입니다.")

if len(st.session_state.setup_results) > 0:
    df_result = st.session_state.df_result

    sectors = df_result["Sector"].dropna().unique().tolist()
    selected_sector = st.selectbox("업종 필터링:", ["전체"] + sorted(sectors))
    if selected_sector != "전체":
        df_result = df_result[df_result["Sector"] == selected_sector]

    gb = GridOptionsBuilder.from_dataframe(df_result.drop(columns=["MarketCap_RAW"]))
    gb.configure_selection(selection_mode="single", use_checkbox=False)
    grid_options = gb.build()

    grid_response = AgGrid(
        df_result.drop(columns=["MarketCap_RAW"]),
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=500,
        fit_columns_on_grid_load=True
    )

    if (
        grid_response is not None and
        "selected_rows" in grid_response and
        len(grid_response["selected_rows"]) > 0
    ):
        try:
            # ✅ 이 부분이 핵심 수정!
            selected_row_df = pd.DataFrame(grid_response["selected_rows"])
            selected_row = selected_row_df.iloc[0]
            selected_symbol = selected_row.get("Symbol") or selected_row.get("종목")

            if not selected_symbol:
                st.error("❌ 선택한 행에서 Symbol 값을 찾을 수 없습니다.")
            else:
                st.markdown(f"### {selected_symbol} 차트 및 백테스트")
                status, df, direction = current_demark_status(selected_symbol)

                if df is not None:
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['MA60'] = df['Close'].rolling(window=60).mean()
                    df['MA120'] = df['Close'].rolling(window=120).mean()

                    fig, ax = plt.subplots(figsize=(12, 5))
                    ax.plot(df.index, df['Close'], label='Close Price', linewidth=1.2)
                    ax.plot(df.index, df['MA20'], label='MA20', linestyle='--')
                    ax.plot(df.index, df['MA60'], label='MA60', linestyle=':')
                    ax.plot(df.index, df['MA120'], label='MA120', linestyle='-.', alpha=0.8)

                    setup_df = df[df['Setup'].notnull()]
                    ax.scatter(setup_df.index, setup_df['Close'], color='orange', label=f"Setup 9 ({direction})", marker='o')

                    if 13 in df['Countdown'].values:
                        countdown_13 = df[df['Countdown'] == 13]
                        ax.scatter(countdown_13.index, countdown_13['Close'], color='red', label="Countdown 13", marker='x')

                    ax.legend()
                    ax.set_title(f"{selected_symbol} DeMark 분석 + 이동평균선")
                    st.pyplot(fig)

                    result = backtest_countdown13(df)
                    st.markdown(f"#### 📊 백테스트 결과: {result}")
                else:
                    st.warning("해당 종목의 데이터가 부족합니다.")
        except Exception as e:
            st.error(f"선택 종목 처리 중 오류 발생: {e}")
    else:
        st.info("표에서 종목을 클릭하면 자동으로 차트가 표시됩니다.")
else:
    st.warning("Setup 완료된 종목이 없습니다.")
