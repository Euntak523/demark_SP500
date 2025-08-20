import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# -----------------------------
# 데이터/헬퍼 함수
# -----------------------------
@st.cache_data(ttl=86400)
def get_sp500_symbols():
    table = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    df = table[0]
    return df[['Symbol', 'GICS Sector']]

def _download_retry(symbol, period="6mo", tries=3):
    last_err = None
    for _ in range(tries):
        try:
            df = yf.download(symbol, period=period, auto_adjust=False, progress=False, threads=False)
            if df is not None and not df.empty:
                return df
        except Exception as e:
            last_err = e
    return None

def current_demark_setup(symbol):
    df = _download_retry(symbol, period="6mo", tries=3)
    if df is None or df.empty or len(df) < 30:
        return "데이터 부족", None, None

    df = df.copy()
    df['Close-4'] = df['Close'].shift(4)
    df['Setup'] = None

    setup_count = 0
    setup_index = 0
    setup_direction = "하락"  # 현재 로직은 하락 Setup 기준

    for i in range(4, len(df)):
        try:
            close = float(df.iloc[i]['Close'])
            close_4 = float(df.iloc[i]['Close-4'])
        except Exception:
            continue

        if close < close_4:
            setup_count += 1
            if setup_count == 9:
                setup_index += 1
                df.loc[df.index[i], 'Setup'] = f"Setup {setup_index}번째 완료"
                setup_count = 0
        else:
            setup_count = 0

    if df['Setup'].isnull().all():
        return "최근 90일 기준 Setup 미완료", df, None

    return f"총 {setup_index}개 Setup 완료", df, setup_direction

def draw_chart_block(symbol):
    """선택/자동심볼에 대해 차트 그리는 공통 블록"""
    status, df, direction = current_demark_setup(symbol)
    st.write("DEBUG-status:", status, "| shape:", None if df is None else df.shape)
    if df is not None and not df.empty:
        df = df.copy()
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA120'] = df['Close'].rolling(window=120).mean()

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(df.index, df['Close'], label='Close', linewidth=1.2)
        ax.plot(df.index, df['MA20'], label='MA20', linestyle='--')
        ax.plot(df.index, df['MA60'], label='MA60', linestyle=':')
        ax.plot(df.index, df['MA120'], label='MA120', linestyle='-.', alpha=0.8)

        setup_df = df[df['Setup'].notnull()]
        if not setup_df.empty:
            ax.scatter(setup_df.index, setup_df['Close'], label="Setup 9 완료", marker='o')

        ax.legend()
        ax.set_title(f"{symbol} DeMark Setup 분석 + 이동평균선")
        st.pyplot(fig)
        plt.close(fig)
    else:
        st.warning("해당 종목의 데이터가 부족합니다.")

# -----------------------------
# 앱 시작
# -----------------------------
st.set_page_config(layout="wide")
st.title("📊 S&P 500 DeMark Setup 자동 분석기")

# 세션 초기화
if "setup_results" not in st.session_state:
    st.session_state.setup_results = []
if "df_result" not in st.session_state:
    st.session_state.df_result = pd.DataFrame()
if "last_selection" not in st.session_state:
    st.session_state.last_selection = []

# -----------------------------
# 전체 분석 버튼
# -----------------------------
if st.button("전체 S&P 500 분석 시작"):
    sp500_df = get_sp500_symbols()
    setup_results = []

    with st.spinner("분석 중입니다..."):
        for _, row in sp500_df.iterrows():
            symbol = row['Symbol']
            sector = row['GICS Sector']
            try:
                status, df, direction = current_demark_setup(symbol)
                if "Setup 미완료" not in status and status != "데이터 부족":
                    # 시총(선택)
                    try:
                        info = yf.Ticker(symbol).info
                        cap = info.get("marketCap")
                        cap_str = f"{cap / 1_000_000_000:.2f}B" if cap else None
                    except Exception:
                        cap, cap_str = None, None

                    setup_results.append({
                        "Symbol": symbol,
                        "Status": status,
                        "Direction": direction,
                        "Sector": sector,
                        "MarketCap": cap_str,
                        "MarketCap_RAW": cap
                    })
            except Exception:
                continue

    if setup_results:
        df_result = pd.DataFrame(setup_results).sort_values(by="MarketCap_RAW", ascending=False, na_position="last")
        st.session_state.setup_results = setup_results
        st.session_state.df_result = df_result
        st.success(f"총 {len(df_result)}개 종목이 Setup 완료 상태입니다.")

# -----------------------------
# 결과 표 & 차트
# -----------------------------
if len(st.session_state.setup_results) > 0:
    df_result = st.session_state.df_result.copy()

    # 업종 필터
    sectors = df_result["Sector"].dropna().unique().tolist()
    selected_sector = st.selectbox("업종 필터링:", ["전체"] + sorted(sectors))
    if selected_sector != "전체":
        df_result = df_result[df_result["Sector"] == selected_sector]

    # 빈 DF 방어
    if df_result.empty:
        st.warning("표시할 결과가 없습니다.")
        st.stop()

    # 그리드 (모바일/터치 안정: 체크박스 선택)
    display_df = df_result.drop(columns=["MarketCap_RAW"])
    gb = GridOptionsBuilder.from_dataframe(display_df)
    gb.configure_selection(selection_mode="single", use_checkbox=True)  # 체크박스 사용
    gb.configure_grid_options(suppressRowClickSelection=False, rowSelection="single")
    grid_options = gb.build()

    grid_response = AgGrid(
        display_df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        height=500,
        fit_columns_on_grid_load=True,
        key="main_grid"
    )

    # ================== 🔎 진단 패널 (표 바로 아래) ==================
    with st.expander("🔎 진단 패널", expanded=True):
        try:
            _rows_dbg = grid_response["selected_rows"] or []
        except Exception:
            _rows_dbg = []
        st.write("DEBUG-selected_rows:", _rows_dbg)

        if _rows_dbg:
            _sr_dbg = pd.DataFrame(_rows_dbg).iloc[0]
            _sym_dbg = (_sr_dbg.get("Symbol") or _sr_dbg.get("종목") or _sr_dbg.get("symbol") or _sr_dbg.get("티커"))
        else:
            _sym_dbg = None
        st.write("DEBUG-selected_symbol:", _sym_dbg)

        test_symbol = st.text_input("테스트 심볼(AAPL, MSFT 등)", "AAPL")
        if st.button("강제 차트 테스트"):
            draw_chart_block(test_symbol)

        st.write("DEBUG-env: pandas", pd.__version__)
    # ============================================================

    # ✅ 선택행 안전 처리 + 마지막 선택 복구
    try:
        rows = grid_response["selected_rows"] or []
    except Exception:
        rows = []

    if rows:
        st.session_state.last_selection = rows
    else:
        rows = st.session_state.last_selection or []

    # 차트 표시
    if rows:
        try:
            selected_row_df = pd.DataFrame(rows)
            selected_row = selected_row_df.iloc[0]
            selected_symbol = (
                selected_row.get("Symbol")
                or selected_row.get("종목")
                or selected_row.get("symbol")
                or selected_row.get("티커")
            )

            if not selected_symbol:
                st.error("❌ 선택한 행에서 Symbol 값을 찾을 수 없습니다.")
            else:
                st.markdown(f"### {selected_symbol} 차트")
                draw_chart_block(selected_symbol)
        except Exception as e:
            st.error(f"선택 종목 처리 중 오류 발생: {e}")
    else:
        # 선택이 감지되지 않을 때 첫 행 자동 표시 (무반응 방지용)
        auto_symbol = display_df.iloc[0]["Symbol"]
        st.info(f"선택이 감지되지 않아 첫 종목({auto_symbol}) 차트를 자동 표시합니다.")
        st.markdown(f"### {auto_symbol} 차트 (자동)")
        draw_chart_block(auto_symbol)
else:
    st.warning("Setup 완료된 종목이 없습니다.")
