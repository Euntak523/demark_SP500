import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt

# S&P 500 종목 리스트 가져오기 (캐싱, 하루 1회)
@st.cache_data(ttl=86400)
def get_sp500_symbols():
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = table[0]
    return df[['Symbol', 'GICS Sector']]

# 시가총액 가져오기 및 단위 변환
def get_market_cap(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        cap = info.get("marketCap", None)
        if cap is not None:
            return cap, f"{cap / 1_000_000_000:.2f}B"  # 숫자와 문자열 모두 반환
        return None, None
    except:
        return None, None

# DeMark 분석 함수 (가장 최근 Setup 기준으로 Countdown)
def current_demark_status(symbol):
    df = yf.download(symbol, period="3mo")
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

    setup_done_index = setup_indices[-1]  # 가장 최근 Setup 사용
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

# Streamlit 앱 시작
st.title("\ud83d\udcca S&P 500 DeMark Setup + Countdown 자동 분석기")

if "setup_results" not in st.session_state:
    st.session_state.setup_results = []
if "df_result" not in st.session_state:
    st.session_state.df_result = pd.DataFrame()
if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None

if st.button("전체 S&P 500 분석 시작"):
    sp500_df = get_sp500_symbols()
    setup_results = []

    with st.spinner("분석 중입니다. 잠시만 기다려 주세요..."):
        for _, row in sp500_df.iterrows():
            symbol = row['Symbol']
            sector = row['GICS Sector']
            try:
                status, df, direction = current_demark_status(symbol)
                if "Setup 미완료" not in status and status != "데이터 부족":
                    cap_raw, cap_str = get_market_cap(symbol)
                    setup_results.append({
                        "종목": symbol,
                        "상태": status,
                        "방향": direction,
                        "업종": sector,
                        "시가총액": cap_str,
                        "시총_RAW": cap_raw
                    })
            except:
                continue

    if setup_results:
        df_result = pd.DataFrame(setup_results)
        df_result = df_result.sort_values(by="시총_RAW", ascending=False)
        st.session_state.setup_results = setup_results
        st.session_state.df_result = df_result
        st.success(f"총 {len(df_result)}개 종목이 Setup 완료 상태입니다.")

if len(st.session_state.setup_results) > 0:
    df_result = st.session_state.df_result

    # 업종 필터 추가
    sectors = df_result["업종"].dropna().unique().tolist()
    selected_sector = st.selectbox("업종으로 필터링:", ["전체"] + sorted(sectors))
    if selected_sector != "전체":
        df_result = df_result[df_result["업종"] == selected_sector]

    # 종목 선택 및 차트 연동
    selected_row = st.data_editor(
        df_result.drop(columns=["시총_RAW"]),
        use_container_width=True,
        num_rows="dynamic",
        key="종목표",
        hide_index=True
    )

    selected_symbol = None
    if isinstance(selected_row, pd.DataFrame) and not selected_row.empty:
        selected_symbol = selected_row.iloc[0]["종목"]
        st.session_state.selected_symbol = selected_symbol
    else:
        selected_symbol = st.session_state.selected_symbol

    if selected_symbol:
        status, df, direction = current_demark_status(selected_symbol)
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df.index, df['Close'], label='Close Price')

        setup_df = df[df['Setup'].notnull()]
        ax.scatter(setup_df.index, setup_df['Close'], color='orange', label=f"Setup 9 ({direction})", marker='o')

        if 13 in df['Countdown'].values:
            countdown_13 = df[df['Countdown'] == 13]
            ax.scatter(countdown_13.index, countdown_13['Close'], color='red', label="Countdown 13", marker='x')

        ax.legend()
        ax.set_title(f"{selected_symbol} DeMark 분석 결과")
        st.pyplot(fig)
    else:
        st.warning("선택한 업종에 해당하는 종목이 없습니다.")
else:
    st.warning("Setup 완료된 종목이 없습니다.")
